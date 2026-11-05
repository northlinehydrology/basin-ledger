# Plaster Creek

Plaster Creek above USGS 04119055 (Plaster Creek at 28th Street, Kentwood, Kent County, Michigan): 124 km², 16
catchments of the NextGen hydrofabric v2.2. This is Basin Ledger's first example on a calibrated model.

## What runs

- **Streamflow: NextGen, calibrated.**
  - The model: NextGen In A Box v2.1.0 with Noah-OWP-Modular and CFE in every catchment, NWM v3 retrospective
    forcing (October 2018 to December 2022), and t-route.
  - The calibration: two stages, from [nextgen-michigan](https://github.com/northlinehydrology/nextgen-michigan)
    (its `docs/calibration.md`).
  - Basin Ledger replays the finished run one day at a time (`coupling/nextgen.py`). Flows are reported for every
    flowpath (`wb-`) and nexus (`nex-`).
- **A water user: an assumed 300 MW tower-cooled campus** in catchment `cat-652066` [A].
  - `CoolingWaterBmi` from `waterledger-models` steps it hourly on the same forcing NextGen used: that catchment's
    2 m temperature and humidity.
  - It is on utility water from outside the basin, and its wastewater is treated outside the basin. The stream sees
    neither. The utility's 10% distribution losses are an assumption [A].
- **Nothing else.** There is no groundwater model and no water quality yet.

## What is calibrated, and what isn't

The calibration record is `calibration/record.toml`. The example's status is `calibrated` because the one hydrologic
model it runs is calibrated. That covers streamflow at the gage only.

| | Calibration (2019-10-01 to 2021-05-16) | Validation (to 2022-12-31) |
|---|---|---|
| KGE, published / recomputed here | 0.87 / 0.861 | 0.81 / 0.789 |
| NSE | 0.75 / 0.735 | 0.72 / 0.659 |
| log NSE | 0.74 / 0.762 | 0.63 / 0.672 |
| bias | 0% / −0.5% | +11% / +11.7% |

"Published" is nextgen-michigan's figure, computed against USGS approved daily values. "Recomputed" is
`check_calibration.py`, run from the replayed run against the instantaneous record ngiab-cal downloaded, averaged to
calendar days. A test checks that the record and a fresh recomputation agree. The two sets differ by up to 0.06 in
validation NSE, most likely because the observations differ: approved daily values, against means of instantaneous
values.

Not calibrated, or only approximately:

- **Low flow is approximate.** The model's 7-day low flows are 8–18% below observed in 2020–2022.
- **The headwaters are ungaged.** The calibration is for the gage. Every catchment has one parameter set, and the
  campus sits in a small catchment with no record.
- **The campus is assumed.** Its size, cooling design and utility losses are assumptions [A], not a proposal, and
  are not calibrated.
- **Groundwater and water quality are screening.** A MODFLOW 6 model, if added, and any water quality stay screening
  until calibrated, to Michigan well records and to the Plaster Creek TMDL data (E. coli, sediment and biota).
- **Four years of weather** include no drought of record.

## What it shows, and what it doesn't yet

- **The engine runs on a calibrated model on NextGen geography.** Results are keyed to hydrofabric ids, so the gage
  flow (`flow:wb-652056`) compares directly with the National Water Model. The campus's hourly withdrawal,
  consumption, return and electricity are integrated by day, and the ledger closes every day.
- **A replay has no feedback.** The campus on utility water changes nothing in the stream, so the replay is exact for
  this case. A user that takes from or returns to the creek would need NextGen to see it. nextgen-michigan does that
  inside the NextGen run, with its WaterUsers component. Replaying those scenario runs, and comparing them with this
  baseline in the ledger, is the next step.
- **No MODFLOW 6 yet.** The run's outputs don't include CFE's percolation to groundwater. A rerun with that flux added
  to the realization's output variables would give MODFLOW 6 its recharge.

## Run it

```bash
uv run python examples/plaster-creek/fetch.py              # checks for the NextGen run; says how to build it
uv run python examples/plaster-creek/check_calibration.py  # the fit at the gage
uv run python -m basinledger run examples/plaster-creek/basin.toml
```

The NextGen run isn't in this repository. It's built by nextgen-michigan (Docker, a few hours), and
`$NEXTGEN_MICHIGAN` points to that checkout.
