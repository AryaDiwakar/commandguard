"""Physics gate: conservation, dynamics sanity, no NaN / invariant violations."""
from __future__ import annotations

import math

from conftest import make_generator
from app.simulation.generator import MachineGenerator


def _run(gen: MachineGenerator, n: int):
    frames = [gen.step() for _ in range(n)]
    return gen, frames


def test_fuel_conserved_in_world():
    gen, frames = _run(make_generator(seed=11), 300)
    fuel_accounted = sum(f.fuel_consumption_rate_lph * (1.0 / 3600.0) for f in frames)
    consumed = frames[-1].fuel_used_l  # fuel_used starts at 0.0 each session
    assert abs(consumed - fuel_accounted) < 5e-3, f"{consumed} vs {fuel_accounted}"


def test_fuel_level_matches_integral():
    gen, frames = _run(make_generator(seed=13), 240)
    cap = gen.machine_cfg.fuel_capacity_l
    expect_l = gen.dynamics.fuel_l
    expect_pct = (expect_l / cap) * 100.0
    # frame value is rounded to 3 decimals; allow rounding slack
    assert abs(frames[-1].fuel_level_pct - expect_pct) < 5e-3


def test_no_nan_and_invariants():
    _, frames = _run(make_generator(seed=17), 120)
    for f in frames:
        d = f.to_dict()
        for k, v in d.items():
            if isinstance(v, float):
                assert math.isfinite(v), f"{k}={v}"
        assert 0.0 <= f.fuel_level_pct <= 100.0
        assert 0.0 <= f.engine_rpm <= 9999.0
        assert -20.0 <= f.engine_temperature_c <= 160.0
        assert -20.0 <= f.coolant_temperature_c <= 160.0
        assert 90.0 <= f.oil_pressure_kpa <= 520.0
        assert 0.0 <= f.hydraulic_pressure_bar <= 350.0
        assert 18.0 <= f.battery_voltage_v <= 28.5
        assert f.machine_speed_kph >= 0.0
        assert f.seatbelt_status in ("Fastened", "Unfastened")


def test_speed_load_correlate_with_state():
    gen, frames = _run(make_generator(seed=19, speed=1.0), 900)
    # at least some active (high load) and some idle/break frames exist
    active = [f for f in frames if f.machine_state.value == "ACTIVE"]
    idle = [f for f in frames if f.machine_state.value in ("IDLE", "BREAK")]
    assert len(active) > 20 and len(idle) > 0
    avg_load_active = sum(f.engine_load_pct for f in active) / len(active)
    assert avg_load_active > 50.0
    if idle:
        avg_rpm_idle = sum(f.engine_rpm for f in idle) / len(idle)
        assert avg_rpm_idle < 1000.0


def test_engine_hours_advance():
    gen, frames = _run(make_generator(seed=23), 180)
    delta = frames[-1].engine_hours - frames[0].engine_hours
    assert 0.03 < delta < 0.06  # 180s ≈ 180/3600 h


def test_long_run_no_blowup():
    gen, frames = _run(make_generator(seed=29), 3600)
    assert gen.dynamics.fuel_level_pct > 0.0  # slow normal burn, not drained
    assert 30.0 < frames[-1].engine_temperature_c < 110.0