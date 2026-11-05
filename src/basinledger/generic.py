"""A generic water user defined only by what's known: a reported or declared daily series.

``ReportedUser`` is a BMI component with the common water-user roles. Its config is a CSV with one row per day:

    date, withdrawal_m3, consumption_m3, return_m3

and optionally ``source`` (declared, permit, reported or range) on each row, carried as provenance. It models no
process: each day it reports that day's volumes as steady rates. Days before or after the series are zero. Return is
taken as given, and the balance (withdrawal = consumption + return) must hold on every row, or the file is refused.

This is evidence level 1 of docs/ideas.md (a generic user): existing users from reported data, a proposal with almost
no detail, or the pumping of a modeled user replayed without its model.

Config (TOML):
    series = "path/to/series.csv"     # relative to the config file
    start = "2018-10-01"              # the run's first day, so that day 0 of the run is that date
"""

from __future__ import annotations

import csv
import datetime as dt
import tomllib
from pathlib import Path

import numpy as np

from .testing import SyntheticUser

DAY = 86400.0


class ReportedUser(SyntheticUser):
    _name = "Basin Ledger generic water user (a reported daily series)"

    def initialize(self, config_file=None):
        if not config_file:
            raise ValueError("ReportedUser needs a config file with series and start")
        path = Path(config_file)
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
        series = Path(cfg["series"])
        series = series if series.is_absolute() else path.parent / series
        start = dt.date.fromisoformat(cfg["start"])
        self.days: dict[int, tuple[float, float, float]] = {}
        self.source: dict[int, str] = {}
        with open(series, newline="") as f:
            for r in csv.DictReader(f):
                d = (dt.date.fromisoformat(r["date"]) - start).days
                w, c, ret = float(r["withdrawal_m3"]), float(r["consumption_m3"]), float(r["return_m3"])
                if abs(w - c - ret) > 1e-9 * max(w, 1.0):
                    raise ValueError(f"{series}: {r['date']}: withdrawal != consumption + return")
                self.days[d] = (w, c, ret)
                self.source[d] = r.get("source", "")
        self._t = 0.0
        self._dt = DAY
        self._v["water_user_water__withdrawal_volume_flux_limit"][:] = np.inf

    def update(self):
        d = int(round(self._t / DAY))
        self._t += self._dt
        w, c, r = self.days.get(d, (0.0, 0.0, 0.0))
        cap = float(self._v["water_user_water__withdrawal_volume_flux_limit"][0]) * DAY
        if w > cap:  # a limit scales the day down, keeping its shares
            c, r, w = c * cap / w, r * cap / w, cap
        self._v["water_user_water__withdrawal_volume_flux"][0] = w / DAY
        self._v["water_user_water__gain_volume_flux"][0] = 0.0
        self._v["water_user_water__consumption_volume_flux"][0] = c / DAY
        self._v["water_user_water__return_volume_flux"][0] = r / DAY
        self._v["water_user_return_water_dissolved_solids__mass_flux"][0] = 0.0
        self._v["water_user_return_water__temperature"][0] = 0.0
        self._v["water_user__electric_power"][0] = 0.0

    def get_output_var_names(self):
        return ("water_user_water__withdrawal_volume_flux", "water_user_water__gain_volume_flux",
                "water_user_water__consumption_volume_flux", "water_user_water__return_volume_flux")


def write_series(path: Path, dates: list[str], withdrawal, consumption, source: str = "reported"):
    """A ReportedUser series from daily volumes (m3); the return is withdrawal less consumption."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "withdrawal_m3", "consumption_m3", "return_m3", "source"])
        for d, a, b in zip(dates, withdrawal, consumption):
            w.writerow([d, repr(float(a)), repr(float(b)), repr(float(a) - float(b)), source])
