"""Explainable predictive signals built on rolling observed telemetry."""
from __future__ import annotations

from statistics import mean, pstdev
from typing import Any

from app.schemas.telemetry import MachineState, TelemetryFrame


def _slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return (values[-1] - values[0]) / max(1, len(values) - 1)


def _z_score(values: list[float]) -> float:
    if len(values) < 8:
        return 0.0
    baseline = values[:-1]
    deviation = pstdev(baseline)
    return (values[-1] - mean(baseline)) / max(0.001, deviation)


def analyze(frame: TelemetryFrame, window: list[TelemetryFrame], incidents: list[dict[str, Any]]) -> dict[str, Any]:
    recent = window[-60:]
    early_warnings: list[dict[str, Any]] = []
    signals = {
        "engine_temperature_c": [item.engine_temperature_c for item in recent],
        "hydraulic_pressure_bar": [item.hydraulic_pressure_bar for item in recent],
        "vibration_g": [item.vibration_g for item in recent],
        "battery_voltage_v": [item.battery_voltage_v for item in recent],
        "fuel_consumption_rate_lph": [item.fuel_consumption_rate_lph for item in recent],
    }
    for signal, values in signals.items():
        score = _z_score(values)
        if abs(score) < 2.5:
            continue
        direction = "high" if score > 0 else "low"
        early_warnings.append(
            {
                "signal": signal,
                "type": "PRE_BREACH_ANOMALY",
                "z_score": round(score, 2),
                "direction": direction,
                "message": f"{signal.replace('_', ' ').title()} is unusually {direction} for this machine's recent baseline.",
                "confidence": round(min(0.98, 0.55 + abs(score) / 10.0), 2),
            }
        )

    avg_temp = mean(signals["engine_temperature_c"]) if recent else frame.engine_temperature_c
    avg_hyd = mean(signals["hydraulic_pressure_bar"]) if recent else frame.hydraulic_pressure_bar
    avg_vibration = mean(signals["vibration_g"]) if recent else frame.vibration_g
    component_health = {
        "engine": {
            "score": round(max(0.0, min(100.0, 100.0 - max(0.0, avg_temp - 70.0) * 1.2 - avg_vibration * 8.0)), 1),
            "trend": "WATCH" if avg_temp > 82.0 else "STABLE",
        },
        "hydraulics": {
            "score": round(max(0.0, min(100.0, 100.0 - max(0.0, 130.0 - avg_hyd) * 0.45)), 1),
            "trend": "WATCH" if avg_hyd < 105.0 else "STABLE",
        },
        "cooling": {
            "score": round(max(0.0, min(100.0, frame.cooling_performance_pct)), 1),
            "trend": "WATCH" if frame.cooling_performance_pct < 82.0 else "STABLE",
        },
        "electrical": {
            "score": round(max(0.0, min(100.0, 100.0 - max(0.0, 24.2 - frame.battery_voltage_v) * 15.0)), 1),
            "trend": "WATCH" if frame.battery_voltage_v < 22.5 else "STABLE",
        },
    }
    maintenance_forecasts = []
    for component, state in component_health.items():
        if state["score"] < 82.0 or state["trend"] == "WATCH":
            maintenance_forecasts.append(
                {
                    "component": component,
                    "health_score": state["score"],
                    "forecast": "INSPECTION_RECOMMENDED",
                    "time_to_maintenance_hours": round(max(2.0, (state["score"] - 55.0) / 2.2), 1),
                    "reason": f"{component.title()} health is {state['score']:.0f}/100 with a {state['trend'].lower()} trend.",
                }
            )

    active = [item for item in incidents if item.get("status") == "ACTIVE"]
    idle_ratio = sum(item.machine_state in (MachineState.IDLE, MachineState.BREAK) for item in recent) / max(1, len(recent))
    unsafe_speed_ratio = sum(item.machine_speed_kph > 12.0 for item in recent) / max(1, len(recent))
    unfastened_ratio = sum(item.seatbelt_status != "Fastened" for item in recent) / max(1, len(recent))
    harsh_ratio = sum(item.vibration_g > 0.9 or item.aggression_index > 0.7 for item in recent) / max(1, len(recent))
    behavior_score = max(0.0, min(100.0, 100.0 - idle_ratio * 18.0 - unsafe_speed_ratio * 35.0 - unfastened_ratio * 45.0 - harsh_ratio * 25.0))

    continuous_minutes = len(recent) / 60.0
    fatigue_score = min(100.0, max(0.0, (continuous_minutes - 90.0) * 0.35 + idle_ratio * 35.0 + harsh_ratio * 25.0))
    fatigue_risk = "HIGH" if fatigue_score >= 65 else "MEDIUM" if fatigue_score >= 35 else "LOW"

    lowest_component = min(state["score"] for state in component_health.values())
    risk_score = min(100.0, max(0.0, (100.0 - lowest_component) * 0.35 + (100.0 - behavior_score) * 0.25 + fatigue_score * 0.15 + len(active) * 18.0 + len(early_warnings) * 8.0))
    pre_shift_risk = "HIGH" if risk_score >= 60 else "MEDIUM" if risk_score >= 30 else "LOW"
    productivity = {
        "output_quantity": frame.task_output_quantity,
        "target_quantity": frame.task_target_quantity,
        "output_unit": frame.task_output_unit,
        "rate_per_min": frame.productivity_rate_per_min,
        "fuel_efficiency_output_per_l": frame.fuel_efficiency_output_per_l,
        "recommended_practice": "BALANCED" if pre_shift_risk != "LOW" else "ECO" if frame.fuel_efficiency_output_per_l < 1.0 else "BALANCED",
        "score": round(max(0.0, min(100.0, frame.task_progress_pct * 0.5 + frame.fuel_efficiency_output_per_l * 25.0)), 1),
    }
    return {
        "early_warnings": early_warnings,
        "component_health": component_health,
        "maintenance_forecasts": maintenance_forecasts,
        "behavior_score": round(behavior_score, 1),
        "behavior_factors": {
            "idle_ratio": round(idle_ratio, 3),
            "unsafe_speed_ratio": round(unsafe_speed_ratio, 3),
            "seatbelt_compliance": round(1.0 - unfastened_ratio, 3),
            "harsh_input_ratio": round(harsh_ratio, 3),
        },
        "fatigue_score": round(fatigue_score, 1),
        "fatigue_risk": fatigue_risk,
        "pre_shift_risk_score": round(risk_score, 1),
        "pre_shift_risk": pre_shift_risk,
        "pre_shift_reasons": [
            "Active incident history" if active else "No active incidents",
            "Component health requires attention" if lowest_component < 82 else "Component health is stable",
            "Operator behavior needs coaching" if behavior_score < 80 else "Operator behavior is within baseline",
            "Fatigue proxy is elevated" if fatigue_risk != "LOW" else "No fatigue signal detected",
        ],
        "productivity": productivity,
    }
