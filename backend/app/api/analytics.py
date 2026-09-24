"""Operational analytics derived from persisted synthetic incidents."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request

from app.db import SessionLocal
from app.dataset.tasks import generate_task_history
from app.ml.eta import eta_model
from app.models import IncidentRecord

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview")
async def overview(
    request: Request,
    machine_id: str | None = Query(default=None),
    operator_id: str | None = Query(default=None),
):
    db = SessionLocal()()
    try:
        query = db.query(IncidentRecord).order_by(IncidentRecord.Detected_At.desc())
        if machine_id:
            query = query.filter(IncidentRecord.Machine_ID == machine_id)
        if operator_id:
            query = query.filter(IncidentRecord.Operator_ID == operator_id)
        rows = query.all()
    finally:
        db.close()

    by_type = Counter(row.Incident_Type for row in rows)
    by_severity = Counter(row.Severity for row in rows)
    by_response = Counter(row.Response_Status for row in rows)
    daily = Counter(row.Detected_At.date().isoformat() for row in rows if row.Detected_At)
    resolved = [row for row in rows if row.Status == "RESOLVED"]
    verified = [row for row in rows if row.Response_Status == "VERIFIED"]

    current_situation = None
    if machine_id:
        situation = request.app.state.sim.latest_situation(machine_id)
        current_situation = situation.model_dump(mode="json") if situation else None

    task_frame = generate_task_history(seed=2026, n_days=30)
    if machine_id:
        task_frame = task_frame[task_frame["Machine_ID"] == machine_id]
    if operator_id:
        task_frame = task_frame[task_frame["Operator_ID"] == operator_id]
    task_metrics = {
        "tasks": int(len(task_frame)),
        "average_estimated_minutes": round(float(task_frame["Estimated_Time_min"].mean()), 1) if len(task_frame) else 0.0,
        "average_actual_minutes": round(float(task_frame["Actual_Time_min"].mean()), 1) if len(task_frame) else 0.0,
        "average_efficiency": round(float(task_frame["Efficiency_Factor"].mean()), 3) if len(task_frame) else 0.0,
        "over_estimate_rate": round(float((task_frame["Actual_Time_min"] > task_frame["Estimated_Time_min"]).mean()), 3) if len(task_frame) else 0.0,
    }
    operator_performance = []
    for operator, group in task_frame.groupby("Operator_ID") if len(task_frame) else []:
        operator_incidents = [row for row in rows if row.Operator_ID == operator]
        verified_count = sum(row.Response_Status == "VERIFIED" for row in operator_incidents)
        operator_performance.append({
            "operator_id": operator,
            "tasks": int(len(group)),
            "average_efficiency": round(float(group["Efficiency_Factor"].mean()), 3),
            "incidents": len(operator_incidents),
            "verified_response_rate": round(verified_count / len(operator_incidents), 3) if operator_incidents else 0.0,
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_mode": "SYNTHETIC_ANALYTICS",
        "history": {
            "label": "30-DAY SYNTHETIC HISTORY",
            "source": "generate_task_history",
            "days": 30,
            "rows": int(len(task_frame)),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "filters": {"machine_id": machine_id, "operator_id": operator_id},
        "metrics": {
            "total_incidents": len(rows),
            "active_incidents": sum(row.Status == "ACTIVE" for row in rows),
            "resolved_incidents": len(resolved),
            "high_critical_incidents": sum(row.Severity in ("HIGH", "CRITICAL") for row in rows),
            "verified_responses": len(verified),
            "response_verification_rate": round(len(verified) / len(rows), 3) if rows else 0.0,
            "average_confidence": round(sum(row.Confidence for row in rows) / len(rows), 3) if rows else 0.0,
        },
        "by_type": [{"label": label, "count": count} for label, count in by_type.most_common()],
        "by_severity": [{"label": label, "count": count} for label, count in by_severity.most_common()],
        "by_response": [{"label": label, "count": count} for label, count in by_response.most_common()],
        "daily_trend": [{"date": date, "count": count} for date, count in sorted(daily.items())],
        "recent_incidents": [
            {
                "incident_id": row.incident_id,
                "machine_id": row.Machine_ID,
                "operator_id": row.Operator_ID,
                "type": row.Incident_Type,
                "severity": row.Severity,
                "status": row.Status,
                "response_status": row.Response_Status,
                "confidence": row.Confidence,
                "detected_at": row.Detected_At.isoformat() if row.Detected_At else None,
            }
            for row in rows[:10]
        ],
        "current_situation": current_situation,
        "eta_model": eta_model().status.__dict__,
        "task_metrics": task_metrics,
        "operator_performance": operator_performance,
    }
