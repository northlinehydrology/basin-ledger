"""Screen Michigan's gaged basins for a first cold-stream study basin, from the data fetch.py caches.

    uv run --group gis python examples/michigan-cold-streams/screen.py

Writes ``screen.csv`` (every gage basin, every measure) and ``screen.json`` (the same, plus statewide stream length by
thermal class and ecoregion) beside this file. The README explains the measures and the score.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString, Point, shape
import shapely
from shapely.ops import unary_union
from shapely.strtree import STRtree

from basinledger.calibration import eckhardt, recession_ratios
from fetch import data_dir

HERE = Path(__file__).parent
TO_M = Transformer.from_crs(4326, 5070, always_xy=True).transform  # CONUS Albers, metres
MGD_M3D = 3785.411784  # 1 Mgal/d in m3/d
NEAR_KM = 15.0  # "near" a basin, for tracker records
AREA_RATIO = (0.8, 1.25)  # NLDI basin area over USGS drainage area; outside this the basin isn't scored

# weights of the score's parts; the README gives the reasons
WEIGHTS = {"cold": 2.0, "groundwater": 1.0, "temperature_data": 1.0, "aquifer": 1.0, "siting": 1.0,
           "irrigation": 0.5, "data_centers": 0.5}


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


def flow_measures(path: Path) -> dict:
    rows = list(csv.DictReader(open(path)))
    q = np.array([float(r["flow"]) for r in rows])
    q = q[np.isfinite(q)]
    if len(q) < 3650:
        return {"flow_years": len(q) / 365.25, "bfi": np.nan, "q90_q50": np.nan, "q90_cms": np.nan}
    alpha = float(np.percentile(recession_ratios(q), 90))
    b = eckhardt(q, alpha)
    return {"flow_years": len(q) / 365.25, "bfi": float(b.sum() / q.sum()),
            "q90_q50": float(np.percentile(q, 10) / np.percentile(q, 50)), "q90_cms": float(np.percentile(q, 10))}


def lines_from_overpass(path: Path) -> list[LineString]:
    out = []
    for e in json.loads(path.read_text())["elements"]:
        if e.get("type") == "way" and len(e.get("geometry", [])) > 1:
            out.append(_m(LineString([(p["lon"], p["lat"]) for p in e["geometry"]])))
    return out


def points_from_overpass(path: Path) -> list[Point]:
    out = []
    for e in json.loads(path.read_text())["elements"]:
        b = e.get("bounds")
        if b:
            out.append(_m(Point((b["minlon"] + b["maxlon"]) / 2, (b["minlat"] + b["maxlat"]) / 2)))
        elif "lat" in e:
            out.append(_m(Point(e["lon"], e["lat"])))
    return out


def county_irrigation(path: Path) -> dict[str, float]:
    """Groundwater withdrawals for irrigation, Mgal/d, by 5-digit county FIPS (USGS 2015, IR-WGWFr)."""
    text = path.read_text(encoding="latin-1").splitlines()
    head = next(i for i, line in enumerate(text) if line.startswith("STATE,"))
    rows = csv.DictReader(io.StringIO("\n".join(text[head:])))
    return {r["FIPS"].zfill(5): float(r["IR-WGWFr"] or 0) for r in rows if r["STATE"] == "MI"}


def main() -> int:
    d = data_dir()
    gages = [g for g in json.loads((d / "gages.json").read_text()) if (d / "basins" / f"{g['site']}.geojson").exists()]
    lengths = json.loads((d / "stream_lengths.json").read_text())
    temp_ts = json.loads((d / "usgs_temperature.json").read_text())
    tracker = json.loads((d / "tracker.json").read_text())
    wqp = [(_m(shape(f["geometry"])), f["properties"]) for f in json.loads((d / "wqp_temperature.geojson").read_text())["features"]]
    wqp_tree = STRtree([p for p, _ in wqp])

    quat = [(_m(shape(f["geometry"]).buffer(0)), f["properties"]["Label"] or "")
            for f in json.loads((d / "quaternary.geojson").read_text())["features"] if f["geometry"]]
    quat_tree = STRtree([g for g, _ in quat])
    counties = [(_m(shape(f["geometry"]).buffer(0)), str(f["properties"]["GEOID"]).zfill(5))
                for f in json.loads((d / "counties.geojson").read_text())["features"] if f["geometry"]]
    irr = county_irrigation(d / "usco2015.csv")
    eco = [(_m(shape(f["geometry"]).buffer(0)), f["properties"])
           for f in json.loads((d / "ecoregions.geojson").read_text())["features"] if f["geometry"]]
    eco_tree = STRtree([g for g, _ in eco])
    hv = lines_from_overpass(d / "hv_lines.json")
    hv_tree = STRtree(hv)
    subs = points_from_overpass(d / "hv_substations.json")
    subs_tree = STRtree(subs)

    records = {k: [(_m(Point(r["lon"], r["lat"])), r) for r in tracker.get(k, []) if r.get("lon") is not None]
               for k in ("existing", "projects", "actions", "proposals", "moratoria")}

    temp_years: dict[str, float] = {}
    for t in temp_ts:
        if t.get("begin") and t.get("end"):
            span = (np.datetime64(t["end"][:10]) - np.datetime64(t["begin"][:10])).astype(int) / 365.25
            temp_years[t["monitoring_location_id"]] = max(temp_years.get(t["monitoring_location_id"], 0.0), span)

    basins = {g["site"]: _m(shape(json.loads((d / "basins" / f"{g['site']}.geojson").read_text())["features"][0]
                                   ["geometry"]).buffer(0)) for g in gages}
    rows = []
    for g in gages:
        site, poly = g["site"], basins[g["site"]]
        area = poly.area / 1e6
        gage_pt = _m(Point(g["lon"], g["lat"]))
        row = {"site": site, "name": g["name"], "km2": round(area, 1), "usgs_km2": round(g["km2"], 1),
               "lon": g["lon"], "lat": g["lat"]}
        row |= flow_measures(d / "flow" / f"{site}.csv")

        v = {k: (val or 0) / 1000 for k, val in lengths[site]["vsec_m"].items()}
        total = sum(v.values())
        row |= {"stream_km": total, "cold_km": v.get("Cold", 0.0), "cold_trans_km": v.get("Cold transitional", 0.0),
                "cold_share": (v.get("Cold", 0.0) + v.get("Cold transitional", 0.0)) / total if total else 0.0}
        t = {k: (val or 0) / 1000 for k, val in lengths[site]["trout_m"].items()}
        row["trout_km"] = sum(val for k, val in t.items() if float(k) == 1.0)

        row["temp_years_at_gage"] = temp_years.get(site, 0.0)
        idx = [i for i in wqp_tree.query(poly) if poly.contains(wqp[i][0])]
        row["wqp_temp_sites"] = len(idx)
        row["wqp_temp_results"] = sum(int(wqp[i][1].get("resultCount") or 0) for i in idx)

        def share(items, tree, keep) -> float:
            hit = [i for i in tree.query(poly) if keep(items[i][1])]
            return unary_union([items[i][0] for i in hit]).intersection(poly).area / poly.area if hit else 0.0

        row["outwash_share"] = share(quat, quat_tree, lambda lab: "outwash" in lab.lower())
        row["coarse_share"] = share(quat, quat_tree, lambda lab: any(
            w in lab.lower() for w in ("outwash", "coarse-textured", "lacustrine sand", "dune sand")))
        row["irrigation_gw_m3d"] = sum(irr.get(fips, 0.0) * MGD_M3D * c.intersection(poly).area / c.area
                                       for c, fips in counties if c.intersects(poly))
        row["irrigation_gw_m3d_km2"] = row["irrigation_gw_m3d"] / area

        lines_in = [hv[i] for i in hv_tree.query(poly) if hv[i].intersects(poly)]
        row["hv_km_in_basin"] = sum(line.intersection(poly).length for line in lines_in) / 1000
        near = hv_tree.query_nearest(poly, return_distance=True)
        row["hv_distance_km"] = float(near[1][0]) / 1000 if len(near[1]) else np.nan
        row["hv_substations"] = sum(1 for i in subs_tree.query(poly) if poly.contains(subs[i]))

        near_poly = poly.buffer(NEAR_KM * 1000)
        for k, pts in records.items():
            row[f"{k}_in"] = "; ".join(r.get("where") or r.get("name") or "" for p, r in pts if poly.contains(p))
            row[f"{k}_near"] = sum(1 for p, _ in pts if near_poly.contains(p) and not poly.contains(p))
        e = [eco[i][1] for i in eco_tree.query(gage_pt) if eco[i][0].contains(gage_pt)]
        row["ecoregion"] = (e[0].get("EcoRegionName") or "") if e else ""
        row["ecoregion_number"] = (e[0].get("EcoRegionNumber") or "").strip() if e else ""
        row["peninsula"] = (e[0].get("Peninsula") or "") if e else ""
        row["nested_in"] = "; ".join(s for s, b in basins.items() if s != site and b.contains(gage_pt)
                                     and b.area > poly.area)
        rows.append(row)

    mismatched = [r for r in rows if not AREA_RATIO[0] <= r["km2"] / r["usgs_km2"] <= AREA_RATIO[1]]
    rows = [r for r in rows if r not in mismatched]
    score_parts(rows)
    rows.sort(key=lambda r: -r["score"])

    fields = list(rows[0])
    with open(HERE / "screen.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
    statewide = json.loads((d / "vsec_by_ecoregion.json").read_text())
    (HERE / "screen.json").write_text(json.dumps(
        {"weights": WEIGHTS, "basins": rows, "area_mismatch": [{k: r[k] for k in ("site", "name", "km2", "usgs_km2")}
                                                               for r in mismatched], "ecoregions": statewide},
        indent=1, default=float))
    print(f"{len(rows)} basins scored; area mismatch, not scored: "
          + ", ".join(f"{r['site']} ({r['km2']:.0f} vs {r['usgs_km2']:.0f} km2)" for r in mismatched))
    for r in rows[:15]:
        print(f"{r['score']:.2f} {r['site']} {r['name'][:40]:40} {r['km2']:7.0f} cold {r['cold_share']:.2f} "
              f"bfi {r['bfi']:.2f} trout {r['trout_km']:5.0f} T {r['temp_years_at_gage']:4.1f} "
              f"wqp {r['wqp_temp_sites']:3d} ow {r['outwash_share']:.2f} hv {r['hv_km_in_basin']:5.1f} "
              f"irr {r['irrigation_gw_m3d_km2']:6.1f} {r['ecoregion'][:25]}")
    return 0


def score_parts(rows: list[dict]):
    """Each part in [0, 1]; the score is their weighted sum. See the README."""
    cold = _rank([r["cold_share"] for r in rows]) * 0.5 + _rank([r["trout_km"] / r["km2"] for r in rows]) * 0.5
    gw = _rank([np.nan_to_num(r["bfi"]) for r in rows]) * 0.5 + _rank([np.nan_to_num(r["q90_q50"]) for r in rows]) * 0.5
    temp = [min(1.0, r["temp_years_at_gage"] / 10) * 0.6 + min(1.0, r["wqp_temp_results"] / 500) * 0.4 for r in rows]
    aquifer = _rank([r["outwash_share"] for r in rows]) * 0.6 + _rank([r["coarse_share"] for r in rows]) * 0.4
    siting = [1.0 if r["hv_km_in_basin"] > 0 and r["hv_substations"] > 0 else 0.7 if r["hv_km_in_basin"] > 0
              else 0.4 if r["hv_distance_km"] <= 5 else 0.0 for r in rows]
    irrigation = _rank([r["irrigation_gw_m3d_km2"] for r in rows])
    dc = [1.0 if (r["existing_in"] or r["projects_in"] or r["actions_in"] or r["proposals_in"])
          else 0.6 if (r["existing_near"] or r["projects_near"] or r["actions_near"] or r["proposals_near"])
          else 0.3 if r["moratoria_in"] else 0.0 for r in rows]
    parts = {"cold": cold, "groundwater": gw, "temperature_data": temp, "aquifer": aquifer, "siting": siting,
             "irrigation": irrigation, "data_centers": dc}
    for i, r in enumerate(rows):
        for k, v in parts.items():
            r[f"part_{k}"] = float(v[i])
        r["score"] = sum(WEIGHTS[k] * r[f"part_{k}"] for k in parts) / sum(WEIGHTS.values())


if __name__ == "__main__":
    sys.exit(main())
