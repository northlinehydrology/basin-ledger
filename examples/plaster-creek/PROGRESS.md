# Plaster Creek groundwater and demo: progress

Kept current at each commit so the work can be resumed from this file alone. Last updated: November 5, 2026 (calibration plan).

## Done (on main, pushed)

- **NextGen rerun** with CFE's percolation (`SOIL_TO_GW_FLUX`) and groundwater outflow in its outputs:
  `groundwater/rerun_nextgen.py`. Q_OUT is identical to the calibrated baseline.
- **Public data fetch:** `groundwater/fetch.py`. Sources: 3DEP, USGS SIM 3392, Michigan Quaternary and bedrock
  geology, Wellogic, USGS daily values.
- **Model build:** `groundwater/geometry.py`, `prepare.py`, `model.py`, and the maps in `maps/`.
  - 250 m grid, 3 layers, 4,405 active cells per layer.
  - K from SIR 2010-5109, by mapped unit.
  - Rivers on the flowpaths, seepage cells, edge heads from Wellogic.
  - A steady-state start.
- **Configs:** `groundwater.toml` (campus on utility water) and `groundwater-wells.toml` (campus on its own well).
- **Engine pieces:**
  - NextGen recharge per catchment;
  - `[rivers]`: stage from t-route's depth, base flow per flowpath;
  - `builder_args`;
  - the generic reported user (`basinledger.generic`);
  - Glover and Balmer (`basinledger.analytic`);
  - USGS daily values and the Eckhardt filter (`basinledger.calibration`).
- **Tests:** `tests/test_plaster_groundwater.py`, the analytic and generic-user tests. The coupled month is marked
  slow and skips without the cache.
- **Decided direction for utility water:** `docs/ideas.md`, section 8.

## Also done (November 4, late)

- **Checks:** `groundwater/checks.py` and `groundwater/results.json`.
  - Heads: RMSE 7.9 m (55 wells since 2000).
  - Base flow: mean within 4%, but too steady.
  - Daily budget closure: 2.4e-8.
- **Demo:** `demo.py`, `demo-results.json`, the figures in `docs/figures/plaster-demo-*.png`, and the page
  `docs/plaster-creek-demo.md`.
  - The campus on its own well lowers the gage's 7-day low flow by 43 L/s (27%) in the driest year (2021-22) and by
    42 L/s (20%) in the median year.
  - MODFLOW 6 takes 63% of the pumping from the streams in the last year. Glover gives 89% with nextgen-michigan's
    settings and 78% with MODFLOW 6's.
  - The streambed's conductance moves the answer most: a 7-day low flow change of −24 to −52 L/s.
  - The utility case: BGUA's maximum day plus the campus's peak day is 9.9 MGD, against an assumed 10 MGD contract
    [A].
- **Write-ups:** `groundwater/README.md` (methods and fit), the screening entry in `calibration/record.toml`, the
  example README, and `docs/design.md`.

## Calibration plan (Andrew, November 5, 2026)

In Basin Ledger the recharge comes from SWAT+, because SWAT+ carries water quality, which is Basin Ledger's point.
NextGen stays as a comparison only: the calibrated check against the National Water Model's frame. The models are
calibrated separately first, then linked.

1. **SWAT+ alone,** against streamflow at USGS 04119055: the land, soil and channel parameters. Its own aquifer
   parameters (alpha_bf, delay) are a stand-in that the coupled run replaces.
2. **MODFLOW 6 alone,** driven one-way by SWAT+ recharge, against Wellogic heads and the Eckhardt base flow:
   streambed conductance, specific yield and storage, and the K multipliers.
3. **Linked both ways,** with MODFLOW 6 supplying base flow (SWAT+'s aquifer passing recharge through). A joint
   PEST++ IES pass on the parameters the feedback touches, against streamflow (low flows), heads and base flow
   together.

**The blocker:** there is no SWAT+ project for Plaster Creek on the hydrofabric yet. That is the hydrofabric
builder (`basinledger.hydrofabric`, stubbed).
- **Until then, stage 2 can be prepared against NextGen's recharge** (CFE's percolation), flagged as an interim
  forcing. The parameter step for MODFLOW 6 (`calibration.apply_parameters`), the PEST++ files, and the observation
  set (Wellogic heads, Eckhardt base flow) don't depend on where the recharge comes from.
- **swatplus-bmi 0.2.0** is planned in the swatplus-bmi session: channel depth for river stage, and recharge per HRU
  for mapping by area.

## The SWAT+ project Andrew is building (November 5, 2026)

What lets it plug straight into stages 1 to 3:

- **SWAT+ 62.0.1**, the version swatplus-bmi supports, as a TxtInOut folder.
- **The hydrofabric v2.2 catchments above USGS 04119055:** the 16 `cat-` divides in
  `~/.cache/basinledger/plaster-creek/nextgen-recharge/config/plaster-cal_subset.gpkg`.
  - Subbasins and routing units, one per catchment.
  - One aquifer per catchment.
  - Channels on the `wb-` flowpaths, with the same network.
  - A lookup from SWAT+ object name to hydrofabric id (a CSV is enough), so maps and results key to the ids.
- **Period:** at least October 2018 to December 2022, the NextGen run's period. Better from 2010, with a warm-up, so
  2012 is included.
- **Weather:** say which source. AORC is the plan; NWM v3 retrospective matches NextGen.
- **Outlet:** the channel at the gage, so stage 1 fits streamflow there.
- **Anything already set** (land use, soils, HRU thresholds, management) is noted, so the record can say so.
- **Where to put it:** anywhere local. Basin Ledger copies the project into each run folder. If it's public data
  only, it can live under `examples/plaster-creek/swatplus/` or be fetched by script.

Once it's here: check that it runs through swatplus-bmi, build the aquifer-to-cell map from the lookup, and start
stage 1.

## swatplus-bmi 0.2.0 (November 5, 2026)

- **Done (4d5e63c):** the two-way exchange uses 0.2.0's `channel_water__groundwater_volume_exchange_rate` when it's
  installed, and enters what SWAT+ actually exchanged. River stage can come from the surface model's channel depth
  (`[rivers] stage = "surface_depth"`). The point-source path stays for 0.1.x.
- **Tested** against a 0.2.0 build in a scratch folder: the exchange and restart tests pass, and the totals match the
  point-source path to the cubic meter.
- **When 0.2.0 is on PyPI:**
  1. require `swatplus-bmi>=0.2` and run `uv lock`;
  2. rebuild SWAT+ (`uv run swatplus-bmi build --jobs 2`);
  3. add `[rivers] stage = "surface_depth"` to `examples/synthetic/two_way.toml`;
  4. note it in `docs/design.md`'s two-way section.

## Next

1. The SWAT+ project for Plaster Creek on the hydrofabric (the builder), then stage 1.
2. Stage 2, prepared now on NextGen recharge as an interim forcing:
   - `calibration.apply_parameters` for MODFLOW 6 (K and streambed multipliers, Sy, Ss, through the builder's
     arguments);
   - the observation set;
   - PEST++ IES files.
3. Extend the forcing to 2011, for the 2012 drought. For NextGen that means NGIAB's preprocessor (an hour's
   download), then `rerun_nextgen.py` and the demo with `--force`. For SWAT+ it means AORC.
4. Existing pumping: Wellogic high-capacity wells (`PMP_CPCITY >= 70` gpm, or `WWAT_ID`) as generic users, once
   volumes can be placed.
5. The Lower Grand: the same build, with several gages (docs/ideas.md).

## Data and runs (outside git)

| What | Where | Made by |
|---|---|---|
| NextGen rerun | `~/.cache/basinledger/plaster-creek/nextgen-recharge` | `groundwater/rerun_nextgen.py` (Docker, ~3 min) |
| Public data (~72 MB) | `~/.cache/basinledger/plaster-creek/data` | `groundwater/fetch.py` (skips what's there) |
| Model arrays and steady heads | `~/.cache/basinledger/plaster-creek/groundwater.npz` | `groundwater/prepare.py` (~5 s) |
| Coupled runs | `runs/plaster-creek-groundwater/{utility,wells,variant-*}` | `demo.py` (skips any run whose `outputs/series.csv` exists) |

`$BASINLEDGER_CACHE` moves the cache. `$NEXTGEN_MICHIGAN` points to the nextgen-michigan checkout, whose calibrated
`runs/scenarios/baseline` the rerun copies.

## Resume

```bash
cd ~/repos/basinledger
uv sync --group gis --group examples
uv run python examples/plaster-creek/groundwater/rerun_nextgen.py           # only if the cache is gone
uv run --group gis python examples/plaster-creek/groundwater/fetch.py       # skips cached files
uv run --group gis python -W ignore examples/plaster-creek/groundwater/prepare.py
uv run --group gis --group examples python -W ignore examples/plaster-creek/demo.py   # skips finished runs
uv run --group gis --group examples python -W ignore examples/plaster-creek/groundwater/checks.py
uv run --group gis pytest -q -m "not slow"
```

## Water quality data at the outlet (checked November 5, 2026)

Sediment, nitrogen and phosphorus, for calibrating SWAT+ beyond streamflow:

- **Water Quality Portal:** 3,554 results from 106 Plaster Creek sites (USGS, EGLE, MiCorps).
  - Nearly all are E. coli: 2,702 results, from 2001-2004 and 2014-2019.
  - At USGS 04119055 there are only three sample dates (May and June 2017): turbidity, total solids, conductance
    and organics.
  - There is no time series of TSS, suspended sediment, nitrogen or phosphorus.
- **The gage:** it measures stage and discharge only. There are no continuous water-quality sensors.
- **Other sources, not in WQP:**
  - The 2002 biota (sediment) TMDL. Its target is 30 mg/L TSS, as reported in a Calvin watershed report; to be
    verified in the TMDL itself.
  - LGROW's 2010 summary sheet gives loads of about 16,000 lb/yr phosphorus and 89,000 lb/yr nitrogen. These are
    probably model estimates, not measurements.
  - Plaster Creek Stewards (Calvin) and GVSU's Annis Water Resources Institute may hold monitoring data. Worth
    asking.
- **For a demo:** water quality would be soft-calibrated or screening only. That means checking SWAT+ loads against
  the TMDL target, LGROW's loads and USGS SPARROW yields. A real calibration needs data from the Stewards or GVSU, or
  a sampling campaign.

## Open questions

- **Base flow too flat.** The model's base flow is too damped: it is about double the separated value in late summer,
  and its mean is 13-16% low. Fit it (Sy, K, streambed) with PEST++ later, or adjust by hand now?
- **No drought of record.** The run has none (2012). Extending the forcing back to 2011 needs NGIAB's preprocessor
  and a NextGen rerun, once the machine is free.
- **Existing pumping.** EGLE's facility-level water use has no locations. Wellogic's high-capacity wells give
  locations and capacities, not volumes.
