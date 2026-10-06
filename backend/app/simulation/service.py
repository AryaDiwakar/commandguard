"""SimService: orchestrates live sessions, ring buffers, and WS broadcast.

One asyncio task per machine session. Pacing = 1 real second per (1/speed)
sim frames → at speed N the UI receives N frames/sec.
"""
from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
import json
from typing import Any

from app.db import SessionLocal
from app.intelligence.engine import IntelligenceEngine
from app.models import IncidentRecord, ReplayFrameRecord
from app.config import Settings
from app.schemas.situation import MachineSituation, derive_situation
from app.schemas.telemetry import TelemetryFrame
from app.simulation.catalog import MACHINES, OPERATORS
from app.simulation.generator import MachineGenerator
from app.simulation.scenarios import ScenarioSpec
from app.ws.manager import ConnectionManager


class Session:
    def __init__(self, machine_id: str, seed: int, speed: float, session_id: str):
        self.machine_id = machine_id
        self.seed = seed
        self.speed = speed
        self.session_id = session_id
        self.generator: MachineGenerator | None = None
        self.intelligence: IntelligenceEngine | None = None
        self.ring: deque[TelemetryFrame] = deque(maxlen=0)
        self.running = False
        self.started_at: datetime | None = None

    def info(self) -> dict[str, Any]:
        return {
            "machine_id": self.machine_id,
            "session_id": self.session_id,
            "seed": self.seed,
            "speed": self.speed,
            "running": self.running,
            "started_at": self.started_at,
            "frames_captured": len(self.ring),
        }


class SimService:
    def __init__(self, settings: Settings, ws: ConnectionManager):
        self.settings = settings
        self.ws = ws
        self.sessions: dict[str, Session] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._seed_counter = 0

    # ------------------------------------------------------------- lifecycle
    async def start(
        self,
        machine_id: str | None = None,
        operator_id: str | None = None,
        seed: int | None = None,
        speed: float | None = None,
        scenario: ScenarioSpec | None = None,
    ) -> Session:
        machine_id = machine_id or self.settings.default_machine_id
        operator_id = operator_id or self.settings.default_operator_id
        if machine_id not in MACHINES:
            raise KeyError(f"Unknown machine {machine_id}")
        if operator_id not in OPERATORS:
            raise KeyError(f"Unknown operator {operator_id}")
        speed = min(self.settings.max_speed, max(1.0, speed or self.settings.default_speed))
        if seed is None:
            self._seed_counter += 7
            seed = self._seed_counter
        session_id = f"S-{machine_id}-{seed}"

        if machine_id in self.sessions and self.sessions[machine_id].running:
            raise RuntimeError(f"Session already running for machine {machine_id}")

        session = Session(machine_id=machine_id, seed=seed, speed=speed, session_id=session_id)
        session.generator = MachineGenerator(
            machine_id=machine_id,
            operator_id=operator_id or self.settings.default_operator_id,
            seed=seed,
            session_id=session_id,
            speed=speed,
            scenario=scenario,
        )
        session.intelligence = IntelligenceEngine(machine_id, window_size=self.settings.ring_size, session_id=session_id)
        session.ring = deque(maxlen=self.settings.ring_size)
        session.running = True
        session.started_at = datetime.now(timezone.utc)
        self.sessions[machine_id] = session
        self._tasks[machine_id] = asyncio.create_task(self._run(session))
        return session

    async def stop(self, machine_id: str) -> None:
        session = self.sessions.get(machine_id)
        if session is None:
            return
        session.running = False
        task = self._tasks.pop(machine_id, None)
        if task is not None:
            try:
                await asyncio.wait_for(task, timeout=3.0)
            except Exception:
                task.cancel()

    async def stop_all(self) -> None:
        """Stop every local simulation session for deterministic demo reset."""
        for machine_id in list(self.sessions):
            await self.stop(machine_id)

    async def reset_demo(self) -> None:
        """Clear runtime and persisted demo state for a clean presentation."""
        await self.stop_all()
        self.sessions.clear()
        self._tasks.clear()
        self._seed_counter = 0
        db = SessionLocal()()
        try:
            db.query(ReplayFrameRecord).delete()
            db.query(IncidentRecord).delete()
            db.commit()
        finally:
            db.close()

    def inject(self, machine_id: str, spec: ScenarioSpec) -> Session:
        session = self.sessions.get(machine_id)
        if session is None or session.generator is None:
            raise KeyError(f"No running session for machine {machine_id}")
        if session.intelligence is not None:
            for incident in session.intelligence.reset_for_scenario():
                self._persist_incident(incident)
        # A previous automatic safe-stop must not block the next practice run.
        session.generator.apply_operator_action("RESUME")
        session.generator.inject(spec)
        return session

    def latest(self, machine_id: str) -> TelemetryFrame | None:
        session = self.sessions.get(machine_id)
        if session is None or session.generator is None or not session.running:
            return None
        return session.generator.last_frame

    def latest_situation(self, machine_id: str) -> MachineSituation | None:
        frame = self.latest(machine_id)
        session = self.sessions.get(machine_id)
        incidents = session.intelligence.active_incidents() if session and session.intelligence else []
        predicted = session.intelligence.predicted_risks(frame) if session and session.intelligence and frame else []
        eta = session.intelligence.estimate_eta(frame) if session and session.intelligence and frame else {}
        predictive = session.intelligence.predictive_snapshot(frame) if session and session.intelligence and frame else {}
        return (
            derive_situation(frame, incidents=[item.to_dict() for item in incidents], predicted_risks=predicted, eta=eta, predictive=predictive)
            if frame is not None
            else None
        )

    def incidents(self, machine_id: str) -> list[dict[str, Any]]:
        session = self.sessions.get(machine_id)
        if session is not None and session.intelligence is not None:
            return [item.to_dict() for item in session.intelligence.incidents()]
        db = SessionLocal()()
        try:
            rows = db.query(IncidentRecord).filter_by(Machine_ID=machine_id).order_by(IncidentRecord.Detected_At.asc()).all()
            return [self._record_dict(row) for row in rows]
        finally:
            db.close()

    async def request_help(
        self,
        machine_id: str,
        incident_id: str | None = None,
        channel: str = "SUPERVISOR",
    ) -> dict[str, Any]:
        session = self._session_with_intelligence(machine_id)
        incident = session.intelligence.request_help(incident_id, channel)
        self._persist_incident(incident)
        await self._broadcast_incident_event(session, "help.requested", incident)
        return incident.to_dict()

    async def acknowledge_help(self, machine_id: str, incident_id: str | None = None) -> dict[str, Any]:
        session = self._session_with_intelligence(machine_id)
        incident = session.intelligence.acknowledge_help(incident_id)
        self._persist_incident(incident)
        await self._broadcast_incident_event(session, "help.acknowledged", incident)
        return incident.to_dict()

    async def operator_action(
        self,
        machine_id: str,
        action: str,
        incident_id: str | None = None,
    ) -> dict[str, Any]:
        session = self._session_with_intelligence(machine_id)
        if session.generator is None:
            raise KeyError(f"No running session for machine {machine_id}")
        if action == "RESUME":
            session.generator.resume_after_safety()
        else:
            session.generator.apply_operator_action(action)
        incident = session.intelligence.record_action(action, incident_id)
        self._persist_incident(incident)
        await self._broadcast_incident_event(session, "operator.action", incident)
        return incident.to_dict()

    def operator_input(self, machine_id: str, action: str) -> dict[str, Any]:
        session = self._session_with_intelligence(machine_id)
        if session.generator is None:
            raise KeyError(f"No running session for machine {machine_id}")
        if action == "RESUME":
            session.generator.resume_after_safety()
        else:
            session.generator.apply_operator_action(action)
        frame = session.generator.last_frame
        requested_status = "Fastened" if action == "FASTEN_SEATBELT" else "Unfastened" if action == "UNFASTEN_SEATBELT" else frame.seatbelt_status if frame else "UNKNOWN"
        return {
            "machine_id": machine_id,
            "action": action,
            "seatbelt_status": requested_status,
            "message": "Input accepted; the next telemetry frame will verify the state.",
        }

    def incident_report(self, machine_id: str, incident_id: str) -> dict[str, Any]:
        session = self.sessions.get(machine_id)
        incident = session.intelligence.get_incident(incident_id) if session and session.intelligence else None
        if incident is None:
            db = SessionLocal()()
            try:
                row = db.query(IncidentRecord).filter_by(incident_id=incident_id, Machine_ID=machine_id).first()
                if row is None:
                    raise KeyError(f"Incident {incident_id} not found for machine {machine_id}")
                data = self._record_dict(row)
            finally:
                db.close()
        else:
            data = incident.to_dict()
        actions = [item for item in data["timeline"] if item["type"] == "OPERATOR_ACTION"]
        return {
            "report_type": "SYNTHETIC_MACHINE_INCIDENT",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "incident": data,
            "operator_actions": actions,
            "outcome": "RESPONSE_VERIFIED" if data["response_status"] == "VERIFIED" else data["status"],
            "recommended_follow_up": "Escalate to designated maintenance or safety personnel.",
            "training_recommendation": "Fuel-system anomaly response and safe shutdown simulation.",
        }

    def incident_replay(self, machine_id: str, incident_id: str) -> dict[str, Any]:
        session = self.sessions.get(machine_id)
        incident = session.intelligence.get_incident(incident_id) if session and session.intelligence else None
        if incident is not None and session is not None:
            end_ms = incident.resolved_timestamp_ms or (session.ring[-1].timestamp_ms if session.ring else incident.detected_timestamp_ms)
            start_ms = max(0, incident.detected_timestamp_ms - 30_000)
            frames = [frame.to_public_dict() for frame in session.ring if start_ms <= frame.timestamp_ms <= end_ms + 30_000]
        else:
            db = SessionLocal()()
            try:
                row = db.query(IncidentRecord).filter_by(incident_id=incident_id, Machine_ID=machine_id).first()
                if row is None:
                    raise KeyError(f"Incident {incident_id} not found for machine {machine_id}")
                start_ms = max(0, row.Detected_Timestamp_ms - 30_000)
                end_ms = row.Resolved_Timestamp_ms or row.Detected_Timestamp_ms
                replay_rows = db.query(ReplayFrameRecord).filter(
                    ReplayFrameRecord.incident_id == incident_id,
                    ReplayFrameRecord.Timestamp_ms >= start_ms,
                    ReplayFrameRecord.Timestamp_ms <= end_ms + 30_000,
                ).order_by(ReplayFrameRecord.Timestamp_ms.asc()).all()
                frames = [json.loads(item.Payload_JSON) for item in replay_rows]
                incident = self._record_dict(row)
            finally:
                db.close()
        return {
            "incident_id": incident_id,
            "machine_id": machine_id,
            "start_timestamp_ms": start_ms,
            "end_timestamp_ms": end_ms,
            "frames": frames,
            "timeline": incident.timeline if hasattr(incident, "timeline") else incident.get("timeline", []),
        }

    def status(self) -> dict[str, Any]:
        return {
            "data_mode": "SIMULATION",
            "disclaimer": "Simulated telemetry only. This application runs entirely on synthetic data; it is not connected to real machines or proprietary data.",
            "sessions": {mid: s.info() for mid, s in self.sessions.items()},
        }

    # ------------------------------------------------------------------ loop
    async def _run(self, session: Session) -> None:
        gen = session.generator
        assert gen is not None
        topic = f"machine:{session.machine_id}"
        # emit one frame immediately so clients get data fast
        await self._emit(session, topic, gen)
        while session.running:
            frame = gen.step()
            await self._emit(session, topic, gen)
            # Re-read each tick so a live speed change applies immediately.
            await asyncio.sleep(1.0 / session.speed)

    def set_speed(self, machine_id: str, speed: float) -> Session:
        session = self.sessions.get(machine_id)
        if session is None:
            raise KeyError(f"No session for machine {machine_id}")
        if not session.running:
            raise KeyError(f"No running session for machine {machine_id}")
        session.speed = min(self.settings.max_speed, max(1.0, speed))
        return session

    async def _emit(self, session: Session, topic: str, gen: MachineGenerator) -> None:
        frame = gen.last_frame or gen.step()
        session.ring.append(frame)
        assert session.intelligence is not None
        events = session.intelligence.observe(frame)
        for event in events:
            if event.get("type") == "automatic_override":
                try:
                    session.generator.apply_operator_action(event["action"])
                except ValueError:
                    pass
            incident = event.get("incident")
            if incident:
                self._persist_incident_by_dict(incident)
                self._persist_replay_frames(session, incident["incident_id"])
        situation = derive_situation(
            frame,
            incidents=[item.to_dict() for item in session.intelligence.active_incidents()],
            predicted_risks=session.intelligence.predicted_risks(frame),
            eta=session.intelligence.estimate_eta(frame),
            predictive=session.intelligence.predictive_snapshot(frame),
        )
        payload = {
            "type": "frame",
            "machine_id": session.machine_id,
            "frame": frame.to_public_dict(),
            "situation": situation.model_dump(mode="json"),
            "events": events,
        }
        await self.ws.broadcast(topic, payload)

    def _session_with_intelligence(self, machine_id: str) -> Session:
        session = self.sessions.get(machine_id)
        if session is None or session.intelligence is None:
            raise KeyError(f"No running session for machine {machine_id}")
        return session

    async def _broadcast_incident_event(self, session: Session, event_type: str, incident) -> None:
        await self.ws.broadcast(
            f"machine:{session.machine_id}",
            {
                "type": event_type,
                "machine_id": session.machine_id,
                "incident": incident.to_dict(),
            },
        )

    def _persist_incident(self, incident) -> None:
        self._persist_incident_by_dict(incident.to_dict())

    @staticmethod
    def _persist_replay_frames(session: Session, incident_id: str) -> None:
        if not session.ring:
            return
        db = SessionLocal()()
        try:
            existing = {
                row.Timestamp_ms
                for row in db.query(ReplayFrameRecord.Timestamp_ms).filter(
                    ReplayFrameRecord.incident_id == incident_id
                ).all()
            }
            for frame in session.ring:
                if frame.timestamp_ms in existing:
                    continue
                db.add(
                    ReplayFrameRecord(
                        incident_id=incident_id,
                        Machine_ID=frame.machine_id,
                        Session_ID=frame.session_id,
                        Timestamp_ms=frame.timestamp_ms,
                        Payload_JSON=json.dumps(frame.to_public_dict()),
                    )
                )
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _persist_incident_by_dict(data: dict[str, Any]) -> None:
        db = SessionLocal()()
        try:
            row = db.query(IncidentRecord).filter_by(incident_id=data["incident_id"]).first()
            if row is None:
                row = IncidentRecord(incident_id=data["incident_id"])
                db.add(row)
            row.Machine_ID = data["machine_id"]
            row.Session_ID = data.get("session_id")
            row.Operator_ID = data.get("operator_id")
            row.Task_ID = data.get("task_id")
            row.Task_Type = data.get("task_type")
            row.Incident_Type = data["incident_type"]
            row.Severity = data["severity"]
            row.Confidence = data["confidence"]
            row.Status = data["status"]
            row.Help_Status = data["help_status"]
            row.Response_Status = data["response_status"]
            row.Detected_At = datetime.fromisoformat(data["detected_at"])
            row.Resolved_At = datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None
            row.Detected_Timestamp_ms = data.get("detected_timestamp_ms", 0)
            row.Resolved_Timestamp_ms = data.get("resolved_timestamp_ms")
            row.Evidence_JSON = json.dumps(data.get("evidence", []))
            row.Causes_JSON = json.dumps(data.get("possible_causes", []))
            row.Timeline_JSON = json.dumps(data.get("timeline", []))
            row.Recommended_Action = data.get("recommended_action", "")
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _record_dict(row: IncidentRecord) -> dict[str, Any]:
        return {
            "incident_id": row.incident_id,
            "machine_id": row.Machine_ID,
            "session_id": row.Session_ID or "",
            "operator_id": row.Operator_ID or "",
            "task_id": row.Task_ID or "",
            "task_type": row.Task_Type or "",
            "incident_type": row.Incident_Type,
            "severity": row.Severity,
            "confidence": row.Confidence,
            "status": row.Status,
            "help_status": row.Help_Status,
            "response_status": row.Response_Status,
            "detected_at": row.Detected_At.isoformat() if row.Detected_At else None,
            "resolved_at": row.Resolved_At.isoformat() if row.Resolved_At else None,
            "detected_timestamp_ms": row.Detected_Timestamp_ms,
            "resolved_timestamp_ms": row.Resolved_Timestamp_ms,
            "evidence": json.loads(row.Evidence_JSON or "[]"),
            "possible_causes": json.loads(row.Causes_JSON or "[]"),
            "timeline": json.loads(row.Timeline_JSON or "[]"),
            "recommended_action": row.Recommended_Action or "",
        }
