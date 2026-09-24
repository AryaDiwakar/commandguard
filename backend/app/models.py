"""SQLAlchemy ORM models mapping the agreed database schema.

The challenge's required columns are preserved verbatim:
  telemetry:  Timestamp, Machine_ID, Operator_ID, Engine_Hours, Fuel_Used_L,
              Load_Cycles, Idling_Time_min, Seatbelt_Status, Safety_Alert_Triggered
  tasks:      Task_ID, Task_Type, Weather, Operator_Skill, Machine_Age_yrs,
              Estimated_Time_min, Actual_Time_min
All additional columns are documented synthetic-evaluation metadata.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, Column

from app.db import Base


class TelemetryRecord(Base):
    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # -- required -------------------------------------------------------
    Timestamp = Column(DateTime, nullable=False, index=True)
    Machine_ID = Column(String(32), nullable=False, index=True)
    Operator_ID = Column(String(32), nullable=False, index=True)
    Engine_Hours = Column(Float, nullable=False, default=0.0)
    Fuel_Used_L = Column(Float, nullable=False, default=0.0)
    Load_Cycles = Column(Integer, nullable=False, default=0)
    Idling_Time_min = Column(Float, nullable=False, default=0.0)
    Seatbelt_Status = Column(String(16), nullable=False, default="Fastened")
    Safety_Alert_Triggered = Column(Boolean, nullable=False, default=False)

    # -- additive telemetry ----------------------------------------------
    timestamp_ms = Column(Integer, default=0)
    session_id = Column(String(64), index=True)
    task_id = Column(String(32))
    current_task_type = Column(String(32))
    fuel_level_pct = Column(Float)
    fuel_consumption_rate_lph = Column(Float)
    engine_rpm = Column(Float)
    engine_temperature_c = Column(Float)
    coolant_temperature_c = Column(Float)
    oil_pressure_kpa = Column(Float)
    hydraulic_pressure_bar = Column(Float)
    hydraulic_temperature_c = Column(Float)
    battery_voltage_v = Column(Float)
    engine_load_pct = Column(Float)
    machine_speed_kph = Column(Float)
    vibration_g = Column(Float)
    proximity_distance_m = Column(Float)
    operating_hours = Column(Float)
    latitude = Column(Float)
    longitude = Column(Float)
    ambient_temperature_c = Column(Float)
    humidity_pct = Column(Float)
    rainfall_mmh = Column(Float)
    visibility_m = Column(Float)
    terrain_type = Column(String(24))
    terrain_condition = Column(String(24))
    slope_deg = Column(Float)
    work_zone = Column(String(48))
    nearby_machine_count = Column(Integer)
    weather_event = Column(String(24))
    machine_state = Column(String(24))
    task_progress_pct = Column(Float)
    efficiency = Column(Float)
    aggression_index = Column(Float)
    compliance = Column(Float)
    cooling_performance_pct = Column(Float)
    diagnostics_consistency = Column(Float)
    scenario_type = Column(String(32))
    phase = Column(String(24))
    anomaly_label = Column(Boolean, default=False)
    incident_type = Column(String(32))
    incident_severity = Column(String(16))
    anomaly_onset_t = Column(DateTime, nullable=True)
    detect_t = Column(DateTime, nullable=True)
    resolve_t = Column(DateTime, nullable=True)
    refuel_event = Column(Boolean, default=False)
    scenario_params = Column(Text, nullable=True)

    @classmethod
    def from_frame(cls, frame: Any) -> "TelemetryRecord":
        d = frame.to_dict()
        return cls(**{k: v for k, v in d.items() if k in cls.__table__.columns.keys()})


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    operator_id = Column(String(32), unique=True, nullable=False, index=True)
    display_name = Column(String(80), nullable=False)
    skill = Column(String(16), nullable=False, default="Intermediate")  # Beginner/Intermediate/Expert
    experience_years = Column(Float, default=3.0)
    machine_id = Column(String(32), default="MX-101")
    site_key = Column(String(48), default="QUARRY-NORTH")
    created_at = Column(DateTime, default=datetime.utcnow)

    def profile_dict(self) -> dict:
        return {
            "operator_id": self.operator_id,
            "display_name": self.display_name,
            "skill": self.skill,
            "experience_years": self.experience_years,
            "machine_id": self.machine_id,
            "site_key": self.site_key,
        }


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    Task_ID = Column(String(32), unique=True, index=True, nullable=False)
    Task_Type = Column(String(24), nullable=False)
    Weather = Column(String(24), nullable=False)
    Operator_Skill = Column(String(16), nullable=False)
    Machine_Age_yrs = Column(Integer, nullable=False)
    Estimated_Time_min = Column(Integer, nullable=False)
    Actual_Time_min = Column(Integer, nullable=False)
    Task_Zone = Column(String(48))
    Task_Priority = Column(String(12), default="MEDIUM")
    Material_Type = Column(String(24))
    Terrain_Condition = Column(String(24))
    Ambient_Temp_C = Column(Float)
    Rainfall_mmh = Column(Float)
    Visibility_m = Column(Float)
    Shift = Column(String(8), default="DAY")
    Required_Equipment = Column(String(24))
    Machine_ID = Column(String(32))
    Operator_ID = Column(String(32))
    Scheduled_Start_Time = Column(DateTime, nullable=True)
    Reference_Time_min = Column(Float, nullable=True)
    Delay_Reason = Column(String(24), default="NONE")


class IncidentRecord(Base):
    """Persisted incident lifecycle for reports, replay, and auditability."""

    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(96), unique=True, nullable=False, index=True)
    Machine_ID = Column(String(32), nullable=False, index=True)
    Session_ID = Column(String(64), nullable=True, index=True)
    Operator_ID = Column(String(32), nullable=True, index=True)
    Task_ID = Column(String(32), nullable=True)
    Task_Type = Column(String(32), nullable=True)
    Incident_Type = Column(String(48), nullable=False)
    Severity = Column(String(16), nullable=False)
    Confidence = Column(Float, nullable=False, default=0.0)
    Status = Column(String(24), nullable=False, default="ACTIVE")
    Help_Status = Column(String(24), nullable=False, default="NOT_REQUESTED")
    Response_Status = Column(String(24), nullable=False, default="NOT_STARTED")
    Detected_At = Column(DateTime, nullable=False)
    Resolved_At = Column(DateTime, nullable=True)
    Detected_Timestamp_ms = Column(Integer, nullable=False, default=0)
    Resolved_Timestamp_ms = Column(Integer, nullable=True)
    Evidence_JSON = Column(Text, nullable=False, default="[]")
    Causes_JSON = Column(Text, nullable=False, default="[]")
    Timeline_JSON = Column(Text, nullable=False, default="[]")
    Recommended_Action = Column(Text, nullable=True)


class ReplayFrameRecord(Base):
    """Public observed frame retained for durable incident replay."""

    __tablename__ = "incident_replay_frames"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(96), nullable=False, index=True)
    Machine_ID = Column(String(32), nullable=False, index=True)
    Session_ID = Column(String(64), nullable=True, index=True)
    Timestamp_ms = Column(Integer, nullable=False, index=True)
    Payload_JSON = Column(Text, nullable=False)
