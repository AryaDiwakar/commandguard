"""Explainable temporal intelligence for observed machine telemetry."""
from __future__ import annotations

from statistics import mean
from typing import Any, Callable

from app.intelligence.models import Evidence, Incident, utc_now
from app.ml.eta import eta_model
from app.predictive.engine import analyze as analyze_predictive
from app.schemas.telemetry import TelemetryFrame
from app.simulation.catalog import MACHINES, TASK_CATALOG
from app.telemetry.state import TelemetryStateStore


Detection = tuple[str, list[Evidence], str, list[str], str]

# Escalation tier: when an active incident crosses its CRITICAL threshold the
# engine requests a safe automatic reaction (never an engine kill). `action` is
# always one of the generator's operator commands; `min_ticks` prevents firing
# on isolated frames so the degradation is visible first.
_ESCALATION_RULES: dict[str, tuple[str, str, int]] = {
    "POSSIBLE_FUEL_LEAK": (
        "STOP_MACHINE",
        "Tank drain crossed the critical fuel-loss threshold; CommandGuard moved the machine to a safe stop.",
        3,
    ),
    "POSSIBLE_ENGINE_OVERHEAT": (
        "STOP_MACHINE",
        "Engine temperature crossed the critical thermal threshold; CommandGuard moved the machine to a safe stop.",
        3,
    ),
    "POSSIBLE_HYDRAULIC_FAILURE": (
        "STOP_MACHINE",
        "Hydraulic pressure collapsed under load; CommandGuard moved the machine to a safe stop.",
        3,
    ),
    "PROXIMITY_HAZARD": (
        "STOP_MACHINE",
        "Obstacle entered the critical proximity radius while moving; CommandGuard stopped the machine.",
        3,
    ),
    "SEATBELT_VIOLATION": (
        "STOP_MACHINE",
        "Operator restraint left unfastened while moving; CommandGuard stopped the machine.",
        8,
    ),
    "EXCESSIVE_IDLE": (
        "STOP_MACHINE",
        "Idling exceeded the critical economy threshold; CommandGuard parked the machine.",
        3,
    ),
    "UNSAFE_OPERATION": (
        "REDUCE_LOAD",
        "Repeated harsh operating bursts crossed the safety threshold; CommandGuard reduced machine load.",
        3,
    ),
    "BATTERY_ELECTRICAL_ANOMALY": (
        "REDUCE_LOAD",
        "Battery voltage dropped below the critical electrical threshold; CommandGuard reduced machine load.",
        3,
    ),
    "POSSIBLE_SENSOR_ANOMALY": (
        "STOP_MACHINE",
        "Telemetry consistency crossed the critical sensor-integrity threshold; CommandGuard stopped the machine for a safe cross-check.",
        3,
    ),
    "MULTI_FACTOR_THERMAL_RISK": (
        "STOP_MACHINE",
        "Combined thermal stress crossed the critical threshold; CommandGuard moved the machine to a safe stop.",
        3,
    ),
}


class IntelligenceEngine:
    """Fuse rolling observations into incidents, forecasts, and ETA context."""

    def __init__(self, machine_id: str, window_size: int = 3600, session_id: str = ""):
        self.machine_id = machine_id
        self.session_id = session_id
        self.state = TelemetryStateStore(window_size=window_size)
        self._incidents: dict[str, Incident] = {}
        self._stable_ticks: dict[str, int] = {}
        self._detected_ticks: dict[str, int] = {}
        self._sequence = 0

    def observe(self, frame: TelemetryFrame) -> list[dict[str, Any]]:
        self.state.append(frame)
        events: list[dict[str, Any]] = []
        detections = {item[0]: item for item in self._detections(frame)}

        for incident_type, evidence, severity, causes, action in detections.values():
            active = self._active(incident_type)
            if active is None:
                self._sequence += 1
                active = Incident(
                    incident_id=f"INC-{frame.machine_id}-{frame.timestamp_ms}-{self._sequence}",
                    machine_id=frame.machine_id,
                    incident_type=incident_type,
                    severity=severity,
                    confidence=min(0.99, max(0.5, max(item.contribution for item in evidence))),
                    detected_at=utc_now(),
                    detected_timestamp_ms=frame.timestamp_ms,
                    operator_id=frame.operator_id,
                    task_id=frame.task_id,
                    task_type=frame.current_task_type,
                    session_id=self.session_id or frame.session_id,
                    evidence=evidence,
                    possible_causes=causes,
                    recommended_action=action,
                )
                active.add_event("DETECTED", self._detection_message(incident_type))
                self._incidents[active.incident_id] = active
                self._stable_ticks[active.incident_id] = 0
                events.append({"type": "incident.detected", "incident": active.to_dict()})
            else:
                active.evidence = evidence
                active.severity = severity
                active.confidence = min(active.confidence + 0.01, 0.99)
                self._stable_ticks[active.incident_id] = 0

        for incident in self.active_incidents():
            if incident.incident_type in detections:
                self._detected_ticks[incident.incident_id] = self._detected_ticks.get(incident.incident_id, 0) + 1
            else:
                self._detected_ticks[incident.incident_id] = 0

        for incident in self.active_incidents():
            action = self._auto_reaction_for(incident, frame)
            if action is None or incident.auto_reaction is not None:
                continue
            reaction, reason = action
            incident.auto_reaction = reaction
            incident.auto_reaction_reason = reason
            if reaction == "STOP_MACHINE":
                incident.response_status = "STOP_REQUESTED"
            incident.add_event("AUTOMATIC_SAFETY_OVERRIDE", f"Safety override armed: {reason}")
            events.append(
                {
                    "type": "automatic_override",
                    "incident": incident.to_dict(),
                    "action": reaction,
                    "reason": reason,
                }
            )

        for incident in self.active_incidents():
            if incident.incident_type not in detections:
                self._stable_ticks[incident.incident_id] += 1
                if self._stable_ticks[incident.incident_id] >= 30:
                    incident.status = "RESOLVED"
                    incident.resolved_at = utc_now()
                    incident.resolved_timestamp_ms = frame.timestamp_ms
                    incident.add_event("RESOLVED", "Signals returned to the expected operating band.")
                    events.append({"type": "incident.resolved", "incident": incident.to_dict()})

        for incident in self.active_incidents():
            if incident.response_status in ("STOP_REQUESTED", "SHUTDOWN_REQUESTED"):
                if self._verify_response(incident, frame):
                    events.append({"type": "response.verified", "incident": incident.to_dict()})

        return events

    def active_incidents(self) -> list[Incident]:
        return [incident for incident in self._incidents.values() if incident.status == "ACTIVE"]

    def incidents(self) -> list[Incident]:
        return list(self._incidents.values())

    def reset_for_scenario(self) -> list[Incident]:
        """Close runtime-only practice state before a new scenario replay.

        Persisted incident history is retained by the service; this only
        prevents a previous auto-stop from poisoning the next scenario.
        """
        resolved: list[Incident] = []
        for incident in self.active_incidents():
            incident.status = "RESOLVED"
            incident.resolved_at = utc_now()
            incident.add_event("RESOLVED", "Practice scenario replaced; prior runtime state was cleared for replay.")
            resolved.append(incident)
        self._detected_ticks.clear()
        self._stable_ticks.clear()
        self.state.clear(self.machine_id)
        return resolved

    def get_incident(self, incident_id: str | None = None) -> Incident | None:
        if incident_id:
            return self._incidents.get(incident_id)
        active = self.active_incidents()
        return active[-1] if active else None

    def request_help(self, incident_id: str | None = None, channel: str = "SUPERVISOR") -> Incident:
        incident = self.get_incident(incident_id)
        if incident is None:
            raise KeyError("No active incident for this machine")
        incident.help_status = "REQUESTED"
        incident.add_event("HELP_REQUESTED", f"Live assistance requested through {channel}.")
        return incident

    def acknowledge_help(self, incident_id: str | None = None) -> Incident:
        incident = self.get_incident(incident_id)
        if incident is None:
            raise KeyError("No incident for this machine")
        incident.help_status = "ACKNOWLEDGED"
        incident.add_event("HELP_ACKNOWLEDGED", "Support acknowledged the live assistance request.")
        return incident

    def record_action(self, action: str, incident_id: str | None = None) -> Incident:
        incident = self.get_incident(incident_id)
        if incident is None:
            raise KeyError("No incident for this machine")
        incident.last_operator_action = action
        if action == "STOP_MACHINE":
            incident.response_status = "STOP_REQUESTED"
        elif action == "SHUTDOWN_ENGINE":
            incident.response_status = "SHUTDOWN_REQUESTED"
        incident.add_event("OPERATOR_ACTION", action)
        return incident

    def predicted_risks(self, frame: TelemetryFrame) -> list[dict[str, Any]]:
        """Return explainable short-horizon risks from recent signal slopes."""
        window = self.state.window(self.machine_id, size=30)
        if len(window) < 10:
            return []
        risks: list[dict[str, Any]] = []
        temp_slope = self._slope(window, "engine_temperature_c", per_minute=True)
        # Ignore the normal startup warm-up transient until the engine is
        # already in a meaningful thermal operating band.
        if temp_slope > 0.35 and 75.0 <= frame.engine_temperature_c < 108.0:
            minutes = max(1.0, (108.0 - frame.engine_temperature_c) / temp_slope)
            risks.append(
                {
                    "type": "THERMAL_ESCALATION",
                    "severity": "HIGH" if minutes < 10 else "MEDIUM",
                    "confidence": min(0.95, 0.55 + temp_slope / 3.0),
                    "time_to_threshold_min": round(minutes, 1),
                    "message": f"Engine temperature is rising {temp_slope:.2f} C/min; warning band may be reached in about {minutes:.1f} min.",
                }
            )

        fuel_slope = self._slope(window, "fuel_level_pct", per_minute=True)
        if fuel_slope < -0.5 and frame.fuel_level_pct > 18.0:
            minutes = max(1.0, (frame.fuel_level_pct - 18.0) / abs(fuel_slope))
            risks.append(
                {
                    "type": "FUEL_DEPLETION",
                    "severity": "HIGH" if minutes < 30 else "MEDIUM",
                    "confidence": min(0.95, 0.55 + abs(fuel_slope) / 8.0),
                    "time_to_threshold_min": round(minutes, 1),
                    "message": f"Fuel is declining {abs(fuel_slope):.2f}%/min; critical band may be reached in about {minutes:.1f} min.",
                }
            )

        hydraulic_slope = self._slope(window, "hydraulic_pressure_bar", per_minute=True)
        if hydraulic_slope < -2.0 and frame.hydraulic_pressure_bar > 60.0:
            minutes = max(1.0, (frame.hydraulic_pressure_bar - 60.0) / abs(hydraulic_slope))
            risks.append(
                {
                    "type": "HYDRAULIC_DECLINE",
                    "severity": "HIGH" if minutes < 10 else "MEDIUM",
                    "confidence": min(0.92, 0.55 + abs(hydraulic_slope) / 20.0),
                    "time_to_threshold_min": round(minutes, 1),
                    "message": f"Hydraulic pressure is declining; safe band may be crossed in about {minutes:.1f} min.",
                }
            )
        return risks

    def estimate_eta(self, frame: TelemetryFrame) -> dict[str, Any]:
        """Estimate remaining task time with transparent synthetic modifiers."""
        # Baseline is the scheduled task's planned duration — the live plan
        # (demo-compressed, e.g. 5 min for the first task) when present, else
        # the TASK_CATALOG fallback. Scaled by remaining progress.
        planned_minutes = float(frame.task_planned_minutes or TASK_CATALOG.get(frame.current_task_type, {}).get("planned_minutes", 240))
        baseline = max(0.0, (100.0 - frame.task_progress_pct) / 100.0 * planned_minutes)
        model_remaining = max(baseline, eta_model().predict_remaining(frame))
        multiplier = 1.0
        reasons: list[str] = []
        if frame.rainfall_mmh > 0.0:
            multiplier += min(0.25, frame.rainfall_mmh / 80.0)
            reasons.append("rainfall")
        if frame.terrain_condition.value in ("WET", "MUDDY", "ICY"):
            multiplier += 0.18 if frame.terrain_condition.value == "MUDDY" else 0.08
            reasons.append(f"{frame.terrain_condition.value.lower()} terrain")
        if frame.visibility_m < 1500.0:
            multiplier += 0.12
            reasons.append("reduced visibility")
        if frame.engine_load_pct > 90.0:
            multiplier += 0.08
            reasons.append("high machine load")
        if self.active_incidents():
            multiplier += 0.15
            reasons.append("active machine incident")
        eta = model_remaining * multiplier
        return {
            "eta_minutes": round(eta, 1),
            "baseline_minutes": round(baseline, 1),
            "model_minutes": round(model_remaining, 1),
            "model_name": eta_model().status.model_name,
            "reasons": reasons,
        }

    def predictive_snapshot(self, frame: TelemetryFrame) -> dict[str, Any]:
        return analyze_predictive(frame, self.state.window(self.machine_id, size=180), [item.to_dict() for item in self.incidents()])

    def _detections(self, frame: TelemetryFrame) -> list[Detection]:
        detectors: tuple[Callable[[TelemetryFrame], Detection | None], ...] = (
            self._fuel_detection,
            self._overheat_detection,
            self._hydraulic_detection,
            self._proximity_detection,
            self._seatbelt_detection,
            self._idle_detection,
            self._unsafe_detection,
            self._sensor_detection,
            self._battery_detection,
            self._multifactor_detection,
        )
        return [result for detector in detectors if (result := detector(frame)) is not None]

    def _auto_reaction_for(self, incident: Incident, frame: TelemetryFrame) -> tuple[str, str] | None:
        """Return (action, reason) when an active incident crosses its CRITICAL tier."""
        if incident.auto_reaction is not None:
            return None
        rule = _ESCALATION_RULES.get(incident.incident_type)
        if rule is None:
            return None
        action, reason, min_ticks = rule
        # Hold the escalation for a few frames so the degradation is visible
        # before the safe-stop fires (longer hold for the seatbelt interlock).
        if self._detected_ticks.get(incident.incident_id, 0) < min_ticks:
            return None
        if not self._critical_crossed(incident.incident_type, frame):
            return None
        return (action, reason)

    def _critical_crossed(self, incident_type: str, frame: TelemetryFrame) -> bool:
        if incident_type == "POSSIBLE_FUEL_LEAK":
            window = self.state.window(self.machine_id, size=20)
            if len(window) >= 15:
                first, last = window[0], window[-1]
                elapsed_h = max(1.0 / 3600.0, (last.timestamp_ms - first.timestamp_ms) / 3_600_000.0)
                observed = first.fuel_level_pct - last.fuel_level_pct
                reported = mean(max(0.0, item.fuel_consumption_rate_lph) for item in window)
                capacity = MACHINES[self.machine_id].fuel_capacity_l
                expected = reported * elapsed_h / capacity * 100.0
                excess = max(0.0, (observed - expected) / elapsed_h)
                return frame.fuel_level_pct <= 15.0 or excess >= 1.0
            return frame.fuel_level_pct <= 15.0
        if incident_type == "POSSIBLE_ENGINE_OVERHEAT":
            return frame.engine_temperature_c >= 108.0
        if incident_type == "POSSIBLE_HYDRAULIC_FAILURE":
            return frame.hydraulic_pressure_bar < 50.0
        if incident_type == "PROXIMITY_HAZARD":
            return frame.proximity_distance_m < 4.0
        if incident_type == "SEATBELT_VIOLATION":
            return True
        if incident_type == "EXCESSIVE_IDLE":
            return frame.idling_time_min >= 8.0
        if incident_type == "UNSAFE_OPERATION":
            window = self.state.window(self.machine_id, size=20)
            bursts = sum(1 for item in window if item.machine_speed_kph > 12.5)
            return bursts >= 2
        if incident_type == "BATTERY_ELECTRICAL_ANOMALY":
            return frame.battery_voltage_v < 20.5
        if incident_type == "POSSIBLE_SENSOR_ANOMALY":
            return frame.diagnostics_consistency < 0.90
        if incident_type == "MULTI_FACTOR_THERMAL_RISK":
            return True
        return False

    def _fuel_detection(self, frame: TelemetryFrame) -> Detection | None:
        # A drifting fuel sensor is investigated separately; do not label the
        # observed divergence as a physical leak at the same time.
        if any(item.diagnostics_consistency < 0.98 for item in self.state.window(self.machine_id, size=20)):
            return None
        window = self.state.window(self.machine_id, size=20)
        if len(window) < 15:
            return None
        first, last = window[0], window[-1]
        elapsed_h = max(1.0 / 3600.0, (last.timestamp_ms - first.timestamp_ms) / 3_600_000.0)
        observed_loss = first.fuel_level_pct - last.fuel_level_pct
        reported_rate = mean(max(0.0, item.fuel_consumption_rate_lph) for item in window)
        capacity = MACHINES[self.machine_id].fuel_capacity_l
        expected_loss = reported_rate * elapsed_h / capacity * 100.0
        excess_rate = max(0.0, (observed_loss - expected_loss) / elapsed_h)
        if excess_rate < 3.5 or observed_loss <= expected_loss * 1.7:
            return None
        confidence = min(0.99, 0.58 + min(0.36, excess_rate / 20.0))
        evidence = [
            Evidence("fuel_level_pct", f"Fuel fell {observed_loss:.2f}% over {elapsed_h * 3600:.0f} seconds.", f"Reported consumption explains approximately {expected_loss:.2f}%.", confidence),
            Evidence("fuel_consumption_rate_lph", f"Reported consumption averaged {reported_rate:.1f} L/h.", "Observed tank loss should remain consistent with reported consumption.", min(0.95, 0.55 + excess_rate / 25.0)),
        ]
        return ("POSSIBLE_FUEL_LEAK", evidence, "HIGH", ["Fuel-system leak or unexpected fuel loss", "Observed sensor drift requiring cross-check"], "Stop safely and request maintenance assistance.")

    def _overheat_detection(self, frame: TelemetryFrame) -> Detection | None:
        window = self.state.window(self.machine_id, size=15)
        slope = self._slope(window, "engine_temperature_c", per_minute=True) if len(window) >= 10 else 0.0
        if frame.engine_temperature_c < 98.0 and not (slope > 0.55 and frame.coolant_temperature_c > 80.0):
            return None
        confidence = min(0.97, 0.62 + max(0.0, frame.engine_temperature_c - 98.0) / 50.0 + max(0.0, slope) / 5.0)
        return (
            "POSSIBLE_ENGINE_OVERHEAT",
            [
                Evidence("engine_temperature_c", f"Engine temperature is {frame.engine_temperature_c:.1f} C with a {slope:.2f} C/min trend.", "Synthetic warning band is 98 C.", confidence),
                Evidence("coolant_temperature_c", f"Coolant temperature is {frame.coolant_temperature_c:.1f} C.", "Coolant should remain aligned with engine load and ambient conditions.", min(0.95, confidence - 0.03)),
            ],
            "HIGH",
            ["Degraded cooling performance", "Sustained load or hot ambient conditions"],
            "Reduce load and move to a safe stop if temperature continues rising.",
        )

    def _hydraulic_detection(self, frame: TelemetryFrame) -> Detection | None:
        window = self.state.window(self.machine_id, size=10)
        sustained_sag = frame.machine_state.value == "ACTIVE" and sum(1 for item in window if item.hydraulic_pressure_bar < 75.0 and item.engine_load_pct >= 70.0) >= 5
        if not sustained_sag:
            return None
        confidence = min(0.96, 0.65 + (75.0 - frame.hydraulic_pressure_bar) / 100.0)
        return (
            "POSSIBLE_HYDRAULIC_FAILURE",
            [Evidence("hydraulic_pressure_bar", f"Hydraulic pressure is {frame.hydraulic_pressure_bar:.1f} bar under {frame.engine_load_pct:.1f}% load.", "Working pressure should remain above the synthetic sag band of 90 bar.", confidence)],
            "HIGH",
            ["Hydraulic pressure loss", "Hydraulic system unable to meet commanded load"],
            "Reduce load and stop safely for maintenance assessment.",
        )

    def _proximity_detection(self, frame: TelemetryFrame) -> Detection | None:
        if frame.proximity_distance_m >= 8.0 or frame.machine_speed_kph <= 0.1:
            return None
        return (
            "PROXIMITY_HAZARD",
            [Evidence("proximity_distance_m", f"Nearest object is {frame.proximity_distance_m:.1f} m away while moving at {frame.machine_speed_kph:.1f} km/h.", "Safe synthetic proximity radius is 8 m.", 0.96)],
            "HIGH",
            ["Nearby asset or person inside the safety radius"],
            "Stop movement if safe and confirm the area is clear before proceeding.",
        )

    def _seatbelt_detection(self, frame: TelemetryFrame) -> Detection | None:
        if frame.seatbelt_status == "Fastened" or frame.machine_speed_kph <= 0.1:
            return None
        return (
            "SEATBELT_VIOLATION",
            [Evidence("seatbelt_status", "Seatbelt is unfastened while the machine is moving.", "Seatbelt must be fastened during movement.", 0.99)],
            "HIGH",
            ["Operator safety restraint not engaged"],
            "Stop movement and fasten the seatbelt before continuing.",
        )

    def _idle_detection(self, frame: TelemetryFrame) -> Detection | None:
        if frame.idling_time_min < 4.0 or frame.machine_speed_kph > 0.1 or frame.engine_rpm < 500.0 or frame.engine_load_pct > 5.0 or frame.machine_state.value != "IDLE":
            return None
        return (
            "EXCESSIVE_IDLE",
            [Evidence("idling_time_min", f"Machine has idled for {frame.idling_time_min:.1f} minutes with engine active.", "Synthetic excessive-idle band is 4 minutes.", 0.9)],
            "MEDIUM",
            ["Engine left running while machine is stationary"],
            "Stop the engine when operationally safe and not required for the task.",
        )

    def _unsafe_detection(self, frame: TelemetryFrame) -> Detection | None:
        window = self.state.window(self.machine_id, size=20)
        burst = max((item.machine_speed_kph for item in window), default=0.0) > 12.5
        harsh = max((item.vibration_g for item in window), default=0.0) > 0.9 and frame.aggression_index > 0.45
        if not burst and not harsh:
            return None
        return (
            "UNSAFE_OPERATION",
            [Evidence("machine_speed_kph", f"Recent speed peaked at {max(item.machine_speed_kph for item in window):.1f} km/h in the work zone.", "Synthetic in-zone reference is 12 km/h.", 0.84), Evidence("vibration_g", f"Vibration is {frame.vibration_g:.2f} g with aggression index {frame.aggression_index:.2f}.", "Harsh input patterns should remain below the synthetic vibration band.", 0.76)],
            "HIGH",
            ["Aggressive operating pattern", "Excessive speed or harsh machine inputs"],
            "Reduce speed and return to controlled operating inputs.",
        )

    def _sensor_detection(self, frame: TelemetryFrame) -> Detection | None:
        if frame.diagnostics_consistency >= 0.98:
            return None
        return (
            "POSSIBLE_SENSOR_ANOMALY",
            [Evidence("diagnostics_consistency", f"Cross-signal consistency is {frame.diagnostics_consistency:.2f}.", "Observed signals should remain above the synthetic consistency band of 0.98.", 0.86)],
            "MEDIUM",
            ["Sensor drift", "Telemetry channel disagreement"],
            "Cross-check the reading against correlated signals before treating it as a machine failure.",
        )

    def _battery_detection(self, frame: TelemetryFrame) -> Detection | None:
        if frame.battery_voltage_v >= 22.0:
            return None
        return (
            "BATTERY_ELECTRICAL_ANOMALY",
            [Evidence("battery_voltage_v", f"Battery voltage is {frame.battery_voltage_v:.1f} V.", "Synthetic low-voltage band is 22 V.", 0.88)],
            "MEDIUM",
            ["Battery discharge", "Charging or electrical-system instability"],
            "Reduce non-essential load and request an electrical-system assessment.",
        )

    def _multifactor_detection(self, frame: TelemetryFrame) -> Detection | None:
        if not (frame.engine_temperature_c >= 100.0 and frame.engine_load_pct >= 75.0 and frame.ambient_temperature_c >= 25.0 and frame.cooling_performance_pct < 80.0):
            return None
        return (
            "MULTI_FACTOR_THERMAL_RISK",
            [Evidence("thermal_load_environment", f"Temperature {frame.engine_temperature_c:.1f} C, load {frame.engine_load_pct:.1f}%, ambient {frame.ambient_temperature_c:.1f} C, cooling {frame.cooling_performance_pct:.1f}%.", "Combined thermal stress should remain below the synthetic multi-factor risk band.", 0.94)],
            "CRITICAL",
            ["High load", "Hot ambient conditions", "Reduced cooling performance"],
            "Reduce load and stop safely if the thermal trend does not reverse.",
        )

    def _active(self, incident_type: str) -> Incident | None:
        return next((item for item in self.active_incidents() if item.incident_type == incident_type), None)

    @staticmethod
    def _slope(window: list[TelemetryFrame], field: str, per_minute: bool = False) -> float:
        if len(window) < 2:
            return 0.0
        elapsed = max(1.0, (window[-1].timestamp_ms - window[0].timestamp_ms) / 1000.0)
        scale = 60.0 if per_minute else 1.0
        return (float(getattr(window[-1], field)) - float(getattr(window[0], field))) / elapsed * scale

    @staticmethod
    def _detection_message(incident_type: str) -> str:
        return f"{incident_type.replace('_', ' ').title()} detected from converging telemetry evidence."

    @staticmethod
    def _verify_response(incident: Incident, frame: TelemetryFrame) -> bool:
        if incident.response_status == "VERIFIED":
            return False
        stationary = frame.machine_speed_kph <= 0.1
        if incident.response_status == "SHUTDOWN_REQUESTED":
            verified = stationary and frame.engine_rpm <= 100.0 and frame.machine_state.value == "SHUTDOWN"
        else:
            verified = stationary and frame.machine_state.value in ("STOPPED", "SHUTDOWN")
        if not verified:
            return False
        incident.response_status = "VERIFIED"
        incident.add_event("RESPONSE_VERIFIED", "Telemetry confirms the requested operator response.")
        return True
