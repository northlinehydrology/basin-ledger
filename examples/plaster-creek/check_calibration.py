"""Recompute the calibrated NextGen run's fit at USGS 04119055 with Basin Ledger's own statistics.

The run (nextgen-michigan's stage-2 baseline) is read the way the driver reads it, daily means of t-route's hourly
flow on the gage's flowpath. The gage record is the one ngiab-cal downloaded for the calibration
(``obs_hourly_discharge_cms.csv``, USGS instantaneous values), averaged to calendar days. Periods are
nextgen-michigan's (docs/calibration.md): calibration 2019-10-01 to 2021-05-16, validation 2021-05-16 to 2022-12-31.

    uv run python examples/plaster-creek/check_calibration.py [run folder] [observations csv]
"""

from __future__ import annotations

import csv
import datetime as dt
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from basinledger import calibration as K
from basinledger.config import nextgen_michigan
from basinledger.coupling.nextgen import QOUT, NgenReplay

FLOWPATH = "wb-652056"  # the gage's flowpath (the crosswalk puts USGS 04119055 on cat-652056)
PERIODS = {"calibration": ("2019-10-01", "2021-05-16"), "validation": ("2021-05-16", "2022-12-31")}


def daily_observed(path: Path) -> dict[str, float]:
    days = defaultdict(list)
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            v = float(r["obs_flow"])
            if v >= 0:
                days[r["value_date"][:10]].append(v)
    return {d: float(np.mean(v)) for d, v in days.items() if len(v) >= 72}  # at least 18 h of 15-min values


def simulated_daily(run: Path) -> dict[str, float]:
    m = NgenReplay()
    m.initialize(str(run))
    i = m.ids.index(FLOWPATH)
    out = {}
    buf = np.empty(len(m.ids))
    for d in range(m.days):
        m.update()
        m.get_value(QOUT, buf)
        out[(m.start.date() + dt.timedelta(days=d)).isoformat()] = float(buf[i])
    return out


def fit(run: Path, obs_path: Path) -> dict[str, dict[str, float]]:
    sim, obs = simulated_daily(run), daily_observed(obs_path)
    out = {}
    for name, (a, b) in PERIODS.items():
        days = sorted(d for d in sim if a <= d < b and d in obs)
        s = np.array([sim[d] for d in days])
        o = np.array([obs[d] for d in days])
        out[name] = {"start": a, "end": b, "days": len(days), "kge": K.kge(s, o), "nse": K.nse(s, o),
                     "log_nse": K.log_nse(s, o), "pbias": K.pbias(s, o)}
    return out


if __name__ == "__main__":
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else nextgen_michigan() / "runs" / "scenarios" / "baseline"
    obs = Path(sys.argv[2]) if len(sys.argv) > 2 else \
        nextgen_michigan() / "runs" / "plaster-cal2" / "calibration" / "obs_hourly_discharge_cms.csv"
    for period, st in fit(run, obs).items():
        print(period, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in st.items()})
