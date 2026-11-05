# Examples

Each folder is one place: a config (`basin.toml`) that wires real models for one basin and its water users, a script
that fetches its public data (`fetch.py`), and a short write-up (`README.md`). Real examples also keep their maps
between the NextGen hydrofabric and the MODFLOW 6 grid (`maps/`) and their calibration record (`calibration/`). An
example without calibrated models is a screening run, never a study result.

An example is also a study's starting point. Private studies are built the same way in the private northline
repository, never here.

| Example | Status | Calibration | What it is |
|---|---|---|---|
| [synthetic](synthetic/) | built | screening run | SWAT+'s Osu_1hru + a small MODFLOW 6 model + a synthetic water user; the tests run on it |
| [plaster-creek](plaster-creek/) | built | streamflow at USGS 04119055 calibrated (NextGen); nothing else | Plaster Creek, Kent County, Michigan: a calibrated NextGen run replayed, an assumed campus on utility water |
| [michigan-cold-streams](michigan-cold-streams/) | screen | none (a screen of public data) | 78 gaged Michigan basins scored for a first cold-stream study: trout streams, groundwater, temperature data, siting, irrigation, data centers |
| [michigan-wwat-check](michigan-wwat-check/) | screen | none (a screen of public data) | Where a well that passes the Water Withdrawal Assessment Tool is most likely to harm a cold stream anyway: 30 eligible basins scored on five failure paths, a step 2 set of five candidates and two controls |
