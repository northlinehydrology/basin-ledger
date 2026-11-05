"""The utility chain: source -> distribution -> customers -> sewer -> wastewater plant -> outfall.

The chain is accounting, not a model. Each day it takes the volumes of the users on the system, adds the system's
existing customers, and places the water in the hydrologic models through routes:

    produced    = delivered / (1 - losses)          withdrawn from the sources, by share
    delivered   = existing demand + users' withdrawals
    losses      = produced - delivered              distribution losses (non-revenue water)
    sewer       = existing demand x sewered + users' returns + inflow and infiltration
    outfall     = sewer                             the plant's discharge, to its route

Config (one ``[[utilities]]`` table per system):

    name = "city"
    sources = [{route = "well:pw2", share = 0.6}, {route = "swat:place_of_use:intake", share = 0.4}]
    losses = 0.10              # fraction of production
    demand = 0.003             # m3 s-1, existing customers (a constant for now; later a daily series)
    sewered = 0.8              # share of existing demand that reaches the sewer
    infiltration = 0.0002      # m3 s-1 of inflow and infiltration into the sewer
    outfall = "swat:point_source:wwtp"

Ledger accounts, all in m3 per day, under ``utility:<name>:``. They pair as: produced = delivered + losses;
produced = the sum of the source shares; sewer = outfall. Each route then carries its own pair of requested and
delivered.

Not yet: losses returned to the aquifer as recharge, inflow and infiltration taken from the aquifer, a daily demand
series, and the plant's own consumption and loads.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .units import DAY


@dataclass
class Source:
    route: str
    share: float


@dataclass
class UtilityChain:
    name: str
    sources: list[Source]
    outfall: str
    losses: float = 0.0
    demand: float = 0.0
    sewered: float = 1.0
    infiltration: float = 0.0
    _withdrawals: float = field(default=0.0, repr=False)
    _returns: float = field(default=0.0, repr=False)

    def __post_init__(self):
        total = sum(s.share for s in self.sources)
        if not self.sources or abs(total - 1.0) > 1e-9:
            raise ValueError(f"utility {self.name}: source shares sum to {total}, not 1")
        if not 0 <= self.losses < 1 or not 0 <= self.sewered <= 1:
            raise ValueError(f"utility {self.name}: losses must be in [0, 1) and sewered in [0, 1]")
        for s in self.sources:
            if s.route.startswith("utility:"):
                raise ValueError(f"utility {self.name}: a source can't be another utility (not yet)")

    @classmethod
    def from_config(cls, c: dict) -> "UtilityChain":
        return cls(name=c["name"], sources=[Source(s["route"], float(s["share"])) for s in c["sources"]],
                   outfall=c["outfall"], losses=float(c.get("losses", 0.0)), demand=float(c.get("demand", 0.0)),
                   sewered=float(c.get("sewered", 1.0)), infiltration=float(c.get("infiltration", 0.0)))

    def add_user(self, withdrawal: float, returned: float):
        """A user's day on this system: m3 withdrawn from the tap, m3 returned to the sewer."""
        self._withdrawals += withdrawal
        self._returns += returned

    def close_day(self, ledger) -> dict[str, float]:
        """The day's requests on each route (m3): sources positive withdrawals, the outfall a discharge."""
        existing = self.demand * DAY
        delivered = existing + self._withdrawals
        produced = delivered / (1.0 - self.losses)
        sewer = existing * self.sewered + self._returns + self.infiltration * DAY
        k = f"utility:{self.name}:"
        ledger.enter(k + "produced", produced)
        ledger.enter(k + "delivered", delivered)
        ledger.enter(k + "losses", produced - delivered)
        ledger.enter(k + "existing_demand", existing)
        ledger.enter(k + "users_withdrawal", self._withdrawals)
        ledger.enter(k + "users_return", self._returns)
        ledger.enter(k + "infiltration", self.infiltration * DAY)
        ledger.enter(k + "consumed_by_existing", existing * (1 - self.sewered))
        ledger.enter(k + "sewer", sewer)
        requests = {}
        for s in self.sources:
            requests[s.route] = requests.get(s.route, 0.0) + produced * s.share
            ledger.enter(k + f"source:{s.route}", produced * s.share)
        requests[self.outfall] = requests.get(self.outfall, 0.0) + sewer
        ledger.enter(k + "outfall", sewer)
        self._withdrawals = self._returns = 0.0
        return requests

    def declare(self, ledger):
        k = f"utility:{self.name}:"
        ledger.pair(k + "produced", [k + "delivered", k + "losses"])
        ledger.pair(k + "produced", [k + f"source:{s.route}" for s in self.sources])
        ledger.pair(k + "delivered", [k + "existing_demand", k + "users_withdrawal"])
        ledger.pair(k + "sewer", k + "outfall")
