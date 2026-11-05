"""SWAT+ through swatplus-bmi: project edits an example needs, and the daily reads and sets the driver uses.

The edits add objects to a copy of a SWAT+ project before it starts: water allocation places of use (withdrawals from
a channel, set daily through ``place_of_use_water__volume_demand_rate``) and daily point sources (recall objects,
set daily through ``point_source_water__volume_flow_rate``). They follow the input readers of SWAT+ 62.0.1
(water_allocation_read.f90, recall_read.f90), as swatplus-bmi's tests do. Places of use are of type "out": SWAT+
delivers their water nowhere, so it leaves SWAT+ and the driver places it.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np

DEMAND = "place_of_use_water__volume_demand_rate"        # m3 s-1, set for the next day
WITHDRAWN = "place_of_use_water__volume_withdrawal_rate"  # m3 s-1, what SWAT+ took
POINT = "point_source_water__volume_flow_rate"           # m3 s-1, set for the next day
QOUT = "channel_water__volume_outflow_rate"
AQU_OUT = "aquifer_water__volume_outflow_rate"
DEPTH = "channel_water__depth"                                   # m, swatplus-bmi 0.2.0
GW_EXCHANGE = "channel_water__groundwater_volume_exchange_rate"  # m3 s-1, positive into the channel, 0.2.0


def has_groundwater_exchange() -> bool:
    """Whether the installed swatplus-bmi sets a channel's groundwater exchange directly (0.2.0 and later). Earlier
    versions route the exchange through a point source and a water allocation place of use per channel."""
    from importlib.metadata import version
    major, minor = (int(x) for x in version("swatplus-bmi").split(".")[:2])
    return (major, minor) >= (0, 2)


def add_places_of_use(project: Path, uses: list[tuple[str, str]], rate_max: float = 100.0):
    """Water allocation places of use, each taking from one channel: [(name, channel), ...]."""
    project = Path(project)
    cio = (project / "file.cio").read_text().splitlines()
    cio = ["water_rights      place_of_use.wro  point_of_diver.wro  null" if l.startswith("water_rights") else l
           for l in cio]
    (project / "file.cio").write_text("\n".join(cio) + "\n")
    chans = _channels(project)
    pou = [f"place_of_use.wro: {len(uses)} places of use (Basin Ledger)", str(len(uses)),
           "num name typ typ_num pods pors dtbl_mx rate_max dtbl_pod_fr dtbl_por_fr"]
    # SWAT+ keeps one point of diversion per channel (sd_ch%wallo_pod), so the places of use on a channel share it
    order = list(dict.fromkeys(ch for _, ch in uses))
    for i, (name, ch) in enumerate(uses, 1):
        pou.append(f"{i} {name} out {i} 1 0 null {rate_max} null null")
        pou.append(f"1 {order.index(ch) + 1} {ch} cha {chans.index(ch) + 1} null 0 null 0.0 null 1000000. 1.0 n")
    pod = [f"point_of_diver.wro: one per channel (Basin Ledger)", str(len(order)),
           "num name typ typ_num pous pou_num pou_name pod_num typ typ_num right"]
    for k, ch in enumerate(order, 1):
        mine = [(i, name) for i, (name, c) in enumerate(uses, 1) if c == ch]
        pod.append(f"{k} {ch} cha {chans.index(ch) + 1} {len(mine)} "
                   + " ".join(f"{i} {name} 1 out {i} senior" for i, name in mine))
    (project / "place_of_use.wro").write_text("\n".join(pou) + "\n")
    (project / "point_of_diver.wro").write_text("\n".join(pod) + "\n")


def add_point_sources(project: Path, sources: list[tuple[str, str]]):
    """Daily point sources (recall objects) into channels, zero flow in the files: [(name, channel), ...]."""
    project = Path(project)
    start, end = _period(project)
    con = (project / "recall.con").read_text().splitlines()
    hdr = con[:2]
    template = con[2].split()
    rows = []
    for i, (name, ch) in enumerate(sources, 1):
        f = list(template)
        c = _channels(project).index(ch) + 1
        f[0], f[1], f[2], f[7] = str(i), name, str(i), str(i)
        f[13], f[14] = "sdc", str(c)
        rows.append("  ".join(f))
    (project / "recall.con").write_text("\n".join(hdr + rows) + "\n")
    cnt = (project / "object.cnt").read_text().splitlines()
    f = cnt[2].split()  # name ls_area tot_area obj hru lhru rtu mfl aqu cha res rec ...
    old = int(f[11])
    f[3] = str(int(f[3]) + len(sources) - old)
    f[11] = str(len(sources))
    cnt[2] = "  ".join(f)
    (project / "object.cnt").write_text("\n".join(cnt) + "\n")
    rec = ["recall.rec: daily point sources (Basin Ledger)", "NUM     NAME    TYPE     FNAME"]
    for i, (name, ch) in enumerate(sources, 1):
        rec.append(f"   {i}    {name}      1    {name}.rec")
        lines = [f"{name}.rec: daily point source, zero in the file; set daily through BMI", "14",
                 "jday mo day_mo yr ob_typ ob_name flo sed orgn sedp no3 solp chla nh3 no2 "
                 "cbod dox san sil cla sag lag grv temp"]
        d = start
        while d <= end:
            lines.append(f"{d.timetuple().tm_yday} {d.month} {d.day} {d.year} sdc {ch} 0 " + " ".join(["0"] * 17))
            d += dt.timedelta(days=1)
        (project / f"{name}.rec").write_text("\n".join(lines) + "\n")
    (project / "recall.rec").write_text("\n".join(rec) + "\n")


def aquifer_pass_through(project: Path):
    """SWAT+'s aquifers keep the recharge they get and return none of it (no return flow, revap or deep recharge),
    for two-way coupling, where MODFLOW 6 handles groundwater. SWAT+ 62.0.1 (aqu_1d_control.f90) returns flow when
    the depth to water is at or above flo_min (m) and allows revap above revap_min (m), so both are set to a depth the
    water table can't reach (-1e6 m); rchg_dp is zero."""
    path = Path(project) / "aquifer.aqu"
    lines = path.read_text().splitlines()
    cols = lines[1].split()
    i_flo, i_rev, i_dp = cols.index("flo_min"), cols.index("revap_min"), cols.index("rchg_dp")
    out = lines[:2]
    for l in lines[2:]:
        f = l.split()
        if not f:
            continue
        f[i_flo] = f[i_rev] = "-1000000.0"
        f[i_dp] = "0.0"
        out.append("  ".join(f))
    path.write_text("\n".join(out) + "\n")


def aquifer_areas(project: Path) -> dict[str, float]:
    """Each aquifer's area in m2, from aquifer.con (hectares)."""
    lines = (Path(project) / "aquifer.con").read_text().splitlines()
    cols = lines[1].split()
    i, a = cols.index("name"), cols.index("area")
    return {f[i]: float(f[a]) * 1e4 for f in (l.split() for l in lines[2:]) if f}


def _channels(project: Path) -> list[str]:
    lines = (Path(project) / "chandeg.con").read_text().splitlines()
    return [l.split()[1] for l in lines[2:] if l.split()]


def _period(project: Path) -> tuple[dt.date, dt.date]:
    f = (Path(project) / "time.sim").read_text().splitlines()[2].split()
    d0, y0, d1, y1 = (int(x) for x in f[:4])
    start = dt.date(y0, 1, 1) + dt.timedelta(days=max(d0, 1) - 1)
    end = dt.date(y1, 12, 31) if d1 == 0 else dt.date(y1, 1, 1) + dt.timedelta(days=d1 - 1)
    return start, end


class Swat:
    """Index lookups and float32 buffers for the variables the driver reads and sets."""

    def __init__(self, bmi):
        self.bmi = bmi
        self._buf = {}

    def has(self, var):
        return var in set(self.bmi.get_input_var_names()) | set(self.bmi.get_output_var_names())

    def names(self, var):
        return list(self.bmi.get_grid_object_names(self.bmi.get_var_grid(var)))

    def get(self, var) -> np.ndarray:
        if var not in self._buf:
            self._buf[var] = np.empty(self.bmi.get_grid_size(self.bmi.get_var_grid(var)), np.float32)
        self.bmi.get_value(var, self._buf[var])
        return self._buf[var].astype(np.float64)

    def set(self, var, values: np.ndarray):
        self.bmi.set_value(var, np.asarray(values, np.float32))
