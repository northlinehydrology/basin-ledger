"""Get the Plaster Creek example's NextGen run.

The calibrated run comes from github.com/northlinehydrology/nextgen-michigan, which builds it with NextGen In A Box
(Docker): the hydrofabric subset and NWM v3 forcing (its README, step 3), the two-stage calibration (steps 4 and 5),
and the calibrated baseline (step 6, ``runs/scenarios/baseline``). That takes Docker, about 4 GB of disk and a few
hours, most of it the forcing download and the calibration, so this script only checks and says what's missing.

    uv run python examples/plaster-creek/fetch.py

``$NEXTGEN_MICHIGAN`` points to the checkout (default ``~/repos/nextgen-michigan``).
"""

from __future__ import annotations

import sys

from basinledger.config import nextgen_michigan

STEPS = """
  git clone https://github.com/northlinehydrology/nextgen-michigan {root}
  then follow its README, steps 1 to 6 (Docker; the calibration takes about an hour per stage on two cores).
  The baseline this example replays is runs/scenarios/baseline; the gage record is
  runs/plaster-cal2/calibration/obs_hourly_discharge_cms.csv."""


def main() -> int:
    root = nextgen_michigan()
    run = root / "runs" / "scenarios" / "baseline"
    obs = root / "runs" / "plaster-cal2" / "calibration" / "obs_hourly_discharge_cms.csv"
    ok = True
    for what, path in (("NextGen run", run / "outputs" / "troute"), ("forcing", run / "forcings" / "forcings.nc"),
                       ("hydrofabric subset", run / "config"), ("gage record", obs)):
        there = path.exists()
        ok &= there
        print(f"{what:20s} {'ok' if there else 'missing'}  {path}")
    if not ok:
        print("To build it:" + STEPS.format(root=root))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
