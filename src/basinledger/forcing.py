"""Hourly weather for water users, from the same forcing the surface model uses.

A user component's weather inputs are set before each of its steps from a forcing source, by CSDMS standard name:

    atmosphere_bottom_air__temperature                        degC     from 2 m air temperature
    atmosphere_bottom_air_water_vapor__relative_saturation    percent  from 2 m specific humidity, temperature and
                                                                       surface pressure

Sources:
- ``nextgen``: an NGIAB run's ``forcings/forcings.nc`` (NWM retrospective or AORC, per catchment, hourly), the
  catchment named in the user's config.

Relative humidity is the ratio of vapor pressure, e = q p / (0.622 + 0.378 q), to saturation vapor pressure over
water, es = 611.2 exp(17.67 T / (T + 243.5)) Pa with T in degC (Bolton 1980), capped at 100%.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np

TEMPERATURE = "atmosphere_bottom_air__temperature"
HUMIDITY = "atmosphere_bottom_air_water_vapor__relative_saturation"


def relative_humidity(q: np.ndarray, p_pa: np.ndarray, t_c: np.ndarray) -> np.ndarray:
    e = q * p_pa / (0.622 + 0.378 * q)
    es = 611.2 * np.exp(17.67 * t_c / (t_c + 243.5))
    return np.minimum(100.0 * e / es, 100.0)


class HourlySeries:
    """Values at hourly times (seconds since the Unix epoch, UTC); value(t) is the hour containing t."""

    def __init__(self, epoch_s: np.ndarray, values: np.ndarray, run_start: dt.datetime):
        self.t0 = float(epoch_s[0])
        if np.any(np.diff(epoch_s) != 3600):
            raise ValueError("forcing must be hourly")
        self.v = values
        self.offset = run_start.replace(tzinfo=dt.timezone.utc).timestamp() - self.t0

    def __call__(self, t_run_s: float) -> float:
        i = int((t_run_s + self.offset) // 3600)
        if not 0 <= i < len(self.v):
            raise IndexError(f"forcing has no hour for {t_run_s} s after the run start")
        return float(self.v[i])


def nextgen_inputs(run_folder: Path, catchment: str, run_start: dt.datetime) -> dict[str, HourlySeries]:
    """Hourly temperature and humidity for one catchment of an NGIAB run, as user inputs."""
    import netCDF4

    with netCDF4.Dataset(Path(run_folder) / "forcings" / "forcings.nc") as d:
        ids = [str(i) for i in d["ids"][:]]
        if catchment not in ids:
            raise KeyError(f"no forcing for {catchment!r} (catchments: {', '.join(ids)})")
        k = ids.index(catchment)
        t = np.asarray(d["Time"][k, :], dtype=float)
        tk = np.asarray(d["TMP_2maboveground"][k, :], dtype=float)
        q = np.asarray(d["SPFH_2maboveground"][k, :], dtype=float)
        p = np.asarray(d["PRES_surface"][k, :], dtype=float)
    tc = tk - 273.15
    return {TEMPERATURE: HourlySeries(t, tc, run_start),
            HUMIDITY: HourlySeries(t, relative_humidity(q, p, tc), run_start)}
