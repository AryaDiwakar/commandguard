"""Prototype token authentication and role authorization.

The local hackathon mode remains usable without login. Supplying a bearer token
activates role checks; production deployment should replace the demo issuer with
an enterprise identity provider.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request


@dataclass(frozen=True)
class Principal:
    operator_id: str
    role: str
    display_name: str


DEMO_USERS: dict[str, dict[str, str]] = {
    "OP-01": {"password": "demo", "role": "operator", "display_name": "A. Wakar"},
    "SUP-01": {"password": "demo", "role": "supervisor", "display_name": "Shift Supervisor"},
    "MNT-01": {"password": "demo", "role": "maintenance", "display_name": "Maintenance Desk"},
    "ADMIN-01": {"password": "demo", "role": "admin", "display_name": "System Admin"},
}


class AuthService:
    def __init__(self) -> None:
        self.tokens: dict[str, Principal] = {}

    def login(self, operator_id: str, password: str) -> dict[str, Any]:
        user = DEMO_USERS.get(operator_id)
        if user is None or not secrets.compare_digest(user["password"], password):
            raise HTTPException(status_code=401, detail="Invalid demo credentials")
        token = secrets.token_urlsafe(24)
        principal = Principal(operator_id, user["role"], user["display_name"])
        self.tokens[token] = principal
        return {"access_token": token, "token_type": "bearer", "principal": principal.__dict__}

    def principal(self, token: str | None) -> Principal | None:
        return self.tokens.get(token) if token else None


def current_principal(request: Request) -> tuple[Principal, bool]:
    header = request.headers.get("authorization", "")
    token = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else None
    principal = request.app.state.auth.principal(token)
    if principal:
        return principal, True
    return Principal("OP-01", "operator", "Demo Operator"), False


def authorize(request: Request, roles: set[str]) -> Principal:
    principal, authenticated = current_principal(request)
    if authenticated and principal.role not in roles and principal.role != "admin":
        raise HTTPException(status_code=403, detail=f"Role {principal.role} cannot perform this action")
    return principal
