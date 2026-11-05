"""Glover and Balmer stream depletion: the closed form and its superposition."""

from __future__ import annotations

import math

import numpy as np
import pytest

from basinledger.analytic import glover_depletion, glover_share


def test_share_limits():
    s = glover_share(np.array([0.0, 1e-6, 1.0, 1e9]), 500.0, 500.0, 0.1)
    assert s[0] == 0.0 and s[1] < 1e-12 and 0 < s[2] < 1 and s[3] == pytest.approx(1.0, abs=1e-3)
    # the closed form at one point: u = sqrt(500^2 0.1 / (4 500 30)) = 0.6455
    assert glover_share(np.array([30.0]), 500.0, 500.0, 0.1)[0] == pytest.approx(math.erfc(math.sqrt(25000 / 60000)))


def test_constant_pumping_is_the_share():
    q = np.full(400, 0.08)
    d = glover_depletion(q, 500.0, 500.0, 0.1)
    np.testing.assert_allclose(d, 0.08 * glover_share(np.arange(1, 401), 500.0, 500.0, 0.1), rtol=1e-12)


def test_superposition_is_linear_and_bounded():
    rng = np.random.default_rng(1)
    q = rng.uniform(0.03, 0.12, 900)
    d = glover_depletion(q, 500.0, 500.0, 0.1)
    assert (d >= -1e-12).all() and (d <= q.max() + 1e-12).all()
    np.testing.assert_allclose(glover_depletion(2 * q, 500.0, 500.0, 0.1), 2 * d, rtol=1e-12)
    # pumping that stops: depletion continues, then decays
    stop = np.r_[np.full(300, 0.1), np.zeros(600)]
    ds = glover_depletion(stop, 500.0, 500.0, 0.1)
    assert ds[310] > 0 and ds[-1] < 0.05 * ds[299]  # the recovery tail decays slowly (about t^-1/2)
