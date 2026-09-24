"""API surfaces for scenarios, schedules, and situation forecasts."""
from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.main import create_app


def test_scenario_catalog_and_task_schedule():
    with TestClient(create_app()) as client:
        scenarios = client.get("/api/simulation/scenarios")
        assert scenarios.status_code == 200
        types = {item["type"] for item in scenarios.json()["scenarios"]}
        assert "FUEL_LEAK" in types
        assert "BATTERY_ANOMALY" in types

        tasks = client.get("/api/tasks/today?machine_id=MX-101")
        assert tasks.status_code == 200
        assert tasks.json()["tasks"][0]["Task_Type"] == "EXCAVATION"
        assert tasks.json()["tasks"][0]["model_predicted_min"] > 0
        assert tasks.json()["eta_model"]["holdout_mae_minutes"] > 0


def test_demo_boot_starts_every_fleet_machine():
    with TestClient(create_app()) as client:
        reset = client.post("/api/demo/reset")
        assert reset.status_code == 200
        boot = client.post("/api/demo/boot")
        assert boot.status_code == 200
        assert boot.json()["machines"] == [True, True, True]
        overview = client.get("/api/fleet/overview")
        assert overview.status_code == 200
        assert all(machine["live"] for machine in overview.json()["machines"])
        client.post("/api/demo/reset")


def test_training_api_runs_decision_workflow():
    with TestClient(create_app()) as client:
        modules = client.get("/api/training/modules")
        assert modules.status_code == 200
        module_id = modules.json()["modules"][0]["module_id"]
        started = client.post("/api/training/sessions", json={"module_id": module_id, "operator_id": "OP-01"})
        assert started.status_code == 200
        state = started.json()
        assert "correct" not in state["step"]
        action = state["step"]["options"][0]
        result = client.post(f"/api/training/sessions/{state['session_id']}/actions", json={"action": action})
        assert result.status_code == 200
        assert "feedback" in result.json()

        safety = client.get("/api/safety/procedures")
        assert safety.status_code == 200
        assert safety.json()["procedures"]


def test_analytics_overview_contract():
    with TestClient(create_app()) as client:
        response = client.get("/api/analytics/overview?machine_id=MX-101")
        assert response.status_code == 200
        body = response.json()
        assert body["data_mode"] == "SYNTHETIC_ANALYTICS"
        assert "metrics" in body
        assert "by_type" in body
        assert "recent_incidents" in body


def test_machine_assistant_is_grounded_in_current_context():
    with TestClient(create_app()) as client:
        started = client.post("/api/simulation/start", json={"machine_id": "MX-103", "seed": 811})
        assert started.status_code == 200
        time.sleep(0.05)
        response = client.post("/api/assistant/message", json={"machine_id": "MX-103", "message": "Is it safe to continue?"})
        assert response.status_code == 200
        body = response.json()
        assert body["grounded"] is True
        assert body["context"]["machine_id"] == "MX-103"
        client.post("/api/simulation/stop", json={"machine_id": "MX-103"})


def test_dashboard_what_if_and_demo_reset_contract():
    with TestClient(create_app()) as client:
        started = client.post("/api/simulation/start", json={"machine_id": "MX-102", "seed": 812})
        assert started.status_code == 200
        dashboard = client.get("/api/dashboard/MX-102")
        assert dashboard.status_code == 200
        assert dashboard.json()["pre_start"]["readiness"] in ("READY", "ATTENTION")

        projection = client.post("/api/what-if/project", json={"machine_id": "MX-102", "action": "STOP"})
        assert projection.status_code == 200
        assert projection.json()["grounded"] is True

        reset = client.post("/api/demo/reset")
        assert reset.status_code == 200
        assert reset.json()["reset"] is True


def test_predictive_fleet_threshold_and_seatbelt_contracts():
    with TestClient(create_app()) as client:
        started = client.post("/api/simulation/start", json={"machine_id": "MX-103", "seed": 813})
        assert started.status_code == 200
        dashboard = client.get("/api/dashboard/MX-103").json()
        assert "pre_shift_risk" in dashboard["situation"]
        assert "component_health" in dashboard["situation"]
        assert "productivity" in dashboard["situation"]

        seatbelt = client.post("/api/operator/input", json={"machine_id": "MX-103", "action": "TOGGLE_SEATBELT"})
        assert seatbelt.status_code == 200
        fleet = client.get("/api/fleet/overview")
        assert fleet.status_code == 200
        assert any(item["machine_id"] == "MX-103" for item in fleet.json()["machines"])

        thresholds = client.get("/api/config/thresholds")
        assert thresholds.status_code == 200
        practice = client.post("/api/practice/compare", json={"machine_id": "MX-103"})
        assert practice.status_code == 200
        assert len(practice.json()["comparisons"]) == 4
        client.post("/api/demo/reset")
