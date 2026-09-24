"""API wiring for scenarios: start-with-script + live inject."""
from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.main import create_app


def _client():
    c = TestClient(create_app())
    c.__enter__()
    return c


def test_start_session_with_scenario_script():
    client = _client()
    try:
        r = client.post("/api/simulation/start", json={
            "machine_id": "MX-101",
            "seed": 3,
            "scenario": {"type": "FUEL_LEAK", "severity": 0.7, "onset_offset_s": 30},
        })
        assert r.status_code == 200, r.text
        assert r.json()["session_id"] == "S-MX-101-3"

        time.sleep(0.1)
        body = client.get("/api/state/MX-101").json()
        f = body["frame"]
        assert "scenario_type" not in f
        assert "anomaly_label" not in f
    finally:
        client.__exit__(None, None, None)


def test_live_inject_endpoint_changes_scenario():
    client = _client()
    try:
        client.post("/api/simulation/start", json={"machine_id": "MX-102", "seed": 5})
        time.sleep(0.1)
        r = client.post("/api/simulation/scenario", json={
            "machine_id": "MX-102",
            "scenario": {"type": "ENGINE_OVERHEAT", "severity": 0.85, "onset_offset_s": 60},
        })
        assert r.status_code == 200, r.text
        assert r.json()["onset_s"] == 60

        body = client.get("/api/state/MX-102").json()
        assert "scenario_type" not in body["frame"]
    finally:
        client.__exit__(None, None, None)


def test_inject_requires_running_session():
    client = _client()
    try:
        r = client.post("/api/simulation/scenario", json={
            "machine_id": "MX-999",
            "scenario": {"type": "FUEL_LEAK"},
        })
        assert r.status_code == 409
    finally:
        client.__exit__(None, None, None)


def test_unsafe_scenario_raises_400():
    client = _client()
    try:
        r = client.post("/api/simulation/start", json={
            "machine_id": "MX-101",
            "scenario": {"type": "ENGINE_OVERHEAT", "severity": 2.0},
        })
        assert r.status_code == 422
    finally:
        client.__exit__(None, None, None)
