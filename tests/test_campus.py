"""A data center on a well, driven by SWAT+'s weather, its blowdown back to the stream (testing G7 with G1 and G6):
CoolingWaterBmi (waterledger-models 3.11) on the synthetic two-way example."""

from __future__ import annotations

import numpy as np
import pytest

from basinledger import analysis as A
from basinledger import config as C
from basinledger.driver import Basin
from conftest import ROOT, RUNS

pytestmark = pytest.mark.slow
DAYS = 365
INTAKE = {"dissolved_solids": 0.30, "chloride": 0.012, "phosphorus": 2e-5}  # kg/m3 [A], a sand aquifer


def campus_config(tmp_path):
    pytest.importorskip("waterledger_models.datacenter.bmi")
    (tmp_path / "cooling.yaml").write_text("design: towers\nit_capacity_mw: 0.5\n")
    cfg = C.load(ROOT / "examples" / "synthetic" / "two_way.toml")
    cfg.run_folder = RUNS
    cfg.point_sources = [("blowdown", "cha01")]
    cfg.users = [C.UserConfig(
        name="campus", component="waterledger_models.datacenter.bmi:CoolingWaterBmi", config=tmp_path / "cooling.yaml",
        withdrawal="well:pw1", returns="swat:point_source:blowdown",
        variables={"withdrawal": "data_center_cooling_water__withdrawal_volume_flux",
                   "consumption": "data_center_cooling_water__consumption_volume_flux",
                   "return": "data_center_cooling_water__return_volume_flux",
                   "gain": "data_center_cooling_water__condensate_volume_flux",
                   "power": "data_center__electric_power"},
        forcing={"source": "swatplus", "station": "s35610n127290e"},
        inputs={"atmosphere_bottom_air_water_vapor__relative_saturation": 70.0,  # Osu_1hru generates humidity [A]
                **{f"water_user_intake_water_{c}__mass_concentration": v for c, v in INTAKE.items()}})]
    return cfg


def test_campus_on_swat_weather(swatplus, tmp_path):
    cfg = campus_config(tmp_path)
    base = Basin(cfg, run="campus-base", users=False, days=DAYS)
    base.run()
    tb = base.ledger.table()
    base.finalize()
    b = Basin(cfg, run="campus", users=True, days=DAYS)
    b.run()
    t, flow = b.ledger.table(), np.array(b.series["flow:cha01"]) * 86400.0
    b.finalize()
    w, cons, ret = t["user:campus:withdrawal"], t["user:campus:consumption"], t["user:campus:return"]
    assert w.sum() > 0 and cons.sum() > 0 and ret.sum() > 0
    # the summer evaporates more than the winter: the weather reached the component
    summer, winter = slice(150, 240), slice(0, 60)
    assert cons[summer].mean() > cons[winter].mean()
    # the blowdown reached SWAT+'s channel, whole
    np.testing.assert_allclose(t["route:swat:point_source:blowdown:delivered"], ret, rtol=1e-6, atol=1e-9)
    # dissolved mass: what comes back is no more than what was taken in
    for c, conc in INTAKE.items():
        assert 0 < t[f"user:campus:{c}:kg"].sum() <= conc * w.sum() * (1 + 1e-9)
    # the well's water is all accounted for, and the blowdown raises the stream's concentration
    cap = A.capture(tb, t)
    assert abs(cap["total"]["residual"]) <= 1e-6 * cap["total"]["pumping"]
    out = A.concentration_change(flow, ret, t["user:campus:dissolved_solids:kg"], 0.15)
    assert np.nanmax(out["change_percent"][ret > 0]) > 0
