"""Phase 2 scenario injectors (incident-time evolution, not one-shot flags).

Each injector wraps a *scripted anomaly* described by :class:`ScenarioSpec`.
It layers a perturbation on top of the existing normal-operation ODEs in
``physics.MachineDynamics`` - never a hard teleport of values - so a fuel leak
shows up as a tank that drains *faster than the reported consumption* would
justify, exactly as it would on real hardware.

The generator (``simulation/generator.py::MachineGenerator``) owns the injector,
merges the returned :class:`Perturbation` with the mission/environment state,
and stamps ground-truth fields (scenario_type / phase / anomaly_label / onset /
resolve) that are *evaluation metadata only*.

Every injector is deterministic given the session RNG.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from app.schemas.telemetry import Phase, ScenarioType, WeatherEvent
from app.simulation.thresholds import severity_bucket


# ---------------------------------------------------------------------------
# Plan / timeline
# ---------------------------------------------------------------------------
@dataclass
class ScenarioSpec:
    """Scripted anomaly timeline (sim-seconds relative to session start)."""

    scenario_type: ScenarioType
    severity: float = 0.7            # 0..1, clamped
    onset_offset_s: float = 600.0    # normal lead-in before the anomaly starts
    ramp_s: float = 30.0             # onset growth
    duration_s: float = 300.0        # sustained anomaly
    abate_s: float = 90.0            # response/recovery
    params: dict[str, Any] = field(default_factory=dict)
    weather: WeatherEvent = WeatherEvent.NONE

    def __post_init__(self) -> None:
        self.severity = max(0.0, min(1.0, self.severity))

    @property
    def end_s(self) -> float:
        return self.onset_offset_s + self.ramp_s + self.duration_s + self.abate_s


def default_plan(scenario_type: ScenarioType) -> dict[str, float | str]:
    return {
        ScenarioType.FUEL_LEAK:          dict(onset_offset_s=720, ramp_s=20,   duration_s=400, abate_s=90),
        ScenarioType.ENGINE_OVERHEAT:    dict(onset_offset_s=900, ramp_s=90,   duration_s=380, abate_s=120),
        ScenarioType.HYDRAULIC_FAILURE:  dict(onset_offset_s=840, ramp_s=60,   duration_s=300, abate_s=90),
        ScenarioType.PROXIMITY_HAZARD:   dict(onset_offset_s=700, ramp_s=40,   duration_s=240, abate_s=60),
        ScenarioType.SEATBELT_VIOLATION: dict(onset_offset_s=560, ramp_s=10,   duration_s=180, abate_s=10),
        ScenarioType.EXCESSIVE_IDLE:     dict(onset_offset_s=1080, ramp_s=15,  duration_s=420, abate_s=20),
        ScenarioType.UNSAFE_OPERATION:   dict(onset_offset_s=780, ramp_s=20,   duration_s=360, abate_s=40),
        ScenarioType.SENSOR_FAILURE:     dict(onset_offset_s=850, ramp_s=30,   duration_s=450, abate_s=90),
        ScenarioType.BATTERY_ANOMALY:    dict(onset_offset_s=820, ramp_s=45,   duration_s=420, abate_s=90),
        ScenarioType.MULTI_FACTOR_INCIDENT: dict(onset_offset_s=950, ramp_s=90, duration_s=480, abate_s=150),
        # Normal operation is the absence of a scripted anomaly; the window is
        # effectively never reached and no injector is built.
        ScenarioType.NORMAL_OPERATION:  dict(onset_offset_s=60000, ramp_s=1, duration_s=0, abate_s=1),
    }[scenario_type]


# ---------------------------------------------------------------------------
# Perturbation bundle
# ---------------------------------------------------------------------------
@dataclass
class Perturbation:
    params: dict[str, float] = field(default_factory=dict)      # physics biases
    cmd: dict[str, Any] = field(default_factory=dict)           # override command keys
    cmd_add: dict[str, float] = field(default_factory=dict)     # additive to command
    env: dict[str, Any] = field(default_factory=dict)           # replace env keys
    env_add: dict[str, float] = field(default_factory=dict)     # additive to env
    sensor_bias: dict[str, float] = field(default_factory=dict) # observed-vs-world drift
    seatbelt_off: bool = False
    proximity_override: float | None = None
    nearby_override: int | None = None


# ---------------------------------------------------------------------------
# Base injector
# ---------------------------------------------------------------------------
_WEATHER_ENV: dict[WeatherEvent, dict[str, Any]] = {
    WeatherEvent.RAIN: dict(rainfall_mmh=8.0, humidity_pct=88.0, visibility_m=2500.0),
    WeatherEvent.HEAVY_RAIN: dict(rainfall_mmh=18.0, humidity_pct=95.0, visibility_m=900.0),
    WeatherEvent.FOG: dict(rainfall_mmh=0.0, humidity_pct=92.0, visibility_m=400.0),
    WeatherEvent.HOT: dict(humidity_pct=38.0),
    WeatherEvent.HIGH_WIND: dict(visibility_m=6000.0),
}


class ScenarioInjector:
    scenario_type = ScenarioType.NORMAL_OPERATION

    def __init__(self, spec: ScenarioSpec):
        self.spec = spec

    # ---------------- timeline ---------------------------------------------
    def envelope(self, t: float) -> float:
        s = self.spec
        if t < s.onset_offset_s:
            return 0.0
        if t < s.onset_offset_s + s.ramp_s:
            return (t - s.onset_offset_s) / max(1.0, s.ramp_s)
        amp_end = s.onset_offset_s + s.ramp_s + s.duration_s
        if t < amp_end:
            return 1.0
        if t < s.end_s:
            return 1.0 - (t - amp_end) / max(1.0, s.abate_s)
        return 0.0

    def phase(self, t: float) -> Phase:
        s = self.spec
        if t < s.onset_offset_s:
            return Phase.NORMAL
        if t < s.onset_offset_s + s.ramp_s:
            return Phase.ONSET
        amp_end = s.onset_offset_s + s.ramp_s + s.duration_s
        if t < amp_end:
            return Phase.ANOMALY
        if t < s.end_s:
            return Phase.RESPONSE
        return Phase.RESOLVED

    # ---------------- perturbation ------------------------------------------
    def perturb(self, t: float, rng: random.Random, cmd: dict, env: dict, dynamics) -> Perturbation:
        raise NotImplementedError

    # ---------------- weather backdrop ----------------------------------------
    def _apply_weather(self, p: Perturbation, e: float) -> None:
        if self.spec.weather is WeatherEvent.NONE or e <= 0.0:
            return
        target = _WEATHER_ENV[self.spec.weather]
        for k, v in target.items():
            p.env[k] = v if k == "humidity_pct" else v * max(e, 0.2)
        p.env["weather_event"] = self.spec.weather
        if self.spec.weather in (WeatherEvent.RAIN, WeatherEvent.HEAVY_RAIN):
            p.env["terrain_condition"] = "MUDDY" if e > 0.45 else "WET"
        if self.spec.weather is WeatherEvent.HOT:
            p.env_add["ambient_temperature_c"] = 7.0 * e


def build_injector(spec: ScenarioSpec) -> ScenarioInjector:
    factory: dict[type, type[ScenarioInjector]] = {
        ScenarioType.FUEL_LEAK: FuelLeakInjector,
        ScenarioType.ENGINE_OVERHEAT: EngineOverheatInjector,
        ScenarioType.HYDRAULIC_FAILURE: HydraulicFailureInjector,
        ScenarioType.PROXIMITY_HAZARD: ProximityHazardInjector,
        ScenarioType.SEATBELT_VIOLATION: SeatbeltViolationInjector,
        ScenarioType.EXCESSIVE_IDLE: ExcessiveIdleInjector,
        ScenarioType.UNSAFE_OPERATION: UnsafeOperationInjector,
        ScenarioType.SENSOR_FAILURE: SensorFailureInjector,
        ScenarioType.BATTERY_ANOMALY: BatteryAnomalyInjector,
        ScenarioType.MULTI_FACTOR_INCIDENT: MultiFactorInjector,
    }
    return factory[spec.scenario_type](spec)


def make_spec(
    scenario_type: ScenarioType,
    severity: float = 0.7,
    onset_offset_s: float | None = None,
    **overrides: Any,
) -> ScenarioSpec:
    plan = default_plan(scenario_type)
    if onset_offset_s is not None:
        plan["onset_offset_s"] = onset_offset_s
    plan.update(overrides)
    return ScenarioSpec(scenario_type=scenario_type, severity=severity, **plan)


# ---------------------------------------------------------------------------
# Concrete injectors
# ---------------------------------------------------------------------------
class FuelLeakInjector(ScenarioInjector):
    """Tank drains faster than reported consumption justifies."""

    scenario_type = ScenarioType.FUEL_LEAK

    def perturb(self, t, rng, cmd, env, dynamics) -> Perturbation:
        e = self.envelope(t)
        p = Perturbation()
        if e <= 0.0:
            return p
        s = self.spec.severity
        # Deliberately dramatic for the operator demo: severity 0.85 is
        # approximately a 4.5% tank loss per simulated minute, clearly above
        # normal consumption while still leaving a visible detection window.
        p.params["fuel_leak_lph"] = (300.0 + 2200.0 * s) * e
        p.params["fuel_rate_bias"] = 0.02 * s * e
        self._apply_weather(p, e)
        return p


class EngineOverheatInjector(ScenarioInjector):
    """Rising engine thermal state from degraded cooling / bias."""

    scenario_type = ScenarioType.ENGINE_OVERHEAT

    def perturb(self, t, rng, cmd, env, dynamics) -> Perturbation:
        e = self.envelope(t)
        p = Perturbation()
        if e <= 0.0:
            return p
        s = self.spec.severity
        p.params["thermal_bias"] = (8.0 + 22.0 * s) * e
        p.params["cooling_perf_mult"] = 1.0 - 0.5 * s * e
        p.params["thermal_tau_mult"] = 1.0 - 0.35 * s * e
        self._apply_weather(p, e)
        return p


class HydraulicFailureInjector(ScenarioInjector):
    """Hydraulic pressure sags while the operator compensates with more load."""

    scenario_type = ScenarioType.HYDRAULIC_FAILURE

    def perturb(self, t, rng, cmd, env, dynamics) -> Perturbation:
        e = self.envelope(t)
        p = Perturbation()
        if e <= 0.0:
            return p
        s = self.spec.severity
        p.params["hyd_gain_mult"] = -(0.30 + 0.40 * s) * e
        p.params["hyd_temp_bias"] = (4.0 + 7.0 * s) * e
        p.cmd_add["load_pct"] = 6.0 * e
        self._apply_weather(p, e)
        return p


class ProximityHazardInjector(ScenarioInjector):
    """A nearby asset/worker closes in - proximity drops toward the danger zone."""

    scenario_type = ScenarioType.PROXIMITY_HAZARD

    def perturb(self, t, rng, cmd, env, dynamics) -> Perturbation:
        e = self.envelope(t)
        p = Perturbation()
        if e <= 0.0:
            return p
        s = self.spec.severity
        min_dist = 2.0 + 3.0 * (1.0 - s)
        p.proximity_override = max(min_dist, 34.0 * (1.0 - e) + min_dist * e)
        p.nearby_override = 1
        self._apply_weather(p, e)
        return p


class SeatbeltViolationInjector(ScenarioInjector):
    """Belt unfastened while the machine is moving."""

    scenario_type = ScenarioType.SEATBELT_VIOLATION

    def perturb(self, t, rng, cmd, env, dynamics) -> Perturbation:
        e = self.envelope(t)
        p = Perturbation()
        if e <= 0.0:
            return p
        p.seatbelt_off = True
        p.cmd_add["speed_kph"] = 0.5 * e
        self._apply_weather(p, e)
        return p


class ExcessiveIdleInjector(ScenarioInjector):
    """Engine kept running while the machine sits - sustained idle accumulation."""

    scenario_type = ScenarioType.EXCESSIVE_IDLE

    def perturb(self, t, rng, cmd, env, dynamics) -> Perturbation:
        e = self.envelope(t)
        p = Perturbation()
        if e <= 0.0:
            return p
        p.cmd = {"state": "IDLE", "load_pct": 4.0, "hyd_bar": 26.0,
                 "speed_kph": 0.0, "rpm_norm": 0.35, "stage": "IDLE-EVENT"}
        self._apply_weather(p, e)
        return p


class UnsafeOperationInjector(ScenarioInjector):
    """Speed / harsh-input bursts the operator applies intermittently."""

    scenario_type = ScenarioType.UNSAFE_OPERATION

    def __init__(self, spec: ScenarioSpec):
        super().__init__(spec)
        self._burst_left_s = 0.0
        self._burst_speed = 0.0

    def perturb(self, t, rng, cmd, env, dynamics) -> Perturbation:
        e = self.envelope(t)
        p = Perturbation()
        if e <= 0.0:
            self._burst_left_s = 0.0
            return p
        if self._burst_left_s > 0.0:
            self._burst_left_s -= 1.0
            p.cmd = {"speed_kph": self._burst_speed, "load_pct": 85.0, "rpm_norm": 0.95}
        elif rng.random() < 0.07 * e:
            self._burst_left_s = rng.uniform(4.0, 9.0)
            self._burst_speed = rng.uniform(13.5, 17.5)
            p.cmd = {"speed_kph": self._burst_speed, "load_pct": 86.0, "rpm_norm": 0.95}
        elif rng.random() < 0.02 * e:
            p.cmd = {"speed_kph": 1.2, "load_pct": 8.0}   # harsh stop / jerk
        self._apply_weather(p, e)
        return p


class SensorFailureInjector(ScenarioInjector):
    """An observed sensor drifts while the underlying (world) value holds."""

    scenario_type = ScenarioType.SENSOR_FAILURE

    def perturb(self, t, rng, cmd, env, dynamics) -> Perturbation:
        e = self.envelope(t)
        p = Perturbation()
        if e <= 0.0:
            return p
        s = self.spec.severity
        target = self.spec.params.get("sensor", "fuel_level_pct")
        if target == "engine_temperature_c":
            p.sensor_bias[target] = -(6.0 + 10.0 * s) * e
        else:
            p.sensor_bias["fuel_level_pct"] = -(2.5 + 7.0 * s) * e
        self._apply_weather(p, e)
        return p


class BatteryAnomalyInjector(ScenarioInjector):
    """Gradual electrical discharge under otherwise continuous operation."""

    scenario_type = ScenarioType.BATTERY_ANOMALY

    def perturb(self, t, rng, cmd, env, dynamics) -> Perturbation:
        e = self.envelope(t)
        p = Perturbation()
        if e <= 0.0:
            return p
        p.params["battery_bias"] = -(1.5 + 3.0 * self.spec.severity) * e
        self._apply_weather(p, e)
        return p


class MultiFactorInjector(ScenarioInjector):
    """Combined thermal + load + ambient stress (orchestrates a complex incident)."""

    scenario_type = ScenarioType.MULTI_FACTOR_INCIDENT

    def perturb(self, t, rng, cmd, env, dynamics) -> Perturbation:
        e = self.envelope(t)
        p = Perturbation()
        if e <= 0.0:
            return p
        s = self.spec.severity
        p.params["thermal_bias"] = (14.0 + 36.0 * s) * e
        p.params["cooling_perf_mult"] = 1.0 - 0.6 * s * e
        p.params["thermal_tau_mult"] = 1.0 - 0.4 * s * e
        p.params["hyd_temp_bias"] = 3.0 * e
        p.cmd_add["load_pct"] = 9.0 * e
        p.env_add["ambient_temperature_c"] = 6.0 * e
        self._apply_weather(p, e)
        return p


__all__ = [
    "Perturbation",
    "ScenarioInjector",
    "ScenarioSpec",
    "build_injector",
    "default_plan",
    "make_spec",
    "severity_bucket",
]
