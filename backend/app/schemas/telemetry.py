"""Canonical telemetry frame.

All machine/environment/operational state flows through this single object.

The challenge's REQUIRED columns are preserved exactly (names + types):
    Timestamp, Machine_ID, Operator_ID, Engine_Hours, Fuel_Used_L,
    Load_Cycles, Idling_Time_min, Seatbelt_Status, Safety_Alert_Triggered

Everything else that our pipeline needs is appended as snake_case columns.
Ground-truth fields are *simulation metadata* used for evaluation only and are
never presented as real machine data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class ScenarioType(str, Enum):
    NORMAL_OPERATION = "NORMAL_OPERATION"
    FUEL_LEAK = "FUEL_LEAK"
    ENGINE_OVERHEAT = "ENGINE_OVERHEAT"
    HYDRAULIC_FAILURE = "HYDRAULIC_FAILURE"
    PROXIMITY_HAZARD = "PROXIMITY_HAZARD"
    SEATBELT_VIOLATION = "SEATBELT_VIOLATION"
    EXCESSIVE_IDLE = "EXCESSIVE_IDLE"
    UNSAFE_OPERATION = "UNSAFE_OPERATION"
    SENSOR_FAILURE = "SENSOR_FAILURE"
    BATTERY_ANOMALY = "BATTERY_ANOMALY"
    MULTI_FACTOR_INCIDENT = "MULTI_FACTOR_INCIDENT"


class Phase(str, Enum):
    NORMAL = "NORMAL"
    ONSET = "ONSET"
    ANOMALY = "ANOMALY"
    RESPONSE = "RESPONSE"
    RESOLVED = "RESOLVED"


class MachineState(str, Enum):
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    REVERSING = "REVERSING"
    STOPPED = "STOPPED"
    IN_TRANSIT = "IN_TRANSIT"
    BREAK = "BREAK"
    SHUTDOWN = "SHUTDOWN"


class TerrainType(str, Enum):
    FLAT = "FLAT"
    SLOPED = "SLOPED"
    ROUGH = "ROUGH"
    ROCKY = "ROCKY"
    LOAMY = "LOAMY"


class TerrainCondition(str, Enum):
    DRY = "DRY"
    WET = "WET"
    MUDDY = "MUDDY"
    PACKED = "PACKED"
    ICY = "ICY"


class WeatherEvent(str, Enum):
    NONE = "NONE"
    RAIN = "RAIN"
    HEAVY_RAIN = "HEAVY_RAIN"
    FOG = "FOG"
    HOT = "HOT"
    HIGH_WIND = "HIGH_WIND"


REQUIRED_COLUMNS = [
    "Timestamp",
    "Machine_ID",
    "Operator_ID",
    "Engine_Hours",
    "Fuel_Used_L",
    "Load_Cycles",
    "Idling_Time_min",
    "Seatbelt_Status",
    "Safety_Alert_Triggered",
]


class TelemetryFrame(BaseModel):
    # -- identities ---------------------------------------------------------
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record time (naive-UTC serialized; ms precision via timestamp_ms).",
    )
    timestamp_ms: int = 0
    machine_id: str = ""
    operator_id: str = ""
    session_id: str = ""
    task_id: str = ""
    current_task_type: str = "EXCAVATION"
    task_index: int = 0
    task_count: int = 1
    task_status: str = "IN_PROGRESS"
    task_planned_minutes: float = 0.0
    task_completed: bool = False
    completed_task_type: str | None = None
    completed_task_id: str | None = None
    next_task_type: str = ""
    next_task_id: str = ""
    shift_total_minutes: float = 0.0
    shift_remaining_minutes: float = 0.0
    task_output_quantity: float = 0.0
    task_target_quantity: float = 1000.0
    task_output_unit: str = "m3"
    productivity_rate_per_min: float = 0.0
    fuel_efficiency_output_per_l: float = 0.0
    hydraulic_cycle_count: int = 0

    # -- required: cumulative counters --------------------------------------
    engine_hours: float = 0.0          # Engine_Hours  (cumulative)
    fuel_used_l: float = 0.0           # Fuel_Used_L   (cumulative, session)
    load_cycles: int = 0               # Load_Cycles
    idling_time_min: float = 0.0       # Idling_Time_min (rolling, resets on motion)
    seatbelt_status: str = "Fastened"  # Seatbelt_Status
    safety_alert_triggered: bool = False  # Safety_Alert_Triggered

    # -- fuel ---------------------------------------------------------------
    fuel_level_pct: float = 0.0
    fuel_consumption_rate_lph: float = 0.0

    # -- engine / powertrain -------------------------------------------------
    engine_rpm: float = 0.0
    engine_temperature_c: float = 0.0
    coolant_temperature_c: float = 0.0
    oil_pressure_kpa: float = 0.0

    # -- hydraulics ----------------------------------------------------------
    hydraulic_pressure_bar: float = 0.0
    hydraulic_temperature_c: float = 0.0

    # -- electrical / motion --------------------------------------------------
    battery_voltage_v: float = 0.0
    engine_load_pct: float = 0.0
    machine_speed_kph: float = 0.0
    vibration_g: float = 0.0
    proximity_distance_m: float = 0.0
    operating_hours: float = 0.0

    # -- position -------------------------------------------------------------
    latitude: float = 0.0
    longitude: float = 0.0

    # -- environment -----------------------------------------------------------
    ambient_temperature_c: float = 20.0
    humidity_pct: float = 50.0
    rainfall_mmh: float = 0.0
    visibility_m: float = 8000.0
    terrain_type: TerrainType = TerrainType.FLAT
    terrain_condition: TerrainCondition = TerrainCondition.DRY
    slope_deg: float = 0.0
    work_zone: str = "QUARRY-NORTH"
    nearby_machine_count: int = 0
    weather_event: WeatherEvent = WeatherEvent.NONE

    # -- derived / behavioural --------------------------------------------------
    machine_state: MachineState = MachineState.ACTIVE
    task_progress_pct: float = 0.0
    efficiency: float = 1.0
    aggression_index: float = 0.0
    compliance: float = 1.0
    cooling_performance_pct: float = 100.0
    diagnostics_consistency: float = 1.0

    # -- ground truth (synthetic evaluation only, never real-machine claims) ---
    scenario_type: ScenarioType = ScenarioType.NORMAL_OPERATION
    phase: Phase = Phase.NORMAL
    anomaly_label: bool = False
    incident_type: str | None = None
    incident_severity: str | None = None
    anomaly_onset_t: datetime | None = None
    detect_t: datetime | None = None
    resolve_t: datetime | None = None
    refuel_event: bool = False
    scenario_params: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self, *, include_ground_truth: bool = True) -> dict[str, Any]:
        """Serialise a flat record, optionally excluding synthetic truth labels.

        Offline datasets and evaluation use the complete record. Runtime
        operator-facing payloads must use ``include_ground_truth=False`` so the
        intelligence engine and UI cannot read the injected scenario answer.
        """
        payload = {
            "Timestamp": self.timestamp.isoformat(),
            "Machine_ID": self.machine_id,
            "Operator_ID": self.operator_id,
            "Engine_Hours": self.engine_hours,
            "Fuel_Used_L": self.fuel_used_l,
            "Load_Cycles": self.load_cycles,
            "Idling_Time_min": self.idling_time_min,
            "Seatbelt_Status": self.seatbelt_status,
            "Safety_Alert_Triggered": self.safety_alert_triggered,
            "timestamp_ms": self.timestamp_ms,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "current_task_type": self.current_task_type,
            "task_index": self.task_index,
            "task_count": self.task_count,
            "task_status": self.task_status,
            "task_planned_minutes": self.task_planned_minutes,
            "task_completed": self.task_completed,
            "completed_task_type": self.completed_task_type,
            "completed_task_id": self.completed_task_id,
            "next_task_type": self.next_task_type,
            "next_task_id": self.next_task_id,
            "shift_total_minutes": self.shift_total_minutes,
            "shift_remaining_minutes": self.shift_remaining_minutes,
            "task_output_quantity": self.task_output_quantity,
            "task_target_quantity": self.task_target_quantity,
            "task_output_unit": self.task_output_unit,
            "productivity_rate_per_min": self.productivity_rate_per_min,
            "fuel_efficiency_output_per_l": self.fuel_efficiency_output_per_l,
            "hydraulic_cycle_count": self.hydraulic_cycle_count,
            "fuel_level_pct": self.fuel_level_pct,
            "fuel_consumption_rate_lph": self.fuel_consumption_rate_lph,
            "engine_rpm": self.engine_rpm,
            "engine_temperature_c": self.engine_temperature_c,
            "coolant_temperature_c": self.coolant_temperature_c,
            "oil_pressure_kpa": self.oil_pressure_kpa,
            "hydraulic_pressure_bar": self.hydraulic_pressure_bar,
            "hydraulic_temperature_c": self.hydraulic_temperature_c,
            "battery_voltage_v": self.battery_voltage_v,
            "engine_load_pct": self.engine_load_pct,
            "machine_speed_kph": self.machine_speed_kph,
            "vibration_g": self.vibration_g,
            "proximity_distance_m": self.proximity_distance_m,
            "operating_hours": self.operating_hours,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "ambient_temperature_c": self.ambient_temperature_c,
            "humidity_pct": self.humidity_pct,
            "rainfall_mmh": self.rainfall_mmh,
            "visibility_m": self.visibility_m,
            "terrain_type": self.terrain_type.value,
            "terrain_condition": self.terrain_condition.value,
            "slope_deg": self.slope_deg,
            "work_zone": self.work_zone,
            "nearby_machine_count": self.nearby_machine_count,
            "weather_event": self.weather_event.value,
            "machine_state": self.machine_state.value,
            "task_progress_pct": self.task_progress_pct,
            "efficiency": self.efficiency,
            "aggression_index": self.aggression_index,
            "compliance": self.compliance,
            "cooling_performance_pct": self.cooling_performance_pct,
            "diagnostics_consistency": self.diagnostics_consistency,
        }
        if include_ground_truth:
            payload.update(
                {
                    "scenario_type": self.scenario_type.value,
                    "phase": self.phase.value,
                    "anomaly_label": self.anomaly_label,
                    "incident_type": self.incident_type,
                    "incident_severity": self.incident_severity,
                    "anomaly_onset_t": self.anomaly_onset_t.isoformat() if self.anomaly_onset_t else None,
                    "detect_t": self.detect_t.isoformat() if self.detect_t else None,
                    "resolve_t": self.resolve_t.isoformat() if self.resolve_t else None,
                    "refuel_event": self.refuel_event,
                    "scenario_params": self.scenario_params,
                }
            )
        return payload

    def to_public_dict(self) -> dict[str, Any]:
        """Return only observed fields safe for the operator experience."""
        return self.to_dict(include_ground_truth=False)
