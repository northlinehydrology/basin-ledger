"""Calibration: parameters, observations, the forward model, statistics, and the calibration record.

Built:
- the record and its status (no record, or a status other than "calibrated", means a screening run);
- parameters and observations as tables (CSV);
- simulated values at observations, from a run's series (channel flow, heads at named cells);
- statistics: NSE, KGE, percent bias, a low-flow NSE (on log flows), mean error and RMSE;
- the forward model: run an example and write simulated values at every observation, for PEST++ to read.

Not built yet (docs/design.md, Calibration):
- applying a parameter set to the models' input files: SWAT+ through ``calibration.cal``, MODFLOW 6 arrays by zone or
  pilot point (flopy, pyEMU), users through their config. ``apply_parameters`` refuses anything it can't apply yet;
- writing PEST++ IES control and template files (pyEMU);
- fetching observations: USGS daily streamflow and groundwater levels (``dataretrieval``), matched to hydrofabric
  flowpaths and nexuses and to MODFLOW 6 cells.

Tables:

    parameters.csv    name, model, target, value, lower, upper, transform
                      model: swatplus | modflow6 | user; target: what it changes (a calibration.cal parameter and
                      object, a MODFLOW 6 package array and zone, a user's config key); transform: none | log
    observations.csv  name, kind, object, date, value, weight, source
                      kind: flow (m3 s-1, object = channel or hydrofabric id) | head (m, object = a named head
                      output); date ISO; source: e.g. "USGS 04119055 dv"
"""

from __future__ import annotations

import csv
import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

STATUSES = ("calibrated", "screening")
SCREENING = "screening"


def model_statuses(record: Path | None, models: list[str]) -> dict[str, str]:
    """Each model's status from an example's record.

    A record gives either one status for the example (top-level ``status``, ``[calibration]``, ``[validation]``)
    or one per model (``[models.<name>]`` with the same keys), e.g. streamflow from NextGen calibrated and MODFLOW 6
    a screening model. A model the record doesn't name is screening. A calibrated model needs its calibration and
    validation statistics.
    """
    if record is None:
        return {m: SCREENING for m in models}
    with open(record, "rb") as f:
        rec = tomllib.load(f)
    per = rec.get("models")
    out = {}
    for m in models:
        entry = per.get(m) if per is not None else rec
        status = (entry or {}).get("status", SCREENING)
        if status not in STATUSES:
            raise ValueError(f"{record}: status must be one of {STATUSES}, not {status!r}")
        if status == "calibrated":
            missing = [k for k in ("calibration", "validation") if k not in entry]
            if missing:
                raise ValueError(f"{record}: a calibrated record needs its {' and '.join(missing)} statistics")
        out[m] = status
    return out


def record_targets(record: Path | None) -> dict[str, str]:
    """What each model in a record was calibrated to (its ``target``), e.g. streamflow at a gage."""
    if record is None:
        return {}
    with open(record, "rb") as f:
        rec = tomllib.load(f)
    return {m: e["target"] for m, e in (rec.get("models") or {}).items() if "target" in e}


def record_status(record: Path | None, models: list[str] | None = None) -> str:
    """'calibrated' only if every model the example runs is calibrated; otherwise a screening run."""
    st = model_statuses(record, models or ["all"])
    return "calibrated" if all(v == "calibrated" for v in st.values()) else SCREENING


@dataclass
class Parameter:
    name: str
    model: str
    target: str
    value: float
    lower: float
    upper: float
    transform: str = "none"

    def __post_init__(self):
        if self.model not in ("swatplus", "modflow6", "user"):
            raise ValueError(f"parameter {self.name}: model must be swatplus, modflow6 or user")
        if not self.lower <= self.value <= self.upper:
            raise ValueError(f"parameter {self.name}: {self.value} outside [{self.lower}, {self.upper}]")


@dataclass
class Observation:
    name: str
    kind: str       # flow | head
    object: str     # channel (or hydrofabric id) for flow; named head output for head
    date: str
    value: float
    weight: float = 1.0
    source: str = ""


def read_parameters(path: Path) -> list[Parameter]:
    with open(path, newline="") as f:
        return [Parameter(r["name"], r["model"], r["target"], float(r["value"]), float(r["lower"]),
                          float(r["upper"]), r.get("transform") or "none") for r in csv.DictReader(f)]


def read_observations(path: Path) -> list[Observation]:
    with open(path, newline="") as f:
        obs = [Observation(r["name"], r["kind"], r["object"], r["date"], float(r["value"]),
                           float(r.get("weight") or 1.0), r.get("source", "")) for r in csv.DictReader(f)]
    for o in obs:
        if o.kind not in ("flow", "head"):
            raise ValueError(f"observation {o.name}: kind must be flow or head")
    return obs


def apply_parameters(model: str, folder: Path, params: list[Parameter]):
    """Write a parameter set into a run's copy of one model's inputs, before it starts (the driver's ``prepare``
    hook). Not built yet for any model."""
    mine = [p for p in params if p.model == model]
    if mine:
        raise NotImplementedError(f"applying {model} parameters is planned; see docs/design.md, Calibration")


def simulated(series: dict[str, list[float]], dates: list[str], observations: list[Observation]) -> np.ndarray:
    """The run's value at each observation: channel flow (``flow:<object>``) or head (``head:<object>``) on its
    date."""
    index = {d: i for i, d in enumerate(dates)}
    out = np.empty(len(observations))
    for j, o in enumerate(observations):
        key = f"{o.kind}:{o.object}"
        if key not in series:
            raise KeyError(f"observation {o.name}: the run has no {key!r} output (add it under [outputs])")
        if o.date not in index:
            raise KeyError(f"observation {o.name}: {o.date} is outside the run")
        out[j] = series[key][index[o.date]]
    return out


def nse(sim, obs) -> float:
    sim, obs = np.asarray(sim, float), np.asarray(obs, float)
    return float(1 - np.sum((sim - obs) ** 2) / np.sum((obs - obs.mean()) ** 2))


def log_nse(sim, obs, floor: float = 1e-6) -> float:
    """NSE on log flows: weights low flows, where a large user shows."""
    return nse(np.log(np.maximum(sim, floor)), np.log(np.maximum(obs, floor)))


def kge(sim, obs) -> float:
    """Kling-Gupta efficiency (Gupta et al. 2009)."""
    sim, obs = np.asarray(sim, float), np.asarray(obs, float)
    r = np.corrcoef(sim, obs)[0, 1]
    return float(1 - np.sqrt((r - 1) ** 2 + (sim.std() / obs.std() - 1) ** 2 + (sim.mean() / obs.mean() - 1) ** 2))


def pbias(sim, obs) -> float:
    """Percent bias, positive when the model overestimates."""
    sim, obs = np.asarray(sim, float), np.asarray(obs, float)
    return float(100 * np.sum(sim - obs) / np.sum(obs))


def mean_error(sim, obs) -> float:
    return float(np.mean(np.asarray(sim, float) - np.asarray(obs, float)))


def rmse(sim, obs) -> float:
    return float(np.sqrt(np.mean((np.asarray(sim, float) - np.asarray(obs, float)) ** 2)))


def statistics(observations: list[Observation], sim: np.ndarray) -> dict[str, dict[str, float]]:
    """Statistics per site (kind and object): flow gets NSE, log NSE, KGE and percent bias; heads mean error, RMSE
    and RMSE over the observed range."""
    out = {}
    for key in dict.fromkeys((o.kind, o.object) for o in observations):
        idx = [i for i, o in enumerate(observations) if (o.kind, o.object) == key]
        s = sim[idx]
        o = np.array([observations[i].value for i in idx])
        if key[0] == "flow":
            out[f"flow:{key[1]}"] = {"n": len(idx), "nse": nse(s, o), "log_nse": log_nse(s, o), "kge": kge(s, o),
                                     "pbias": pbias(s, o)}
        else:
            rng = float(o.max() - o.min())
            out[f"head:{key[1]}"] = {"n": len(idx), "mean_error": mean_error(s, o), "rmse": rmse(s, o),
                                     "rmse_over_range": rmse(s, o) / rng if rng > 0 else float("nan")}
    return out


def run_forward_model(config: str | Path, parameters: Path | None, observations: Path, out: Path,
                      run: str = "calibration") -> Path:
    """The forward model PEST++ calls: apply a parameter set, run the example, and write the simulated value at
    every observation (name, simulated) to ``out``."""
    from . import config as C
    from .driver import Basin

    cfg = C.load(config)
    obs = read_observations(observations)
    params = read_parameters(parameters) if parameters else []
    b = Basin(cfg, run=run, prepare=lambda model, folder: apply_parameters(model, folder, params))
    try:
        b.run()
        sim = simulated(b.series, b.dates(), obs)
    finally:
        b.finalize()
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "simulated"])
        for o, s in zip(obs, sim):
            w.writerow([o.name, repr(float(s))])
    return out


def write_pest_files(*args, **kwargs):
    raise NotImplementedError("PEST++ IES control and template files (pyEMU) are planned; see docs/design.md")


def fetch_usgs(*args, **kwargs):
    raise NotImplementedError("USGS streamflow and groundwater level downloads are planned; see docs/design.md")
