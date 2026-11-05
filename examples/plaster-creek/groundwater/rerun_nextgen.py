"""Rerun the calibrated NextGen baseline with CFE's groundwater fluxes in its outputs, for MODFLOW 6's recharge.

nextgen-michigan's calibrated baseline (runs/scenarios/baseline) writes Q_OUT, ET and the groundwater store's level
for each catchment, but not CFE's percolation into the store. This script copies the run's inputs (config, forcing)
into Basin Ledger's cache and adds two CFE outputs to the realization:
- SOIL_TO_GW_FLUX: percolation from the soil into CFE's groundwater store, m per hour: the recharge passed to MODFLOW 6;
- DEEP_GW_TO_CHANNEL_FLUX: the store's outflow to the channel, m per hour: CFE's own base flow, for comparison.
It then runs ngen serially in nextgen-michigan's image (NGIAB v2.1.0 with its WaterUsers component), the same way
nextgen-michigan's scripts/run_ngen.sh does. Nothing else in the run changes, which the script checks: Q_OUT must
equal the baseline's.

    uv run python examples/plaster-creek/groundwater/rerun_nextgen.py [--image nextgen-michigan:dev]

Needs Docker and the image (nextgen-michigan's README, step 2). About a minute on one core.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

from basinledger.config import cache_dir, nextgen_michigan

EXTRA = ["SOIL_TO_GW_FLUX", "DEEP_GW_TO_CHANNEL_FLUX"]


def prepare(src: Path, dst: Path) -> Path:
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for d in ("config", "forcings", "metadata"):
        shutil.copytree(src / d, dst / d)
    path = dst / "config" / "realization.json"
    r = json.loads(path.read_text())
    out = r["global"]["formulations"][0]["params"]["output_variables"]
    for v in EXTRA:
        if v not in out:
            out.append(v)
    path.write_text(json.dumps(r, indent=2))
    return dst


def run(dst: Path, image: str):
    gpkg = next((dst / "config").glob("*.gpkg")).name
    (dst / "outputs" / "ngen").mkdir(parents=True, exist_ok=True)
    (dst / "outputs" / "troute").mkdir(parents=True, exist_ok=True)
    with open(dst / "run.log", "w") as log:
        subprocess.run(["docker", "run", "--rm", "-w", "/ngen/ngen/data", "-v", f"{dst}:/ngen/ngen/data",
                        "--entrypoint", "/dmod/bin/ngen-serial", image, f"config/{gpkg}", "all", f"config/{gpkg}",
                        "all", "config/realization.json"], stdout=log, stderr=subprocess.STDOUT, check=True)


def same_as_baseline(src: Path, dst: Path) -> list[str]:
    """Catchments whose Q_OUT differs from the baseline's (empty when the rerun changed nothing)."""
    bad = []
    for f in sorted((src / "outputs" / "ngen").glob("cat-*.csv")):
        a = [r["Q_OUT"] for r in csv.DictReader(open(f))]
        b = [r["Q_OUT"] for r in csv.DictReader(open(dst / "outputs" / "ngen" / f.name))]
        if a != b:
            bad.append(f.stem)
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default="nextgen-michigan:dev")
    ap.add_argument("--src", default=str(nextgen_michigan() / "runs" / "scenarios" / "baseline"))
    a = ap.parse_args(argv)
    src = Path(a.src)
    dst = cache_dir() / "plaster-creek" / "nextgen-recharge"
    prepare(src, dst)
    run(dst, a.image)
    bad = same_as_baseline(src, dst)
    if bad:
        print(f"Q_OUT differs from the baseline in {bad}", file=sys.stderr)
        return 1
    print(f"NextGen rerun with {', '.join(EXTRA)}: {dst} (Q_OUT identical to the baseline)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
