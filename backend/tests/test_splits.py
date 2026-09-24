"""Leakage-safe split audit tests."""
from __future__ import annotations

from app.dataset.splits import config_tag, split_sessions


def _meta(ids, mapping):
    return {sid: {"machine_id": mapping[sid][0], "scenario": mapping[sid][1], "severity": mapping[sid][2]}
            for sid in ids}


def test_session_split_no_row_level_leakage_surfaces():
    meta = _meta(
        [f"s{i}" for i in range(12)],
        {f"s{i}": ("MX-101", "FUEL_LEAK", 0.7) for i in range(8)}
        | {f"s{i}": ("MX-103", None, 0.0) for i in range(8, 12)},
    )
    r = split_sessions(meta, seed=7)
    assert r.audit["no_session_leakage"] is True
    assert r.audit["strict_no_feature_leakage"] is True
    assert r.audit["test_machines_unseen"] == ["MX-103"]
    assert set(r.splits["train"]) & set(r.splits["test"]) == set()


def test_unseen_configs_reserved_for_test():
    meta = _meta(
        [f"s{i}" for i in range(10)],
        {f"s{i}": ("MX-102", "ENGINE_OVERHEAT", 0.8) for i in range(4)}
        | {f"s{i}": ("MX-102", "SENSOR_FAILURE", 0.6) for i in range(4, 7)}
        | {f"s{i}": ("MX-101", None, 0.0) for i in range(7, 10)},
    )
    r = split_sessions(meta, seed=7)
    test_configs = r.audit["test_configs"]
    assert any(c.startswith("SENSOR_FAILURE") for c in test_configs)
    assert not any(c.startswith("SENSOR_FAILURE") for c in r.audit["train_configs"])


def test_split_deterministic_given_seed():
    meta = _meta([f"s{i}" for i in range(10)],
                 {f"s{i}": ("MX-101", None, 0.0) for i in range(10)})
    r1 = split_sessions(meta, seed=9)
    r2 = split_sessions(meta, seed=9)
    assert r1.splits == r2.splits


def test_config_tag_mapping():
    assert config_tag(None, None) == "NORMAL_OPERATION"
    assert config_tag("FUEL_LEAK", 0.2) == "FUEL_LEAK/LOW"
    assert config_tag("FUEL_LEAK", 0.65) == "FUEL_LEAK/MEDIUM"
    assert config_tag("FUEL_LEAK", 0.9) == "FUEL_LEAK/HIGH"