"""SWAT+ -> MODFLOW 6, one way, on the synthetic example: recharge and pumping arrive whole, and the budget closes.

Three years of Osu_1hru (2010-2012) drive the synthetic aquifer, once with the synthetic user pumping and once without.
The driver's ledger already refuses any day where a pair differs; these tests check the same quantities again from
MODFLOW 6's own budget file, and check that the budget closes on every day.
"""

from __future__ import annotations

import shutil

import flopy
import numpy as np
import pytest

from basinledger.driver import Basin
from conftest import synthetic_config

DAYS = 3 * 365 + 1


def osu_printing_aquifers(refdata, dest):
    """Osu_1hru for 2010-2012 only, with the aquifer's daily output on from the first day (no other change).
    SWAT+ reads print.prt's rows by position unless object labels are on, so labels are turned on."""
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(refdata / "Osu_1hru", dest)
    prt = dest / "print.prt"
    lines = prt.read_text().splitlines()
    lines[2] = "0" + lines[2][1:]  # nyskip: print from the first year
    f = lines[6].split()
    lines[6] = f"{f[0]:<14}{'y':<14}{f[2]:<14}"  # use_obj_labels: SWAT+ reads the rows by name, not position
    for i, line in enumerate(lines):
        if line.split()[:1] == ["aquifer"]:
            lines[i] = f"{'aquifer':<24}" + "".join(f"{x:>14}" for x in "yny") + f"{'y':>14}"
    prt.write_text("\n".join(lines) + "\n")
    sim = dest / "time.sim"
    lines = sim.read_text().splitlines()
    lines[2] = f"{0:>8}{2010:>11}{0:>10}{2012:>10}{lines[2].split()[4]:>10}"
    sim.write_text("\n".join(lines) + "\n")
    return dest


def run(name, users, project=None):
    cfg = synthetic_config(**({"swat_project": project} if project else {}))
    b = Basin(cfg, run=name, users=users, days=DAYS)
    b.run()
    table = b.ledger.table()
    ws, swat_dir = b.mf6.ws, b.swat.run_dir
    b.finalize()
    return table, ws, swat_dir


@pytest.fixture(scope="module")
def pumping(swatplus):
    from conftest import RUNS
    return run("pumping", users=True, project=osu_printing_aquifers(swatplus, RUNS / "Osu_1hru-aquifer-daily"))


@pytest.fixture(scope="module")
def base(swatplus):
    return run("base", users=False)


def budget(ws):
    cbc = flopy.utils.CellBudgetFile(ws / "gwf.cbc", precision="double")
    out = {}
    for text in ("STO-SS", "STO-SY", "RCH", "WEL", "RIV"):
        rows = []
        for d in cbc.get_data(text=text):
            rows.append(float(d["q"].sum()) if d.dtype.names else float(np.sum(d)))
        out[text] = np.array(rows)
    return out


def test_every_day_ran(pumping):
    table, ws, _ = pumping
    assert len(table["recharge:sent"]) == DAYS
    assert len(budget(ws)["RCH"]) == DAYS


def test_recharge_sent_equals_recharge_received(pumping):
    table, ws, _ = pumping
    assert table["recharge:sent"].sum() > 0
    np.testing.assert_allclose(table["recharge:received"], table["recharge:sent"], rtol=1e-12, atol=1e-9)
    np.testing.assert_allclose(budget(ws)["RCH"], table["recharge:sent"], rtol=1e-12, atol=1e-9)


def test_recharge_is_swat_recharge(pumping):
    """The depth SWAT+ wrote for its aquifer, times the mapped area, is what MODFLOW 6 got."""
    table, ws, swat_dir = pumping
    lines = (swat_dir / "aquifer_day.txt").read_text().splitlines()
    col = lines[1].split().index("rchrg")
    rchrg_mm = np.array([float(l.split()[col]) for l in lines[3:3 + DAYS]])  # SWAT+ prints mm, 5 significant digits
    area = 41 * 41 * 50.0 * 50.0
    assert len(rchrg_mm) == DAYS
    np.testing.assert_allclose(table["recharge:sent"], rchrg_mm / 1000 * area, rtol=1e-4, atol=0.5e-3 / 1000 * area)


def test_well_pumps_what_the_user_withdrew(pumping):
    table, ws, _ = pumping
    w = table["user:plant:withdrawal"]
    assert w.min() > 0
    np.testing.assert_allclose(table["well:pw1:pumped"], w, rtol=1e-12)
    np.testing.assert_allclose(-budget(ws)["WEL"], w, rtol=1e-12)


def test_user_water_goes_somewhere(pumping):
    table, _, _ = pumping
    lhs = table["user:plant:withdrawal"] + table["user:plant:gain"]
    rhs = table["user:plant:consumption"] + table["user:plant:return"]
    np.testing.assert_allclose(lhs, rhs, rtol=1e-12)
    np.testing.assert_allclose(table["outfall:creek"], table["user:plant:return"], rtol=0)


@pytest.mark.parametrize("which", ["pumping", "base"])
def test_modflow_budget_closes_every_day(which, request):
    _, ws, _ = request.getfixturevalue(which)
    b = budget(ws)
    net = sum(b.values())  # storage, recharge, wells, river: inflow positive
    gross = sum(np.abs(v) for v in b.values())
    assert np.max(np.abs(net) / gross) < 1e-7
    lst = flopy.utils.Mf6ListBudget(ws / "gwf.lst")
    pd = lst.get_incremental()["PERCENT_DISCREPANCY"]
    assert np.max(np.abs(pd)) <= 0.01  # printed to two decimals


def test_pumping_draws_down_and_depletes_the_river(pumping, base):
    _, wp, _ = pumping
    _, wb, _ = base
    hp = flopy.utils.HeadFile(wp / "gwf.hds").get_alldata()[:, 0]
    hb = flopy.utils.HeadFile(wb / "gwf.hds").get_alldata()[:, 0]
    drawdown = hb - hp
    assert drawdown[-1, 20, 28] > drawdown[-1, 20, 5] > 0
    riv_p, riv_b = budget(wp)["RIV"], budget(wb)["RIV"]  # negative: water to the river
    depletion = riv_p - riv_b  # less water reaching the river
    pumped = -budget(wp)["WEL"]
    assert 0 < depletion.sum() < pumped.sum()
    assert depletion[-365:].sum() / pumped[-365:].sum() > depletion[:365].sum() / pumped[:365].sum()
