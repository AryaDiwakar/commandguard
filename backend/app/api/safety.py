"""Approved, non-repair safety guidance for the operator experience."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/safety", tags=["safety"])


@router.get("/procedures")
async def procedures():
    return {
        "procedures": [
            {"id": "safe_stop", "title": "Safe stop", "severity": "HIGH", "steps": ["Reduce load if safe", "Stop movement", "Confirm the work area is clear", "Request support if the condition persists"]},
            {"id": "thermal", "title": "Thermal escalation", "severity": "HIGH", "steps": ["Reduce machine load", "Monitor engine and coolant temperature", "Stop safely if the trend continues", "Escalate to maintenance or safety personnel"]},
            {"id": "proximity", "title": "Proximity hazard", "severity": "CRITICAL", "steps": ["Stop movement if safe", "Keep the machine stationary", "Confirm the area is clear", "Resume only when authorized"]},
            {"id": "seatbelt", "title": "Seatbelt compliance", "severity": "HIGH", "steps": ["Stop movement", "Fasten the seatbelt", "Confirm the safety state", "Resume only when secure"]},
        ]
    }
