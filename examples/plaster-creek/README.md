# Plaster Creek

## Summary

Plaster Creek above USGS 04119055 (Plaster Creek at 28th Street, Kentwood, Kent County, Michigan) drains 124 km² in 16
catchments of the NextGen hydrofabric v2.2. The example runs three parts.

- **Streamflow:** a calibrated NextGen run, replayed one day at a time (`coupling/nextgen.py`). The model is
  NextGen In A Box v2.1.0 with Noah-OWP-Modular and CFE in every catchment, NWM v3 retrospective forcing (October
  2018 to December 2022) and t-route. Its calibration is from
  [nextgen-michigan](https://github.com/northlinehydrology/nextgen-michigan) (`docs/calibration.md` there).
- **A water user:** an assumed 300 MW tower-cooled campus in catchment `cat-652066` [A]. `CoolingWaterBmi` from
  `waterledger-models` steps it hourly on that catchment's 2 m temperature and humidity.
- **Groundwater:** a screening MODFLOW 6 model in `groundwater/`. Its recharge is CFE's daily percolation. Its river
  stages follow t-route's depth.

The campus runs two ways. In `basin.toml` and `groundwater.toml` it takes utility water from outside the basin. In
`groundwater-wells.toml` it pumps its own well 500 m from the nearest stream cell [A].

## What it shows

On utility water the creek sees nothing. The water comes from Lake Michigan and returns to the Grand River through
Wyoming's plant. On its own well the campus lowers the gage's 7-day low flow by 43 L/s (27%) in the driest year
(2021-22) and by 42 L/s (20%) in the median year (2020-21). Days below Q90 go from 48 to 62 in the driest year and
from 49 to 73 in the median year.

MODFLOW 6 takes 63% of the pumping from streams and seepage in the last year. Glover's method gives 89% with
nextgen-michigan's settings and 78% with MODFLOW 6's aquifer properties at the well. Streambed conductance moves the
answer most. The full results are in [docs/plaster-creek-demo.md](../../docs/plaster-creek-demo.md).

Streamflow at the gage is calibrated:

| | Calibration (2019-10-01 to 2021-05-16) | Validation (to 2022-12-31) |
|---|---|---|
| KGE, published / recomputed here | 0.87 / 0.861 | 0.81 / 0.789 |
| NSE | 0.75 / 0.735 | 0.72 / 0.659 |
| log NSE | 0.74 / 0.762 | 0.63 / 0.672 |
| bias | 0% / −0.5% | +11% / +11.7% |

"Published" is nextgen-michigan's figure against USGS approved daily values. "Recomputed" is `check_calibration.py`
against the instantaneous record averaged to calendar days. A test checks that the record and a fresh recomputation
agree. The record is `calibration/record.toml`.

## What Basin Ledger measures

- Daily flow and depth on every flowpath (`wb-`) and nexus (`nex-`), keyed to hydrofabric ids so they compare
  directly with the National Water Model.
- The campus's withdrawal, consumption, return and electricity, hourly, integrated by day.
- The utility chain: water produced for the campus at the plant, including distribution losses.
- Heads in every MODFLOW 6 cell, and the exchange with each river cell, gross and net.
- Streamflow depletion by reach, and the share of pumping taken from streams and seepage.
- Low-flow measures at the gage: 7-day low flow and days below Q90.
- The water balance of every model and every transfer between them. The ledger closes every day.

## Limitations

- **Groundwater is screening.** Steady heads match 55 Wellogic drift wells with an RMSE of 7.9 m (mean error
  +1.9 m, a 66 m range). Mean base flow is within 4% of the base flow separated from the gage record. It is too
  steady: 76–93% high on days of below-median flow.
- **Low flow is approximate.** The calibrated model's 7-day low flows are 8–18% below observed in 2020–2022.
  Depletion percentages are shares of the model's low flow.
- **The headwaters are ungaged.** Every catchment has one parameter set, and the campus sits in a small catchment with
  no record.
- **The campus is assumed.** Its size, cooling design, utility losses and well site are assumptions [A].
- **A replay has no feedback.** NextGen doesn't see the well. Depletion is taken off its flows afterward.
- **No water quality.** The SWAT+ surface that would carry it doesn't exist yet for Plaster Creek.
- **Four years of weather.** The run includes no drought of record such as 2012.
- **Existing pumping isn't included.** EGLE's facility-level water use has no locations [A].

## Run

```bash
uv run python examples/plaster-creek/fetch.py              # checks for the NextGen run; says how to build it
uv run python examples/plaster-creek/check_calibration.py  # the fit at the gage
uv run python -m basinledger run examples/plaster-creek/basin.toml
```

The NextGen run isn't in this repository. nextgen-michigan builds it (Docker, a few hours), and `$NEXTGEN_MICHIGAN`
points to that checkout. The groundwater model and the demo are built by the steps in `groundwater/README.md`.
Progress and resume steps are in `PROGRESS.md`.
