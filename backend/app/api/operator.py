"""Direct simulated operator inputs such as the seatbelt sensor."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import authorize

router = APIRouter(prefix="/api/operator", tags=["operator"])


class OperatorInput(BaseModel):
    machine_id: str = "MX-101"
    action: str = Field(pattern="^(FASTEN_SEATBELT|UNFASTEN_SEATBELT|TOGGLE_SEATBELT|STOP_MACHINE|REDUCE_LOAD|RESUME)$")


@router.post("/input")
async def operator_input(body: OperatorInput, request: Request):
    authorize(request, {"operator", "supervisor"})
    try:
        return request.app.state.sim.operator_input(body.machine_id, body.action)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
