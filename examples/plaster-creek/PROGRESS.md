# Plaster Creek groundwater and demo: progress

Kept current at each commit so the work can be resumed from this file alone. Last updated: November 4, 2026, late night (demo done).

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

## Next

1. Fit the groundwater model (specific yield, glacial K, streambed conductance) to base flow and heads, with
   PEST++ IES. That needs the calibration module's parameter step (`calibration.apply_parameters`) for MODFLOW 6.
2. Extend NextGen's forcing to 2011, for the 2012 drought: NGIAB's preprocessor (an hour's download), then
   `rerun_nextgen.py` and the demo with `--force`.
3. Existing pumping: Wellogic high-capacity wells (`PMP_CPCITY >= 70` gpm, or `WWAT_ID`) as generic users, once
   volumes can be placed.
4. The Lower Grand: the same build, several gages (docs/ideas.md).

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

## Open questions

- **Base flow too flat.** The model's base flow is too damped: it is about double the separated value in late summer,
  and its mean is 13-16% low. Fit it (Sy, K, streambed) with PEST++ later, or adjust by hand now?
- **No drought of record.** The run has none (2012). Extending the forcing back to 2011 needs NGIAB's preprocessor
  and a NextGen rerun, once the machine is free.
- **Existing pumping.** EGLE's facility-level water use has no locations. Wellogic's high-capacity wells give
  locations and capacities, not volumes.
