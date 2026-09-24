"""Command-center aggregation for the operator dashboard."""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException, Query, Request

from app.simulation.catalog import MACHINES
from app.dataset.tasks import generate_shift_schedule

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _ensure_machine(machine_id: str) -> None:
    if machine_id not in MACHINES:
        raise HTTPException(status_code=404, detail=f"Unknown machine {machine_id}")


@router.get("/{machine_id}")
async def dashboard(machine_id: str, request: Request):
    _ensure_machine(machine_id)
    sim = request.app.state.sim
    frame = sim.latest(machine_id)
    situation = sim.latest_situation(machine_id)
    incidents = sim.incidents(machine_id)
    tasks = generate_shift_schedule(machines=(machine_id,)).to_dict(orient="records")
    active = [item for item in incidents if item.get("status") == "ACTIVE"]
    # Follow the live task plan: the frame carries the current task index so
    # the dashboard picks the matching scheduled job after each rollover.
    current_task = tasks[0] if tasks else None
    if frame and tasks:
        idx = min(max(0, getattr(frame, "task_index", 0)), len(tasks) - 1)
        current_task = tasks[idx]
    if situation:
        pre_start = {
            "readiness": "ATTENTION" if active or situation.current_risk in ("HIGH", "CRITICAL") else "READY",
            "focus": [
                "Confirm seatbelt and work-zone clearance before movement.",
                f"Review current ETA of {situation.eta_minutes:.1f} minutes before starting the task.",
            ],
            "environment": {
                "terrain": frame.terrain_condition.value if frame else None,
                "visibility_m": frame.visibility_m if frame else None,
                "weather": frame.weather_event.value if frame else None,
            },
        }
    else:
        pre_start = {"readiness": "NO_SESSION", "focus": ["Start the synthetic machine session before beginning a task."], "environment": {}}

    by_type = Counter(item.get("incident_type") for item in incidents)
    shift_handoff = {
        "open_incidents": active,
        "recent_incidents": incidents[-5:],
        "machine_state": situation.model_dump(mode="json") if situation else None,
        "handoff_notes": [
            f"{count} {label.replace('_', ' ').lower()} event(s) recorded." for label, count in by_type.most_common()
        ] or ["No incidents recorded for this machine."],
    }
    return {
        "machine_id": machine_id,
        "data_mode": "SIMULATION",
        "live": frame is not None,
        "frame": frame.to_public_dict() if frame else None,
        "situation": situation.model_dump(mode="json") if situation else None,
        "active_incidents": active,
        "recent_incidents": incidents[-5:],
        "current_task": current_task,
        "task_schedule": tasks,
        "pre_start": pre_start,
        "shift_handoff": shift_handoff,
    }


@router.get("/{machine_id}/brief")
async def pre_start_brief(machine_id: str, request: Request):
    data = await dashboard(machine_id, request)
    return {"machine_id": machine_id, "brief_type": "PRE_START", **data["pre_start"], "task": data["current_task"], "situation": data["situation"]}


@router.get("/{machine_id}/handoff")
async def shift_handoff(machine_id: str, request: Request):
    data = await dashboard(machine_id, request)
    return {"machine_id": machine_id, "brief_type": "SHIFT_HANDOFF", **data["shift_handoff"]}
