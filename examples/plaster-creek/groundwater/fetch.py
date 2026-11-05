"""Download the public data the Plaster Creek groundwater model is built from, into Basin Ledger's cache.

    uv run --group gis python examples/plaster-creek/groundwater/fetch.py

Everything goes to ``{cache}/plaster-creek/data`` (``$BASINLEDGER_CACHE``, default ``~/.cache/basinledger``), about
40 MB, nothing into git. A file already there is kept; delete it to fetch it again. Sources, all public:

- **Land surface:** USGS 3DEP, 1 arc-second (about 30 m), through the National Map's ImageServer, in EPSG:5070.
- **Glacial drift thickness and bedrock topography:** Soller, D.R., and Garrity, C.P., 2018, Quaternary sediment
  thickness and bedrock topography of the glaciated United States east of the Rocky Mountains. USGS Scientific
  Investigations Map 3392, https://doi.org/10.3133/sim3392 (500 m grids).
- **Surficial (Quaternary) geology:** Farrand, W.R., and Bell, D.L., 1982, Quaternary geology of southern Michigan
  (QG-01, 1:500,000), from EGLE's GrmdOpenData map service, layer 8.
- **Bedrock geology:** Milstein, R.L., 1987, Bedrock geology of southern Michigan (BG-01, 1:500,000), the same service,
  layer 0.
- **Water wells:** EGLE's Wellogic records (DwOpenData map service, layer 3): location, ground elevation, depth,
  static water level at completion, aquifer code, screen depths, pump capacity.
- **Streamflow:** USGS daily values at 04119055, from the USGS Water Data API.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from basinledger.calibration import usgs_daily
from basinledger.config import cache_dir

# the model area plus a margin: EPSG:5070 (m) for rasters, geographic for the vector services
BOX_5070 = (827400.0, 2242800.0, 856500.0, 2274600.0)
BOX_4326 = (-85.77, 42.78, -85.45, 43.04)

DEM = ("https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage?"
       "bbox={0},{1},{2},{3}&bboxSR=5070&imageSR=5070&size={4},{5}&format=tiff&pixelType=F32"
       "&interpolation=RSP_BilinearInterpolation&f=image")
SIM3392 = "https://pubs.usgs.gov/sim/3392/sim3392_spatialdata.zip"
GRMD = "https://gisagoegle.state.mi.us/arcgis/rest/services/EGLE/GrmdOpenData/MapServer/{layer}/query"
WELLS = "https://gisagoegle.state.mi.us/arcgis/rest/services/EGLE/DwOpenData/MapServer/3/query"
WELL_FIELDS = ("WELLID,LATITUDE,LONGITUDE,ELEVATION,ELEV_DEM,WELL_DEPTH,SWL,SWL_FLAG,CONST_DATE,AQ_TYPE,AQ_CODE,"
               "SCREEN_FRM,SCREEN_TO,ROCK_TOP,WELL_TYPE,WEL_STATUS,PMP_CPCITY,WWAT_ID")


def data_dir() -> Path:
    d = cache_dir() / "plaster-creek" / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get(url: str, dest: Path, timeout: int = 180):
    req = urllib.request.Request(url, headers={"User-Agent": "basinledger (github.com/northlinehydrology/basin-ledger)"})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
        f.write(r.read())


def dem(d: Path):
    out = d / "dem30_5070.tif"
    if not out.exists():
        x0, y0, x1, y1 = BOX_5070
        _get(DEM.format(x0, y0, x1, y1, int((x1 - x0) / 30), int((y1 - y0) / 30)), out)
    with open(out, "rb") as f:
        if f.read(2) not in (b"II", b"MM"):
            out.unlink()
            raise RuntimeError("3DEP returned something other than a GeoTIFF")
    return out


def drift(d: Path):
    z = d / "sim3392_spatialdata.zip"
    if not z.exists():
        _get(SIM3392, z, timeout=600)
    folder = d / "sim3392"
    if not folder.exists():
        with zipfile.ZipFile(z) as f:
            f.extractall(folder)
    return folder


def features(url: str, dest: Path, fields: str = "*", where: str = "1=1"):
    """All features in the box from an ArcGIS map service layer, as one GeoJSON file in EPSG:5070."""
    if dest.exists():
        return dest
    feats, offset = [], 0
    while True:
        q = urllib.parse.urlencode({
            "geometry": ",".join(map(str, BOX_4326)), "geometryType": "esriGeometryEnvelope", "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects", "where": where, "outFields": fields, "outSR": 5070,
            "orderByFields": "OBJECTID", "resultOffset": offset, "resultRecordCount": 1000, "f": "geojson"})
        req = urllib.request.Request(f"{url}?{q}", headers={"User-Agent": "basinledger"})
        with urllib.request.urlopen(req, timeout=180) as r:
            page = json.load(r)
        got = page.get("features", [])
        feats += got
        if not got or not page.get("properties", {}).get("exceededTransferLimit", page.get("exceededTransferLimit")):
            if len(got) < 1000:
                break
        offset += len(got)
    dest.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    return dest


def main() -> int:
    d = data_dir()
    print("3DEP", dem(d))
    print("SIM 3392", drift(d))
    print("Quaternary geology", features(GRMD.format(layer=8), d / "quaternary_geology.geojson"))
    print("bedrock geology", features(GRMD.format(layer=0), d / "bedrock_geology.geojson"))
    wells = features(WELLS, d / "wellogic.geojson", WELL_FIELDS)
    print("Wellogic", wells, len(json.loads(wells.read_text())["features"]), "wells")
    q = usgs_daily("04119055", "2018-10-01", "2022-12-31", cache=d / "usgs_04119055_daily.csv")
    print("USGS 04119055", len(q), "days,", sum(1 for r in q if r[2] == "Approved"), "approved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
