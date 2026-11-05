"""The Plaster Creek demo: one question, answered with the calibrated NextGen surface and a screening MODFLOW 6 model.

    uv run --group gis --group examples python examples/plaster-creek/demo.py

The question: if the campus ran on its own wells instead of utility water, what would Plaster Creek see in a normal
year and in the driest year of the run, and how much would that change the answer a simple method (Glover and
Balmer) gives?

It runs what isn't there yet (in runs/plaster-creek-groundwater):
- the campus on utility water (groundwater.toml) and on its own well (groundwater-wells.toml);
- one-at-a-time ranges on the two assumptions that move the answer most, the glacial deposits' hydraulic conductivity
  (x0.5, x2) and the streambed conductance (x0.1, x10). Each pair (no pumping, pumping) replays the campus's pumping
  as a generic reported user, so the cooling model runs once.

Then it writes four figures to docs/figures (plaster-demo-*.png), the utility case's capacity numbers, and
docs/plaster-creek-demo.md, a page that reads on its own. Before this script: fetch.py, rerun_nextgen.py and
prepare.py in groundwater/ (see its README).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "groundwater"))
import checks as CH  # noqa: E402
import geometry as G  # noqa: E402

from basinledger import config as C  # noqa: E402
from basinledger.analytic import glover_depletion  # noqa: E402
from basinledger.calibration import usgs_daily  # noqa: E402
from basinledger.driver import Basin  # noqa: E402
from basinledger.generic import write_series  # noqa: E402

RUNS = ROOT / "runs" / "plaster-creek-groundwater"
FIGS = ROOT / "docs" / "figures"
PAGE = ROOT / "docs" / "plaster-creek-demo.md"
GAGE = "wb-652056"
VARIANTS = {"K x0.5": {"k_mult": 0.5}, "K x2": {"k_mult": 2.0},
            "streambed x0.1": {"riv_mult": 0.1}, "streambed x10": {"riv_mult": 10.0}, "as built": {}}
# nextgen-michigan's Glover case for the same campus (scenarios/gaines-wells.csv) [A]
GLOVER_NM = {"distance_m": 500.0, "transmissivity_m2_d": 500.0, "storativity": 0.1}
# the utility case (sources: Northline's Gaines site record, public; [A] where an assumption)
UTILITY = {
    "bgua_population": (37464, "EPA SDWIS"),
    "gpcd": (100, [80, 120], "[A] typical Michigan residential and commercial use"),
    "max_day_factor": (2.0, [1.7, 2.3], "[A] suburban systems with lawn irrigation"),
    "bgua_contract_mgd": (10.0, [8, 12], "[A] the BGUA-Wyoming contract maximum isn't public"),
    "wyoming_capacity_mgd": ([90, 120], "City of Wyoming page (90); Prein & Newhof (120): a range [A]"),
    "wyoming_average_mgd": (40, "Prein & Newhof"),
    "cwp_capacity_mgd": (24, "City of Wyoming Clean Water Plant page; NPDES MI0024392"),
    "cwp_current_mgd": (15, [12, 18], "[A] ECHO monitoring reports not yet loaded"),
}
M3_PER_MGAL = 3785.411784  # m3 in a million US gallons


def run_case(cfg_name: str, run: str, force: bool):
    out = RUNS / run / "outputs" / "series.csv"
    if out.exists() and not force:
        return
    cfg = C.load(HERE / cfg_name)
    cfg.run_folder = RUNS
    b = Basin(cfg, run=run)
    try:
        b.run()
        b.write_outputs()
    finally:
        b.finalize()


def pumping_series() -> Path:
    """The campus's daily pumping from the own-well run, as a generic reported user's series."""
    with open(RUNS / "wells" / "outputs" / "ledger.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    path = RUNS / "campus-pumping.csv"
    write_series(path, [r["date"] for r in rows], [float(r["user:campus:withdrawal"]) for r in rows],
                 [float(r["user:campus:consumption"]) for r in rows], source="modeled (CoolingWaterBmi)")
    (RUNS / "campus-pumping.toml").write_text(f'series = "{path.name}"\nstart = "{rows[0]["date"]}"\n')  # relative to the toml
    return RUNS / "campus-pumping.toml"


def run_variant(name: str, args: dict, series_cfg: Path, force: bool):
    tag = name.replace(" ", "-").replace(".", "")
    for pumped in (False, True):
        run = f"variant-{tag}-{'wells' if pumped else 'none'}"
        if (RUNS / run / "outputs" / "series.csv").exists() and not force:
            continue
        cfg = C.load(HERE / "groundwater-wells.toml")
        cfg.run_folder = RUNS
        cfg.mf6_builder_args = dict(args)
        u = cfg.users[0]
        cfg.users = [C.UserConfig(name="campus", component="basinledger.generic:ReportedUser", config=series_cfg,
                                  withdrawal="well:campus", returns="offsite:wastewater-plant", constituents={})]
        b = Basin(cfg, run=run, users=pumped)
        try:
            b.run()
            b.write_outputs()
        finally:
            b.finalize()


def seven_day(q):
    return np.r_[np.full(6, np.nan), np.convolve(q, np.ones(7) / 7, "valid")]


def year_of(dates):
    """April-March years, labelled by the April they start in."""
    return np.array([int(d[:4]) if d[5:7] >= "04" else int(d[:4]) - 1 for d in dates])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="rerun every case")
    ap.add_argument("--no-variants", action="store_true")
    a_ = ap.parse_args(argv)
    run_case("groundwater.toml", "utility", a_.force)
    run_case("groundwater-wells.toml", "wells", a_.force)
    series_cfg = pumping_series()
    if not a_.no_variants:
        for name, args in VARIANTS.items():
            run_variant(name, args, series_cfg, a_.force)

    a = np.load(CH.NPZ, allow_pickle=True)
    basin = CH.inside_basin(a)
    s_u, s_w = CH.series("utility"), CH.series("wells")
    dates = s_u["date"]
    flow = s_u[f"flow:{GAGE}"]
    _, net_u = CH.discharge_to_streams("utility", a, basin)
    _, net_w = CH.discharge_to_streams("wells", a, basin)
    dep = net_u - net_w
    flow_w = np.maximum(flow - dep, 0.0)
    led = list(csv.DictReader(open(RUNS / "wells" / "outputs" / "ledger.csv", newline="")))
    pumped = np.array([float(r["route:well:campus:delivered"]) for r in led]) / 86400.0
    led_u = list(csv.DictReader(open(RUNS / "utility" / "outputs" / "ledger.csv", newline="")))
    campus_u = np.array([float(r["user:campus:withdrawal"]) for r in led_u])
    campus_ret = np.array([float(r["user:campus:return"]) for r in led_u])
    campus_use = np.array([float(r["user:campus:consumption"]) for r in led_u])

    # year types from the gage record: the driest and the median April-March year by observed 7-day low flow
    obs = {d: q for d, q, _ in usgs_daily("04119055", "2018-10-01", "2022-12-31", cache=CH.DATA / "usgs_04119055_daily.csv")}
    q_obs = np.array([obs[d] for d in dates])
    yr = year_of(dates)
    full = [int(y) for y in sorted(set(yr)) if (yr == y).sum() >= 360]
    lows_obs = {y: float(np.nanmin(seven_day(q_obs)[yr == y])) for y in full}
    order = sorted(full, key=lambda y: lows_obs[y])
    dry, normal, wet = order[0], order[len(order) // 2], order[-1]
    threshold = float(np.quantile(flow[dates >= "2019-10-01"], 0.10))  # the baseline's Q90, Oct 2019 on

    res = {"question": __doc__.split("\n\n")[1].replace("\n", " ").strip(), "dry_year": dry, "normal_year": normal,
           "observed_7day_low_m3s": lows_obs, "threshold_q90_m3s": threshold}
    by_year = {}
    for y in full:
        m = yr == y
        b7, w7 = np.nanmin(seven_day(flow)[m]), np.nanmin(seven_day(flow_w)[m])
        by_year[y] = {"type": "driest" if y == dry else ("median" if y == normal else ("wettest" if y == wet else "other")),
                      "baseline_7day_low_m3s": float(b7), "wells_7day_low_m3s": float(w7),
                      "change_7day_low_m3s": float(w7 - b7), "change_7day_low_pct": float(100 * (w7 - b7) / b7),
                      "days_below_q90_baseline": int((flow[m] < threshold).sum()),
                      "days_below_q90_wells": int((flow_w[m] < threshold).sum()),
                      "depletion_jul_oct_m3s": float(dep[m & np.isin([d[5:7] for d in dates], ["07", "08", "09", "10"])].mean()),
                      "pumping_jul_oct_m3s": float(pumped[m & np.isin([d[5:7] for d in dates], ["07", "08", "09", "10"])].mean())}
    res["by_year"] = by_year

    # Glover against MODFLOW 6, the same pumping
    lay, r, c = (int(v) for v in a["campus_well"])
    t_mf6 = float(sum(a["k"][l, r, c] * ((a["top"][r, c] if l == 0 else a["botm"][l - 1, r, c]) - a["botm"][l, r, c])
                      for l in (0, 1)))
    g_nm = glover_depletion(pumped, **GLOVER_NM)
    g_mf = glover_depletion(pumped, float(a["campus_well_distance"]), t_mf6, 0.15)
    last = slice(-365, None)
    res["glover"] = {"nextgen_michigan_parameters": GLOVER_NM,
                     "modflow6_parameters": {"distance_m": float(a["campus_well_distance"]),
                                             "transmissivity_m2_d": t_mf6, "storativity": 0.15},
                     "share_of_pumping_last_year": {"modflow6": float(dep[last].sum() / pumped[last].sum()),
                                                    "glover_nextgen_michigan": float(g_nm[last].sum() / pumped[last].sum()),
                                                    "glover_modflow6_parameters": float(g_mf[last].sum() / pumped[last].sum())}}
    m_dry = (yr == dry) & np.isin([d[5:7] for d in dates], ["07", "08", "09", "10"])
    res["glover"]["dry_year_jul_oct_m3s"] = {"pumping": float(pumped[m_dry].mean()), "modflow6": float(dep[m_dry].mean()),
                                             "glover_nextgen_michigan": float(g_nm[m_dry].mean()),
                                             "glover_modflow6_parameters": float(g_mf[m_dry].mean())}

    # sensitivity: the change in the driest year's 7-day low flow, and the depletion share, per variant
    sens = {}
    for name in VARIANTS:
        tag = name.replace(" ", "-").replace(".", "")
        try:
            _, n0 = CH.discharge_to_streams(f"variant-{tag}-none", a, basin)
            _, n1 = CH.discharge_to_streams(f"variant-{tag}-wells", a, basin)
        except (FileNotFoundError, OSError):
            continue
        d = n0 - n1
        fw = np.maximum(flow - d, 0.0)
        m = yr == dry
        sens[name] = {"change_7day_low_driest_m3s": float(np.nanmin(seven_day(fw)[m]) - np.nanmin(seven_day(flow)[m])),
                      "depletion_share_last_year": float(d[last].sum() / pumped[last].sum()),
                      "days_below_q90_driest": int((fw[m] < threshold).sum())}
    res["sensitivity"] = sens

    # the utility case: capacity, not the creek
    mgd = lambda m3_per_day: m3_per_day / M3_PER_MGAL  # noqa: E731  (m3 a day to million gallons a day)
    bgua_avg = UTILITY["bgua_population"][0] * UTILITY["gpcd"][0] / 1e6
    peak = float(mgd(campus_u.max()))
    res["utility_case"] = {
        "campus_withdrawal_mgd": {"mean": float(mgd(campus_u.mean())), "peak_day": peak},
        "campus_consumption_mgd_mean": float(mgd(campus_use.mean())),
        "campus_return_to_sewer_mgd": {"mean": float(mgd(campus_ret.mean())), "peak_day": float(mgd(campus_ret.max()))},
        "bgua_average_mgd": bgua_avg, "bgua_max_day_mgd": bgua_avg * UTILITY["max_day_factor"][0],
        "bgua_max_day_plus_campus_peak_mgd": bgua_avg * UTILITY["max_day_factor"][0] + peak,
        "bgua_contract_mgd": UTILITY["bgua_contract_mgd"][0],
        "wyoming_headroom_over_average_mgd": [c - UTILITY["wyoming_average_mgd"][0] for c in UTILITY["wyoming_capacity_mgd"][0]],
        "campus_peak_share_of_wyoming_headroom": [peak / (c - UTILITY["wyoming_average_mgd"][0])
                                                  for c in UTILITY["wyoming_capacity_mgd"][0]],
        "cwp_headroom_mgd": UTILITY["cwp_capacity_mgd"][0] - UTILITY["cwp_current_mgd"][0],
        "great_lakes_consumptive_use_mgd_mean": float(mgd(campus_use.mean())),
        "sources": {k: v[-1] for k, v in UTILITY.items()},
    }
    res["calibration"] = {"streamflow": "calibrated at USGS 04119055 (NextGen; calibration/record.toml)",
                          "groundwater": "screening: not fitted; see groundwater/README.md and results.json"}
    (HERE / "demo-results.json").write_text(json.dumps(res, indent=2, default=lambda o: o.item()))
    figures(dates, flow, flow_w, threshold, dry, normal, yr, a, basin, dep, pumped, g_nm, g_mf, by_year)
    page(res)
    print(json.dumps({k: res[k] for k in ("dry_year", "normal_year", "by_year", "glover", "sensitivity", "utility_case")},
                     indent=1)[:6000])
    return 0


def figures(dates, flow, flow_w, threshold, dry, normal, yr, a, basin, dep, pumped, g_nm, g_mf, by_year):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = np.array([dt.date.fromisoformat(d) for d in dates])
    # 1. low-flow hydrographs, median year and driest year
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    for ax, y, label in ((axes[0], normal, "median year"), (axes[1], dry, "driest year")):
        m = (t >= dt.date(y, 6, 1)) & (t <= dt.date(y, 11, 30))
        ax.plot(t[m], flow[m], color="#3b6ea5", lw=1.2, label="utility water (the stream as calibrated)")
        ax.plot(t[m], flow_w[m], color="#c0504d", lw=1.2, label="campus on its own well")
        ax.axhline(threshold, color="#777777", lw=0.8, ls="--", label="low-flow threshold (Q90)")
        ax.set_yscale("log")
        ax.set_title(f"{label}: June to November {y}")
        ax.tick_params(axis="x", labelrotation=30)
    axes[0].set_ylabel("flow at the gage, m³/s")
    axes[0].legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIGS / "plaster-demo-hydrograph.png", dpi=150)

    # 2. map: drawdown at the water table on September 30 of the driest year, reaches by depletion
    import flopy
    hu = flopy.utils.HeadFile(RUNS / "utility" / "mf6" / "gwf.hds")
    hw = flopy.utils.HeadFile(RUNS / "wells" / "mf6" / "gwf.hds")
    day = (dt.date(dry, 9, 30) - dt.date.fromisoformat(dates[0])).days + 1
    kstpkper = (day - 1, 0)
    dd = hu.get_data(kstpkper=kstpkper)[0] - hw.get_data(kstpkper=kstpkper)[0]
    dd = np.where(a["active"], dd, np.nan)
    x0, y0, cell, nrow, ncol = float(a["x0"]), float(a["y0"]), float(a["cell"]), int(a["nrow"]), int(a["ncol"])
    gpkg = next((CH.NGEN / "config").glob("*.gpkg"))
    cats, fps = G.catchments(gpkg), G.flowpaths(gpkg)
    su, sw = CH.series("utility"), CH.series("wells")
    m = (yr == dry) & np.isin([d[5:7] for d in dates], ["07", "08", "09", "10"])
    reach_dep = {f: float((su[f"baseflow:{f}"][m] - sw[f"baseflow:{f}"][m]).mean()) for f in fps
                 if f"baseflow:{f}" in su}
    fig, ax = plt.subplots(figsize=(6.2, 7.2))
    im = ax.imshow(dd, extent=(x0, x0 + ncol * cell, y0, y0 + nrow * cell), cmap="Reds", vmin=0,
                   vmax=np.nanpercentile(dd, 99.5))
    for p in cats.values():
        for g in getattr(p, "geoms", [p]):
            ax.plot(*g.exterior.xy, color="#999999", lw=0.5)
    vmax = max(reach_dep.values()) or 1.0
    for f, line in fps.items():
        v = reach_dep.get(f, 0.0)
        for g in getattr(line, "geoms", [line]):
            ax.plot(*g.xy, color=plt.cm.Blues(0.3 + 0.7 * max(v, 0) / vmax), lw=1 + 5 * max(v, 0) / vmax)
    ax.plot(x0 + (a["campus_well"][2] + 0.5) * cell, y0 + nrow * cell - (a["campus_well"][1] + 0.5) * cell,
            marker="v", color="black", ms=8, label="campus well")
    ax.set_xticks([]), ax.set_yticks([])
    ax.set_title(f"Drawdown, September 30, {dry} (m), and stream depletion by reach,\nJuly to October {dry} "
                 f"(darker, thicker: more; largest {1000 * vmax:.0f} L/s)", fontsize=9)
    fig.colorbar(im, ax=ax, shrink=0.6, label="drawdown at the water table, m")
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(FIGS / "plaster-demo-map.png", dpi=150)

    # 3. days below the threshold, by year
    years = sorted(by_year)
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    xs = np.arange(len(years))
    ax.bar(xs - 0.2, [by_year[y]["days_below_q90_baseline"] for y in years], 0.4, color="#3b6ea5",
           label="utility water (as calibrated)")
    ax.bar(xs + 0.2, [by_year[y]["days_below_q90_wells"] for y in years], 0.4, color="#c0504d",
           label="campus on its own well")
    ax.set_xticks(xs, [f"{y}-{(y + 1) % 100:02d}\n{by_year[y]['type']}" for y in years])
    ax.set_ylabel("days below Q90 at the gage")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGS / "plaster-demo-days-below.png", dpi=150)

    # 4. Glover against MODFLOW 6
    fig, ax = plt.subplots(figsize=(9, 3.4))
    mean7 = lambda x: np.r_[np.full(6, np.nan), np.convolve(x, np.ones(7) / 7, "valid")]  # noqa: E731
    ax.plot(t, pumped, color="#bbbbbb", lw=0.8, label="campus pumping")
    ax.plot(t, dep, color="#c0504d", lw=0.4, alpha=0.35, label="MODFLOW 6, daily (spikes: flood days)")
    ax.plot(t, mean7(dep), color="#c0504d", lw=1.3, label="MODFLOW 6: all reaches and seepage, 7-day mean")
    ax.plot(t, g_nm, color="#3b6ea5", lw=1.0, ls="--", label="Glover, nextgen-michigan's T and S")
    ax.plot(t, g_mf, color="#333333", lw=1.0, ls=":", label="Glover, MODFLOW 6's T and Sy at the well")
    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_ylabel("m³/s")
    ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    fig.savefig(FIGS / "plaster-demo-glover.png", dpi=150)


def page(res):
    """docs/plaster-creek-demo.md, from the numbers."""
    by = res["by_year"]
    dry, med = res["dry_year"], res["normal_year"]
    gd, gm = by[dry], by[med]
    u = res["utility_case"]
    g = res["glover"]["share_of_pumping_last_year"]
    sens = res["sensitivity"]
    chk = json.loads((HERE / "groundwater" / "results.json").read_text())  # groundwater/checks.py
    hf, bfc, bfv = chk["heads"]["since_2000"], chk["baseflow"]["calibration"], chk["baseflow"]["validation"]
    obs7 = res["observed_7day_low_m3s"]
    rows = "\n".join(f"| {k} | {1000 * v['change_7day_low_driest_m3s']:.0f} | {100 * v['depletion_share_last_year']:.0f}% "
                     f"| {v['days_below_q90_driest']} |" for k, v in sens.items())
    yrows = "\n".join(f"| {y}-{(y + 1) % 100:02d} ({v['type']}) | {v['baseline_7day_low_m3s']:.3f} | "
                      f"{v['wells_7day_low_m3s']:.3f} | {v['change_7day_low_pct']:.0f}% | {v['days_below_q90_baseline']} | "
                      f"{v['days_below_q90_wells']} |" for y, v in sorted(by.items()))
    text = f"""# Plaster Creek: a campus on its own wells or on utility water

**The question.** If a 300 MW data center campus in Gaines Township ran on its own wells instead of utility water,
what would Plaster Creek see in a normal year and in a dry year, and how much would that change the answer a simple
method gives?

**Short answer.** On utility water, the creek sees nothing. The water comes from Lake Michigan through Wyoming's plant
and returns to the Grand River through Wyoming's Clean Water Plant, so the binding question is the utility's capacity
(below). On its own well, the campus would lower the creek's 7-day low flow at the gage by
{-1000 * gd['change_7day_low_m3s']:.0f} L/s ({-gd['change_7day_low_pct']:.0f}%) in the driest year of the run
({dry}-{(dry + 1) % 100:02d}) and by {-1000 * gm['change_7day_low_m3s']:.0f} L/s ({-gm['change_7day_low_pct']:.0f}%)
in the median year ({med}-{(med + 1) % 100:02d}). Days below the gage's low-flow threshold (Q90) would go from
{gd['days_below_q90_baseline']} to {gd['days_below_q90_wells']} in the driest year. In the last year, the coupled model
takes {100 * g['modflow6']:.0f}% of the pumping from the streams, against {100 * g['glover_nextgen_michigan']:.0f}% by
Glover's method with nextgen-michigan's settings.

**What's calibrated.** Streamflow at USGS 04119055 is calibrated (NextGen, KGE 0.87 in calibration and 0.81 in
validation). The groundwater model is screening: it is built from public data and not yet fitted to heads or base
flow.
- **Heads:** its steady heads match {hf['wells']} Wellogic drift wells completed since 2000 with a mean error of
  {hf['mean_error_m']:+.1f} m and an RMSE of {hf['rmse_m']:.1f} m (a {hf['observed_range_m']:.0f} m range).
- **Base flow:** its mean is within {max(abs(bfc['modflow6_vs_separated']['pbias']), abs(bfv['modflow6_vs_separated']['pbias'])):.0f}% of the
  base flow separated from the gage record. It is too steady, though: on days of below-median flow it is
  {bfc['modflow6_vs_separated']['low_flow_days_pbias']:.0f}-{bfv['modflow6_vs_separated']['low_flow_days_pbias']:.0f}% too high, and its daily NSE is near zero
  (groundwater/README.md).
- **Low flow:** the calibrated streamflow's own 7-day low flows are below the gage's. Depletion is taken off those flows,
  so the percentages below are shares of the model's low flow.
- **The campus:** an assumption [A]. Its size, cooling design and well site are not a proposal's.

## 1. The creek, with and without the well

![Hydrographs](figures/plaster-demo-hydrograph.png)

*Flow at the gage, June to November, in the median and the driest year of the run: as calibrated (utility water) and
with the well's depletion taken off.*

| Year (April-March) | 7-day low flow, utility water (m³/s) | with the well | change | days below Q90, utility | with the well |
|---|---|---|---|---|---|
{yrows}

Q90 is the flow the calibrated run exceeds 90% of the time from October 2019 on: {res['threshold_q90_m3s']:.3f} m³/s.
The gage's observed 7-day low flows in the same years were {', '.join(f"{float(v):.3f}" for _, v in sorted(obs7.items()))} m³/s.
The years are those in the calibrated run (October 2018 to December 2022). It doesn't include a drought of record such
as 2012. Its driest year, by the gage's observed 7-day low flow, is {dry}-{(dry + 1) % 100:02d}.

## 2. Where the drawdown and the depletion are

![Map](figures/plaster-demo-map.png)

*Drawdown at the water table on September 30 of the driest year, and the depletion of each reach from July to October.
The well is 500 m from the nearest stream cell [A].*

## 3. Days below the low-flow threshold

![Days below](figures/plaster-demo-days-below.png)

*Days below Q90 at the gage in each year. Utility water leaves the creek as calibrated.*

## 4. Glover's method against the coupled model

![Glover](figures/plaster-demo-glover.png)

*The same pumping series through MODFLOW 6 and through Glover and Balmer's solution, with nextgen-michigan's settings
and with MODFLOW 6's transmissivity and specific yield at the well.*

Glover's method assumes one straight stream that fully penetrates a uniform, infinite aquifer, with no streambed
resistance. MODFLOW 6's daily depletion spikes on flood days. On those days the river stands above the water table, and
the drawn-down aquifer takes more water from it than it would without the well. The solid line is a 7-day mean.

MODFLOW 6 has every reach, seepage to wetlands and small streams, streambed resistance, layered glacial deposits and
the basin's edges. With the same pumping, the share taken from the streams and seepage in the last year is:
- MODFLOW 6: {100 * g['modflow6']:.0f}%;
- Glover with nextgen-michigan's settings (T 500 m²/d, S 0.1, 500 m): {100 * g['glover_nextgen_michigan']:.0f}%;
- Glover with MODFLOW 6's settings at the well (T {res['glover']['modflow6_parameters']['transmissivity_m2_d']:.0f} m²/d,
  Sy 0.15, 500 m): {100 * g['glover_modflow6_parameters']:.0f}%.

Most of the gap between the two Glover lines is the aquifer: MODFLOW 6's drift near the well is less transmissive than
nextgen-michigan assumed. The rest of the gap to MODFLOW 6 is the structure Glover leaves out. Streambed resistance
slows the stream's share. The rest of the pumping still comes from aquifer storage, and from flow across the basin's
edges that would otherwise have reached the creek. nextgen-michigan's own Glover result for this case, a change of −0.026 m³/s in the mean 7-day low flow,
used hourly pumping and its own years. It is the right order but isn't the same measure as the table above.

## 5. The one or two assumptions that move the answer

| Variant | change in the driest year's 7-day low flow (L/s) | depletion share, last year | days below Q90, driest year |
|---|---|---|---|
{rows}

The streambed's conductance moves the answer most. A tighter streambed delays the stream's share, and more of the
pumping comes from storage and across the edges. Halving or doubling the glacial deposits' conductivity changes the
share by a few points either way, because the well is close to the creek in both cases. These are the parameters to fit first, against base flow at the gage.

## 6. The utility case: capacity, not the creek

On utility water, the campus's water is Lake Michigan water through Wyoming's plant and BGUA's single connection.
- **The campus's withdrawal:** {u['campus_withdrawal_mgd']['mean']:.2f} MGD on average, {u['campus_withdrawal_mgd']['peak_day']:.2f}
  MGD on its peak day.
- **BGUA's demand:** an estimated {u['bgua_average_mgd']:.1f} MGD on average and {u['bgua_max_day_mgd']:.1f} MGD on a maximum
  day [A]. With the campus's peak day added, that is {u['bgua_max_day_plus_campus_peak_mgd']:.1f} MGD, against an assumed
  contract maximum of {u['bgua_contract_mgd']:.0f} MGD [A].
- **Wyoming's plant:** the campus's peak day is {100 * min(u['campus_peak_share_of_wyoming_headroom']):.0f}-{100 * max(u['campus_peak_share_of_wyoming_headroom']):.0f}%
  of the plant's headroom over average use (90-120 MGD capacity, 40 MGD average). Wyoming's 2023 reliability study, as
  Georgetown Township summarized it, already projects expansion by 2034.
- **The return:** the campus returns {u['campus_return_to_sewer_mgd']['mean']:.2f} MGD to the sewer on average. It goes to
  the Clean Water Plant (24 MGD, current flow assumed 12-18 MGD) and on to the Grand River, outside Plaster Creek.
- **Great Lakes accounting:** the campus consumes {u['great_lakes_consumptive_use_mgd_mean']:.2f} MGD on average, which is
  Great Lakes consumptive use. The lake itself isn't modeled.

## Reproduce it

```bash
pip install "basinledger[users,nextgen]"
```

Then, from a checkout of github.com/northlinehydrology/basinledger:
1. Build NextGen's run with nextgen-michigan (Docker).
2. Run `examples/plaster-creek/groundwater/rerun_nextgen.py`, `fetch.py` and `prepare.py`.
3. Run `examples/plaster-creek/demo.py`.

The numbers on this page are in `examples/plaster-creek/demo-results.json`.
"""
    PAGE.write_text(text)


if __name__ == "__main__":
    sys.exit(main())
