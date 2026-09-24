"""Integration gate: start session via API, stream frames over WebSocket."""
from __future__ import annotations

import json


def test_system_status(client):
    r = client.get("/api/system/status")
    assert r.status_code == 200
    body = r.json()
    assert body["data_mode"] == "SIMULATION"
    assert "disclaimer" in body
    assert "Caterpillar" in body["disclaimer"]


def test_start_stop_lifecycle(client):
    r = client.post("/api/simulation/start", json={"machine_id": "MX-101", "seed": 77, "speed": 1.0})
    assert r.status_code == 200
    info = r.json()
    assert info["machine_id"] == "MX-101"
    assert info["running"] is True

    r2 = client.get("/api/simulation/status")
    assert r2.status_code == 200
    assert "MX-101" in r2.json()["sessions"]

    r3 = client.post("/api/simulation/stop", json={"machine_id": "MX-101"})
    assert r3.status_code == 200


def test_state_endpoint_returns_situation(client):
    import time

    client.post("/api/simulation/start", json={"machine_id": "MX-101", "seed": 88, "speed": 30})
    body = None
    # the first frame is produced by the background sim loop; poll briefly
    for _ in range(30):
        r = client.get("/api/state/MX-101")
        if r.status_code == 200:
            body = r.json()
            break
        time.sleep(0.05)
    assert body is not None, "state endpoint did not return a frame in time"
    assert body["frame"]["Machine_ID"] == "MX-101"
    assert body["situation"]["machine_health"] == "HEALTHY"
    assert "Timestamp" in body["frame"]
    client.post("/api/simulation/stop", json={"machine_id": "MX-101"})


def test_websocket_streams_frames(client):
    client.post("/api/simulation/start", json={"machine_id": "MX-101", "seed": 99, "speed": 30})
    collected = []
    with client.websocket_connect("/ws/telemetry?machine_id=MX-101") as ws:
        ws.send_text("hello")  # protocol-level keepalive
        for _ in range(4):
            data = json.loads(ws.receive_text())
            if data.get("type") == "frame":
                collected.append(data["frame"])
    client.post("/api/simulation/stop", json={"machine_id": "MX-101"})

    assert len(collected) >= 2
    first, last = collected[0], collected[-1]
    assert first["Machine_ID"] == "MX-101"
    assert last["Timestamp"] >= first["Timestamp"]
    # normal operation: fuel should be drifting downward overall
    assert last["fuel_level_pct"] <= first["fuel_level_pct"] + 1e-9