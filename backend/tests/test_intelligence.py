"""Observed-signal intelligence and operator response tests."""
from __future__ import annotations

from app.intelligence.engine import IntelligenceEngine
from app.schemas.telemetry import ScenarioType
from app.simulation.generator import MachineGenerator
from app.simulation.scenarios import make_spec


def test_fuel_loss_detector_uses_temporal_observed_signals():
    generator = MachineGenerator(
        seed=31,
        scenario=make_spec(
            ScenarioType.FUEL_LEAK,
            severity=0.8,
            onset_offset_s=30,
            ramp_s=5,
            duration_s=120,
            abate_s=30,
        ),
    )
    engine = IntelligenceEngine("MX-101")
    events = []
    for _ in range(220):
        events.extend(engine.observe(generator.step()))

    detected = [event for event in events if event["type"] == "incident.detected"]
    assert len(detected) == 1
    incident = detected[0]["incident"]
    assert incident["incident_type"] == "POSSIBLE_FUEL_LEAK"
    assert incident["evidence"]
    assert incident["confidence"] > 0.7


def test_shutdown_action_stops_engine_and_suppresses_simulated_leak():
    generator = MachineGenerator(
        seed=32,
        scenario=make_spec(
            ScenarioType.FUEL_LEAK,
            severity=0.8,
            onset_offset_s=1,
            ramp_s=1,
            duration_s=200,
            abate_s=30,
        ),
    )
    for _ in range(40):
        generator.step()
    generator.apply_operator_action("SHUTDOWN_ENGINE")
    frame = generator.step()
    for _ in range(8):
        frame = generator.step()

    assert frame.machine_state.value == "SHUTDOWN"
    assert frame.engine_rpm < 100
    assert frame.machine_speed_kph == 0.0


def test_operator_shutdown_is_verified_from_following_telemetry():
    generator = MachineGenerator(
        seed=33,
        scenario=make_spec(
            ScenarioType.FUEL_LEAK,
            severity=0.8,
            onset_offset_s=5,
            ramp_s=1,
            duration_s=200,
            abate_s=30,
        ),
    )
    engine = IntelligenceEngine("MX-101")
    detected = None
    for _ in range(80):
        for event in engine.observe(generator.step()):
            if event["type"] == "incident.detected":
                detected = event["incident"]
    assert detected is not None

    engine.record_action("SHUTDOWN_ENGINE", detected["incident_id"])
    generator.apply_operator_action("SHUTDOWN_ENGINE")
    events = []
    for _ in range(10):
        events.extend(engine.observe(generator.step()))

    assert any(event["type"] == "response.verified" for event in events)
    assert engine.get_incident(detected["incident_id"]).response_status == "VERIFIED"


def test_scenario_families_have_observed_signal_detectors():
    scenarios = {
        ScenarioType.ENGINE_OVERHEAT: "POSSIBLE_ENGINE_OVERHEAT",
        ScenarioType.HYDRAULIC_FAILURE: "POSSIBLE_HYDRAULIC_FAILURE",
        ScenarioType.PROXIMITY_HAZARD: "PROXIMITY_HAZARD",
        ScenarioType.SEATBELT_VIOLATION: "SEATBELT_VIOLATION",
        ScenarioType.EXCESSIVE_IDLE: "EXCESSIVE_IDLE",
        ScenarioType.UNSAFE_OPERATION: "UNSAFE_OPERATION",
        ScenarioType.SENSOR_FAILURE: "POSSIBLE_SENSOR_ANOMALY",
        ScenarioType.BATTERY_ANOMALY: "BATTERY_ELECTRICAL_ANOMALY",
        ScenarioType.MULTI_FACTOR_INCIDENT: "MULTI_FACTOR_THERMAL_RISK",
    }
    for scenario, expected_type in scenarios.items():
        generator = MachineGenerator(
            seed=3,
            scenario=make_spec(scenario, severity=0.8, onset_offset_s=30, ramp_s=10, duration_s=500, abate_s=60),
        )
        engine = IntelligenceEngine("MX-101")
        detected: set[str] = set()
        for _ in range(900):
            detected.update(
                event["incident"]["incident_type"]
                for event in engine.observe(generator.step())
                if event["type"] == "incident.detected"
            )
        assert expected_type in detected, scenario


def test_eta_and_risk_forecast_are_explainable():
    generator = MachineGenerator(
        seed=3,
        scenario=make_spec(ScenarioType.ENGINE_OVERHEAT, severity=0.8, onset_offset_s=30, ramp_s=10, duration_s=500, abate_s=60),
    )
    engine = IntelligenceEngine("MX-101")
    frame = None
    for _ in range(300):
        frame = generator.step()
        engine.observe(frame)
    assert frame is not None
    risks = engine.predicted_risks(frame)
    eta = engine.estimate_eta(frame)
    assert risks
    assert all("time_to_threshold_min" in risk for risk in risks)
    assert eta["eta_minutes"] >= eta["baseline_minutes"]


def test_automatic_safety_override_stops_machine_and_verifies():
    generator = MachineGenerator(
        seed=7,
        scenario=make_spec(
            ScenarioType.FUEL_LEAK,
            severity=0.9,
            onset_offset_s=5,
            ramp_s=1,
            duration_s=300,
            abate_s=30,
        ),
    )
    engine = IntelligenceEngine("MX-101")
    override = None
    for _ in range(400):
        for event in engine.observe(generator.step()):
            if event["type"] == "automatic_override":
                override = event
        if override is not None:
            generator.apply_operator_action(override["action"])
            break
    assert override is not None
    assert override["action"] == "STOP_MACHINE"
    incident = engine.get_incident(override["incident"]["incident_id"])
    assert incident is not None
    assert incident.auto_reaction == "STOP_MACHINE"
    assert incident.auto_reaction_reason
    assert incident.response_status == "STOP_REQUESTED"

    fuel_at_override = generator.last_frame.fuel_level_pct if generator.last_frame else None
    events = []
    for _ in range(12):
        events.extend(engine.observe(generator.step()))
    assert any(event["type"] == "response.verified" for event in events)
    assert engine.get_incident(incident.incident_id).response_status == "VERIFIED"
    assert fuel_at_override is not None
    assert generator.last_frame is not None
    assert generator.last_frame.fuel_level_pct >= fuel_at_override - 0.1


def test_fuel_scenario_can_be_replayed_after_automatic_stop():
    generator = MachineGenerator(
        seed=17,
        scenario=make_spec(ScenarioType.FUEL_LEAK, severity=0.9, onset_offset_s=5, ramp_s=1, duration_s=300, abate_s=30),
    )
    engine = IntelligenceEngine("MX-101")

    for _ in range(400):
        events = engine.observe(generator.step())
        override = next((event for event in events if event["type"] == "automatic_override"), None)
        if override:
            generator.apply_operator_action(override["action"])
            break
    assert override is not None

    engine.reset_for_scenario()
    generator.apply_operator_action("RESUME")
    generator.inject(make_spec(ScenarioType.FUEL_LEAK, severity=0.9, onset_offset_s=5, ramp_s=1, duration_s=300, abate_s=30))

    replay_override = None
    for _ in range(400):
        events = engine.observe(generator.step())
        replay_override = next((event for event in events if event["type"] == "automatic_override"), None)
        if replay_override:
            break
    assert replay_override is not None
    assert replay_override["action"] == "STOP_MACHINE"
