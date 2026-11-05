# Plaster Creek groundwater and demo: progress

Kept current at each commit so the work can be resumed from this file alone. Last updated: November 4, 2026, night.

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

## In progress

- **Uncommitted in the working tree, being verified by the demo run:**
  - `groundwater/checks.py`: gross and net discharge, the daily budget closure;
  - `demo.py`: the runs, four figures, the utility case, the sensitivity table, and `docs/plaster-creek-demo.md`.
- **Next steps:**
  1. Read `demo-results.json` and the figures in `docs/figures/plaster-demo-*.png`. Check the numbers against the
     checks.
  2. Commit `checks.py`, then `demo.py`, `demo-results.json`, the figures and `docs/plaster-creek-demo.md`.
  3. Write `groundwater/README.md`: methods, choices [A], the fit.
  4. Add a `[models.modflow6]` screening entry with the fit to `calibration/record.toml`.
  5. Update the example README and `docs/design.md`.
  6. Run the full suite, then push.

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
cd ~/repos/basin-ledger
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
