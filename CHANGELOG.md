# Changelog

## 0.1.0 (2026-11-04)

First release.

- A daily driver for coupled models through BMI, with a ledger that enters every transfer as sent and as received
  and stops a run on any day they differ.
- Surface models: SWAT+ live through swatplus-bmi, or a finished NextGen (NGIAB) run replayed day by day.
- MODFLOW 6 through libmf6 and modflowapi: SWAT+ recharge in, wells, and the two-way stream-aquifer exchange through
  the river package, with SWAT+'s aquifer passing recharge through.
- The water-user interface: any BMI component reporting withdrawal, consumption and return (and optionally gain,
  storage, loads, return temperature, electricity), integrated from hourly to daily, its balance checked every step.
  CoolingWaterBmi plugs in by role.
- Routes (wells, SWAT+ intakes and point sources, outfalls, offsite), utility chains, and feedback rules
  (curtailment, dry mode, drawdown limit).
- Restarts from a saved day, matching unbroken runs bit for bit.
- Calibration records per model, statistics, and a forward model; applying parameters and PEST++ are planned.
- Examples: synthetic (Osu_1hru with small MODFLOW 6 models) and Plaster Creek, Michigan (calibrated NextGen
  streamflow).
