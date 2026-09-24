"""Derived machine situation (USB #2: Machine Situation Awareness).

In Phase 1 this is a *minimal* deterministic derivation from a single frame.
Phase 3 grows it into the full multi-signal engine (health, safety, risks,
active incidents, confidence) fed by detectors and the EvidenceStore.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.schemas.telemetry import MachineState, TelemetryFrame


class MachineSituation(BaseModel):
    machine_id: str
    timestamp_ms: int
    operating_state: str
    machine_health: str
    safety_state: str
    task: str
    task_progress_pct: float
    task_index: int = 0
    task_count: int = 1
    task_status: str = "IN_PROGRESS"
    next_task_type: str = ""
    next_task_id: str = ""
    shift_total_minutes: float = 0.0
    shift_remaining_minutes: float = 0.0
    current_risk: str
    active_incidents: list[dict[str, Any]]
    predicted_risks: list[dict[str, Any]]
    eta_minutes: float
    eta_baseline_minutes: float
    eta_reasons: list[str]
    early_warnings: list[dict[str, Any]]
    component_health: dict[str, Any]
    maintenance_forecasts: list[dict[str, Any]]
    behavior_score: float
    fatigue_risk: str
    pre_shift_risk: str
    pre_shift_risk_score: float
    pre_shift_reasons: list[str]
    productivity: dict[str, Any]
    confidence: float
    mode: str  # raw machine enum (machine_state)


def derive_situation(
    frame: TelemetryFrame,
    incidents: list[dict[str, Any]] | None = None,
    predicted_risks: list[dict[str, Any]] | None = None,
    eta: dict[str, Any] | None = None,
    predictive: dict[str, Any] | None = None,
) -> MachineSituation:
    """Derive the operator situation from observed state and intelligence."""
    state = frame.machine_state

    if state == MachineState.IDLE or state == MachineState.BREAK:
        operating = "IDLE"
    elif state == MachineState.REVERSING:
        operating = "REVERSING"
    elif state == MachineState.STOPPED or state == MachineState.SHUTDOWN:
        operating = "STANDBY"
    elif state == MachineState.IN_TRANSIT:
        operating = "IN_TRANSIT"
    else:
        operating = "ACTIVE"

    # Phase 1 health bands (DEMO thresholds). No anomaly engine yet => nominal.
    vitals_ok = all(
        (
            0.0 <= frame.fuel_level_pct <= 100.0,
            0.0 <= frame.engine_rpm <= 9999,
            -20.0 <= frame.engine_temperature_c <= 130.0,
            0.0 <= frame.hydraulic_pressure_bar <= 350.0,
            18.0 <= frame.battery_voltage_v <= 30.0,
        )
    )

    incidents = incidents or []
    predicted_risks = predicted_risks or []
    eta = eta or {}
    predictive = predictive or {}
    safe = (
        vitals_ok
        and frame.seatbelt_status == "Fastened"
        and frame.proximity_distance_m >= 8.0
    )
    health = "WARNING" if not vitals_ok or incidents else "HEALTHY"
    risk = "HIGH" if any(item.get("severity") in ("HIGH", "CRITICAL") for item in incidents) else (
        "MEDIUM" if incidents or predicted_risks else "LOW"
    )

    return MachineSituation(
        machine_id=frame.machine_id,
        timestamp_ms=frame.timestamp_ms,
        operating_state=operating,
        machine_health=health,
        safety_state="SAFE" if safe else "UNSAFE",
        task=frame.current_task_type,
        task_progress_pct=frame.task_progress_pct,
        task_index=frame.task_index,
        task_count=frame.task_count,
        task_status=frame.task_status,
        next_task_type=frame.next_task_type,
        next_task_id=frame.next_task_id,
        shift_total_minutes=frame.shift_total_minutes,
        shift_remaining_minutes=frame.shift_remaining_minutes,
        current_risk=risk,
        active_incidents=incidents,
        predicted_risks=predicted_risks,
        eta_minutes=float(eta.get("eta_minutes", 0.0)),
        eta_baseline_minutes=float(eta.get("baseline_minutes", 0.0)),
        eta_reasons=list(eta.get("reasons", [])),
        early_warnings=list(predictive.get("early_warnings", [])),
        component_health=dict(predictive.get("component_health", {})),
        maintenance_forecasts=list(predictive.get("maintenance_forecasts", [])),
        behavior_score=float(predictive.get("behavior_score", 100.0)),
        fatigue_risk=str(predictive.get("fatigue_risk", "LOW")),
        pre_shift_risk=str(predictive.get("pre_shift_risk", "LOW")),
        pre_shift_risk_score=float(predictive.get("pre_shift_risk_score", 0.0)),
        pre_shift_reasons=list(predictive.get("pre_shift_reasons", [])),
        productivity=dict(predictive.get("productivity", {})),
        confidence=min(
            [1.0, *[float(item.get("confidence", 1.0)) for item in incidents]]
        ),
        mode=state.value,
    )
