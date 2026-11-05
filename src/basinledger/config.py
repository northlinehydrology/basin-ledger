"""An example's configuration: one TOML file that wires real models for one basin and its water users.

Paths are relative to the config file. ``{swatplus_refdata}`` stands for the example projects that ship with SWAT+
(``refdata/`` in the source that ``swatplus-bmi build`` fetched), for the synthetic example.

    name = "synthetic"
    description = "..."

    [run]
    folder = "../../runs/synthetic"     # each run copies the models here
    days = 0                            # 0: the SWAT+ project's whole period

    [swatplus]                          # the surface model: SWAT+, stepped live through swatplus-bmi
    project = "{swatplus_refdata}/Osu_1hru"
    places_of_use = [{name = "intake", channel = "cha01"}]    # added to the run's copy, set daily
    point_sources = [{name = "wwtp", channel = "cha01"}]

    # or [nextgen]                      # the surface model: a finished NGIAB run, replayed (coupling/nextgen.py)
    # run = "{nextgen_michigan}/runs/scenarios/baseline"

    [modflow6]                          # optional: the groundwater model
    builder = "model:build"             # model.py beside this file: build(workspace, days, start_date)
    builder_args = {}                   # optional keyword arguments for the builder (a scenario's variant)
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

    [rivers]                            # optional: MODFLOW 6 river cells by flowpath, for stage and base flow out
    package = "riv"
    map = "maps/river_cells.csv"        # object (flowpath or channel), layer, row, col
    stage = "nextgen_depth"             # or "fixed": the stage in MODFLOW 6's input
    bed_thickness = 1.0                 # m [A]: stage = RBOT + bed thickness + the day's depth

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
    # forcing = {source = "nextgen", catchment = "cat-652059"}   hourly weather inputs (forcing.py)

Routes also include ``offsite:<name>``: water from or to somewhere outside the basin (a Great Lakes intake, a plant on
another river), entered in the ledger only.

``{nextgen_michigan}`` stands for a checkout of github.com/northlinehydrology/nextgen-michigan (``$NEXTGEN_MICHIGAN``,
or ``~/repos/nextgen-michigan``).
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


def cache_dir() -> Path:
    """Where examples keep downloaded and generated data, outside git: $BASINLEDGER_CACHE or ~/.cache/basinledger."""
    return Path(os.environ.get("BASINLEDGER_CACHE", Path.home() / ".cache" / "basinledger"))


def nextgen_michigan() -> Path:
    return Path(os.environ.get("NEXTGEN_MICHIGAN", Path.home() / "repos" / "nextgen-michigan"))


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
    forcing: dict | None = None


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
    swat_project: Path | None
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
    nextgen_run: Path | None = None
    rivers: dict | None = None
    mf6_builder_args: dict = field(default_factory=dict)

    @property
    def surface(self) -> str:
        return "nextgen" if self.nextgen_run else "swatplus"

    @property
    def has_modflow6(self) -> bool:
        return bool(self.mf6_builder or self.mf6_workspace)

    @property
    def models(self) -> list[str]:
        """The hydrologic models a run of this example uses, for its calibration status."""
        return [self.surface] + (["modflow6"] if self.has_modflow6 else [])

    @property
    def folder(self) -> Path:
        return self.path.parent

    @property
    def calibration_status(self) -> str:
        """'calibrated' or 'screening' (no record, or a record that doesn't say calibrated)."""
        from .calibration import record_status
        return record_status(self.calibration_record, self.models)


def _path(base: Path, p: str) -> Path:
    if "{swatplus_refdata}" in p:
        p = p.replace("{swatplus_refdata}", str(swatplus_refdata()))
    p = p.replace("{nextgen_michigan}", str(nextgen_michigan()))
    p = p.replace("{cache}", str(cache_dir()))
    q = Path(p).expanduser()
    return q if q.is_absolute() else (base / q).resolve()


def load(path: str | Path) -> ExampleConfig:
    path = Path(path).resolve()
    with open(path, "rb") as f:
        c = tomllib.load(f)
    base = path.parent
    known = {"name", "description", "run", "swatplus", "modflow6", "recharge", "wells", "users", "calibration",
             "exchange", "utilities", "rules", "outputs", "nextgen", "rivers"}
    if set(c) - known:
        raise ValueError(f"{path}: unknown sections {sorted(set(c) - known)}")
    mf = c.get("modflow6", {})
    if "modflow6" in c and bool(mf.get("builder")) == bool(mf.get("workspace")):
        raise ValueError(f"{path}: [modflow6] needs one of builder or workspace")
    if ("swatplus" in c) == ("nextgen" in c):
        raise ValueError(f"{path}: needs one surface model, [swatplus] or [nextgen]")
    sw = c.get("swatplus", {})
    rch = c.get("recharge", {})
    users = []
    for u in c.get("users", []):
        users.append(UserConfig(
            name=u["name"], component=u["component"],
            config=_path(base, u["config"]) if u.get("config") else None,
            withdrawal=u["withdrawal"], returns=u["return"],
            variables=u.get("variables", {}), constituents=u.get("constituents"), forcing=u.get("forcing")))
    return ExampleConfig(
        path=path, name=c["name"], description=c.get("description", ""),
        run_folder=_path(base, c.get("run", {}).get("folder", f"runs/{c['name']}")),
        days=int(c.get("run", {}).get("days", 0)),
        swat_project=_path(base, sw["project"]) if sw else None,
        mf6_builder=mf.get("builder"),
        mf6_workspace=_path(base, mf["workspace"]) if mf.get("workspace") else None,
        mf6_model=mf.get("model", "gwf"),
        recharge_package=rch.get("package", "rch"),
        recharge_map=rch.get("map", ""),
        area_rtol=rch.get("area_rtol"),
        wells=[WellConfig(w["name"], w.get("package", "wel"), tuple(w["cell"])) for w in c.get("wells", [])],
        users=users,
        calibration_record=_path(base, c["calibration"]["record"]) if c.get("calibration", {}).get("record") else None,
        places_of_use=[(x["name"], x["channel"]) for x in sw.get("places_of_use", [])],
        point_sources=[(x["name"], x["channel"]) for x in sw.get("point_sources", [])],
        exchange=c.get("exchange"),
        utilities=c.get("utilities", []),
        rules=c.get("rules", []),
        outputs=c.get("outputs", {}),
        nextgen_run=_path(base, c["nextgen"]["run"]) if "nextgen" in c else None,
        rivers=c.get("rivers"),
        mf6_builder_args=mf.get("builder_args", {}),
    )
