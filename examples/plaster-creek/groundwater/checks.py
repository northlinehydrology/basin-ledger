"""Check the Plaster Creek groundwater model against observations, and compare the campus on its own well with the
campus on utility water.

    uv run --group gis python examples/plaster-creek/groundwater/checks.py

Reads the two runs ``python -m basinledger run`` writes (groundwater.toml as run ``utility``, groundwater-wells.toml
as run ``wells``) and writes ``results.json`` beside this file and figures to ``docs/figures/plaster-gw-*.png``.

1. **Heads.** Steady-state heads against Wellogic drift wells' static water levels: ground elevation less the level,
   at completion. Wells completed since 2000 are the main set, since the levels are single readings at completion
   and older records are incomplete in Wellogic. All dates are shown too. Each well is compared with its cell, in
   layer 1 if its screen's midpoint is within layer 1, else layer 2.
2. **Base flow.** The model's groundwater discharge to streams inside the basin (river cells plus seepage cells,
   daily) against an Eckhardt (2005) separation of the gage's approved daily record. CFE's own groundwater outflow
   is shown for comparison. Calibration and validation periods are as nextgen-michigan's.
3. **Balance.** MODFLOW 6's budget closes every day, from its list file, and the ledger closed every day of both runs.
4. **The campus on its own well.** The drawdown at the well, and the streamflow depletion: the drop in groundwater
   discharge to streams in the basin, against the gage's low flow and nextgen-michigan's Glover result.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import flopy
import numpy as np
from shapely import contains_xy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import geometry as G  # noqa: E402
import prepare as P  # noqa: E402

from basinledger import calibration as K  # noqa: E402
from basinledger.config import cache_dir  # noqa: E402

ROOT = HERE.parents[2]
RUNS = ROOT / "runs" / "plaster-creek-groundwater"
DATA = cache_dir() / "plaster-creek" / "data"
NPZ = cache_dir() / "plaster-creek" / "groundwater.npz"
NGEN = cache_dir() / "plaster-creek" / "nextgen-recharge"
CAL, VAL = ("2019-10-01", "2021-05-16"), ("2021-05-16", "2022-12-31")
GLOVER = {"change_7day_low_flow_m3s": -0.026, "baseline_7day_low_flow_m3s": 0.194,
          "source": "nextgen-michigan docs/note.md: own wells, sewered wastewater; wells 500 m from the stream, "
                    "T 500 m2/d, Sy 0.1 [A]; April 2019 to December 2022"}


def head_fit(a) -> dict:
    h, top, botm = a["strt"], a["top"], a["botm"]
    x0, y0, cell, nrow, ncol = float(a["x0"]), float(a["y0"]), float(a["cell"]), int(a["nrow"]), int(a["ncol"])
    rows = []
    for v in P.wells(DATA):
        c, r = int((v["x"] - x0) // cell), int((y0 + nrow * cell - v["y"]) // cell)
        if not (0 <= r < nrow and 0 <= c < ncol) or not a["active"][r, c]:
            continue
        lay = 0 if v["screen_mid"] <= top[r, c] - botm[0, r, c] else 1
        rows.append((v["date"], v["head"], float(h[lay, r, c]), v["x"], v["y"]))
    out = {}
    for name, keep in (("since_2000", lambda d: d >= "2000-01-01"), ("all_dates", lambda d: True)):
        sel = [x for x in rows if keep(x[0])]
        o = np.array([x[1] for x in sel])
        s = np.array([x[2] for x in sel])
        out[name] = {"wells": len(sel), "mean_error_m": K.mean_error(s, o), "mae_m": float(np.mean(np.abs(s - o))),
                     "rmse_m": K.rmse(s, o), "observed_range_m": float(o.max() - o.min()),
                     "rmse_over_range": K.rmse(s, o) / float(o.max() - o.min())}
    out["_points"] = rows
    return out


def inside_basin(a):
    gpkg = next((NGEN / "config").glob("*.gpkg"))
    outline = G.basin_outline(G.catchments(gpkg))
    x0, y0, cell, nrow, ncol = float(a["x0"]), float(a["y0"]), float(a["cell"]), int(a["nrow"]), int(a["ncol"])
    XC, YC = np.meshgrid(x0 + (np.arange(ncol) + 0.5) * cell, y0 + nrow * cell - (np.arange(nrow) + 0.5) * cell)
    return contains_xy(outline, XC, YC)


def discharge_to_streams(run: str, a, basin, runs: Path = RUNS) -> tuple[np.ndarray, np.ndarray]:
    """Daily groundwater discharge to river and seepage cells inside the basin, m3 s-1: gross (aquifer to stream
    only, the counterpart of separated base flow) and net (less what flooded rivers lose to the aquifer)."""
    cbc = flopy.utils.CellBudgetFile(runs / run / "mf6" / "gwf.cbc", precision="double")
    inbasin = set(np.flatnonzero(basin.ravel()) + 1)  # 1-based user nodes of layer 1
    nodes_cache = {}
    gross, net = [], []
    for riv, drn in zip(cbc.get_data(text="RIV"), cbc.get_data(text="DRN")):
        g = n_ = 0.0
        for name, rec in (("riv", riv), ("drn", drn)):
            if name not in nodes_cache:
                nodes_cache[name] = np.array([x in inbasin for x in rec["node"]])
            q = rec["q"][nodes_cache[name]]
            g += -float(q[q < 0].sum())
            n_ += -float(q.sum())
        gross.append(g / 86400.0)
        net.append(n_ / 86400.0)
    return np.array(gross), np.array(net)


def daily_closure(run: str, runs: Path = RUNS) -> float:
    """The largest daily budget imbalance, as a share of that day's gross flow, from the budget file."""
    cbc = flopy.utils.CellBudgetFile(runs / run / "mf6" / "gwf.cbc", precision="double")
    terms = [t.decode().strip() for t in cbc.get_unique_record_names()]
    net, gross = None, None
    for t in terms:
        v = []
        for d in cbc.get_data(text=t):
            q = d["q"] if d.dtype.names else d.ravel()
            v.append((q.sum(), np.abs(q).sum()))
        v = np.array(v)
        net = v[:, 0] if net is None else net + v[:, 0]
        gross = v[:, 1] if gross is None else gross + v[:, 1]
    return float(np.max(np.abs(net) / gross))


def series(run: str, runs: Path = RUNS) -> dict[str, np.ndarray]:
    with open(runs / run / "outputs" / "series.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    return {k: (np.array([r[k] for r in rows]) if k == "date" else np.array([float(r[k]) for r in rows]))
            for k in rows[0]}


def cfe_baseflow(dates) -> np.ndarray:
    """CFE's groundwater outflow to the channels (DEEP_GW_TO_CHANNEL_FLUX), summed over catchments, m3 s-1."""
    from basinledger.coupling.nextgen import catchment_areas
    areas = catchment_areas(NGEN)
    total = np.zeros(len(dates))
    for f in sorted((NGEN / "outputs" / "ngen").glob("cat-*.csv")):
        with open(f) as fh:
            head = fh.readline().strip().split(",")
            k = head.index("DEEP_GW_TO_CHANNEL_FLUX")
            v = np.array([float(l.split(",")[k]) for l in fh if l.strip()])
        total += v[: len(dates) * 24].reshape(len(dates), 24).sum(axis=1) * areas[f.stem] / 86400.0
    return total


def seven_day_lows(dates, q) -> dict[str, float]:
    """The lowest 7-day mean flow in each April-March year."""
    q7 = np.convolve(q, np.ones(7) / 7, "valid")
    d7 = dates[6:]
    out = {}
    for y in range(2019, 2023):
        m = (d7 >= f"{y}-04-01") & (d7 < f"{y + 1}-04-01")
        if m.sum() > 300:
            out[str(y)] = float(q7[m].min())
    return out


def main() -> int:
    a = np.load(NPZ, allow_pickle=True)
    res = {"model": {"active_cells_per_layer": int(a["active"].sum()), "cell_m": float(a["cell"]),
                     "active_area_km2": float(a["active"].sum() * float(a["cell"]) ** 2 / 1e6), "layers": 3,
                     "river_cells": int(len(a["riv_cells"])), "choices": P.CHOICES}}
    hf = head_fit(a)
    pts = hf.pop("_points")
    res["heads"] = hf

    basin = inside_basin(a)
    s_u, s_w = series("utility"), series("wells")
    dates = s_u["date"]
    gw_u, net_u = discharge_to_streams("utility", a, basin)
    gw_w, net_w = discharge_to_streams("wells", a, basin)
    obs = {d: q for d, q, _ in K.usgs_daily("04119055", "2018-10-01", "2022-12-31",
                                            cache=DATA / "usgs_04119055_daily.csv")}
    q = np.array([obs[d] for d in dates])
    alpha = float(np.quantile(K.recession_ratios(q), 0.9))
    bf = K.eckhardt(q, alpha)
    cfe = cfe_baseflow(dates)
    res["baseflow"] = {"alpha": alpha, "bfi_max": 0.8, "modflow6": "gross discharge to streams (aquifer to stream "
                       "only); flooded rivers' losses to the aquifer are excluded, as separated base flow has none"}
    low = q < np.median(q)
    for name, (d0, d1) in (("calibration", CAL), ("validation", VAL)):
        m = (dates >= d0) & (dates < d1)
        res["baseflow"][name] = {
            "observed_flow_mean_m3s": float(q[m].mean()), "separated_baseflow_mean_m3s": float(bf[m].mean()),
            "modflow6_discharge_mean_m3s": float(gw_u[m].mean()), "cfe_baseflow_mean_m3s": float(cfe[m].mean()),
            "modflow6_net_discharge_mean_m3s": float(net_u[m].mean()),
            "modflow6_vs_separated": {"pbias": K.pbias(gw_u[m], bf[m]), "nse": K.nse(gw_u[m], bf[m]),
                                      "log_nse": K.log_nse(gw_u[m], bf[m]),
                                      "low_flow_days_pbias": K.pbias(gw_u[m & low], bf[m & low])},
            "cfe_vs_separated": {"pbias": K.pbias(cfe[m], bf[m]), "nse": K.nse(cfe[m], bf[m])}}
    res["balance"] = {"max_daily_imbalance_share": {r: daily_closure(r) for r in ("utility", "wells")},
                      "ledger": "closed every day of both runs (the driver stops otherwise)"}

    dd = s_u["head:campus-well"] - s_w["head:campus-well"]
    dep = net_u - net_w  # depletion: the drop in net discharge to streams in the basin
    pumped = np.array([0.0])
    with open(RUNS / "wells" / "outputs" / "ledger.csv", newline="") as f:
        led = list(csv.DictReader(f))
    pumped = np.array([float(r["route:well:campus:delivered"]) for r in led]) / 86400.0
    flow = s_u["flow:wb-652056"]
    lows = seven_day_lows(dates, flow)
    lows_w = seven_day_lows(dates, np.maximum(flow - dep, 0.0))
    res["campus_wells"] = {
        "well": {"layer": int(a["campus_well"][0]) + 1, "row": int(a["campus_well"][1]),
                 "col": int(a["campus_well"][2]), "distance_to_river_cell_m": float(a["campus_well_distance"])},
        "pumping_mean_m3s": float(pumped.mean()), "pumping_max_day_m3s": float(pumped.max()),
        "drawdown_at_well_m": {"end": float(dd[-1]), "max": float(dd.max())},
        "depletion_mean_m3s": float(dep.mean()), "depletion_last_year_m3s": float(dep[-365:].mean()),
        "depletion_share_of_pumping_last_year": float(dep[-365:].mean() / pumped[-365:].mean()),
        "gage_7day_low_flow_baseline_m3s": lows,
        "gage_7day_low_flow_with_wells_m3s": lows_w,
        "change_mean_7day_low_flow_m3s": float(np.mean(list(lows_w.values())) - np.mean(list(lows.values()))),
        "note": "the replayed NextGen flow less MODFLOW 6's depletion; t-route doesn't see the well",
        "glover": GLOVER,
    }
    (HERE / "results.json").write_text(json.dumps(res, indent=2))
    figures(dates, q, bf, gw_u, cfe, pts, dep, pumped, dd)
    print(json.dumps({k: v for k, v in res.items() if k != "model"}, indent=1)[:4000])
    return 0


def figures(dates, q, bf, gw, cfe, pts, dep, pumped, dd):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import datetime as dt

    figs = ROOT / "docs" / "figures"
    t = np.array([dt.date.fromisoformat(d) for d in dates])
    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.semilogy(t, q, color="#bbbbbb", lw=0.6, label="observed flow, USGS 04119055")
    ax.semilogy(t, bf, color="#333333", lw=1.0, label="base flow, Eckhardt separation")
    ax.semilogy(t, gw, color="#c0504d", lw=1.0, label="MODFLOW 6 discharge to streams")
    ax.semilogy(t, cfe, color="#3b6ea5", lw=0.8, ls="--", label="CFE groundwater outflow")
    ax.set_ylabel("m³ per second")
    ax.set_title("Base flow at the gage: separated from the record, MODFLOW 6 and CFE (screening)")
    ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    fig.savefig(figs / "plaster-gw-baseflow.png", dpi=150)

    o = np.array([p[1] for p in pts if p[0] >= "2000-01-01"])
    s = np.array([p[2] for p in pts if p[0] >= "2000-01-01"])
    oa = np.array([p[1] for p in pts])
    sa = np.array([p[2] for p in pts])
    fig, ax = plt.subplots(figsize=(4.6, 4.4))
    ax.scatter(oa, sa, s=4, color="#cccccc", label="all dates")
    ax.scatter(o, s, s=12, color="#c0504d", label="completed since 2000")
    lo, hi = min(oa.min(), sa.min()), max(oa.max(), sa.max())
    ax.plot([lo, hi], [lo, hi], color="#333333", lw=0.8)
    ax.set_xlabel("observed head, m (Wellogic, at completion)")
    ax.set_ylabel("simulated head, m (steady state)")
    ax.set_title("Heads, drift wells (screening)")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(figs / "plaster-gw-heads.png", dpi=150)

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
    a1.plot(t, pumped, color="#c0504d", lw=0.8, label="campus pumping")
    a1.plot(t, dep, color="#3b6ea5", lw=1.0, label="streamflow depletion in the basin")
    a1.set_ylabel("m³ per second")
    a1.legend(frameon=False, fontsize=8)
    a2.plot(t, dd, color="#333333", lw=1.0)
    a2.set_ylabel("drawdown at the well, m")
    a1.set_title("The campus on its own well, against utility water (screening)")
    fig.tight_layout()
    fig.savefig(figs / "plaster-gw-campus-wells.png", dpi=150)


if __name__ == "__main__":
    sys.exit(main())
