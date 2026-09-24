"""Optional operator onboarding (local profile, not real authentication)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.db import SessionLocal
from app.models import UserProfile

router = APIRouter(prefix="/api/onboard", tags=["onboard"])


class ProfileIn(BaseModel):
    operator_id: str = Field(min_length=2, max_length=32)
    display_name: str = Field(min_length=1, max_length=80)
    skill: str = Field(default="Intermediate")
    experience_years: float = Field(default=3.0, ge=0.0, le=50.0)
    machine_id: str = "MX-101"
    site_key: str = "QUARRY-NORTH"


@router.get("/profile")
async def get_profile():
    db = SessionLocal()()
    try:
        prof = db.query(UserProfile).order_by(UserProfile.id.asc()).first()
        return {"profile": prof.profile_dict() if prof else None}
    finally:
        db.close()


@router.post("/profile")
async def upsert_profile(body: ProfileIn):
    db = SessionLocal()()
    try:
        prof = db.query(UserProfile).filter_by(operator_id=body.operator_id).first()
        if prof is None:
            prof = UserProfile(operator_id=body.operator_id)
            db.add(prof)
        prof.display_name = body.display_name
        prof.skill = body.skill
        prof.experience_years = body.experience_years
        prof.machine_id = body.machine_id
        prof.site_key = body.site_key
        db.commit()
        db.refresh(prof)
        return {"profile": prof.profile_dict()}
    finally:
        db.close()