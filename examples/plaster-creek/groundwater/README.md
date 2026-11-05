# Plaster Creek groundwater model (screening)

A MODFLOW 6 model under the calibrated NextGen surface, built from public data. Its status is screening: it isn't
fitted yet. Streamflow at the gage stays the only calibrated part of the example.

Its recharge, CFE's percolation from NextGen, is an interim forcing. In Basin Ledger, recharge comes from SWAT+, which
carries water quality. NextGen stays as a comparison. The calibration order is SWAT+ alone, then MODFLOW 6 under
SWAT+'s recharge, then both linked (`../PROGRESS.md`, `docs/design.md`). The SWAT+ project for Plaster Creek doesn't
exist yet. The demo that uses it is in
`docs/plaster-creek-demo.md`. Progress and how to resume are in `../PROGRESS.md`.

## Build

```bash
uv sync --group gis --group examples
uv run python examples/plaster-creek/groundwater/rerun_nextgen.py         # NextGen with CFE's percolation (Docker)
uv run --group gis python examples/plaster-creek/groundwater/fetch.py     # public data to the cache (~72 MB)
uv run --group gis python -W ignore examples/plaster-creek/groundwater/prepare.py   # arrays, maps, steady heads
uv run --group gis --group examples python -W ignore examples/plaster-creek/demo.py # runs and the demo
uv run --group gis --group examples python -W ignore examples/plaster-creek/groundwater/checks.py
```

## The model

| | |
|---|---|
| Grid | 250 m cells in EPSG:5070, 104 × 72; active where a cell's center is within the 16 catchments plus 2 km (4,405 cells a layer, 275 km²) [A] |
| Top | USGS 3DEP 1 arc-second, averaged to each cell |
| Layer 1 | the upper 30.5 m (100 ft) of glacial drift, following SIR 2010-5109's split by depth |
| Layer 2 | the rest of the drift (thickness from USGS SIM 3392, 500 m, regional) |
| Layer 3 | the upper 30 m of bedrock [A] |
| Glacial K | by mapped unit (Farrand and Bell 1982): fine-textured till 5.2 ft/d (Kv/Kh 0.009), medium-textured till 11.1 (0.026), outwash and alluvium 144 (0.027), from SIR 2010-5109's calibrated values; layer 2 at the southern Lower Peninsula mean, 12.4 ft/d [A] |
| Bedrock K | by subcrop (Milstein 1987): Michigan Formation 0.1 ft/d, Bayport Limestone 1.2 [A], Marshall Sandstone 27.6 [A], from SIR 2010-5109 |
| Storage | Sy 0.15, Ss 1e-5 m⁻¹ [A]; transmissivity held at the full layer's (ICELLTYPE 0) [A] |
| Recharge | CFE's daily percolation per catchment from the calibrated NextGen run (225 mm a year over the basin); buffer cells take their nearest catchment's rate [A] |
| Rivers | every cell a hydrofabric flowpath crosses (358): streambed at the cell's lowest 30 m DEM value, conductance 0.3 m/d × the hydrofabric's top width × length / 1 m [A], stage = streambed + the day's t-route depth |
| Seepage | drains at land surface in every other layer-1 cell, conductance Kv × area / 1 m [A] |
| Edges | general heads on the outer ring of active cells, from Wellogic water levels by inverse distance [A] |
| Start | steady state under mean recharge and mean river depth |
| Existing pumping | not included: EGLE's facility-level water use has no locations [A] |

`prepare.py` holds every choice with its source (`CHOICES`), and the README of the example cites the data.

## Fit (`results.json`)

- **Heads:** steady-state heads against Wellogic drift wells' static water levels at completion. Wells must have a
  level, no QC flag, and a ground elevation within 10 ft of the DEM.
  - Completed since 2000: 55 wells, mean error +1.9 m, RMSE 7.9 m, over a 66 m range (RMSE/range 0.12).
  - All dates: 740 wells, mean error +3.3 m, RMSE 6.9 m.

  Single readings at completion over decades scatter by several meters by themselves.
- **Base flow:** gross groundwater discharge to river and seepage cells in the basin, against an Eckhardt separation
  of the approved daily record (alpha 0.978, the recession constant at the 90th percentile; BFImax 0.8 [A]).
  - The mean is within 4%: −4% in calibration, +4% in validation.
  - It is too steady. Daily NSE is about 0, and on days of below-median flow it is 76–93% too high. Storage and
    transmissivity damp the recharge pulses that CFE passes in.
  - CFE's own groundwater outflow fits the separation better (NSE 0.65–0.67). It was calibrated to the gage, and
    MODFLOW 6 wasn't.
- **Balance:** the budget's largest daily imbalance is 2.4e-8 of the day's gross flow. The ledger closed every day
  (recharge sent = received, well pumping = the campus's withdrawal).

## What's next

1. Fit specific yield, the glacial K and the streambed conductance to base flow at the gage and to the heads, with
   PEST++ IES.
2. Add the existing high-capacity wells, once their volumes can be placed.
3. Extend NextGen's forcing to 2011, to include the 2012 drought.

Until then the groundwater is screening, and results from it are labeled so.
