"""Knowledge, auth, and deployment-boundary contracts."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_knowledge_search_returns_approved_sources():
    with TestClient(create_app()) as client:
        response = client.get("/api/knowledge/search?query=what should I do for a fuel leak")
        assert response.status_code == 200
        assert response.json()["results"][0]["source"].startswith("approved://")


def test_demo_auth_exposes_role_and_restricts_supervisor_action():
    with TestClient(create_app()) as client:
        login = client.post("/api/auth/login", json={"operator_id": "OP-01", "password": "demo"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["authenticated"] is True
        assert me.json()["principal"]["role"] == "operator"
        denied = client.post(
            "/api/incidents/MX-101/acknowledge",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert denied.status_code == 403


def test_data_modes_mark_live_gateway_as_opt_in():
    with TestClient(create_app()) as client:
        response = client.get("/api/system/data-modes")
        assert response.status_code == 200
        modes = {item["mode"]: item for item in response.json()["modes"]}
        assert modes["SIMULATION"]["available"] is True
        assert modes["LIVE"]["available"] is False
