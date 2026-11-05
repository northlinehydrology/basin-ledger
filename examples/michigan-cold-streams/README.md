# Michigan cold-stream screen

## Summary

A script that scores Michigan's gaged basins (USGS gages with 20 or more years of daily flow, 100 to 1,500 km²) as
places to study a groundwater-sourced water user next to a cold, groundwater-fed stream. It uses public data only and
runs no models.

## What it shows

`screen.csv` lists every basin with its measures and score. `screen.json` adds statewide stream length by thermal
class and ecoregion. `screen-map.png` maps the scores with Water Ledger's tracker records.

## What it measures

- Cold and cold-transitional stream share (Michigan's valley segment classification) and designated trout stream
  length.
- Base flow index and Q90/Q50 from daily flow.
- Water temperature records at the gage and in the Water Quality Portal.
- Outwash and coarse surficial geology.
- Transmission lines and substations of 138 kV and up.
- Groundwater irrigation, from county totals.
- Data centers, projects, inquiries and moratoria from Water Ledger's public tracker.

The weights are in `screen.py` and are judgment [A]. `fetch.py` lists every source.

## Limitations

- A different weighting reorders the list.
- Irrigation is county-level, and tracker records sit at their place's centroid.
- Only gaged basins are scored, and two with NLDI areas far from USGS's are left out.
- Lakes, existing high-capacity wells and temperature loggers outside the Water Quality Portal aren't checked.

## Run

```bash
uv sync --group gis --group examples
uv run --group gis python examples/michigan-cold-streams/fetch.py      # public data to the cache (~45 MB)
uv run --group gis python examples/michigan-cold-streams/screen.py     # screen.csv, screen.json
uv run --group gis --group examples python examples/michigan-cold-streams/figure.py   # screen-map.png
```
