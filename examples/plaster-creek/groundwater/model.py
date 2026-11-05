"""Write the Plaster Creek MODFLOW 6 simulation from the arrays prepare.py made.

``build(workspace, days, start)`` is the builder the example's config names. It writes a transient model of daily
steps, starting from prepare.py's steady-state heads. Recharge, the campus well's rate and the river stages are zero
or placeholders in the files, because the driver sets them every day. ``steady=True`` writes the one-step steady state
prepare.py runs to get those heads, with mean recharge and mean river depth.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import flopy
import numpy as np

from basinledger.config import cache_dir

NPZ = cache_dir() / "plaster-creek" / "groundwater.npz"
SY, SS = 0.15, 1e-5  # [A]
BED = 1.0            # m, streambed thickness [A]


def build(workspace, days: int, start: dt.date | None, steady: bool = False, recharge=None, depth=None,
          npz: Path = NPZ) -> Path:
    a = np.load(npz, allow_pickle=True)
    nrow, ncol, cell = int(a["nrow"]), int(a["ncol"]), float(a["cell"])
    top, botm = a["top"], a["botm"]
    ws = Path(workspace)
    sim = flopy.mf6.MFSimulation(sim_name="plaster", sim_ws=ws, exe_name="mf6")
    tdis = dict(time_units="days", nper=1, perioddata=[(float(days), days, 1.0)])
    if start is not None:
        tdis["start_date_time"] = start.isoformat()
    flopy.mf6.ModflowTdis(sim, **tdis)
    flopy.mf6.ModflowIms(sim, complexity="moderate", outer_dvclose=1e-5, inner_dvclose=1e-7,
                         rcloserecord=[1e-3, "strict"], outer_maximum=200, inner_maximum=300,
                         linear_acceleration="bicgstab")
    gwf = flopy.mf6.ModflowGwf(sim, modelname="gwf")  # flows saved per package, not cell to cell
    active = a["active"]
    flopy.mf6.ModflowGwfdis(gwf, length_units="meters", nlay=3, nrow=nrow, ncol=ncol, delr=cell, delc=cell,
                            xorigin=float(a["x0"]), yorigin=float(a["y0"]), top=top, botm=botm,
                            idomain=np.broadcast_to(active.astype(int), botm.shape))
    flopy.mf6.ModflowGwfnpf(gwf, icelltype=0, k=a["k"], k33=a["k33"])
    flopy.mf6.ModflowGwfsto(gwf, iconvert=1, sy=SY, ss=SS, save_flows=True, **({"steady_state": {0: True}} if steady
                                                               else {"transient": {0: True}}))
    strt = a["strt"] if "strt" in a.files else np.broadcast_to(top - 2.0, botm.shape)
    flopy.mf6.ModflowGwfic(gwf, strt=strt)
    flopy.mf6.ModflowGwfrcha(gwf, recharge=recharge if recharge is not None else 0.0, pname="rch", save_flows=True)

    riv_cells, bed, cond, obj = a["riv_cells"], a["riv_bed"], a["riv_cond"], a["riv_obj"]
    rbot = bed - BED
    stage = bed + (np.array([depth[o] for o in obj]) if depth is not None else 0.0)
    flopy.mf6.ModflowGwfriv(gwf, pname="riv", save_flows=True, stress_period_data={0: [
        ((0, int(r), int(c)), float(s), float(k), float(b)) for (r, c), s, k, b in zip(riv_cells, stage, cond, rbot)]})
    is_riv = np.zeros((nrow, ncol), bool)
    is_riv[riv_cells[:, 0], riv_cells[:, 1]] = True
    kv1 = a["k33"][0]
    flopy.mf6.ModflowGwfdrn(gwf, pname="drn", save_flows=True, stress_period_data={0: [
        ((0, r, c), float(top[r, c]), float(kv1[r, c] * cell * cell / 1.0))
        for r in range(nrow) for c in range(ncol) if active[r, c] and not is_riv[r, c]]})
    gh = a["ghb_head"]
    ghb = []
    for r, c in zip(*np.where(np.isfinite(gh))):
        for lay in (0, 1):
            thick = (top[r, c] if lay == 0 else botm[0, r, c]) - botm[lay, r, c]
            ghb.append(((lay, int(r), int(c)), float(gh[r, c]), float(a["k"][lay, r, c] * thick)))
    flopy.mf6.ModflowGwfghb(gwf, pname="ghb", save_flows=True, stress_period_data={0: ghb})
    lay, r, c = (int(v) for v in a["campus_well"])
    flopy.mf6.ModflowGwfwel(gwf, pname="wel", save_flows=True, stress_period_data={0: [((lay, r, c), 0.0)]})
    flopy.mf6.ModflowGwfoc(gwf, budget_filerecord="gwf.cbc", head_filerecord="gwf.hds",
                           saverecord=[("HEAD", "LAST" if not steady else "ALL"), ("BUDGET", "ALL")],
                           printrecord=[("BUDGET", "LAST")])
    sim.write_simulation(silent=True)
    return ws


def campus_well() -> tuple[int, int, int]:
    return tuple(int(v) for v in np.load(NPZ, allow_pickle=True)["campus_well"])
