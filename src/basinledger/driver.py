"""The driver: steps every model of an example one day at a time, moves water between them, and keeps the ledger.

Day d, in order:

1. **Rules** read yesterday's state (SWAT+ channel flow, MODFLOW 6 heads) and set controls on users for today.
2. **Users** are stepped through the day (hourly) and their volumes integrated.
3. **Routing.** Each user's withdrawal and return go to their routes, directly or through a utility chain. Yesterday's
   stream-aquifer exchange is routed to SWAT+ too.
4. **SWAT+** takes today's demands and point sources and runs the day. Then what it actually withdrew and received is
   read back.
5. **MODFLOW 6** prepares the day, takes SWAT+'s recharge and today's well pumping, and solves. Then the wells and the
   river exchange are read back.
6. **The ledger** enters both sides of every transfer and checks them. The day's flows and heads go to the outputs.

``save(folder)`` writes the state at the pause after a day: SWAT+'s saved state (swatplus-bmi), MODFLOW 6's heads, the
ledger, and the exchange due. ``Basin(..., restart=folder)`` carries on from there. SWAT+ and MODFLOW 6 continue
exactly, and the users are stepped forward to the restart day.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import math
import shutil
from pathlib import Path

import numpy as np
from swatplus_bmi import SwatPlusBmi

from . import config as C
from . import rules as R
from .chain import UtilityChain
from .coupling import swatplus as S
from .coupling.exchange import ChannelMap, StreamExchange, requests as exchange_requests
from .coupling.modflow6 import Modflow6, remaining_simulation
from .coupling.recharge import RechargeLink
from .ledger import FLOAT32, Ledger
from .mapping import AreaMap
from .routes import Router, kind
from .units import DAY
from .users import WaterUser, load_component


def _example_function(cfg: C.ExampleConfig, spec: str, default: str):
    mod, _, fn = spec.partition(":")
    spec_ = importlib.util.spec_from_file_location(f"basinledger_example_{cfg.name}_{mod}", cfg.folder / f"{mod}.py")
    m = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(m)
    return getattr(m, fn or default)


class Basin:
    def __init__(self, cfg: C.ExampleConfig, run: str = "base", users: bool = True, days: int | None = None,
                 restart: str | Path | None = None, prepare=None):
        """``prepare(model, folder)``, if given, is called on the run's copy of each model's files ("swatplus",
        "modflow6") before that model starts: where a calibration writes a parameter set."""
        self.cfg = cfg
        self.status = cfg.calibration_status  # 'screening' unless the example's record says 'calibrated'
        self.folder = cfg.run_folder / run
        if self.folder.exists():
            shutil.rmtree(self.folder)
        self.folder.mkdir(parents=True)
        saved = json.loads((Path(restart) / "basin.json").read_text()) if restart else None

        # SWAT+, from a copy of the project with the objects the run needs
        ex = cfg.exchange
        swat_dir = self.folder / "swatplus"
        shutil.copytree(cfg.swat_project, swat_dir)
        channels = S._channels(swat_dir)
        ex_channels = self._exchange_channels(ex) if ex else []
        places = list(cfg.places_of_use) + [(f"seep_{c}", c) for c in ex_channels]
        points = list(cfg.point_sources) + [(f"gw_{c}", c) for c in ex_channels]
        if places:
            S.add_places_of_use(swat_dir, places)
        if points:
            S.add_point_sources(swat_dir, points)
        if ex:
            S.aquifer_pass_through(swat_dir)
        if prepare:
            prepare("swatplus", swat_dir)
        self.swat = SwatPlusBmi()
        self.swat.initialize(str(swat_dir))
        self.sw = S.Swat(self.swat)
        units = self.swat.get_time_units()  # days since YYYY-MM-DD hh:mm:ss
        self.start = dt.date.fromisoformat(units.split(" since ")[1].split()[0])
        self.days = days or cfg.days or int(self.swat.get_end_time() - self.swat.get_start_time())
        self.day = 0
        if saved:
            self.swat.load_state(str(Path(restart) / "swatplus"))
            self.day = saved["day"]

        # MODFLOW 6: built (or copied) for the run, or for the days left after a restart
        ws = self.folder / "mf6"
        if cfg.mf6_builder:
            _example_function(cfg, cfg.mf6_builder, "build")(ws, self.days - self.day,
                                                             self.start + dt.timedelta(days=self.day))
        elif saved:
            remaining_simulation(cfg.mf6_workspace, ws, self.day)
        else:
            shutil.copytree(cfg.mf6_workspace, ws)
        if prepare:
            prepare("modflow6", ws)
        self.mf6 = Modflow6(ws, cfg.mf6_model)
        if saved:
            self.mf6.set_heads(np.load(Path(restart) / "heads.npy"))
        if self.mf6.end < self.days - self.day - 1e-9:
            raise ValueError(f"MODFLOW 6 simulation is {self.mf6.end} days; the run needs {self.days - self.day}")

        # recharge: SWAT+ aquifers -> MODFLOW 6 cells
        aquifers = self.sw.names("soil_water_table__recharge_rate")
        self.map = self._area_map(cfg.recharge_map, aquifers)
        areas = S.aquifer_areas(swat_dir)
        self.map.check(self.mf6.cell_area, np.array([areas[a] for a in aquifers]), cfg.area_rtol)
        self.recharge = RechargeLink(self.swat, self.mf6, self.map, cfg.recharge_package)

        self.ledger = Ledger()
        L = self.ledger
        L.pair("recharge:sent", "recharge:received")
        wells = {w.name: (w.package, self.mf6.node(*w.cell)) for w in cfg.wells}
        self.router = Router(self.sw, self.mf6, wells, L)

        # stream-aquifer exchange (built on the first day, once MODFLOW 6's river package has its entries)
        self.exchange = None
        self.due = {c: 0.0 for c in ex_channels}  # yesterday's exchange, m3 per channel, applied in SWAT+ today
        if saved and saved.get("exchange_due"):
            self.due = dict(saved["exchange_due"])
        if ex:
            for c in ex_channels:
                self.router.check(f"swat:point_source:gw_{c}")
                self.router.check(f"swat:place_of_use:seep_{c}")
                k = f"exchange:{c}:"
                L.pair(k + "due", [k + "applied", k + "shortfall"], rtol=FLOAT32)
            L.zero("swatplus:aquifer_outflow", atol=1e-9)

        # utilities, users, rules
        self.utilities = {u["name"]: UtilityChain.from_config(u) for u in cfg.utilities}
        for u in self.utilities.values():
            u.declare(L)
            for s in u.sources:
                self.router.check(s.route)
            self.router.check(u.outfall)
        self.users = []
        if users:
            for u in cfg.users:
                comp = load_component(u.component)
                wu = WaterUser(u.name, comp, str(u.config) if u.config else None,
                               variables=u.variables or None, constituents=u.constituents)
                self.users.append((u, wu))
                for route in (u.withdrawal, u.returns):
                    k, name = kind(route)
                    if k == "utility":
                        if name not in self.utilities:
                            raise KeyError(f"user {u.name}: no utility named {name!r}")
                    else:
                        self.router.check(route)
                k = f"user:{u.name}:"
                L.pair(k + "withdrawal", [k + "consumption", k + "return", k + "storage_less_gain"])
        users_by_name = {u.name: wu for u, wu in self.users}
        self.rules = []
        for r in cfg.rules:
            settings = {k: v for k, v in r.items() if k not in ("name", "kind")}
            fn = R.BUILT_IN.get(r["kind"]) or _example_function(cfg, r["kind"], "rule")
            if users and settings.get("user") not in users_by_name:
                raise KeyError(f"rule {r.get('name', r['kind'])}: no user {settings.get('user')!r}")
            need = {"curtailment": "limit", "drawdown_limit": "limit", "dry_mode": "dry_mode"}.get(r["kind"])
            if users and need and need not in users_by_name[settings["user"]].control_vars:
                raise KeyError(f"rule {r.get('name')}: user {settings['user']!r} takes no {need!r} input")
            self.rules.append(R.Rule(r.get("name", r["kind"]), fn, settings))
        self.rule_memory = {}

        # outputs
        out = cfg.outputs
        self.out_channels = out.get("channels", channels)
        self._ch_index = {c: channels.index(c) for c in self.out_channels}
        self.out_heads = [(h["name"], self.mf6.node(*h["cell"])) for h in out.get("heads", [])]
        self.series: dict[str, list[float]] = {f"flow:{c}": [] for c in self.out_channels}
        self.series.update({f"head:{n}": [] for n, _ in self.out_heads})

        if saved:
            L.load(saved["ledger"])
            self.series = saved["series"]
            self.rule_memory = saved["rule_memory"]
            for _, wu in self.users:
                wu.fast_forward(self.day)

    @staticmethod
    def _exchange_channels(ex) -> list[str]:
        spec = ex.get("map", "")
        if spec.startswith("all:"):
            return [spec[4:]]
        raise NotImplementedError("exchange maps from CSV need their channels listed before SWAT+ starts (not yet)")

    def _area_map(self, spec: str, aquifers: list[str]) -> AreaMap:
        if spec.startswith("all:"):
            nodes = self.mf6.package_nodes(self.cfg.recharge_package)
            return AreaMap.all_cells(aquifers, spec[4:], nodes, self.mf6.cell_area)
        return AreaMap.from_csv(self.cfg.folder / spec, aquifers, self.mf6.node)

    # ---------- one day ----------
    def _state(self) -> R.State:
        q = self.sw.get(S.QOUT)
        heads = self.mf6.head()
        return R.State(day=self.day, flows=dict(zip(self.sw.names(S.QOUT), q)),
                       head_at=lambda c: float(heads[self.mf6.node(*c)]), memory=self.rule_memory)

    def step(self):
        d = self.day
        L = self.ledger
        rt = self.router

        # 1. rules
        if self.rules:
            state = self._state()
            decisions = []
            for rule in self.rules:
                dec = rule(state)
                L.enter(f"rule:{rule.name}:active", 1.0 if dec else 0.0)
                decisions.append(dec)
            controls = R.combine(decisions)
            for u, wu in self.users:
                wu.set_controls(**controls.get(u.name, {}))

        # 2-3. users and routing
        for u, wu in self.users:
            use = wu.advance_day(d)
            k = f"user:{u.name}:"
            L.enter(k + "withdrawal", use.withdrawal)
            L.enter(k + "gain", use.gain)
            L.enter(k + "storage_less_gain", use.storage_change - use.gain)
            L.enter(k + "consumption", use.consumption)
            L.enter(k + "return", use.returned)
            for c, kg in use.constituents.items():
                L.enter(k + f"{c}:kg", kg)
            if use.energy is not None:
                L.enter(k + "MWh", use.energy)
            for route, vol, is_return in ((u.withdrawal, use.withdrawal, False), (u.returns, use.returned, True)):
                kd, name = kind(route)
                if kd == "utility":
                    self.utilities[name].add_user(0.0 if is_return else vol, vol if is_return else 0.0)
                else:
                    rt.request(route, vol)
        for chain in self.utilities.values():
            for route, vol in chain.close_day(L).items():
                rt.request(route, vol)
        for route, vol in exchange_requests(self.due).items():
            rt.request(route, vol)

        # 4. SWAT+
        rt.apply_swat()
        self.swat.update()
        rt.read_swat()

        # 5. MODFLOW 6
        self.mf6.prepare_day()
        if self.cfg.exchange and self.exchange is None:
            ex = self.cfg.exchange
            cmap = ChannelMap.from_spec(ex.get("map", ""), self.cfg.folder, self.mf6, ex.get("package", "riv"),
                                        self.sw.names(S.QOUT))
            if cmap.channels != list(self.due):
                raise ValueError(f"exchange map channels {cmap.channels} differ from {list(self.due)}")
            self.exchange = StreamExchange(self.mf6, ex.get("package", "riv"), cmap)
        L.enter("recharge:sent", self.recharge.transfer())
        rt.apply_wells()
        self.mf6.solve_day()
        L.enter("recharge:received", self.recharge.received())
        rt.read_wells()
        if self.cfg.exchange:
            self._enter_exchange(L)
            L.enter("swatplus:aquifer_outflow", float(self.sw.get(S.AQU_OUT).sum()) * DAY)
        rt.close_day()

        # 6. outputs and checks
        q = self.sw.get(S.QOUT)
        for c, i in self._ch_index.items():
            self.series[f"flow:{c}"].append(float(q[i]))
        if self.out_heads:
            h = self.mf6.head()
            for n, node in self.out_heads:
                self.series[f"head:{n}"].append(float(h[node]))
        L.close_day()
        self.day += 1

    def _enter_exchange(self, L):
        """Today's SWAT+ side of yesterday's exchange, then today's MODFLOW 6 exchange as tomorrow's due."""
        for c in self.due:
            k = f"exchange:{c}:"
            pt = L.today(f"route:swat:point_source:gw_{c}:delivered")
            taken = L.today(f"route:swat:place_of_use:seep_{c}:delivered")
            short = L.today(f"route:swat:place_of_use:seep_{c}:shortfall")
            L.enter(k + "due", self.due[c])
            L.enter(k + "applied", pt - taken)
            L.enter(k + "shortfall", -short)
        self.due = self.exchange.after_solve()
        for c, net in self.due.items():
            L.enter(f"exchange:{c}:to_stream", net)

    def run(self, days: int | None = None):
        n = self.days - self.day if days is None else days
        for _ in range(n):
            self.step()
        return self

    # ---------- restarts ----------
    def save(self, folder: str | Path):
        """The state at the pause after the last day run, for ``Basin(..., restart=folder)``."""
        folder = Path(folder)
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        self.swat.save_state(str(folder / "swatplus"))
        np.save(folder / "heads.npy", self.mf6.head())
        (folder / "basin.json").write_text(json.dumps({
            "day": self.day, "ledger": self.ledger.state(), "series": self.series,
            "rule_memory": self.rule_memory,
            "exchange_due": self.due,
        }))

    # ---------- outputs ----------
    def dates(self) -> list[str]:
        return [(self.start + dt.timedelta(days=i)).isoformat() for i in range(self.ledger.days)]

    def write_outputs(self, folder: str | Path | None = None) -> Path:
        """ledger.csv (every account, m3 per day unless named otherwise), series.csv (flows m3 s-1, heads m) and
        summary.json (status, totals, what's in transit)."""
        out = Path(folder) if folder else self.folder / "outputs"
        out.mkdir(parents=True, exist_ok=True)
        dates = self.dates()
        self.ledger.write_csv(out / "ledger.csv", dates)
        with open(out / "series.csv", "w") as f:
            cols = sorted(self.series)
            f.write(",".join(["day", "date", *cols]) + "\n")
            for i in range(len(dates)):
                f.write(",".join([str(i), dates[i], *(repr(self.series[c][i]) for c in cols)]) + "\n")
        summary = {
            "example": self.cfg.name, "status": self.status,
            "status_note": None if self.status == "calibrated" else
            "screening run: the models are not calibrated; results show how the engine and scenarios work, "
            "not what would happen in this basin",
            "start": self.start.isoformat(), "days": self.ledger.days,
            "totals": {k: v for k, v in self.ledger.totals().items() if not math.isnan(v)},
            "in_transit": self.due,
        }
        (out / "summary.json").write_text(json.dumps(summary, indent=2))
        return out

    def finalize(self):
        for _, wu in self.users:
            wu.finalize()
        self.mf6.finalize()
        self.swat.finalize()

    @classmethod
    def from_config(cls, path, run: str = "base", users: bool = True, days: int | None = None,
                    restart: str | Path | None = None, prepare=None) -> "Basin":
        """``users=False`` runs the example without its water users (the baseline); ``days`` shortens the run;
        ``restart`` carries on from a folder written by ``save``."""
        return cls(C.load(path), run, users, days, restart, prepare)
