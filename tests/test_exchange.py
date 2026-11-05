"""Two-way stream-aquifer exchange on the synthetic example (examples/synthetic/two_way.toml).

Osu_1hru over a 10 ha MODFLOW 6 aquifer of the same area. SWAT+'s aquifer passes its recharge through; MODFLOW 6's
river exchange goes back to SWAT+'s channel the next day. Three years.
"""

from __future__ import annotations

import flopy
import numpy as np
import pytest

from basinledger import config as C
from basinledger.coupling import swatplus as S
from basinledger.driver import Basin
from conftest import ROOT, RUNS

pytestmark = pytest.mark.slow

DAYS = 1096


@pytest.fixture(scope="module")
def two_way(swatplus):
    cfg = C.load(ROOT / "examples" / "synthetic" / "two_way.toml")
    cfg.run_folder = RUNS
    b = Basin(cfg, run="two-way", days=DAYS)
    storage = []
    for _ in range(DAYS):
        b.step()
        storage.append(float(b.sw.get("aquifer_water__volume").sum()))
    out = dict(table=b.ledger.table(), due=dict(b.due), ws=b.mf6.ws, storage=np.array(storage))
    b.finalize()
    return out


def test_swat_aquifer_returns_nothing(two_way):
    t = two_way["table"]
    assert (t["swatplus:aquifer_outflow"] == 0).all()


def test_swat_aquifer_keeps_exactly_its_recharge(two_way):
    """No double counting: SWAT+'s aquifer only stores what it sent to MODFLOW 6."""
    t, v = two_way["table"], two_way["storage"]
    eps = np.finfo(np.float32).eps
    # SWAT+ holds storage as a 4-byte real, so a day's change is known to the rounding of the storage itself
    np.testing.assert_allclose(np.diff(v), t["recharge:sent"][1:], rtol=0, atol=4 * eps * v.max())
    assert v[-1] - v[0] == pytest.approx(t["recharge:sent"][1:].sum(), rel=1e-5)


def test_exchange_arrives_the_next_day(two_way):
    t = two_way["table"]
    k = "exchange:cha01:"
    np.testing.assert_allclose(t[k + "due"][1:], t[k + "to_stream"][:-1], rtol=0)
    assert t[k + "due"][0] == 0
    np.testing.assert_allclose(t[k + "due"], t[k + "applied"] + t[k + "shortfall"], rtol=1e-6, atol=1e-6)
    total = t[k + "to_stream"].sum()
    accounted = (t[k + "applied"] + t[k + "shortfall"]).sum() + two_way["due"]["cha01"]
    assert accounted == pytest.approx(total, rel=1e-6)


def test_the_river_gains_and_loses(two_way):
    t = two_way["table"]
    x = t["exchange:cha01:to_stream"]
    assert (x > 0).sum() > 100 and (x < 0).sum() > 10
    applied = t["exchange:cha01:applied"]
    assert (applied > 0).sum() > 100 and (applied < 0).sum() > 0


def test_shortfalls_are_reported_not_hidden(two_way):
    """A losing reach SWAT+ can't supply is entered as a shortfall; SWAT+ never takes more than was due."""
    t = two_way["table"]
    due, applied, short = (t[f"exchange:cha01:{k}"] for k in ("due", "applied", "shortfall"))
    assert (short <= 1e-9).all()
    loss = due < 0
    assert (applied[loss] >= due[loss] * (1 + 1e-6) - 1e-6).all()
    np.testing.assert_allclose(due, applied + short, rtol=1e-6, atol=1e-6)


def test_modflow_budget_closes_and_matches_the_ledger(two_way):
    ws = two_way["ws"]
    cbc = flopy.utils.CellBudgetFile(ws / "gwf.cbc", precision="double")
    terms = {}
    for text in ("STO-SS", "STO-SY", "RCH", "WEL", "RIV"):
        terms[text] = np.array([float(d["q"].sum()) if d.dtype.names else float(np.sum(d))
                                for d in cbc.get_data(text=text)])
    net = sum(terms.values())
    gross = sum(np.abs(v) for v in terms.values())
    assert np.max(np.abs(net) / gross) < 1e-7
    np.testing.assert_allclose(-terms["RIV"], two_way["table"]["exchange:cha01:to_stream"], rtol=1e-12)
    np.testing.assert_allclose(terms["RCH"], two_way["table"]["recharge:sent"], rtol=1e-12, atol=1e-9)


def test_pass_through_settings(tmp_path, swatplus):
    import shutil
    d = tmp_path / "p"
    shutil.copytree(swatplus / "Osu_1hru", d)
    S.aquifer_pass_through(d)
    lines = (d / "aquifer.aqu").read_text().splitlines()
    cols = lines[1].split()
    for l in lines[2:]:
        f = l.split()
        assert float(f[cols.index("flo_min")]) == -1e6 and float(f[cols.index("rchg_dp")]) == 0


def test_stage_from_swat_depth(swatplus):
    """With swatplus-bmi 0.2.0, river stage = RBOT + bed thickness + SWAT+'s channel depth (the pause's, yesterday's)."""
    if not S.has_groundwater_exchange():
        pytest.skip("needs swatplus-bmi 0.2.0 (channel depth)")
    cfg = C.load(ROOT / "examples" / "synthetic" / "two_way.toml")
    cfg.run_folder = RUNS
    cfg.rivers = {"package": "riv", "map": "all:cha01", "stage": "surface_depth", "bed_thickness": 1.0}
    b = Basin(cfg, run="two-way-stage", days=200)
    stages, depths = [], []
    for _ in range(200):
        b.step()
        stages.append(b.mf6.get("STAGE", "GWF", "RIV").copy())
        depths.append(float(b.sw.get(S.DEPTH)[0]))  # day d's depth, which set day d's stage
    rbot = b.mf6.get("RBOT", "GWF", "RIV")
    t = b.ledger.table()
    b.finalize()
    # the stage set on day d is RBOT + 1 m + the depth SWAT+ reported for day d (4-byte reals)
    st = np.array(stages)[:, 0]
    np.testing.assert_allclose(st, rbot[0] + 1.0 + np.array(depths), rtol=0, atol=1e-5)
    assert np.ptp(st) > 0
    assert (t["exchange:cha01:due"] != 0).sum() > 100
