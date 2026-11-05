"""Analytical stream depletion, for comparison with the coupled models.

Glover and Balmer (1954): a well at distance d from a straight, fully penetrating stream in a uniform, infinite
aquifer of transmissivity T and storativity S. After pumping at a constant rate starts, the share of the pumping the
stream supplies at time t is

    q(t) / Q = erfc( sqrt( d^2 S / (4 T t) ) ).

A varying pumping series is handled by superposition: each step's pumping change starts its own response. This is
the method nextgen-michigan uses for wells, and the one Michigan's Water Withdrawal Assessment Tool's depletion is
built on. Its assumptions (one straight stream, no streambed resistance, a uniform aquifer, no other boundaries) are
what a coupled groundwater model relaxes.

Glover, R.E., Balmer, G.G., 1954. River depletion resulting from pumping a well near a river. Eos Trans. AGU 35(3),
468-470. https://doi.org/10.1029/TR035i003p00468
"""

from __future__ import annotations

import math

import numpy as np


def glover_share(t_days: np.ndarray, distance_m: float, transmissivity_m2_d: float, storativity: float) -> np.ndarray:
    """The share of a constant pumping rate the stream supplies t days after it starts (0 at t <= 0)."""
    t = np.asarray(t_days, float)
    out = np.zeros_like(t)
    pos = t > 0
    u = np.sqrt(distance_m ** 2 * storativity / (4.0 * transmissivity_m2_d * t[pos]))
    out[pos] = np.array([math.erfc(x) for x in u])
    return out


def glover_depletion(pumping: np.ndarray, distance_m: float, transmissivity_m2_d: float, storativity: float,
                     dt_days: float = 1.0) -> np.ndarray:
    """Daily stream depletion (same units as ``pumping``) for a pumping series of one value per step, by
    superposition of step changes. Each step's pumping is taken as starting at the step's beginning; the depletion
    reported for a step is at its end."""
    p = np.asarray(pumping, float)
    n = len(p)
    share = glover_share(dt_days * np.arange(1, n + 1), distance_m, transmissivity_m2_d, storativity)
    dp = np.diff(np.r_[0.0, p])
    return np.convolve(dp, share)[:n]
