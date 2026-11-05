"""Routes: where a day's water goes in the models, and what each model actually took or gave.

A route is a string naming a source or sink:

    well:<name>                   a MODFLOW 6 well (withdrawal)
    swat:place_of_use:<name>      a SWAT+ water allocation place of use, taking from its channel (withdrawal)
    swat:point_source:<name>      a SWAT+ daily point source into its channel (discharge)
    outfall:<name>                recorded in the ledger only (discharge)

(``utility:<name>`` routes go to the utility chain, which then requests these.)

Each day the driver adds requests (m3), applies them to the models (SWAT+ before its day, MODFLOW 6 after preparing
its day), and reads back what each model did. For every route the ledger gets ``route:<r>:requested`` and
``route:<r>:delivered``; withdrawals from SWAT+ also get ``route:<r>:shortfall`` (what the channel couldn't supply).
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from .coupling import swatplus as S
from .ledger import FLOAT32
from .units import DAY

KINDS = ("well", "swat:place_of_use", "swat:point_source", "outfall")


def kind(route: str) -> tuple[str, str]:
    for k in KINDS:
        if route.startswith(k + ":"):
            return k, route[len(k) + 1:]
    if route.startswith("utility:"):
        return "utility", route[len("utility:"):]
    raise ValueError(f"unknown route {route!r} (known: {', '.join(KINDS)}, utility)")


class Router:
    def __init__(self, swat: S.Swat, mf6, wells: dict[str, tuple[str, int]], ledger):
        self.swat, self.mf6, self.wells, self.ledger = swat, mf6, wells, ledger
        self.places = swat.names(S.DEMAND) if swat.has(S.DEMAND) else []
        self.points = swat.names(S.POINT) if swat.has(S.POINT) else []
        self.req: dict[str, float] = defaultdict(float)
        self.used: set[str] = set()

    def check(self, route: str):
        k, name = kind(route)
        known = {"well": self.wells, "swat:place_of_use": self.places, "swat:point_source": self.points}.get(k)
        if known is not None and name not in known:
            raise KeyError(f"route {route!r}: no {k} named {name!r}")
        if k in KINDS and route not in self.used:
            self.used.add(route)
            r = f"route:{route}:"
            if k == "swat:place_of_use":
                self.ledger.pair(r + "requested", [r + "delivered", r + "shortfall"], rtol=FLOAT32)
                self.ledger.zero(r + "overdraw")
            elif k == "swat:point_source":
                self.ledger.pair(r + "requested", r + "delivered", rtol=FLOAT32)
            else:
                self.ledger.pair(r + "requested", r + "delivered")

    def request(self, route: str, m3: float):
        self.check(route)
        self.req[route] += m3

    def apply_swat(self):
        if self.places:
            d = np.zeros(len(self.places))
            for i, n in enumerate(self.places):
                d[i] = self.req.get(f"swat:place_of_use:{n}", 0.0) / DAY
            self.swat.set(S.DEMAND, d)
        if self.points:
            p = np.zeros(len(self.points))
            for i, n in enumerate(self.points):
                p[i] = self.req.get(f"swat:point_source:{n}", 0.0) / DAY
            self.swat.set(S.POINT, p)

    def read_swat(self):
        L = self.ledger
        if self.places:
            got = self.swat.get(S.WITHDRAWN) * DAY
            for i, n in enumerate(self.places):
                r = f"swat:place_of_use:{n}"
                if r in self.used:
                    want = self.req.get(r, 0.0)
                    L.enter(f"route:{r}:requested", want)
                    L.enter(f"route:{r}:delivered", got[i])
                    L.enter(f"route:{r}:shortfall", max(want - got[i], 0.0))
                    L.enter(f"route:{r}:overdraw", max(got[i] - want * (1 + FLOAT32) - 1e-6, 0.0))
        if self.points:
            got = self.swat.get(S.POINT) * DAY
            for i, n in enumerate(self.points):
                r = f"swat:point_source:{n}"
                if r in self.used:
                    L.enter(f"route:{r}:requested", self.req.get(r, 0.0))
                    L.enter(f"route:{r}:delivered", got[i])

    def apply_wells(self):
        self._entries = {name: (pkg, self.mf6.entry(pkg, node)) for name, (pkg, node) in self.wells.items()}
        for name, (pkg, i) in self._entries.items():
            self.mf6.set_well(pkg, i, -self.req.get(f"well:{name}", 0.0))

    def read_wells(self):
        for name, (pkg, i) in self._entries.items():
            r = f"well:{name}"
            if r in self.used:
                self.ledger.enter(f"route:{r}:requested", self.req.get(r, 0.0))
                self.ledger.enter(f"route:{r}:delivered", -self.mf6.simvals(pkg)[i])

    def close_day(self):
        for r in self.used:
            if r.startswith("outfall:"):
                self.ledger.enter(f"route:{r}:requested", self.req.get(r, 0.0))
                self.ledger.enter(f"route:{r}:delivered", self.req.get(r, 0.0))
        self.req = defaultdict(float)
