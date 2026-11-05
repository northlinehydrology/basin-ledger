# Plaster Creek

## Summary

Plaster Creek above USGS 04119055 (Kentwood, Kent County, Michigan), 124 km² in 16 NextGen catchments. The example
replays a calibrated NextGen run, runs an assumed 300 MW tower-cooled campus with `CoolingWaterBmi`, and couples a
screening MODFLOW 6 model (`groundwater/`). The campus takes utility water (`basin.toml`, `groundwater.toml`) or its
own well (`groundwater-wells.toml`).

## What it shows

On its own well the campus cuts the gage's 7-day low flow by 43 L/s (27%) in the driest year of the run. MODFLOW 6
takes 63% of the pumping from the streams in the last year. Glover's method, with nextgen-michigan's screening
settings, gives 89%. On utility water from Lake Michigan the creek sees nothing. Streamflow at the gage is calibrated
(KGE 0.87 in calibration, 0.81 in validation; `calibration/record.toml`). The figures and tables are in
[docs/plaster-creek-demo.md](../../docs/plaster-creek-demo.md).

## What Basin Ledger measures

- Daily flow and depth on every flowpath and nexus, keyed to hydrofabric ids.
- The campus's withdrawal, consumption, return and electricity, hourly, integrated by day.
- Water produced at the utility's plant, including distribution losses.
- MODFLOW 6 heads and river exchange, gross and net, by cell.
- Depletion by reach and the share of pumping taken from streams.
- 7-day low flow and days below Q90 at the gage.
- Each model's water balance and every transfer between models, closed daily.

## Limitations

- Groundwater is screening: heads RMSE 7.9 m over 55 wells, base flow too steady at low flow.
- The calibrated 7-day low flows are 8–18% below observed.
- The campus and its well site are assumptions [A].
- A NextGen replay has no feedback. Depletion is taken off its flows afterward.
- No water quality, and no existing pumping.
- Four years of weather, with no drought of record.

## Open problems

- Fit the groundwater model to heads and base flow. Streambed conductance moves the answer most.
- Extend the forcing to include the 2012 drought.
- Add stream temperature from the change in groundwater inflow.
- Run water quality through SWAT+ on the same catchments, against the Plaster Creek TMDL.
- Add existing high-capacity wells and other water users.

## Run

```bash
uv run python examples/plaster-creek/fetch.py              # checks for the NextGen run; says how to build it
uv run python examples/plaster-creek/check_calibration.py  # the fit at the gage
uv run python -m basinledger run examples/plaster-creek/basin.toml
```

The NextGen run is built by nextgen-michigan (`$NEXTGEN_MICHIGAN`). The groundwater model and the demo are built by
the steps in `groundwater/README.md`.
