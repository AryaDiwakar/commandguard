"""Headless end-to-end smoke for Phase 1 (server-less via TestClient)."""
from __future__ import annotations

import json
import sys
import time

from fastapi.testclient import TestClient

sys.path.insert(0, ".")
from app.main import create_app

with TestClient(create_app()) as client:
    status = client.get("/api/system/status").json()
    assert status["data_mode"] == "SIMULATION"
    print("[ok] system status:", status["data_mode"])

    r = client.post("/api/simulation/start", json={"machine_id": "MX-101", "seed": 4242, "speed": 30})
    assert r.status_code == 200, r.text
    print("[ok] session started:", r.json()["session_id"])

    time.sleep(0.3)

    st = client.get("/api/simulation/status").json()
    n = st["sessions"]["MX-101"]["frames_captured"]
    assert n > 0, "no frames captured"
    print(f"[ok] frames captured: {n}")

    body = client.get("/api/state/MX-101").json()
    f = body["frame"]
    for col in ["Timestamp", "Machine_ID", "Operator_ID", "Engine_Hours", "Fuel_Used_L",
                "Load_Cycles", "Idling_Time_min", "Seatbelt_Status", "Safety_Alert_Triggered"]:
        assert col in f, f"missing {col}"
    print("[ok] required schema columns present; situation=", body["situation"]["operating_state"], body["situation"]["machine_health"])

    frames = []
    with client.websocket_connect("/ws/telemetry?machine_id=MX-101") as ws:
        for _ in range(5):
            data = json.loads(ws.receive_text())
            if data.get("type") == "frame":
                frames.append(data["frame"])
    assert len(frames) >= 2
    assert frames[-1]["fuel_level_pct"] <= frames[0]["fuel_level_pct"] + 1e-9
    print(f"[ok] ws streamed {len(frames)} frames; fuel monotone: "
          f"{frames[0]['fuel_level_pct']:.3f} -> {frames[-1]['fuel_level_pct']:.3f}")

    client.post("/api/simulation/stop", json={"machine_id": "MX-101"})
    print("[ok] session stopped")
    print("SMOKE PASSED")