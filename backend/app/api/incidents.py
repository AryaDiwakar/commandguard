"""Incident visibility, live-help relay, and operator response endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.auth import authorize
from app.reports.pdf import incident_pdf

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


class HelpRequest(BaseModel):
    incident_id: str | None = None
    channel: str = Field(default="SUPERVISOR", min_length=2, max_length=32)


class ActionRequest(BaseModel):
    action: str = Field(min_length=2, max_length=40)
    incident_id: str | None = None


@router.get("/{machine_id}")
async def list_incidents(machine_id: str, request: Request):
    return {"machine_id": machine_id, "incidents": request.app.state.sim.incidents(machine_id)}


@router.post("/{machine_id}/help")
async def request_help(machine_id: str, body: HelpRequest, request: Request):
    authorize(request, {"operator", "supervisor", "maintenance"})
    try:
        incident = await request.app.state.sim.request_help(
            machine_id,
            incident_id=body.incident_id,
            channel=body.channel,
        )
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"machine_id": machine_id, "relay": incident}


@router.post("/{machine_id}/acknowledge")
async def acknowledge_help(machine_id: str, body: HelpRequest, request: Request):
    authorize(request, {"supervisor", "maintenance"})
    try:
        incident = await request.app.state.sim.acknowledge_help(
            machine_id,
            incident_id=body.incident_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"machine_id": machine_id, "relay": incident}


@router.post("/{machine_id}/action")
async def operator_action(machine_id: str, body: ActionRequest, request: Request):
    authorize(request, {"operator", "supervisor"})
    try:
        incident = await request.app.state.sim.operator_action(
            machine_id,
            action=body.action,
            incident_id=body.incident_id,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"machine_id": machine_id, "action": body.action, "incident": incident}


@router.get("/{machine_id}/{incident_id}/report")
async def incident_report(machine_id: str, incident_id: str, request: Request):
    try:
        return request.app.state.sim.incident_report(machine_id, incident_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{machine_id}/{incident_id}/replay")
async def incident_replay(machine_id: str, incident_id: str, request: Request):
    try:
        return request.app.state.sim.incident_replay(machine_id, incident_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{machine_id}/{incident_id}/handoff")
async def maintenance_handoff(machine_id: str, incident_id: str, request: Request):
    try:
        report = request.app.state.sim.incident_report(machine_id, incident_id)
        replay = request.app.state.sim.incident_replay(machine_id, incident_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    incident = report["incident"]
    return {
        "packet_type": "MAINTENANCE_HANDOFF",
        "incident": incident,
        "machine_id": machine_id,
        "operator_id": incident.get("operator_id"),
        "task": incident.get("task_type"),
        "severity": incident.get("severity"),
        "evidence": incident.get("evidence", []),
        "operator_actions": report["operator_actions"],
        "outcome": report["outcome"],
        "recommended_follow_up": report["recommended_follow_up"],
        "replay_frame_count": len(replay["frames"]),
        "safe_boundary": "This packet supports escalation and investigation. It does not authorize repair or remote machine control.",
    }


@router.get("/{machine_id}/{incident_id}/pdf")
async def incident_pdf_export(machine_id: str, incident_id: str, request: Request):
    try:
        report = request.app.state.sim.incident_report(machine_id, incident_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=incident_pdf(report),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{incident_id}.pdf"'},
    )
