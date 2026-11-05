"""NextGen as the surface model: a finished NGIAB run, replayed one day at a time.

ngen runs every catchment over the whole period and t-route routes the result afterward, so a NextGen run can't be
paused between days the way SWAT+ can through swatplus-bmi. Basin Ledger reads a finished run instead: NextGen In A Box's
run folder, with ``config/realization.json``, ``config/*_subset.gpkg`` (the hydrofabric subset) and
``outputs/troute/*.nc``. ``NgenReplay`` presents it to the driver through the same few BMI calls the driver uses for
SWAT+, so channel flows, rules on flow, outputs and the ledger work unchanged. Objects are hydrofabric flowpaths
(``wb-``), and every result is keyed to their ids.

What a replay can't do:
- **No feedback.** Users and rules in Basin Ledger don't change the flows NextGen computed. Water users inside the
  NextGen run (nextgen-michigan's WaterUsers component) are in its flows; Basin Ledger's users are accounted beside
  them. A rule acting on a replayed flow acts on the flow without that user.
- **No recharge yet.** The run's catchment outputs don't include CFE's percolation to its groundwater store, so there
  is nothing to pass to MODFLOW 6. That needs a rerun with the flux in the realization's output variables.
- **No surface routes.** Withdrawals and returns can't be set in a finished run.

Daily values are means of t-route's hourly values that end within the day (t-route reports the end of each hour).
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path

import numpy as np

QOUT = "channel_water__volume_outflow_rate"   # m3 s-1, per flowpath, daily mean
DEPTH = "channel_water__depth"                # m, per flowpath, daily mean (t-route's depth)
VARS = {QOUT: "m3 s-1", DEPTH: "m"}


def _troute(run: Path):
    import netCDF4

    files = sorted((run / "outputs" / "troute").glob("*.nc"))
    if not files:
        raise FileNotFoundError(f"no t-route output in {run / 'outputs' / 'troute'}")
    if len(files) > 1:
        raise NotImplementedError("t-route output in several files isn't read yet")
    with netCDF4.Dataset(files[0]) as d:
        ids = [f"wb-{int(i)}" for i in d["feature_id"][:]]
        t = np.asarray(d["time"][:], dtype=float)           # s since the run start, the end of each hour
        start = d["time"].units.split(" since ")[1].strip()
        flow = np.asarray(d["flow"][:], dtype=float)        # (feature, time), m3 s-1
        depth = np.asarray(d["depth"][:], dtype=float)
    return ids, t, start, flow, depth


def flowpath_nexus(run: Path) -> dict[str, str]:
    """Each flowpath's downstream nexus, from the hydrofabric subset."""
    gpkg = sorted((run / "config").glob("*.gpkg"))
    if not gpkg:
        return {}
    with sqlite3.connect(gpkg[0]) as db:
        return {i: t for i, t in db.execute("select id, toid from flowpaths")}


class NgenReplay:
    """A finished NGIAB run as a daily, read-only model with the BMI calls the driver uses."""

    _name = "NextGen (NGIAB run, replayed)"

    def initialize(self, run_folder: str):
        self.run = Path(run_folder)
        ids, t, start, flow, depth = _troute(self.run)
        if np.any(np.diff(t) != 3600):
            raise ValueError("t-route output must be hourly")
        hours = len(t)
        if hours % 24:
            raise ValueError(f"t-route output has {hours} hours, not whole days")
        days = hours // 24
        self.ids = ids
        self.start = dt.datetime.fromisoformat(start)
        self._daily = {QOUT: flow.reshape(len(ids), days, 24).mean(axis=2),
                       DEPTH: depth.reshape(len(ids), days, 24).mean(axis=2)}
        self.days = days
        self.day = 0
        self.nexus = flowpath_nexus(self.run)
        real = json.loads((self.run / "config" / "realization.json").read_text())
        self.realization_start = real.get("time", {}).get("start_time")

    def update(self):
        if self.day >= self.days:
            raise RuntimeError("the replayed run has ended")
        self.day += 1

    def update_until(self, time):
        while self.day < time:
            self.update()

    def finalize(self):
        pass

    # time
    def get_time_units(self):
        return f"days since {self.start:%Y-%m-%d %H:%M:%S}"

    def get_start_time(self):
        return 0.0

    def get_end_time(self):
        return float(self.days)

    def get_current_time(self):
        return float(self.day)

    def get_time_step(self):
        return 1.0

    # variables: values read after day d are day d's (the last day run), as with swatplus-bmi
    def get_input_var_names(self):
        return ()

    def get_output_var_names(self):
        return tuple(VARS)

    def get_var_units(self, name):
        return VARS[name]

    def get_var_grid(self, name):
        VARS[name]
        return 0

    def get_grid_size(self, grid):
        return len(self.ids)

    def get_grid_object_names(self, grid):
        return list(self.ids)

    def get_value(self, name, dest):
        dest[:] = self._daily[name][:, self.day - 1] if self.day > 0 else 0.0
        return dest

    def set_value(self, name, src):
        raise KeyError(f"{name}: a replayed NextGen run takes no inputs")

    # restarts
    def save_state(self, folder: str):
        Path(folder).mkdir(parents=True, exist_ok=True)
        (Path(folder) / "nextgen.json").write_text(json.dumps({"day": self.day, "run": str(self.run)}))

    def load_state(self, folder: str):
        s = json.loads((Path(folder) / "nextgen.json").read_text())
        if Path(s["run"]) != self.run:
            raise ValueError("saved state is from another NextGen run")
        self.day = s["day"]
