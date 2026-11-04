"""Unit factors to the SI units the ledger keeps: m3 s-1, kg s-1, MW, degC, seconds.

Small on purpose. A component that reports a unit not listed here is refused with a clear error rather than guessed at.
"""

from __future__ import annotations

DAY = 86400.0

VOLUME_FLUX = {  # to m3 s-1
    "m3 s-1": 1.0, "m3/s": 1.0, "m^3/s": 1.0,
    "m3 d-1": 1.0 / DAY, "m3/d": 1.0 / DAY, "m3/day": 1.0 / DAY,
    "L s-1": 1e-3, "l/s": 1e-3,
}
VOLUME = {"m3": 1.0, "m^3": 1.0, "L": 1e-3}  # to m3
MASS_FLUX = {  # to kg s-1
    "kg s-1": 1.0, "kg/s": 1.0, "g s-1": 1e-3, "kg d-1": 1.0 / DAY, "kg/d": 1.0 / DAY,
}
POWER = {"MW": 1.0, "kW": 1e-3, "W": 1e-6}  # to MW
TEMPERATURE = {"degC": 0.0, "C": 0.0, "K": -273.15}  # offset to degC
TIME = {"s": 1.0, "h": 3600.0, "hr": 3600.0, "d": DAY, "day": DAY, "days": DAY}  # to seconds


def factor(table: dict[str, float], units: str, what: str) -> float:
    try:
        return table[units.strip()]
    except KeyError:
        raise ValueError(f"{what}: unit {units!r} not recognized (known: {', '.join(table)})") from None


def time_factor(units: str) -> float:
    """Seconds per unit of a BMI time unit string, including 'days since ...' and 'seconds since ...'."""
    u = units.strip().split(" since ")[0].strip()
    u = {"seconds": "s", "second": "s", "hours": "h", "hour": "h"}.get(u, u)
    return factor(TIME, u, "time")
