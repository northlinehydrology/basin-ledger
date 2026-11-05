"""Download the public data the Michigan WWAT check adds to the cold-stream screen's, into Basin Ledger's cache.

    uv run --group gis python examples/michigan-cold-streams/fetch.py   # first: gages, basins, flows, tracker
    uv run --group gis python examples/michigan-wwat-check/fetch.py

Everything goes to ``{cache}/michigan-wwat-check/data``, nothing into git. A file already there is kept; delete it to
fetch it again. Sources, all public:

- **WWAT stream segments:** the Water Withdrawal Assessment Tool's valley segments with stream type, index flow
  (QE50, ft3/s), the fractions of index flow at the zone lines (A_LINE, B_LINE, C_LINE), the zone cutoffs and the
  groundwater model's inputs, from the state's Water_Withdrawal map service, layer 3 (service dated 12/22/2014).
- **Community supply wells:** EGLE's Wellogic Type I wells (community public water supplies), with system number
  (WSSN), status and pump capacity (gal/min), from EGLE's DwOpenData map service, layer 1.
- **NHDPlus COMIDs:** USGS NLDI, the flowline each gage is indexed to.
- **NextGen flowpath and nexus:** the v2.2 hydrofabric's hydrolocations table, read from a local copy
  (``$HYDROFABRIC``, default ``~/.ngiab/hydrofabric/v2.2/conus_nextgen.gpkg``) when there is one.
- **Index flows at gages:** ``index_flows_sir2008-5096.csv`` beside this file (Hamilton and others, 2008).
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "michigan-cold-streams"))

from fetch import _all_features, _json, _save
from fetch import data_dir as cold_dir

from basinledger.config import cache_dir

WWAT_STREAMS = "https://gisp.mcgi.state.mi.us/maps/rest/services/DEQ/Water_Withdrawal/MapServer/3/query"
TYPE1_WELLS = "https://gisagoegle.state.mi.us/arcgis/rest/services/EGLE/DwOpenData/MapServer/1/query"
NLDI_SITE = "https://api.water.usgs.gov/nldi/linked-data/nwissite/{site}"
HYDROFABRIC = Path(os.environ.get("HYDROFABRIC", Path.home() / ".ngiab/hydrofabric/v2.2/conus_nextgen.gpkg"))

WWAT_FIELDS = ("ADJ_SEGMNT,ADJ_NAME,TYPE,QE50,NET_ARMI2,SHORELINE,MEDIAN_T,EST_Kv_W,DPH_ZONED,EST_DPH_BR,BDRK_FLAG,"
               "BDRK_T,PCTDRIFT,PCTROCK,A_LINE,B_LINE,C_LINE,A_CUT_OFF,B_CUT_OFF,C_CUT_OFF,URL,VERSION")
WELL_FIELDS = "WELLID,OWNER_NAME,WSSN,WELL_TYPE,WEL_STATUS,PMP_CPCITY,WELL_DEPTH,AQ_TYPE,CONST_DATE"


def data_dir() -> Path:
    d = cache_dir() / "michigan-wwat-check" / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def comids(d: Path, sites: list[str]):
    out = d / "comids.json"
    done = json.loads(out.read_text()) if out.exists() else {}
    for s in sites:
        if s not in done:
            f = _json(NLDI_SITE.format(site=s))["features"]
            done[s] = f[0]["properties"].get("comid") if f else None
            _save(out, done)


def hydrofabric_ids(d: Path, sites: list[str]):
    out = d / "hydrofabric_ids.json"
    if out.exists():
        return
    if not HYDROFABRIC.exists():
        print(f"no hydrofabric at {HYDROFABRIC}; results won't carry NextGen ids")
        return
    con = sqlite3.connect(f"file:{HYDROFABRIC}?mode=ro", uri=True)
    rows = {}
    for s in sites:
        r = con.execute("select id, nex_id from hydrolocations where hl_reference = 'gages' and hl_link = ?",
                        (s.removeprefix("USGS-"),)).fetchone()
        if r:
            area = con.execute("select tot_drainage_areasqkm from network where id = ? limit 1", (r[0],)).fetchone()
            rows[s] = {"flowpath": r[0], "nexus": r[1], "hf_km2": area[0] if area else None}
    _save(out, {"hydrofabric": str(HYDROFABRIC.name), "version": "v2.2", "gages": rows})


def main() -> int:
    d = data_dir()
    sites = [g["site"] for g in json.loads((cold_dir() / "gages.json").read_text())]
    _all_features(WWAT_STREAMS, WWAT_FIELDS, d, "wwat_streams", 0.0002)
    _all_features(TYPE1_WELLS, WELL_FIELDS, d, "type1_wells")
    print("WWAT segments and community supply wells done", flush=True)
    comids(d, sites)
    hydrofabric_ids(d, sites)
    print(f"done: {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
