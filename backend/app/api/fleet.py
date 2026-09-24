"""Supervisor fleet overview."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.simulation.catalog import MACHINES

router = APIRouter(prefix="/api/fleet", tags=["fleet"])


@router.get("/overview")
async def fleet_overview(request: Request):
    sim = request.app.state.sim
    machines = []
    for machine_id, config in MACHINES.items():
        frame = sim.latest(machine_id)
        session = sim.sessions.get(machine_id)
        running = session is not None and session.running
        situation = sim.latest_situation(machine_id)
        incidents = [item for item in sim.incidents(machine_id) if item.get("status") == "ACTIVE"]
        machines.append(
            {
                "machine_id": machine_id,
                "model": config.model,
                "site": config.site_key,
                "live": frame is not None and running,
                "operator_id": frame.operator_id if frame else config.dem_operator_id,
                "machine_health": situation.machine_health if situation else "OFFLINE",
                "current_risk": situation.current_risk if situation else "UNKNOWN",
                "pre_shift_risk": situation.pre_shift_risk if situation else "UNKNOWN",
                "behavior_score": situation.behavior_score if situation else None,
                "fatigue_risk": situation.fatigue_risk if situation else "UNKNOWN",
                "task": situation.task if situation else None,
                "eta_minutes": situation.eta_minutes if situation else None,
                "active_incidents": incidents,
                "component_health": situation.component_health if situation else {},
            }
        )
    return {"data_mode": "SIMULATION", "machines": machines}
