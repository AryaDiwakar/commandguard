"""Schema gate: required 8 columns present with correct types/semantics."""
from __future__ import annotations

import re
from datetime import datetime

from conftest import make_generator
from app.schemas.telemetry import REQUIRED_COLUMNS
from app.simulation.generator import MachineGenerator


def test_required_columns_present():
    gen: MachineGenerator = make_generator(seed=5)
    frame = gen.step()
    row = frame.to_dict()
    for col in REQUIRED_COLUMNS:
        assert col in row, f"missing required column {col}"


def test_required_column_types():
    frame = make_generator(seed=6).step()
    row = frame.to_dict()
    assert isinstance(row["Timestamp"], str)
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", row["Timestamp"])
    assert isinstance(row["Machine_ID"], str) and row["Machine_ID"]
    assert isinstance(row["Operator_ID"], str) and row["Operator_ID"]
    assert isinstance(row["Engine_Hours"], float)
    assert isinstance(row["Fuel_Used_L"], float)
    assert isinstance(row["Load_Cycles"], int)
    assert isinstance(row["Idling_Time_min"], float)
    assert row["Seatbelt_Status"] in ("Fastened", "Unfastened")
    assert isinstance(row["Safety_Alert_Triggered"], bool)


def test_normal_frame_is_clean():
    frame = make_generator(seed=8).step()
    assert frame.scenario_type.value == "NORMAL_OPERATION"
    assert frame.phase.value == "NORMAL"
    assert frame.anomaly_label is False
    assert frame.incident_type is None
    assert frame.safety_alert_triggered is False
    assert frame.diagnostics_consistency > 0.99


def test_monotonic_counters():
    gen = make_generator(seed=9)
    prev = gen.step()
    for _ in range(30):
        cur = gen.step()
        assert cur.engine_hours >= prev.engine_hours
        assert cur.fuel_used_l >= prev.fuel_used_l
        assert cur.operating_hours >= prev.operating_hours
        assert cur.load_cycles >= prev.load_cycles
        prev = cur