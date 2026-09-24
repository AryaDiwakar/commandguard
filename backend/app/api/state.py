"""Current machine state snapshot (frame + derived situation)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/state", tags=["state"])


@router.get("/{machine_id}")
async def state(machine_id: str, request: Request):
    sim = request.app.state.sim
    frame = sim.latest(machine_id)
    if frame is None:
        raise HTTPException(status_code=404, detail=f"No session / frame for {machine_id}")
    situation = sim.latest_situation(machine_id)
    return {
        "frame": frame.to_public_dict(),
        "situation": situation.model_dump(mode="json") if situation else None,
    }
