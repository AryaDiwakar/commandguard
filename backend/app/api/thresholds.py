"""Supervisor/admin configuration for synthetic site thresholds."""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.auth import authorize

router = APIRouter(prefix="/api/config/thresholds", tags=["thresholds"])


class ThresholdUpdate(BaseModel):
    profile: str = Field(default="DEFAULT", min_length=2, max_length=48)
    values: dict[str, float]


@router.get("")
async def get_thresholds(request: Request):
    return {"profiles": request.app.state.thresholds.profiles()}


@router.put("")
async def update_thresholds(body: ThresholdUpdate, request: Request):
    authorize(request, {"supervisor", "maintenance", "admin"})
    return {"profile": body.profile, "thresholds": request.app.state.thresholds.update(body.profile, body.values)}
