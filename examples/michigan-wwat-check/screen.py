"""Rank the cold-stream screen's basins by where a withdrawal that passes the WWAT is most likely to harm a cold stream.

    uv run --group gis python examples/michigan-wwat-check/screen.py

Reads the caches both fetch.py scripts fill and ``../michigan-cold-streams/screen.csv``. Writes ``candidates.csv``
(every basin, every measure, the five scores and the rule's result) and ``layer-check.json`` (what the WWAT layer's
values were checked against) beside this file. The README gives the question and the rule.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import shapely
from pyproj import Transformer
from scipy.special import erfc, erfcx
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

HERE = Path(__file__).parent
COLD = HERE.parent / "michigan-cold-streams"
sys.path.insert(0, str(COLD))

from fetch import data_dir as cold_dir

TO_M = Transformer.from_crs(4326, 5070, always_xy=True).transform  # CONUS Albers, metres
SQMI_KM2 = 2.589988
CFS_GPM = 448.831
CMS_CFS = 35.3147
FT_M = 0.3048

ELIGIBLE_COLD_SHARE = 0.25  # the rule: a quarter of the basin's WWAT length cold or cold-transitional
TOP = 0.75  # top quarter
STEP2_CANDIDATES, STEP2_CONTROLS = 5, 2
DRY_PERCENTILE = 10  # 1-in-10 dry summer
SUMMER = (7, 8, 9)
GAGE_SEARCH_M = 3000.0  # WWAT segments within this distance of the gage are matched by drainage area
AREA_MATCH = (2 / 3, 1.5)  # segment area over gage area, for a match

# the WWAT groundwater model at five years (Reeves and others, 2009)
STORAGE = 0.01
PUMP_DAYS = 1825.0
WELL_DISTANCE_FT = 2640.0  # [A] half a mile from the stream
DISTANCE_SENSITIVITY_FT = (1320.0, 5280.0)  # a quarter mile and a mile, reported beside it

COMMUNITY_WELL_KEEP = {"ACT", "UNK", None}  # Wellogic status: active, unknown or blank; plugged and inactive dropped
SCORES = ("median_summer", "delay", "unregistered_use", "municipal", "temperature")
COLD_TYPES = ("Cold stream", "Cold small river")
COLD_TRANS_TYPES = ("Cold transitional stream", "Cold transitional small river", "Cold transitional large river")
NO_LIMIT = 99999  # zone line value the layer uses on some segments


def wwat_dir() -> Path:
    return cold_dir().parent.parent / "michigan-wwat-check" / "data"


def _m(geom):
    return shapely.transform(geom, lambda c: np.column_stack(TO_M(c[:, 0], c[:, 1])))


def _rank(values) -> np.ndarray:
    """Percentile rank in [0, 1]; ties share a rank."""
    v = np.asarray(values, float)
    order = v.argsort().argsort().astype(float)
    out = np.empty_like(order)
    for x in np.unique(v):
        out[v == x] = order[v == x].mean()
    return out / max(len(v) - 1, 1)


def hunt_fraction(t_days, T, S, lam, d):
    """Streamflow depletion as a fraction of pumping, Hunt (1999); consistent units (here ft and days)."""
    v = np.sqrt(S * d * d / (4 * T * t_days))
    u = np.sqrt(lam * lam * t_days / (4 * S * T))
    return erfc(v) - np.exp(-v * v) * erfcx(u + v)


def kvw(url: str) -> float:
    """The streambed term (T/B') w the tool passes to its depletion model, ft2/d (Reeves and others, 2009, eq. 5)."""
    m = re.search(r"kvw=([\d.]+)", url or "")
    return float(m.group(1)) if m else np.nan


def segment_mismatch(seg, gage, km2: float, gage_name: str) -> float:
    """How poorly a WWAT segment fits a gage: drainage area first, then the river's name, then distance."""
    g, p = seg
    words = gage_name.split(" AT ")[0].split(" NEAR ")[0].split(" NR ")[0].split(" ABOVE ")[0].split()
    key = words[-2] if len(words) > 1 and words[-1] in ("RIVER", "CREEK", "R") else words[-1]
    same_name = key.rstrip(".").lower() in p["ADJ_NAME"].lower()
    return abs(np.log(p["NET_ARMI2"] * SQMI_KM2 / km2)) + (0.0 if same_name else 0.5) + g.distance(gage) / 1e4


def same_river(p: dict, gage_name: str) -> bool:
    return segment_mismatch((Point(0, 0), p), Point(0, 0), p["NET_ARMI2"] * SQMI_KM2, gage_name) < 0.5


def five_year_share(inside: list, distance_ft: float) -> float:
    """Length-weighted median, over a basin's WWAT segments, of the tool's depletion fraction at five years."""
    share, weight = [], []
    for km, p in inside:
        T, b, k = p["MEDIAN_T"], p["DPH_ZONED"], kvw(p["URL"])
        if T and b and np.isfinite(k) and T > 0 and b > 0:
            share.append(float(hunt_fraction(PUMP_DAYS, T, STORAGE, k / 10 / b, distance_ft)))
            weight.append(km)
    if not share:
        return np.nan
    order = np.argsort(share)
    cum = np.cumsum(np.array(weight)[order])
    return float(np.array(share)[order][np.searchsorted(cum, cum[-1] / 2)])


def summer_flows(path: Path) -> dict:
    """Index flow (median daily flow of the lowest summer month) and the 1-in-10 dry summer month mean, ft3/s."""
    days = defaultdict(list)  # (year, month) -> flows
    for r in csv.DictReader(open(path)):
        y, m = int(r["date"][:4]), int(r["date"][5:7])
        if m in SUMMER:
            days[(y, m)].append(float(r["flow"]) * CMS_CFS)
    if not days:
        return {"index_flow_cfs": np.nan, "index_month": "", "summer_years": 0, "dry_summer_cfs": np.nan}
    by_month = {m: [x for (y, mm), v in days.items() if mm == m for x in v] for m in SUMMER}
    medians = {m: float(np.median(v)) for m, v in by_month.items() if len(v)}
    lowest = {}
    for (y, m), v in days.items():
        if len(v) >= 25:
            lowest.setdefault(y, []).append(float(np.mean(v)))
    yearly = [min(v) for v in lowest.values() if len(v) == len(SUMMER)]
    month = min(medians, key=medians.get)
    return {"index_flow_cfs": medians[month], "index_month": month, "summer_years": len(yearly),
            "dry_summer_cfs": float(np.percentile(yearly, DRY_PERCENTILE)) if yearly else np.nan}


def main() -> int:
    cd, wd = cold_dir(), wwat_dir()
    cold = {r["site"]: r for r in csv.DictReader(open(COLD / "screen.csv"))}
    report = {r["station"]: r for r in csv.DictReader(l for l in open(HERE / "index_flows_sir2008-5096.csv")
                                                       if not l.startswith("#"))}
    comid = json.loads((wd / "comids.json").read_text())
    hf_file = wd / "hydrofabric_ids.json"
    hf = json.loads(hf_file.read_text())["gages"] if hf_file.exists() else {}

    segs = []
    for f in json.loads((wd / "wwat_streams.geojson").read_text())["features"]:
        p = f["properties"]
        if f["geometry"] and p["TYPE"] != "Coastline":
            segs.append((_m(shape(f["geometry"])), p))
    tree = STRtree([g for g, _ in segs])

    wells = []
    for f in json.loads((wd / "type1_wells.geojson").read_text())["features"]:
        p = f["properties"]
        if f["geometry"] and p["WEL_STATUS"] in COMMUNITY_WELL_KEEP:
            wells.append((_m(shape(f["geometry"])), p))
    well_tree = STRtree([g for g, _ in wells])

    rows = []
    for site, c in cold.items():
        poly = _m(shape(json.loads((cd / "basins" / f"{site}.geojson").read_text())["features"][0]["geometry"])
                  .buffer(0))
        gage = _m(Point(float(c["lon"]), float(c["lat"])))
        usgs_km2 = float(c["usgs_km2"])
        station = site.removeprefix("USGS-")
        row = {"site": site, "name": c["name"], "km2": float(c["km2"]), "usgs_km2": usgs_km2,
               "lon": c["lon"], "lat": c["lat"], "comid": comid.get(site),
               "nextgen_flowpath": hf.get(site, {}).get("flowpath", ""),
               "nextgen_nexus": hf.get(site, {}).get("nexus", ""),
               "cold_screen_score": float(c["score"])}

        # WWAT segments in the basin, by length inside it
        inside = [(segs[i][0].intersection(poly).length / 1000, segs[i][1]) for i in tree.query(poly)
                  if segs[i][0].intersects(poly)]
        inside = [(km, p) for km, p in inside if km > 0]
        total = sum(km for km, _ in inside)
        cold_km = sum(km for km, p in inside if p["TYPE"] in COLD_TYPES)
        trans_km = sum(km for km, p in inside if p["TYPE"] in COLD_TRANS_TYPES)
        no_limit_km = sum(km for km, p in inside if p["C_LINE"] == NO_LIMIT)
        bedrock_pass_km = sum(km for km, p in inside if p["BDRK_FLAG"] in (-1, 1))
        row |= {"wwat_km": total, "wwat_cold_km": cold_km, "wwat_cold_trans_km": trans_km,
                "wwat_cold_share": (cold_km + trans_km) / total if total else 0.0,
                "wwat_cold_trans_share": trans_km / total if total else 0.0,
                "wwat_no_limit_km": no_limit_km, "wwat_bedrock_pass_share": bedrock_pass_km / total if total else 0.0}

        # 1. median summer only: the Zone D boundary at the gage's segment against the gage's dry summer
        near = [segs[i] for i in tree.query(gage.buffer(GAGE_SEARCH_M)) if segs[i][0].distance(gage) <= GAGE_SEARCH_M]
        near = [(g, p) for g, p in near if p["NET_ARMI2"] and p["QE50"]
                and AREA_MATCH[0] <= p["NET_ARMI2"] * SQMI_KM2 / usgs_km2 <= AREA_MATCH[1]]
        best = min(near, key=lambda s: segment_mismatch(s, gage, usgs_km2, c["name"]), default=None)
        if best:
            p = best[1]
            scale = usgs_km2 / (p["NET_ARMI2"] * SQMI_KM2)
            row |= {"gage_segment": p["ADJ_SEGMNT"], "gage_segment_name": p["ADJ_NAME"].strip(),
                    "gage_segment_same_name": same_river(p, c["name"]),
                    "gage_segment_type": p["TYPE"], "gage_segment_km2": p["NET_ARMI2"] * SQMI_KM2,
                    "layer_index_flow_cfs": p["QE50"] * scale,
                    "zone_d_line": p["C_LINE"] if p["C_LINE"] != NO_LIMIT else np.nan,
                    "zone_d_cutoff_cfs": p["C_CUT_OFF"] / CFS_GPM * scale if p["C_LINE"] != NO_LIMIT else np.nan}
        else:
            row |= {"gage_segment": "", "gage_segment_name": "", "gage_segment_same_name": False,
                    "gage_segment_type": "", "gage_segment_km2": np.nan,
                    "layer_index_flow_cfs": np.nan, "zone_d_line": np.nan, "zone_d_cutoff_cfs": np.nan}
        row |= summer_flows(cd / "flow" / f"{site}.csv")
        rep = report.get(station)
        row["report_index_flow_cfs"] = float(rep["iq50_cfs"]) * usgs_km2 / (float(rep["drainage_sqmi"]) * SQMI_KM2) \
            if rep else np.nan
        row["dry_over_index"] = row["dry_summer_cfs"] / row["index_flow_cfs"]
        row["passing_share_of_dry"] = row["zone_d_cutoff_cfs"] / row["dry_summer_cfs"]

        # 2. delay: the tool's own depletion model at five years, half a mile from the stream
        for name, dist in (("five_year_share", WELL_DISTANCE_FT),
                           *((f"five_year_share_{x:.0f}ft", x) for x in DISTANCE_SENSITIVITY_FT)):
            row[name] = five_year_share(inside, dist)
        row["outwash_share"] = float(c["outwash_share"])

        # 3. registered and actual use
        row["irrigation_gw_m3d_km2"] = float(c["irrigation_gw_m3d_km2"])

        # 4. municipal exemption
        w_in = [wells[i][1] for i in well_tree.query(poly) if poly.contains(wells[i][0])]
        row["community_wells"] = len(w_in)
        row["community_systems"] = len({p["WSSN"] for p in w_in if p["WSSN"]})
        row["community_pump_gpm"] = float(sum(p["PMP_CPCITY"] or 0 for p in w_in))
        row["tracker_part"] = float(c["part_data_centers"])
        row["tracker_in"] = "; ".join(c[k] for k in ("existing_in", "projects_in", "actions_in", "proposals_in")
                                      if c[k])
        rows.append(row)

    eligible = [r for r in rows if r["wwat_cold_share"] >= ELIGIBLE_COLD_SHARE]
    for r in rows:
        r["eligible"] = r in eligible
    measures = {
        "median_summer": [r["passing_share_of_dry"] for r in eligible],
        "delay": [1 - r["five_year_share"] for r in eligible],
        "unregistered_use": [r["irrigation_gw_m3d_km2"] for r in eligible],
        "municipal": list(_rank([r["community_pump_gpm"] for r in eligible]) * 0.5
                          + np.array([r["tracker_part"] for r in eligible]) * 0.5),
        "temperature": [r["wwat_cold_trans_share"] for r in eligible],
    }
    for k, v in measures.items():
        v = np.asarray(v, float)
        have = np.isfinite(v)
        ranks = np.full(len(v), np.nan)
        ranks[have] = _rank(v[have])  # a missing measure stays unranked
        for r, x in zip(eligible, ranks):
            r[f"score_{k}"] = float(x)
    for r in eligible:
        s = [r[f"score_{k}"] for k in SCORES if np.isfinite(r[f"score_{k}"])]
        r["scores_present"] = len(s)
        r["top_quarter"] = sum(x >= TOP for x in s)
        r["mean_rank"] = float(np.mean(s))
        r["candidate"] = r["top_quarter"] >= 2 and len(s) == len(SCORES)
    eligible.sort(key=lambda r: (-r["candidate"], -r["top_quarter"], -r["mean_rank"]))
    cands = [r for r in eligible if r["candidate"]]
    for i, r in enumerate(cands):
        r["candidate_rank"] = i + 1
    controls = sorted((r for r in eligible if r["scores_present"] == len(SCORES)),
                      key=lambda r: r["mean_rank"])[:STEP2_CONTROLS]
    for r in rows:
        r["step2"] = ("candidate" if r in cands[:STEP2_CANDIDATES] else "control" if r in controls else "")
    out = eligible + sorted((r for r in rows if not r["eligible"]), key=lambda r: -r["wwat_cold_share"])

    fields = list(dict.fromkeys(k for r in out for k in r))
    with open(HERE / "candidates.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in out:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})

    layer_check(rows, segs, wd)
    print(f"{len(rows)} basins, {len(eligible)} eligible, {len(cands)} candidates")
    for r in eligible[:15]:
        print(f"{r.get('candidate_rank', '-'):>2} {r['site']} {r['name'][:34]:34} top {r['top_quarter']} "
              f"mean {r['mean_rank']:.2f} | " + " ".join(f"{r[f'score_{k}']:.2f}" for k in SCORES) + f" {r['step2']}")
    for r in controls:
        print(f"control {r['site']} {r['name'][:34]} mean {r['mean_rank']:.2f}")
    return 0


def layer_check(rows, segs, wd):
    """What the WWAT layer's index flows and cutoffs were checked against."""
    props = [p for _, p in segs]
    ok = [p for p in props if p["QE50"] and p["C_LINE"] not in (None, NO_LIMIT) and not p["SHORELINE"]]
    factor = np.array([p["C_CUT_OFF"] / (p["QE50"] * p["C_LINE"] * CFS_GPM) for p in ok])
    shore = [p["C_CUT_OFF"] for p in props if p["SHORELINE"]]
    lines = defaultdict(set)
    for p in props:
        lines[p["TYPE"]].add((p["A_LINE"], p["B_LINE"], p["C_LINE"]))

    def ratios(a, b):
        x = np.array([r[a] / r[b] for r in rows if r["gage_segment_same_name"] and np.isfinite(r[a])
                      and np.isfinite(r[b]) and r[b] > 0])
        return {"n": len(x), "median": float(np.median(x)), "p10": float(np.percentile(x, 10)),
                "p90": float(np.percentile(x, 90))} if len(x) else {"n": 0}

    eligible = [r for r in rows if r["eligible"]]
    sensitivity = [f"five_year_share_{x:.0f}ft" for x in DISTANCE_SENSITIVITY_FT]
    base = _rank([r["five_year_share"] for r in eligible])
    out = {
        "service": "https://gisp.mcgi.state.mi.us/maps/rest/services/DEQ/Water_Withdrawal/MapServer/3",
        "service_description": "C11491. 12/22/2014",
        "segments": len(props), "version_field": sorted({str(p["VERSION"]) for p in props}),
        "cutoff_over_line_times_index_flow_gpm": {"segments": len(ok), "median": float(np.median(factor)),
                                                   "share_within_1pct_of_half": float(np.mean(np.abs(factor - 0.5)
                                                                                              < 0.005))},
        "shoreline_segments_cutoff_gpm": sorted({round(x) for x in shore if x is not None}),
        "no_limit_segments": {t: sum(1 for p in props if p["TYPE"] == t and p["C_LINE"] == NO_LIMIT)
                              for t in sorted({p["TYPE"] for p in props})},
        "zone_lines_by_type": {t: sorted(v - {(NO_LIMIT, NO_LIMIT, NO_LIMIT)}) for t, v in sorted(lines.items())},
        "index_flow_at_gages": {
            "layer_over_report": ratios("layer_index_flow_cfs", "report_index_flow_cfs"),
            "layer_over_gage_1997_2025": ratios("layer_index_flow_cfs", "index_flow_cfs"),
            "report_over_gage_1997_2025": ratios("report_index_flow_cfs", "index_flow_cfs"),
        },
        "gages_matched_to_a_segment": sum(1 for r in rows if r["gage_segment"] != ""),
        "gages_matched_same_name": sum(1 for r in rows if r["gage_segment_same_name"]),
        "five_year_share_eligible": {k: np.percentile([r[k] for r in eligible], [0, 50, 100]).tolist()
                                     for k in ("five_year_share", *sensitivity)},
        "delay_rank_correlation_with_distance": {k: float(np.corrcoef(base, _rank([r[k] for r in eligible]))[0, 1])
                                                 for k in sensitivity},
    }
    (HERE / "layer-check.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    sys.exit(main())
