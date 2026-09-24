"""Interactive training and adaptive recommendation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import authorize

router = APIRouter(prefix="/api/training", tags=["training"])


class StartTrainingRequest(BaseModel):
    module_id: str
    operator_id: str = "OP-01"


class TrainingActionRequest(BaseModel):
    action: str = Field(min_length=2, max_length=48)


@router.get("/modules")
async def modules(request: Request):
    return {"modules": request.app.state.training.modules()}


@router.get("/recommendations/{operator_id}")
async def recommendations(operator_id: str, request: Request):
    incidents = []
    for session in request.app.state.sim.sessions.values():
        if session.intelligence:
            incidents.extend(item.to_dict() for item in session.intelligence.incidents() if item.operator_id == operator_id)
    return {"operator_id": operator_id, "recommendations": request.app.state.training.recommendations(incidents)}


@router.post("/sessions")
async def start_training(body: StartTrainingRequest, request: Request):
    authorize(request, {"operator", "supervisor"})
    try:
        return request.app.state.training.start(body.module_id, body.operator_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/actions")
async def training_action(session_id: str, body: TrainingActionRequest, request: Request):
    authorize(request, {"operator", "supervisor"})
    try:
        return request.app.state.training.act(session_id, body.action)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
