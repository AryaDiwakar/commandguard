"""Serializable intelligence objects shared by APIs and the frontend."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Evidence:
    signal: str
    observation: str
    expected: str
    contribution: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Incident:
    incident_id: str
    machine_id: str
    incident_type: str
    severity: str
    confidence: float
    detected_at: datetime
    detected_timestamp_ms: int = 0
    operator_id: str = ""
    task_id: str = ""
    task_type: str = ""
    session_id: str = ""
    status: str = "ACTIVE"
    evidence: list[Evidence] = field(default_factory=list)
    possible_causes: list[str] = field(default_factory=list)
    recommended_action: str = ""
    help_status: str = "NOT_REQUESTED"
    response_status: str = "NOT_STARTED"
    last_operator_action: str | None = None
    auto_reaction: str | None = None
    auto_reaction_reason: str | None = None
    timeline: list[dict[str, Any]] = field(default_factory=list)
    resolved_at: datetime | None = None
    resolved_timestamp_ms: int | None = None

    def add_event(self, event_type: str, message: str) -> None:
        self.timeline.append(
            {
                "type": event_type,
                "message": message,
                "timestamp": utc_now().isoformat(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["detected_at"] = self.detected_at.isoformat()
        result["resolved_at"] = self.resolved_at.isoformat() if self.resolved_at else None
        result["evidence"] = [item.to_dict() for item in self.evidence]
        return result
