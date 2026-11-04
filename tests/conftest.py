"""Shared fixtures. Tests that need SWAT+ or libmf6 skip with a message saying how to get them."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "examples" / "synthetic" / "basin.toml"
RUNS = ROOT / "tests" / "runs"


@pytest.fixture(scope="session")
def libmf6():
    from basinledger.coupling.modflow6 import find_library
    try:
        return find_library()
    except FileNotFoundError as e:
        pytest.skip(str(e))


@pytest.fixture(scope="session")
def swatplus(libmf6):
    from basinledger.config import swatplus_refdata
    from swatplus_bmi.bmi import find_executable
    try:
        find_executable()
    except FileNotFoundError:
        pytest.skip("SWAT+ with the exchange mode not built: uv run swatplus-bmi build --jobs 2")
    if not (swatplus_refdata() / "Osu_1hru").is_dir():
        pytest.skip(f"no SWAT+ refdata at {swatplus_refdata()}: uv run swatplus-bmi build, or set SWATPLUS_REFDATA")
    return swatplus_refdata()


def synthetic_config(**changes):
    """The synthetic example's config, with its run folder under tests/runs."""
    from basinledger import config as C
    cfg = C.load(SYNTHETIC)
    cfg.run_folder = RUNS
    for k, v in changes.items():
        setattr(cfg, k, v)
    return cfg
