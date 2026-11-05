"""The utility chain balances by construction: production, delivery and losses; sources by share; sewer to outfall."""

from __future__ import annotations

import pytest

from basinledger.chain import Source, UtilityChain
from basinledger.ledger import Ledger


def city(**kw):
    c = dict(name="city", sources=[Source("well:a", 0.6), Source("swat:place_of_use:intake", 0.4)],
             outfall="swat:point_source:wwtp", losses=0.1, demand=0.002, sewered=0.8, infiltration=0.0001)
    c.update(kw)
    return UtilityChain(**c)


def test_a_day_on_the_chain():
    L = Ledger()
    u = city()
    u.declare(L)
    u.add_user(500.0, 0.0)   # m3 withdrawn from the tap
    u.add_user(0.0, 150.0)   # m3 returned to the sewer
    req = u.close_day(L)
    L.close_day()            # the chain's pairs hold
    existing = 0.002 * 86400
    produced = (existing + 500.0) / 0.9
    assert req["well:a"] == pytest.approx(0.6 * produced)
    assert req["swat:place_of_use:intake"] == pytest.approx(0.4 * produced)
    assert req["swat:point_source:wwtp"] == pytest.approx(existing * 0.8 + 150.0 + 0.0001 * 86400)
    assert L.today("utility:city:losses") == 0.0  # the day is closed; the totals hold it
    assert L.totals()["utility:city:losses"] == pytest.approx(produced * 0.1)


def test_users_start_fresh_each_day():
    L = Ledger()
    u = city(losses=0.0, demand=0.0, infiltration=0.0)
    u.add_user(100.0, 40.0)
    u.close_day(L)
    req = u.close_day(L)
    assert req["well:a"] == 0.0 and req["swat:point_source:wwtp"] == 0.0


@pytest.mark.parametrize("bad", [dict(sources=[Source("well:a", 0.5)]), dict(losses=1.0), dict(sewered=1.2),
                                 dict(sources=[Source("utility:other", 1.0)])])
def test_bad_systems_are_refused(bad):
    with pytest.raises(ValueError):
        city(**bad)
