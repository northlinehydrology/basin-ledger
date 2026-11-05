"""Calibration's structure: tables, statistics, simulated values at observations, the forward model."""

from __future__ import annotations

import csv

import numpy as np
import pytest

from basinledger import calibration as K
from conftest import ROOT, RUNS


def test_statistics_on_known_values():
    obs = np.array([1.0, 2.0, 3.0, 4.0])
    assert K.nse(obs, obs) == 1.0
    assert K.nse(np.full(4, obs.mean()), obs) == pytest.approx(0.0)
    assert K.kge(obs, obs) == pytest.approx(1.0)
    assert K.pbias(obs * 1.1, obs) == pytest.approx(10.0)
    assert K.rmse(obs + 0.5, obs) == pytest.approx(0.5) and K.mean_error(obs - 0.25, obs) == pytest.approx(-0.25)
    assert K.log_nse(obs, obs) == 1.0


def test_tables(tmp_path):
    p = tmp_path / "parameters.csv"
    p.write_text("name,model,target,value,lower,upper,transform\nk,modflow6,npf.k:all,5,0.5,50,log\n")
    assert K.read_parameters(p)[0].transform == "log"
    p.write_text("name,model,target,value,lower,upper,transform\nk,modflow6,npf.k:all,500,0.5,50,log\n")
    with pytest.raises(ValueError, match="outside"):
        K.read_parameters(p)
    o = tmp_path / "observations.csv"
    o.write_text("name,kind,object,date,value,weight,source\nq1,flow,cha01,2010-02-01,0.002,1,test\n"
                 "h1,head,pw1,2010-02-01,88.5,2,test\n")
    obs = K.read_observations(o)
    assert [x.kind for x in obs] == ["flow", "head"] and obs[1].weight == 2.0


def test_simulated_and_statistics_by_site():
    obs = [K.Observation("a", "flow", "cha01", "2010-01-02", 1.0), K.Observation("b", "flow", "cha01", "2010-01-03", 3.0),
           K.Observation("c", "head", "pw1", "2010-01-02", 88.0), K.Observation("d", "head", "pw1", "2010-01-03", 89.0)]
    series = {"flow:cha01": [0.5, 1.0, 3.0], "head:pw1": [87.0, 88.5, 89.5]}
    sim = K.simulated(series, ["2010-01-01", "2010-01-02", "2010-01-03"], obs)
    assert sim.tolist() == [1.0, 3.0, 88.5, 89.5]
    st = K.statistics(obs, sim)
    assert st["flow:cha01"]["nse"] == 1.0 and st["head:pw1"]["mean_error"] == pytest.approx(0.5)
    with pytest.raises(KeyError, match="no 'flow:cha09'"):
        K.simulated(series, ["2010-01-01"], [K.Observation("x", "flow", "cha09", "2010-01-01", 1.0)])


def test_forward_model(tmp_path, swatplus):
    """The forward model runs the example and writes simulated values at each observation."""
    import shutil
    d = tmp_path / "synthetic"
    shutil.copytree(ROOT / "examples" / "synthetic", d, ignore=shutil.ignore_patterns("__marimo__"))
    text = (d / "basin.toml").read_text().replace('folder = "../../runs/synthetic"', f'folder = "{RUNS / "fwd"}"')
    text = text.replace('[run]\nfolder', '[run]\ndays = 60\nfolder')
    text += '\n[outputs]\nheads = [{name = "pw1", cell = [0, 20, 28]}]\n'
    (d / "basin.toml").write_text(text)
    o = tmp_path / "obs.csv"
    o.write_text("name,kind,object,date,value,weight,source\nq1,flow,cha01,2010-02-01,0.002,1,synthetic\n"
                 "h1,head,pw1,2010-02-15,88.6,1,synthetic\n")
    out = K.run_forward_model(d / "basin.toml", None, o, tmp_path / "sim.csv")
    rows = list(csv.DictReader(open(out)))
    assert [r["name"] for r in rows] == ["q1", "h1"]
    assert 80 < float(rows[1]["simulated"]) < 100 and float(rows[0]["simulated"]) >= 0
    p = tmp_path / "pars.csv"
    p.write_text("name,model,target,value,lower,upper,transform\nk,modflow6,npf.k:all,5,0.5,50,log\n")
    with pytest.raises(NotImplementedError, match="modflow6"):
        K.run_forward_model(d / "basin.toml", p, o, tmp_path / "sim2.csv")


def test_baseflow_separation():
    # a flow that only recedes is all base flow once the filter settles; a spike adds quick flow only
    q = 10 * 0.95 ** np.arange(200)
    alpha = float(np.quantile(K.recession_ratios(q), 0.9))
    assert alpha == pytest.approx(0.95)
    b = K.eckhardt(q, alpha)
    assert (b <= q + 1e-12).all() and b[-1] / q[-1] > 0.95
    spike = q.copy()
    spike[100] += 50
    bs = K.eckhardt(spike, alpha)
    assert bs[100] < spike[100] / 2 and bs.sum() < spike.sum()
