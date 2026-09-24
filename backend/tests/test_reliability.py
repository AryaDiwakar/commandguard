"""Reliability contracts: session lifecycle, valid IDs, normal mode, live speed."""
from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.main import create_app


def _client():
    c = TestClient(create_app())
    c.__enter__()
    return c


def test_stopped_session_reports_offline_everywhere():
    client = _client()
    try:
        client.post("/api/demo/reset")
        r = client.post("/api/simulation/start", json={"machine_id": "MX-101", "seed": 11, "speed": 1.0})
        assert r.status_code == 200
        time.sleep(0.1)

        client.post("/api/simulation/stop", json={"machine_id": "MX-101"})

        status = client.get("/api/system/status").json()
        assert status["running"] is False

        assert client.get("/api/state/MX-101").status_code == 404

        overview = client.get("/api/fleet/overview").json()
        machine = next(item for item in overview["machines"] if item["machine_id"] == "MX-101")
        assert machine["live"] is False
        assert machine["machine_health"] == "OFFLINE"
    finally:
        client.__exit__(None, None, None)


def test_unknown_machine_and_operator_start_are_404():
    client = _client()
    try:
        assert client.post("/api/simulation/start", json={"machine_id": "MX-999"}).status_code == 404
        assert client.post("/api/simulation/start", json={"machine_id": "MX-101", "operator_id": "OP-99"}).status_code == 404
        assert client.post("/api/simulation/start", json={"machine_id": "MX-101", "operator_id": "OP-01"}).status_code == 200
    finally:
        client.__exit__(None, None, None)


def test_dashboard_and_tasks_unknown_machine_are_404():
    client = _client()
    try:
        assert client.get("/api/dashboard/MX-999").status_code == 404
        assert client.get("/api/dashboard/MX-999/brief").status_code == 404
        assert client.get("/api/dashboard/MX-999/handoff").status_code == 404
        assert client.get("/api/tasks/today?machine_id=MX-999").status_code == 404
    finally:
        client.__exit__(None, None, None)


def test_normal_operation_session_starts_and_runs_without_crash():
    client = _client()
    try:
        r = client.post("/api/simulation/start", json={
            "machine_id": "MX-103",
            "seed": 21,
            "scenario": {"type": "NORMAL_OPERATION"},
        })
        assert r.status_code == 200, r.text
        time.sleep(0.1)
        body = client.get("/api/state/MX-103").json()
        assert body["situation"]["operating_state"] == "ACTIVE"
        assert client.get("/api/system/status").json()["running"] is True
    finally:
        client.__exit__(None, None, None)


def test_speed_change_mutates_running_session_live():
    client = _client()
    try:
        client.post("/api/demo/reset")
        client.post("/api/simulation/start", json={"machine_id": "MX-101", "seed": 4, "speed": 2.0})
        time.sleep(0.1)

        r = client.patch("/api/simulation/MX-101/speed", json={"speed": 10.0})
        assert r.status_code == 200, r.text
        assert r.json()["speed"] == 10.0

        status = client.get("/api/simulation/status").json()
        assert status["sessions"]["MX-101"]["speed"] == 10.0

        assert client.patch("/api/simulation/MX-999/speed", json={"speed": 5.0}).status_code == 409

        client.post("/api/simulation/stop", json={"machine_id": "MX-101"})
        assert client.patch("/api/simulation/MX-101/speed", json={"speed": 5.0}).status_code == 409
    finally:
        client.__exit__(None, None, None)