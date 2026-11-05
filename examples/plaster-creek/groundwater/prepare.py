"""Build the Plaster Creek groundwater model's inputs from the public data fetch.py downloaded.

    uv run --group gis python examples/plaster-creek/groundwater/prepare.py

Writes:
- ``examples/plaster-creek/maps/catchment_cells.csv``: recharge areas, catchment to cell (in git, small);
- ``examples/plaster-creek/maps/river_cells.csv``: river cells by flowpath (in git);
- ``{cache}/plaster-creek/groundwater.npz``: the grid, layers, properties, boundaries and steady-state starting
  heads that ``model.py`` writes a MODFLOW 6 simulation from.

Every choice is listed in ``CHOICES`` with its source or as an assumption [A]; the README prints them. Units are
meters and days. Feet from the sources are converted (1 ft = 0.3048 m).
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from shapely import STRtree, points

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import geometry as G  # noqa: E402

from basinledger.config import cache_dir  # noqa: E402

FT = 0.3048
CELL = 250.0
BUFFER = 2000.0
CAMPUS_CATCHMENT = "cat-652066"   # nextgen-michigan's gaines-wells scenario
CAMPUS_WELL_DISTANCE = 500.0      # m from the stream, the same scenario's assumption [A]

# Glacial hydraulic conductivity by Quaternary map unit (Farrand and Bell 1982), from the calibrated values of the
# Lake Michigan Basin model (Feinstein, Hunt and Reeves 2010, SIR 2010-5109, App. 3 Table 3-1 and App. 5 Table 5-2):
# calibrated Kh in ft/d and Kv/Kh. The match of map units to the report's categories is an assumption [A].
GLACIAL = {
    "Fine-textured glacial till": ("clayey till", 5.2, 0.009),
    "End moraines of fine-textured till": ("clayey till", 5.2, 0.009),
    "Medium-textured glacial till": ("loamy till", 11.1, 0.026),
    "End moraines of medium-textured till": ("loamy till", 11.1, 0.026),
    "Coarse-textured glacial till": ("sandy till", 20.3, 0.032),
    "Glacial outwash sand and gravel and postglacial alluvium": ("medium and coarse stratified", 144.0, 0.027),
    "Water": ("medium and coarse stratified", 144.0, 0.027),
}
# deeper drift: the calibrated geometric mean for glacial deposits in the southern Lower Peninsula (Table 9-1) [A]
DEEP_DRIFT = (12.4, 0.03)
# bedrock Kh and Kv (ft/d) by subcrop formation (Milstein 1987), from SIR 2010-5109 App. 4 and Tables 5-1, 5-2
BEDROCK = {
    "MICHIGAN FORMATION": (0.1, 1.2e-4),        # MICH, confining unit, Kh fixed
    "BAYPORT LIMESTONE": (1.2, 5.5e-3),         # PEN2 range 0.3-4.6 (Kv 4.4e-4 to 7e-2): geometric middle [A]
    "SAGINAW FORMATION": (10.0, 0.1),           # PEN1 range 6-20; Kv/Kh 0.01 [A]
    "MARSHALL FORMATION": (27.6, 0.208),        # MSHL southern zone [A: the zone for Kent County isn't confirmed]
    "RED BEDS": (0.5, 5e-4),                    # JURA
}
CHOICES = {
    "grid": f"{CELL:.0f} m cells in EPSG:5070 (the hydrofabric's projection); active where a cell's center is "
            f"within the 16 catchments plus a {BUFFER / 1000:.0f} km buffer [A]",
    "top": "USGS 3DEP 1 arc-second land surface, averaged to each cell",
    "layers": "3 layers, following SIR 2010-5109's scheme of glacial layers by depth (Table 3B): layer 1 the upper "
              "30.5 m (100 ft) of drift; layer 2 the rest of the drift; layer 3 the upper 30 m of bedrock [A]. "
              "Each layer at least 1 m thick [A]",
    "drift": "Quaternary sediment thickness from USGS SIM 3392 (Soller and Garrity 2018, 500 m, from 1:1,000,000 "
             "isopachs at 0, 50, 100, 200, 400 ft): regional only",
    "glacial K": "by Farrand and Bell (1982) map unit at each cell's center, calibrated values from SIR 2010-5109 "
                 "(Table 5-2); layer 2 the southern Lower Peninsula geometric mean (Table 9-1) [A]",
    "bedrock K": "by Milstein (1987) subcrop formation, from SIR 2010-5109 (App. 4, Tables 5-1 and 5-2) [A where "
                 "noted in BEDROCK]",
    "storage": "specific yield 0.15 and specific storage 1e-5 per m in every layer [A]; transmissivity held at "
               "its value for the full layer thickness (ICELLTYPE 0) [A]",
    "recharge": "CFE's daily percolation (SOIL_TO_GW_FLUX) by catchment, from the calibrated NextGen run; buffer "
                "cells take their nearest catchment's rate [A]",
    "rivers": "RIV in every cell a hydrofabric flowpath crosses: streambed at the cell's lowest 30 m DEM value; "
              "bottom 1 m below it; conductance 0.3 m/d (bed K) x channel top width (hydrofabric TopWdth) x length "
              "in the cell / 1 m [A]; stage = streambed + the day's t-route depth",
    "seepage": "DRN in every other layer-1 cell at land surface, conductance = layer 1 Kv x cell area / 1 m [A], so "
               "the water table can't rise above the land surface and discharges there (wetlands, unmapped streams)",
    "edges": "GHB at the outer ring of active cells in layers 1 and 2, head from the water table interpolated from "
             "Wellogic drift wells (inverse distance, the 12 nearest) [A], conductance = Kh x thickness x 250 m "
             "/ 250 m [A]",
    "start": "steady state under the run's mean recharge and mean river depth",
    "campus well": "one well in cat-652066, about 500 m from the nearest river cell (nextgen-michigan's Glover case) "
                   "and nearest the catchment's center, screened in layer 2 [A]",
    "existing pumping": "not included: EGLE's facility-level water use has no locations, and Wellogic's "
                        "high-capacity wells have capacities, not withdrawals [A]",
}


def _project(src_path: Path, transform, shape, resampling, scale=1.0, nodata=None):
    with rasterio.open(src_path) as src:
        out = np.full(shape, np.nan, dtype="float64")
        reproject(rasterio.band(src, 1), out, src_transform=src.transform, src_crs=src.crs,
                  src_nodata=src.nodata if nodata is None else nodata, dst_transform=transform,
                  dst_crs="EPSG:5070", dst_nodata=np.nan, resampling=resampling)
    return out * scale


def _cell_values(geojson: Path, key: str, xc: np.ndarray, yc: np.ndarray) -> np.ndarray:
    from shapely.geometry import shape
    feats = json.loads(geojson.read_text())["features"]
    polys = [shape(f["geometry"]) for f in feats]
    tree = STRtree(polys)
    pts = points(xc.ravel(), yc.ravel())
    idx_pt, idx_poly = tree.query(pts, predicate="within")
    out = np.full(xc.size, "", dtype=object)
    out[idx_pt] = [feats[i]["properties"][key] for i in idx_poly]
    return out.reshape(xc.shape)


def wells(data: Path) -> list[dict]:
    """Wellogic drift wells usable as water-table observations: drift aquifer, a static level, no QC flag, ground
    elevation within 10 ft of the DEM value (a location check) [A]. Elevation and depths in meters."""
    out = []
    for f in json.loads((data / "wellogic.geojson").read_text())["features"]:
        p = f["properties"]
        if p.get("AQ_CODE") != "D" or not p.get("SWL") or p["SWL"] <= 0 or p.get("SWL_FLAG"):
            continue
        if p.get("ELEVATION") is None or p.get("ELEV_DEM") is None or abs(p["ELEVATION"] - p["ELEV_DEM"]) > 10:
            continue
        x, y = f["geometry"]["coordinates"]
        out.append({"id": p["WELLID"], "x": x, "y": y, "date": (p.get("CONST_DATE") or "")[:10],
                    "ground": p["ELEVATION"] * FT, "head": (p["ELEVATION"] - p["SWL"]) * FT,
                    "screen_mid": ((p.get("SCREEN_FRM") or p.get("WELL_DEPTH") or 0) +
                                   (p.get("SCREEN_TO") or p.get("WELL_DEPTH") or 0)) / 2 * FT})
    return out


def idw(xs, ys, vs, x, y, k=12):
    from scipy.spatial import cKDTree
    d, i = cKDTree(np.c_[xs, ys]).query(np.c_[x, y], k=k)
    w = 1.0 / np.maximum(d, 1.0) ** 2
    return (w * np.asarray(vs)[i]).sum(axis=1) / w.sum(axis=1)


def prepare(run: Path, data: Path, maps: Path, out: Path) -> dict:
    gpkg = next((run / "config").glob("*.gpkg"))
    cats, fps = G.catchments(gpkg), G.flowpaths(gpkg)
    outline = G.basin_outline(cats)
    x0, y0, nrow, ncol = G.extent(outline, BUFFER, CELL)
    transform = from_origin(x0, y0 + nrow * CELL, CELL, CELL)  # rows run north to south, as MODFLOW's do
    xc = x0 + (np.arange(ncol) + 0.5) * CELL
    yc = y0 + nrow * CELL - (np.arange(nrow) + 0.5) * CELL
    XC, YC = np.meshgrid(xc, yc)

    top = _project(data / "dem30_5070.tif", transform, (nrow, ncol), Resampling.average)
    bed_dem = _project(data / "dem30_5070.tif", transform, (nrow, ncol), Resampling.min)
    sim = next(p for p in (data / "sim3392").rglob("*driftthickness.img") if "__MACOSX" not in p.parts)
    drift = _project(sim, transform, (nrow, ncol), Resampling.bilinear, FT)
    drift = np.where(np.isfinite(drift), drift, np.nanmedian(drift))
    drift = np.maximum(drift, 2.0)
    t1 = np.clip(np.minimum(30.48, drift - 1.0), 1.0, None)
    bot1 = top - t1
    bot2 = np.minimum(top - drift, bot1 - 1.0)
    bot3 = bot2 - 30.0

    # active cells: centers within the buffered basin; the rest of the rectangle is inactive (IDOMAIN 0)
    zone = outline.buffer(BUFFER)
    from shapely import contains_xy
    active = contains_xy(zone, XC, YC)

    unit = _cell_values(data / "quaternary_geology.geojson", "Label", XC, YC)
    rock = _cell_values(data / "bedrock_geology.geojson", "FormationName", XC, YC)
    kh1 = np.array([GLACIAL.get(u, (None, DEEP_DRIFT[0], DEEP_DRIFT[1]))[1] for u in unit.ravel()]).reshape(unit.shape)
    vk1 = np.array([GLACIAL.get(u, (None, DEEP_DRIFT[0], DEEP_DRIFT[1]))[2] for u in unit.ravel()]).reshape(unit.shape)
    kh3 = np.array([BEDROCK.get(r, BEDROCK["MICHIGAN FORMATION"])[0] for r in rock.ravel()]).reshape(rock.shape)
    kv3 = np.array([BEDROCK.get(r, BEDROCK["MICHIGAN FORMATION"])[1] for r in rock.ravel()]).reshape(rock.shape)
    k = np.stack([kh1, np.full_like(kh1, DEEP_DRIFT[0]), kh3]) * FT
    k33 = np.stack([kh1 * vk1, np.full_like(kh1, DEEP_DRIFT[0] * DEEP_DRIFT[1]), kv3]) * FT

    # maps: recharge (catchments, buffer cells to their nearest catchment) and rivers
    import flopy
    mg = flopy.discretization.StructuredGrid(delr=np.full(ncol, CELL), delc=np.full(nrow, CELL), xoff=x0, yoff=y0,
                                             nlay=1, top=top, botm=bot1[None])
    gi = G.grid_intersect(mg)
    cc = G.catchment_cells(gi, cats)
    covered = np.zeros((nrow, ncol))
    for _, r, c, a in cc:
        covered[r, c] += a
    names = list(cats)
    tree = STRtree([cats[n] for n in names])
    rest = []
    for r in range(nrow):
        for c in range(ncol):
            left = CELL * CELL - covered[r, c]
            if active[r, c] and left > 1.0:
                n = names[tree.nearest(points(XC[r, c], YC[r, c]))]
                rest.append((n, r, c, left))
    maps.mkdir(parents=True, exist_ok=True)
    cc = [row for row in cc if active[row[1], row[2]]]
    G.write_map(maps / "catchment_cells.csv", cc + rest, "area_m2")
    fc = G.flowpath_cells(gi, fps)
    G.write_map(maps / "river_cells.csv", fc, "length_m")

    import sqlite3
    with sqlite3.connect(gpkg) as db:
        width = dict(db.execute('select id, TopWdth from "flowpath-attributes"').fetchall())
    riv = {}
    for fid, r, c, length in fc:
        e = riv.setdefault((r, c), [fid, 0.0, 0.0])
        e[1] += 0.3 * width[fid] * length / 1.0  # conductance, m2/d
        e[2] = max(e[2], length)
    riv_cells = np.array([[r, c] for (r, c) in riv], dtype=int)
    riv_bed = np.array([bed_dem[r, c] for r, c in riv_cells])
    riv_cond = np.array([v[1] for v in riv.values()])
    riv_obj = np.array([v[0] for v in riv.values()])

    # the water table from Wellogic drift wells, for the edges
    w = wells(data)
    pad = np.pad(active, 1, constant_values=False)
    inner = pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:]
    edge = active & ~inner
    wt = idw([v["x"] for v in w], [v["y"] for v in w], [v["head"] for v in w], XC[edge], YC[edge])
    ghb_head = np.full((nrow, ncol), np.nan)
    ghb_head[edge] = np.minimum(wt, top[edge] - 0.1)

    # the campus's well, as nextgen-michigan's Glover case places it: in cat-652066, 500 m from the stream [A];
    # here the cell nearest the catchment's center whose distance to the nearest river cell is closest to 500 m,
    # screened in layer 2 (the lower drift) [A]
    site = cats[CAMPUS_CATCHMENT]
    rxy = np.c_[xc[riv_cells[:, 1]], yc[riv_cells[:, 0]]]
    best, campus = None, None
    for r in range(nrow):
        for c in range(ncol):
            if not active[r, c] or not site.contains(points(XC[r, c], YC[r, c])):
                continue
            d = np.min(np.hypot(rxy[:, 0] - XC[r, c], rxy[:, 1] - YC[r, c]))
            score = (abs(d - CAMPUS_WELL_DISTANCE) // CELL, np.hypot(XC[r, c] - site.centroid.x, YC[r, c] - site.centroid.y))
            if best is None or score < best:
                best, campus = score, (1, r, c, float(d))

    arrays = dict(x0=x0, y0=y0, nrow=nrow, ncol=ncol, cell=CELL, top=top, botm=np.stack([bot1, bot2, bot3]),
                  k=k, k33=k33, riv_cells=riv_cells, riv_bed=riv_bed, riv_cond=riv_cond, riv_obj=riv_obj,
                  ghb_head=ghb_head, active=active, unit=unit.astype(str), rock=rock.astype(str), drift=drift,
                  campus_well=np.array(campus[:3]), campus_well_distance=campus[3])
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, **arrays)
    return arrays


def steady_heads(npz: Path, run: Path, maps: Path):
    """Steady-state heads under the run's mean recharge (catchment area weighted) and mean river depth, saved into
    the npz as the transient model's starting heads."""
    from basinledger.coupling.nextgen import NgenReplay, DEPTH, RECHARGE
    import model as M

    m = NgenReplay()
    m.initialize(str(run))
    rch = m._daily[RECHARGE].mean(axis=1)               # m s-1 per catchment
    depth = dict(zip(m.ids, m._daily[DEPTH].mean(axis=1)))
    rate = dict(zip(m.catchments, rch * 86400.0))        # m d-1
    cell_rch = np.zeros((int(np.load(npz)["nrow"]), int(np.load(npz)["ncol"])))
    area = np.zeros_like(cell_rch)
    with open(maps / "catchment_cells.csv", newline="") as f:
        for r in csv.DictReader(f):
            cell_rch[int(r["row"]), int(r["col"])] += rate[r["object"]] * float(r["area_m2"])
            area[int(r["row"]), int(r["col"])] += float(r["area_m2"])
    cell_rch /= np.maximum(area, 1.0)
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        M.build(ws, 1, None, steady=True, recharge=cell_rch, depth=depth, npz=npz)
        from basinledger.coupling.modflow6 import find_library
        exe = find_library().with_name("mf6")  # get-modflow puts mf6 beside libmf6
        r = subprocess.run([str(exe)], cwd=ws, capture_output=True, text=True)
        if "Normal termination" not in r.stdout:
            raise RuntimeError("steady-state MODFLOW 6 run failed:\n" + r.stdout[-2000:])
        import flopy
        h = flopy.utils.HeadFile(ws / "gwf.hds").get_data()
    a = dict(np.load(npz, allow_pickle=True))
    h = np.where(np.broadcast_to(a["active"], h.shape), h, np.broadcast_to(a["top"], h.shape))  # inactive: 1e30
    a["strt"] = h
    np.savez_compressed(npz, **a)
    return h


def main() -> int:
    run = cache_dir() / "plaster-creek" / "nextgen-recharge"
    data = cache_dir() / "plaster-creek" / "data"
    maps = HERE.parent / "maps"
    npz = cache_dir() / "plaster-creek" / "groundwater.npz"
    a = prepare(run, data, maps, npz)
    print(f"grid {a['nrow']} x {a['ncol']} cells of {CELL:.0f} m, 3 layers; {len(a['riv_cells'])} river cells")
    h = steady_heads(npz, run, maps)
    print(f"steady state: heads {h.min():.1f} to {h.max():.1f} m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
