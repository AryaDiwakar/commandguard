"""Explainable synthetic counterfactual projections."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter(prefix="/api/what-if", tags=["what-if"])


class WhatIfRequest(BaseModel):
    machine_id: str = settings.default_machine_id
    action: str = Field(pattern="^(CONTINUE|STOP|REDUCE_LOAD)$")


@router.post("/project")
async def project(body: WhatIfRequest, request: Request):
    sim = request.app.state.sim
    frame = sim.latest(body.machine_id)
    situation = sim.latest_situation(body.machine_id)
    if frame is None or situation is None:
        raise HTTPException(status_code=404, detail="No current machine session")

    current_risk = situation.current_risk
    current_eta = situation.eta_minutes
    risks = situation.predicted_risks
    if body.action == "STOP":
        projected_risk = "LOW" if situation.safety_state == "SAFE" else "MEDIUM"
        projected_eta = current_eta + 5.0
        message = "Stopping reduces active operating exposure. Task completion is delayed by the safe-stop and restart window."
        assumptions = ["Machine reaches a verified stationary state", "No new incident signal appears while stopped"]
    elif body.action == "REDUCE_LOAD":
        projected_risk = "MEDIUM" if current_risk in ("HIGH", "CRITICAL") else "LOW"
        projected_eta = current_eta * 1.08
        message = "Reducing load lowers stress and may slow the current risk trajectory, with a modest productivity penalty."
        assumptions = ["Load is reduced by approximately 20%", "Operator maintains controlled movement"]
    else:
        projected_risk = "HIGH" if risks or current_risk in ("HIGH", "CRITICAL") else current_risk
        projected_eta = current_eta
        message = "Continuing preserves task momentum but allows the current risk trajectory to continue."
        assumptions = ["Current operating inputs remain unchanged", "No corrective action is taken"]
    return {
        "machine_id": body.machine_id,
        "action": body.action,
        "grounded": True,
        "current": {"risk": current_risk, "eta_minutes": current_eta, "safety": situation.safety_state},
        "projection": {"risk": projected_risk, "eta_minutes": round(projected_eta, 1), "message": message},
        "assumptions": assumptions,
        "evidence": risks,
    }
