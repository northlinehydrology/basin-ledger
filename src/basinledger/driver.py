"""The driver: steps every model of an example one day at a time, moves water between them, and keeps the ledger.

This is the first, one-way version. Each day:

1. each water user is stepped through the day (hourly) and its volumes integrated;
2. SWAT+ runs the day;
3. MODFLOW 6 prepares the day, takes SWAT+'s recharge and the users' well pumping, and solves;
4. the ledger enters both sides of every transfer and checks they agree.

Still to come (docs/design.md): two-way stream-aquifer exchange, surface withdrawals and returns through SWAT+, the
utility chain (chain.py), feedback rules (rules.py), shared forcing, and scenarios from a shared warm-up.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import shutil
from pathlib import Path

import numpy as np
from swatplus_bmi import SwatPlusBmi

from . import config as C
from .coupling.modflow6 import Modflow6
from .coupling.recharge import RechargeLink
from .ledger import Ledger
from .mapping import AreaMap
from .users import WaterUser, load_component


def _builder(cfg: C.ExampleConfig):
    mod, _, fn = cfg.mf6_builder.partition(":")
    spec = importlib.util.spec_from_file_location(f"basinledger_example_{cfg.name}_{mod}", cfg.folder / f"{mod}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return getattr(m, fn or "build")


class Basin:
    def __init__(self, cfg: C.ExampleConfig, run: str = "base", users: bool = True, days: int | None = None):
        self.cfg = cfg
        self.folder = cfg.run_folder / run
        if self.folder.exists():
            shutil.rmtree(self.folder)
        self.folder.mkdir(parents=True)

        # SWAT+, run from a copy of the project
        (self.folder / "swatplus.toml").write_text(f'project = "{cfg.swat_project}"\nrun_dir = "swatplus"\n')
        self.swat = SwatPlusBmi()
        self.swat.initialize(str(self.folder / "swatplus.toml"))
        units = self.swat.get_time_units()  # days since YYYY-MM-DD hh:mm:ss
        self.start = dt.date.fromisoformat(units.split(" since ")[1].split()[0])
        self.days = days or cfg.days or int(self.swat.get_end_time() - self.swat.get_start_time())

        # MODFLOW 6, built for this run or copied in
        ws = self.folder / "mf6"
        if cfg.mf6_builder:
            _builder(cfg)(ws, self.days, self.start)
        else:
            shutil.copytree(cfg.mf6_workspace, ws)
        self.mf6 = Modflow6(ws, cfg.mf6_model)
        if self.mf6.end < self.days - 1e-9:
            raise ValueError(f"MODFLOW 6 simulation is {self.mf6.end} days; the run needs {self.days}")

        # SWAT+ aquifers -> MODFLOW 6 cells
        g = self.swat.get_var_grid("soil_water_table__recharge_rate")
        aquifers = list(self.swat.get_grid_object_names(g))
        self.map = self._area_map(cfg.recharge_map, aquifers)
        self.map.check(self.mf6.cell_area)
        self.recharge = RechargeLink(self.swat, self.mf6, self.map, cfg.recharge_package)

        # list packages are filled when MODFLOW 6 reads a period, so entries are found after prepare_day
        self.wells = {w.name: (w.package, self.mf6.node(*w.cell)) for w in cfg.wells}
        self.users = []
        if users:
            for u in cfg.users:
                comp = load_component(u.component)
                self.users.append((u, WaterUser(u.name, comp, str(u.config) if u.config else None,
                                                variables=u.variables or None, constituents=u.constituents)))
                for route in (u.withdrawal, u.returns):
                    kind, _, name = route.partition(":")
                    if kind == "well" and name not in self.wells:
                        raise KeyError(f"user {u.name}: no well named {name!r}")
                    if kind not in ("well", "outfall"):
                        raise NotImplementedError(f"user {u.name}: route {route!r} needs the utility chain (planned)")

        self.ledger = Ledger()
        self.ledger.pair("recharge:sent", "recharge:received")
        for name in self.wells:
            self.ledger.pair(f"well:{name}:requested", f"well:{name}:pumped")
        self.day = 0

    def _area_map(self, spec: str, aquifers: list[str]) -> AreaMap:
        if spec.startswith("all:"):
            nodes = self.mf6.package_nodes(self.cfg.recharge_package)
            return AreaMap.all_cells(aquifers, spec[4:], nodes, self.mf6.cell_area)
        return AreaMap.from_csv(self.cfg.folder / spec, aquifers, self.mf6.node)

    def step(self):
        d = self.day
        L = self.ledger
        well_q = {name: 0.0 for name in self.wells}
        for u, wu in self.users:
            use = wu.advance_day(d)
            L.enter(f"user:{u.name}:withdrawal", use.withdrawal)
            L.enter(f"user:{u.name}:gain", use.gain)
            L.enter(f"user:{u.name}:consumption", use.consumption)
            L.enter(f"user:{u.name}:return", use.returned)
            for c, kg in use.constituents.items():
                L.enter(f"user:{u.name}:{c}:kg", kg)
            if use.energy is not None:
                L.enter(f"user:{u.name}:MWh", use.energy)
            kind, _, name = u.withdrawal.partition(":")
            if kind == "well":
                well_q[name] += use.withdrawal
            kind, _, name = u.returns.partition(":")
            if kind == "outfall":
                L.enter(f"outfall:{name}", use.returned)

        self.swat.update()

        self.mf6.prepare_day()
        L.enter("recharge:sent", self.recharge.transfer())
        entries = {name: (pkg, self.mf6.entry(pkg, node)) for name, (pkg, node) in self.wells.items()}
        for name, (pkg, i) in entries.items():
            self.mf6.set_well(pkg, i, -well_q[name])
            L.enter(f"well:{name}:requested", well_q[name])
        self.mf6.solve_day()
        L.enter("recharge:received", self.recharge.received())
        for name, (pkg, i) in entries.items():
            L.enter(f"well:{name}:pumped", -self.mf6.simvals(pkg)[i])
        L.close_day()
        self.day += 1

    def run(self, days: int | None = None):
        n = self.days - self.day if days is None else days
        for _ in range(n):
            self.step()
        return self

    def finalize(self):
        for _, wu in self.users:
            wu.finalize()
        self.mf6.finalize()
        self.swat.finalize()

    @classmethod
    def from_config(cls, path, run: str = "base", users: bool = True, days: int | None = None) -> "Basin":
        """``users=False`` runs the example without its water users (the baseline); ``days`` shortens the run."""
        return cls(C.load(path), run, users, days)
