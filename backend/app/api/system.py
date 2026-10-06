"""System-level endpoints: data mode + source disclaimer."""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status")
async def system_status(request: Request):
    sim = request.app.state.sim
    return {
        "name": "CommandGuard",
        "data_mode": "SIMULATION",
        "running": any(session.running for session in sim.sessions.values()),
        "disclaimer": (
            "Simulated telemetry only. This application runs entirely on synthetic "
            "data: it is not connected to any real machine and does not use "
            "proprietary manufacturer data."
        ),
        "version": "0.5.0-hackathon",
    }


@router.get("/data-modes")
async def data_modes():
    return {
        "active": "SIMULATION",
        "modes": [
            {"mode": "SIMULATION", "available": True, "description": "Causal synthetic telemetry for demonstration."},
            {"mode": "REPLAY", "available": True, "description": "Persisted incident and historical telemetry replay."},
            {"mode": "LIVE_STUB", "available": True, "description": "Queue-backed contract adapter for integration tests."},
            {"mode": "LIVE", "available": False, "description": "Opt-in read-only HTTP gateway adapter; requires approved deployment configuration."},
        ],
    }
