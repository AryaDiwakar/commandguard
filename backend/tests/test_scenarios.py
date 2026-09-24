"""Phase 2 scenario-injector signature tests.

Each scenario must produce a *causally consistent, time-continuous* signature —
never a hard teleport of values. Detectors in Phase 3 are validated against
exactly these behaviours.
"""
from __future__ import annotations

import statistics
from typing import Any

import pytest

from app.schemas.telemetry import Phase, ScenarioType
from app.simulation.generator import MachineGenerator
from app.simulation.scenarios import make_spec

TRACE_LEN = 900
SPEC_KW = dict(severity=0.7, onset_offset_s=180, ramp_s=20, duration_s=520, abate_s=60)


def run(st: ScenarioType, seed: int = 3, **kw) -> tuple[list[Any], MachineGenerator]:
    spec = make_spec(st, **{**SPEC_KW, **kw})
    gen = MachineGenerator(seed=seed, scenario=spec)
    frames = [gen.step() for _ in range(TRACE_LEN)]
    return frames, gen


def windows(frames):
    anom = [f for f in frames if f.anomaly_label]
    norm = [f for f in frames if not f.anomaly_label]
    return anom, norm


def p90(xs):
    xs = sorted(xs)
    return xs[-30]


# ---------------------------------------------------------------------------
def test_all_injectable_types_cover_arc():
    injectable = [
        ScenarioType.FUEL_LEAK, ScenarioType.ENGINE_OVERHEAT, ScenarioType.HYDRAULIC_FAILURE,
        ScenarioType.PROXIMITY_HAZARD, ScenarioType.SEATBELT_VIOLATION, ScenarioType.EXCESSIVE_IDLE,
        ScenarioType.UNSAFE_OPERATION, ScenarioType.SENSOR_FAILURE, ScenarioType.MULTI_FACTOR_INCIDENT,
    ]
    for st in injectable:
        frames, _ = run(st)
        phases = {f.phase for f in frames}
        assert Phase.NORMAL in phases
        assert Phase.ONSET in phases
        assert Phase.ANOMALY in phases
        assert Phase.RESPONSE in phases
        assert Phase.RESOLVED in phases
        anom, norm = windows(frames)
        assert len(anom) > 50, st
        assert len(norm) > 100, st
        # labels reset on the recovery tail
        assert frames[-1].phase == Phase.RESOLVED
        assert frames[-1].anomaly_label is False
        assert frames[-1].incident_type is None


def test_fuel_leak_drains_beyond_reported_consumption():
    frames, gen = run(ScenarioType.FUEL_LEAK)
    anom = [f for f in frames if f.anomaly_label]
    first_anom_i = next(i for i, f in enumerate(frames) if f.anomaly_label)
    base = frames[:first_anom_i]  # contiguous pre-onset baseline

    def slope_min(seq):
        dt_min = (seq[-1].timestamp_ms - seq[0].timestamp_ms) / 60000.0
        return (seq[-1].fuel_level_pct - seq[0].fuel_level_pct) / dt_min

    a_slope, n_slope = slope_min(anom), slope_min(base)
    assert a_slope < -0.1                       # clearly draining
    assert a_slope < n_slope * 1.6              # faster than normal operations justify

    # the loss exceeds what the REPORTED consumption rate explains (the leak)
    hours = (anom[-1].timestamp_ms - anom[0].timestamp_ms) / 3_600_000.0
    cons_l = statistics.mean(f.fuel_consumption_rate_lph for f in anom) * hours
    cons_drop_pct = (cons_l / gen.machine_cfg.fuel_capacity_l) * 100.0
    obs_drop_pct = anom[0].fuel_level_pct - anom[-1].fuel_level_pct
    assert obs_drop_pct > cons_drop_pct * 1.4
    assert gen.dynamics.fuel_leaked_l > 1.0


def test_engine_overheat_rises_with_degraded_cooling():
    frames, _ = run(ScenarioType.ENGINE_OVERHEAT)
    anom, norm = windows(frames)
    a_peak = max(f.engine_temperature_c for f in anom)
    n_peak = max(f.engine_temperature_c for f in norm)
    assert a_peak > n_peak + 6.0
    a_cool = statistics.mean(f.cooling_performance_pct for f in anom)
    n_cool = statistics.mean(f.cooling_performance_pct for f in norm)
    assert a_cool < n_cool * 0.9


def test_hydraulic_failure_sags_pressure_and_heats_oil():
    frames, _ = run(ScenarioType.HYDRAULIC_FAILURE)
    anom, norm = windows(frames)
    a_min = min(f.hydraulic_pressure_bar for f in anom)
    n_min = min(f.hydraulic_pressure_bar for f in norm)
    assert a_min < n_min * 0.7
    a_oil = statistics.mean(f.hydraulic_temperature_c for f in anom)
    n_oil = statistics.mean(f.hydraulic_temperature_c for f in norm)
    assert a_oil > n_oil + 1.0


def test_proximity_hazard_drops_into_unsafe_zone():
    frames, _ = run(ScenarioType.PROXIMITY_HAZARD)
    anom, norm = windows(frames)
    assert min(f.proximity_distance_m for f in anom) <= 8.0
    assert min(f.proximity_distance_m for f in anom) < min(f.proximity_distance_m for f in norm)
    assert sum(1 for f in anom if f.nearby_machine_count >= 1) > len(anom) // 2


def test_seatbelt_violation_while_moving():
    frames, _ = run(ScenarioType.SEATBELT_VIOLATION)
    anom, _ = windows(frames)
    moving_unfastened = [
        f for f in anom if f.machine_speed_kph > 0.1 and f.seatbelt_status == "Unfastened"
    ]
    assert len(moving_unfastened) > 10
    norm_moving = sum(1 for f in frames if not f.anomaly_label and f.seatbelt_status == "Unfastened")
    assert norm_moving == 0


def test_excessive_idle_accumulates_without_motion():
    frames, _ = run(ScenarioType.EXCESSIVE_IDLE)
    anom, _ = windows(frames)
    assert max(f.idling_time_min for f in anom) >= 4.0
    assert sum(1 for f in anom if f.machine_speed_kph > 0.1) < len(anom) * 0.1


def test_unsafe_operation_speed_bursts():
    frames, _ = run(ScenarioType.UNSAFE_OPERATION)
    anom, _ = windows(frames)
    assert max(f.machine_speed_kph for f in anom) > 12.5
    assert sum(1 for f in anom if f.machine_speed_kph > 12.5) >= 3


def test_sensor_failure_observed_drifts_world_holds():
    gen = MachineGenerator(seed=3, scenario=make_spec(ScenarioType.SENSOR_FAILURE, **SPEC_KW))
    observed, world, flags = [], [], []
    for _ in range(TRACE_LEN):
        f = gen.step()
        observed.append(f.fuel_level_pct)             # biased sensor reading (frame)
        world.append(gen.dynamics.fuel_level_pct)     # true physics tank at the same tick
        flags.append(f)
    anom_idx = [i for i, f in enumerate(flags) if f.anomaly_label]
    assert len(anom_idx) > 50
    assert statistics.mean(observed[i] for i in anom_idx) < statistics.mean(world[i] for i in anom_idx) - 1.0
    assert any(flags[i].diagnostics_consistency < 0.9 for i in anom_idx)


def test_multi_factor_combines_thermal_load_and_ambient():
    frames, _ = run(ScenarioType.MULTI_FACTOR_INCIDENT)
    anom, norm = windows(frames)
    m_load = p90([f.engine_load_pct for f in anom])
    m_amb = statistics.mean(f.ambient_temperature_c for f in anom)
    n_amb = statistics.mean(f.ambient_temperature_c for f in norm)
    m_peak = max(f.engine_temperature_c for f in anom)
    assert m_amb > n_amb + 1.0                    # ambient add
    assert m_peak > 100.0                          # severe thermal
    o_frames, _ = run(ScenarioType.ENGINE_OVERHEAT)
    o_peak = max(f.engine_temperature_c for f in o_frames if f.anomaly_label)
    assert m_peak > o_peak                          # worse than single-factor overheat
    # load elevation visible in the p90 band
    o_p90 = p90([f.engine_load_pct for f in o_frames if f.anomaly_label])
    assert m_load > o_p90 - 1.0               # equal-or-higher working load


def test_severity_buckets_map_to_labels():
    import app.simulation.thresholds as th
    assert th.severity_bucket(0.2) == "LOW"
    assert th.severity_bucket(0.65) == "MEDIUM"
    assert th.severity_bucket(0.7) == "HIGH"


def test_scenario_determinism_and_ground_truth_timestamps():
    f1, _ = run(ScenarioType.FUEL_LEAK, seed=11)
    f2, _ = run(ScenarioType.FUEL_LEAK, seed=11)
    assert [f.to_dict() for f in f1] == [f.to_dict() for f in f2]
    f3, _ = run(ScenarioType.FUEL_LEAK, seed=12)
    assert f1[0].to_dict() != f3[0].to_dict()
    anom = [f for f in f1 if f.anomaly_label]
    assert any(f.incident_type == ScenarioType.FUEL_LEAK.value for f in anom)
    assert all(f.anomaly_onset_t is not None for f in anom)
    assert all(f.resolve_t is not None for f in anom)
    assert all(f.detect_t is None for f in anom)   # engine detection arrives in Phase 3