"""Calibration: model parameters, observations, the calibration record, and PEST++ IES. Mostly not built yet.

Built: reading an example's record and its status. Without a record, or with a status other than "calibrated", an
example is a screening run, and everything the driver reports says so.

Planned (docs/design.md, Calibration):

- **Parameters.** One named list with bounds across the models: SWAT+ through ``calibration.cal`` changes, MODFLOW 6
  package arrays by zone or pilot point (flopy, pyEMU), water-user component parameters.
- **Observations.** USGS daily streamflow, matched to hydrofabric flowpaths and nexuses through the hydrofabric's gage
  crosswalk; USGS groundwater levels (and state records, weighted), matched to MODFLOW 6 cells by location and screened
  depth; water quality where a question needs it.
- **Forward model.** ``python -m basinledger run basin.toml --parameters pars.csv --observations obs.csv``: apply a
  parameter set, run the driver, write simulated values at every observation for PEST++ to read.
- **PEST++ IES**, jointly where the coupling has feedback, from the individual calibrations as the prior.
- **The record** (``calibration/record.toml``): status, periods, versions, method, and statistics by site for
  calibration and validation (NSE, KGE, percent bias, a low-flow statistic; head mean error and RMSE).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

STATUSES = ("calibrated", "screening")
SCREENING = "screening"


def record_status(record: Path | None) -> str:
    """The status an example's calibration record gives it; no record means a screening run."""
    if record is None:
        return SCREENING
    with open(record, "rb") as f:
        rec = tomllib.load(f)
    status = rec.get("status")
    if status not in STATUSES:
        raise ValueError(f"{record}: status must be one of {STATUSES}, not {status!r}")
    if status == "calibrated":
        missing = [k for k in ("calibration", "validation") if k not in rec]
        if missing:
            raise ValueError(f"{record}: a calibrated record needs its {' and '.join(missing)} statistics")
    return status


def run_forward_model(*args, **kwargs):
    raise NotImplementedError("the PEST++ forward model is planned; see docs/design.md, Calibration")
