"""Feedback rules: built-in decisions, and the strictest control winning."""

from __future__ import annotations

import math

import pytest

from basinledger import rules as R


def state(day=3, q=0.002, h=88.0):
    return R.State(day=day, flows={"cha01": q}, head_at=lambda c: h)


def test_curtailment():
    assert R.curtailment(state(q=0.001), user="u", channel="cha01", threshold=0.0015) == {"u": {"limit": 0.0}}
    assert R.curtailment(state(q=0.002), user="u", channel="cha01", threshold=0.0015) == {}
    assert R.curtailment(state(day=0, q=0.0), user="u", channel="cha01", threshold=0.0015) == {}  # no yesterday
    with pytest.raises(KeyError):
        R.curtailment(state(), user="u", channel="cha99", threshold=1)


def test_dry_mode_and_drawdown():
    assert R.dry_mode(state(q=0.001), user="u", channel="cha01", threshold=0.0015) == {"u": {"dry_mode": 1.0}}
    assert R.drawdown_limit(state(h=87.9), user="u", cell=(0, 1, 1), head_min=88.0, limit=0.002) == \
        {"u": {"limit": 0.002}}
    assert R.drawdown_limit(state(h=88.1), user="u", cell=(0, 1, 1), head_min=88.0) == {}


def test_strictest_control_wins():
    c = R.combine([{"u": {"limit": 0.003}}, {"u": {"limit": 0.001, "dry_mode": 0.0}}, {"u": {"dry_mode": 1.0}},
                   {"v": {"limit": math.inf}}])
    assert c == {"u": {"limit": 0.001, "dry_mode": 1.0}, "v": {"limit": math.inf}}
