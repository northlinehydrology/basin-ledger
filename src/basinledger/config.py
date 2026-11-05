"""An example's configuration: one TOML file that wires real models for one basin and its water users.

Paths are relative to the config file. ``{swatplus_refdata}`` stands for the example projects that ship with SWAT+
(``refdata/`` in the source that ``swatplus-bmi build`` fetched), for the synthetic example.

    name = "synthetic"
    description = "..."

    [run]
    folder = "../../runs/synthetic"     # each run copies the models here
    days = 0                            # 0: the SWAT+ project's whole period

    [swatplus]
    project = "{swatplus_refdata}/Osu_1hru"
    places_of_use = [{name = "intake", channel = "cha01"}]    # added to the run's copy, set daily
    point_sources = [{name = "wwtp", channel = "cha01"}]

    [modflow6]
    builder = "model:build"             # model.py beside this file: build(workspace, days, start_date)
    # workspace = "mf6"                 # or an existing simulation folder, copied into the run
    model = "gwf"

    [recharge]                          # SWAT+ aquifers -> MODFLOW 6 recharge (one-way)
    package = "rch"
    map = "all:aqu001"                  # every top-layer cell to one aquifer, or a CSV (see mapping.py)
    area_rtol = 0.001                   # optional: mapped area must match SWAT+'s aquifer area

    [[wells]]
    name = "pw1"
    package = "wel"
    cell = [0, 20, 30]                  # layer, row, col (0-based)

    [exchange]                          # optional: two-way stream-aquifer exchange (MODFLOW 6 RIV <-> SWAT+)
    package = "riv"
    map = "all:cha01"                   # every RIV entry to one channel, or a CSV: object, layer, row, col

    [[utilities]]                       # optional: a water system (see chain.py)
    name = "city"
    sources = [{route = "well:pw1", share = 1.0}]
    outfall = "swat:point_source:wwtp"

    [[rules]]                           # optional: feedback rules (see rules.py)
    name = "low-flow cut"
    kind = "curtailment"
    user = "plant"
    channel = "cha01"
    threshold = 0.001

    [outputs]                           # optional: daily series written with the ledger
    channels = ["cha01"]                # outflow, m3 s-1 (default: every channel)
    heads = [{name = "pw1", cell = [0, 20, 28]}]

    [calibration]                       # optional: the example's calibration record
    record = "calibration/record.toml"  # without one, the example is a screening run

    [[users]]
    name = "plant"
    component = "basinledger.testing:SyntheticUser"
    config = "user.toml"
    withdrawal = "well:pw1"             # source: a MODFLOW 6 well (later: a SWAT+ place of use, a utility)
    return = "outfall:creek"            # sink: an outfall account (later: a SWAT+ point source, a sewer)
    # variables = {withdrawal = "...", gain = "..."}   for components without the common names
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


def swatplus_refdata() -> Path:
    if os.environ.get("SWATPLUS_REFDATA"):
        return Path(os.environ["SWATPLUS_REFDATA"])
    from swatplus_bmi.build import DEFAULT_TAG, home
    return home() / "build" / DEFAULT_TAG / "swatplus" / "refdata"


@dataclass
class UserConfig:
    name: str
    component: str
    config: Path | None
    withdrawal: str
    returns: str
    variables: dict = field(default_factory=dict)
    constituents: dict | None = None


@dataclass
class WellConfig:
    name: str
    package: str
    cell: tuple[int, int, int]


@dataclass
class ExampleConfig:
    path: Path
    name: str
    description: str
    run_folder: Path
    days: int
    swat_project: Path
    mf6_builder: str | None
    mf6_workspace: Path | None
    mf6_model: str
    recharge_package: str
    recharge_map: str
    area_rtol: float | None
    wells: list[WellConfig]
    users: list[UserConfig]
    calibration_record: Path | None = None
    places_of_use: list[tuple[str, str]] = field(default_factory=list)
    point_sources: list[tuple[str, str]] = field(default_factory=list)
    exchange: dict | None = None
    utilities: list[dict] = field(default_factory=list)
    rules: list[dict] = field(default_factory=list)
    outputs: dict = field(default_factory=dict)

    @property
    def folder(self) -> Path:
        return self.path.parent

    @property
    def calibration_status(self) -> str:
        """'calibrated' or 'screening' (no record, or a record that doesn't say calibrated)."""
        from .calibration import record_status
        return record_status(self.calibration_record)


def _path(base: Path, p: str) -> Path:
    p = p.replace("{swatplus_refdata}", str(swatplus_refdata()))
    q = Path(p).expanduser()
    return q if q.is_absolute() else (base / q).resolve()


def load(path: str | Path) -> ExampleConfig:
    path = Path(path).resolve()
    with open(path, "rb") as f:
        c = tomllib.load(f)
    base = path.parent
    known = {"name", "description", "run", "swatplus", "modflow6", "recharge", "wells", "users", "calibration",
             "exchange", "utilities", "rules", "outputs"}
    if set(c) - known:
        raise ValueError(f"{path}: unknown sections {sorted(set(c) - known)}")
    mf = c.get("modflow6", {})
    if bool(mf.get("builder")) == bool(mf.get("workspace")):
        raise ValueError(f"{path}: [modflow6] needs one of builder or workspace")
    rch = c.get("recharge", {})
    users = []
    for u in c.get("users", []):
        users.append(UserConfig(
            name=u["name"], component=u["component"],
            config=_path(base, u["config"]) if u.get("config") else None,
            withdrawal=u["withdrawal"], returns=u["return"],
            variables=u.get("variables", {}), constituents=u.get("constituents")))
    return ExampleConfig(
        path=path, name=c["name"], description=c.get("description", ""),
        run_folder=_path(base, c.get("run", {}).get("folder", f"runs/{c['name']}")),
        days=int(c.get("run", {}).get("days", 0)),
        swat_project=_path(base, c["swatplus"]["project"]),
        mf6_builder=mf.get("builder"),
        mf6_workspace=_path(base, mf["workspace"]) if mf.get("workspace") else None,
        mf6_model=mf.get("model", "gwf"),
        recharge_package=rch.get("package", "rch"),
        recharge_map=rch.get("map", ""),
        area_rtol=rch.get("area_rtol"),
        wells=[WellConfig(w["name"], w.get("package", "wel"), tuple(w["cell"])) for w in c.get("wells", [])],
        users=users,
        calibration_record=_path(base, c["calibration"]["record"]) if c.get("calibration", {}).get("record") else None,
        places_of_use=[(x["name"], x["channel"]) for x in c["swatplus"].get("places_of_use", [])],
        point_sources=[(x["name"], x["channel"]) for x in c["swatplus"].get("point_sources", [])],
        exchange=c.get("exchange"),
        utilities=c.get("utilities", []),
        rules=c.get("rules", []),
        outputs=c.get("outputs", {}),
    )
