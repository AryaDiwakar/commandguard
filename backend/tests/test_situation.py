"""Situation gate: normal operation derives a clean ACTIVE/HEALTHY/SAFE state."""
from __future__ import annotations

import math

from conftest import make_generator
from app.schemas.situation import derive_situation


def test_normal_situation_fields():
    frame = make_generator(seed=31).step()
    sit = derive_situation(frame)
    assert sit.machine_id == frame.machine_id
    assert sit.operating_state in ("ACTIVE", "IDLE", "REVERSING", "STANDBY", "IN_TRANSIT")
    assert sit.machine_health == "HEALTHY"
    assert sit.safety_state == "SAFE"
    assert sit.current_risk == "LOW"
    assert sit.active_incidents == []
    assert sit.confidence == 1.0
    assert 0.0 <= sit.task_progress_pct <= 100.0


def test_situation_idle_vs_active():
    gen = make_generator(seed=37)
    seen_states: set[str] = set()
    for _ in range(600):
        frame = gen.step()
        seen_states.add(derive_situation(frame).operating_state)
        assert derive_situation(frame).machine_health == "HEALTHY"
    assert "ACTIVE" in seen_states, "mission should involve active operation"
    assert math.isfinite(gen.dynamics.fuel_level_pct)