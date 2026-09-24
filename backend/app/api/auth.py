"""Demo authentication endpoints for the standalone prototype."""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.auth import current_principal

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    operator_id: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=1, max_length=128)


@router.post("/login")
async def login(body: LoginRequest, request: Request):
    return request.app.state.auth.login(body.operator_id, body.password)


@router.get("/me")
async def me(request: Request):
    principal, authenticated = current_principal(request)
    return {"authenticated": authenticated, "principal": principal.__dict__}
