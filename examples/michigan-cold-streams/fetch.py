"""Download the public data the Michigan cold-stream screen uses, into Basin Ledger's cache.

    uv run --group gis python examples/michigan-cold-streams/fetch.py

Everything goes to ``{cache}/michigan-cold-streams/data`` (``$BASINLEDGER_CACHE``, default ``~/.cache/basinledger``),
nothing into git. A file already there is kept; delete it to fetch it again. Sources, all public:

- **Streamgages:** USGS Water Data API, monitoring locations and time series (daily discharge 00060, daily water
  temperature 00010) in Michigan; daily discharge for the selected gages.
- **Gage basins:** USGS NLDI, the basin upstream of each gage.
- **Stream thermal classes:** Michigan's valley segment ecological classification (VSEC), the reach network and
  thermal classes the Water Withdrawal Assessment Tool uses, from the University of Michigan's Institute for Fisheries
  Research map service (MIFI_CAR, layer 6). Summed per basin on the server.
- **Designated trout streams:** EGLE's MiEnviro map service, layer 32 (Fisheries Order 210). Summed per basin on the
  server.
- **Surficial (Quaternary) geology:** Farrand and Bell (1982), EGLE's GrmdOpenData map service, layer 8.
- **Counties:** Census TIGERweb (to spread county irrigation over basins by area).
- **Ecoregions:** Albert (1995), Regional landscape ecosystems of Michigan, Minnesota and Wisconsin, from EGLE's
  MiEnviro map service, layer 6; stream length by thermal class is summed per ecoregion on the server.
- **High-voltage lines and substations:** OpenStreetMap (power=line or substation, 138 kV and up), through Overpass.
  OSM data is ODbL.
- **Irrigation:** Dieter and others (2018), Estimated use of water in the United States, county-level data for 2015
  (USGS data release, https://doi.org/10.5066/F7TB15V5).
- **Data centers, proposals, inquiries and moratoria:** Water Ledger's public Michigan tracker
  (https://waterledger.org/mi/data/tracker.json), places at their Census centroids.
- **Stream temperature sampling:** Water Quality Portal stations with stream temperature results since 2010.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from basinledger.calibration import usgs_daily
from basinledger.config import cache_dir

UA = {"User-Agent": "basinledger (github.com/northlinehydrology/basinledger)"}
WDAPI = "https://api.waterdata.usgs.gov/ogcapi/v0/collections"
NLDI = "https://api.water.usgs.gov/nldi/linked-data/nwissite/{site}/basin?simplified=true&splitCatchment=false"
VSEC = "https://arcgis-server.lsa.umich.edu/arcgis/rest/services/MIFI_CAR/MapServer/6/query"
TROUT = "https://gisagoegle.state.mi.us/arcgis/rest/services/EGLE/MiEnviro/MapServer/32/query"
QUATERNARY = "https://gisagoegle.state.mi.us/arcgis/rest/services/EGLE/GrmdOpenData/MapServer/8/query"
COUNTIES = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query"
ECOREGIONS = "https://gisagoegle.state.mi.us/arcgis/rest/services/EGLE/MiEnviro/MapServer/6/query"
OVERPASS = "https://overpass-api.de/api/interpreter"
WATER_USE = "https://www.sciencebase.gov/catalog/file/get/5af3311be4b0da30c1b245d8?name=usco2015v2.0.csv"
TRACKER = "https://waterledger.org/mi/data/tracker.json"
WQP = ("https://www.waterqualitydata.us/data/Station/search?statecode=US%3A26&siteType=Stream"
       "&characteristicName=Temperature%2C%20water&startDateLo=01-01-2010&mimeType=geojson")
MI_BOX = "-90.5,41.6,-82.1,48.4"

# the screen's gages: active, 20 or more years of daily flow, basins of 100 to 1,500 km2
MIN_KM2, MAX_KM2, MIN_YEARS, ACTIVE_SINCE = 100.0, 1500.0, 20, "2024-01-01"
SQMI_KM2 = 2.589988
FLOW_YEARS = ("1996-10-01", "2025-09-30")  # water years 1997-2025


def data_dir() -> Path:
    d = cache_dir() / "michigan-cold-streams" / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read(url: str, data: bytes | None = None, timeout: int = 300) -> bytes:
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, data=data, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(5 * (attempt + 1))


def _json(url: str, data: dict | None = None, timeout: int = 300):
    body = urllib.parse.urlencode(data).encode() if data else None
    return json.loads(_read(url, body, timeout))


def _save(path: Path, obj):
    path.write_text(json.dumps(obj))


def gages(d: Path) -> list[dict]:
    out = d / "gages.json"
    if out.exists():
        return json.loads(out.read_text())
    ml = _json(f"{WDAPI}/monitoring-locations/items?f=json&state_code=26&site_type_code=ST&limit=10000"
               "&properties=monitoring_location_name,drainage_area")
    loc = {f["id"]: f for f in ml["features"]}
    ts = _json(f"{WDAPI}/time-series-metadata/items?f=json&bbox={MI_BOX}&parameter_code=00060"
               "&computation_period_identifier=Daily&limit=10000&skipGeometry=true"
               "&properties=monitoring_location_id,begin,end")
    span: dict[str, tuple[str, str]] = {}
    for f in ts["features"]:
        p = f["properties"]
        if p["begin"] and p["end"]:
            i, b, e = p["monitoring_location_id"], p["begin"][:10], p["end"][:10]
            span[i] = (min(span[i][0], b), max(span[i][1], e)) if i in span else (b, e)
    rows = []
    for i, (b, e) in span.items():
        if i not in loc or loc[i]["properties"].get("drainage_area") is None:
            continue
        km2 = float(loc[i]["properties"]["drainage_area"]) * SQMI_KM2
        if MIN_KM2 <= km2 <= MAX_KM2 and e >= ACTIVE_SINCE and int(e[:4]) - int(b[:4]) >= MIN_YEARS:
            lon, lat = loc[i]["geometry"]["coordinates"][:2]
            rows.append({"site": i, "name": loc[i]["properties"]["monitoring_location_name"], "km2": km2,
                         "begin": b, "end": e, "lon": lon, "lat": lat})
    rows.sort(key=lambda r: r["site"])
    _save(out, rows)
    return rows


def temperature_series(d: Path):
    out = d / "usgs_temperature.json"
    if out.exists():
        return
    ts = _json(f"{WDAPI}/time-series-metadata/items?f=json&bbox={MI_BOX}&parameter_code=00010"
               "&computation_period_identifier=Daily&limit=10000&skipGeometry=true"
               "&properties=monitoring_location_id,begin,end")
    _save(out, [f["properties"] for f in ts["features"]])


def basins(d: Path, sites: list[dict]) -> list[dict]:
    """The gages NLDI can delineate a basin for; the others are listed in basins/missing.json."""
    import urllib.error

    bd = d / "basins"
    bd.mkdir(exist_ok=True)
    missing_file = bd / "missing.json"
    missing = set(json.loads(missing_file.read_text())) if missing_file.exists() else set()
    for g in sites:
        out = bd / f"{g['site']}.geojson"
        if out.exists() or g["site"] in missing:
            continue
        try:
            out.write_bytes(_read_once(NLDI.format(site=g["site"])))
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            missing.add(g["site"])
            _save(missing_file, sorted(missing))
    return [g for g in sites if g["site"] not in missing]


def _read_once(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def flows(d: Path, sites: list[dict]):
    for g in sites:
        usgs_daily(g["site"].removeprefix("USGS-"), *FLOW_YEARS, cache=d / "flow" / f"{g['site']}.csv")


def _esri_polygon(geojson: dict) -> str:
    geom = geojson["features"][0]["geometry"]
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    rings = [[[round(x, 5), round(y, 5)] for x, y in ring[:: max(1, len(ring) // 400)] + [ring[0]]]
             for poly in polys for ring in poly[:1]]
    return json.dumps({"rings": rings, "spatialReference": {"wkid": 4326}})


def _sum_lengths(url: str, geometry: str, field: str, group: str) -> dict[str, float]:
    stats = json.dumps([{"statisticType": "sum", "onStatisticField": field, "outStatisticFieldName": "total"}])
    r = _json(url, {"where": "1=1", "geometry": geometry, "geometryType": "esriGeometryPolygon", "inSR": "4326",
                    "spatialRel": "esriSpatialRelIntersects", "outStatistics": stats,
                    "groupByFieldsForStatistics": group, "f": "json"})
    if "error" in r:
        raise RuntimeError(r["error"])
    return {str(f["attributes"][group]): f["attributes"]["total"] for f in r.get("features", [])}


def streams(d: Path, sites: list[dict]):
    """Stream length (m) by VSEC thermal class and by trout designation, for segments touching each basin."""
    out = d / "stream_lengths.json"
    done = json.loads(out.read_text()) if out.exists() else {}
    for g in sites:
        if g["site"] in done:
            continue
        geom = _esri_polygon(json.loads((d / "basins" / f"{g['site']}.geojson").read_text()))
        done[g["site"]] = {"vsec_m": _sum_lengths(VSEC, geom, "Length_M", "TEMP_"),
                           "trout_m": _sum_lengths(TROUT, geom, "Shape.STLength()", "Designated")}
        _save(out, done)


def statewide_classes(d: Path):
    """Statewide stream length (m) by VSEC thermal class and 8-digit HUC basin."""
    out = d / "vsec_statewide.json"
    if out.exists():
        return
    stats = json.dumps([{"statisticType": "sum", "onStatisticField": "Length_M", "outStatisticFieldName": "total"}])
    r = _json(VSEC, {"where": "1=1", "outStatistics": stats, "groupByFieldsForStatistics": "HUC,HUC_BASIN,TEMP_",
                     "f": "json"})
    _save(out, [f["attributes"] for f in r["features"]])


def _all_features(url: str, fields: str, d: Path, name: str, offset_deg: float = 0.0005, where: str = "1=1"):
    out = d / f"{name}.geojson"
    if out.exists():
        return
    feats, offset = [], 0
    while True:
        page = _json(url, {"where": where, "outFields": fields, "outSR": "4326", "f": "geojson",
                           "resultOffset": str(offset), "resultRecordCount": "1000",
                           "maxAllowableOffset": str(offset_deg)})
        feats += page["features"]
        if len(page["features"]) < 1000:
            break
        offset += 1000
    _save(out, {"type": "FeatureCollection", "features": feats})


def ecoregion_classes(d: Path):
    """Statewide stream length (m) by VSEC thermal class within each ecoregion (segments touching it)."""
    out = d / "vsec_by_ecoregion.json"
    done = json.loads(out.read_text()) if out.exists() else {}
    eco = json.loads((d / "ecoregions.geojson").read_text())["features"]
    groups: dict[str, list] = {}
    for f in eco:
        key = (f["properties"].get("EcoRegionNumber") or "").strip()
        if key and f["geometry"]:
            groups.setdefault(key, []).append(f)
    for key, feats in groups.items():
        if key in done:
            continue
        rings = []
        for f in feats:
            g = f["geometry"]
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            rings += [[[round(x, 4), round(y, 4)] for x, y in poly[0]] for poly in polys if len(poly[0]) > 20]
        if not rings:
            continue
        geom = json.dumps({"rings": rings, "spatialReference": {"wkid": 4326}})
        done[key] = {"name": feats[0]["properties"]["EcoRegionName"], "peninsula": feats[0]["properties"]["Peninsula"],
                     "vsec_m": _sum_lengths(VSEC, geom, "Length_M", "TEMP_")}
        _save(out, done)


def power(d: Path):
    for name, what in (("hv_lines", "way[\"power\"=\"line\"]"), ("hv_substations", "nwr[\"power\"=\"substation\"]")):
        out = d / f"{name}.json"
        if out.exists():
            continue
        q = (f'[out:json][timeout:300];area["ISO3166-2"="US-MI"]->.a;'
             f'({what}["voltage"~"^(138|230|345|765)"](area.a););out center geom;')
        out.write_bytes(_read(OVERPASS, urllib.parse.urlencode({"data": q}).encode(), timeout=400))


def small_files(d: Path):
    for name, url in (("usco2015.csv", WATER_USE), ("tracker.json", TRACKER), ("wqp_temperature.geojson", WQP)):
        out = d / name
        if not out.exists():
            out.write_bytes(_read(url, timeout=600))


def main() -> int:
    d = data_dir()
    sites = gages(d)
    print(f"{len(sites)} gages", flush=True)
    temperature_series(d)
    sites = basins(d, sites)
    print(f"basins done: {len(sites)}", flush=True)
    streams(d, sites)
    statewide_classes(d)
    print("stream lengths done")
    _all_features(QUATERNARY, "Label", d, "quaternary")
    _all_features(COUNTIES, "GEOID,NAME", d, "counties", 0.002, where="STATE='26'")
    _all_features(ECOREGIONS, "EcoRegionNumber,EcoRegionName,Peninsula", d, "ecoregions", 0.002)
    ecoregion_classes(d)
    print("geology, counties and ecoregions done")
    power(d)
    small_files(d)
    flows(d, sites)
    print(f"done: {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
