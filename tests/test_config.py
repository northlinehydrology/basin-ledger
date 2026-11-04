"""An example's config, and its calibration status: a screening run unless its record says calibrated."""

from __future__ import annotations

import pytest

from basinledger import config as C
from conftest import SYNTHETIC


def test_synthetic_example_is_a_screening_run():
    cfg = C.load(SYNTHETIC)
    assert cfg.calibration_record is None
    assert cfg.calibration_status == "screening"
    assert [u.name for u in cfg.users] == ["plant"] and cfg.wells[0].cell == (0, 20, 28)


def with_record(tmp_path, record: str):
    (tmp_path / "calibration").mkdir()
    (tmp_path / "calibration" / "record.toml").write_text(record)
    text = SYNTHETIC.read_text().replace('[[wells]]', '[calibration]\nrecord = "calibration/record.toml"\n\n[[wells]]', 1)
    (tmp_path / "basin.toml").write_text(text)
    return C.load(tmp_path / "basin.toml")


def test_a_calibrated_record_needs_its_statistics(tmp_path):
    cfg = with_record(tmp_path, 'status = "calibrated"\n[calibration]\nperiod = "2000-2010"\n')
    with pytest.raises(ValueError, match="validation"):
        cfg.calibration_status


def test_a_calibrated_record(tmp_path):
    cfg = with_record(tmp_path, 'status = "calibrated"\n[calibration.statistics]\nnse = 0.7\n'
                                '[validation.statistics]\nnse = 0.6\n')
    assert cfg.calibration_status == "calibrated"


def test_an_unknown_status_is_refused(tmp_path):
    cfg = with_record(tmp_path, 'status = "good enough"\n')
    with pytest.raises(ValueError, match="status must be one of"):
        cfg.calibration_status
