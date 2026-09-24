"""Interactive, decision-based training scenarios built on incident patterns."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrainingSession:
    session_id: str
    module_id: str
    operator_id: str
    started_at: float = field(default_factory=time.monotonic)
    step_index: int = 0
    mistakes: int = 0
    actions: list[dict[str, Any]] = field(default_factory=list)
    complete: bool = False


MODULES: dict[str, dict[str, Any]] = {
    "fuel_leak_response": {
        "title": "Fuel Loss Response",
        "scenario": "POSSIBLE_FUEL_LEAK",
        "description": "Investigate abnormal fuel loss, protect the operator, and complete a safe shutdown.",
        "steps": [
            {"id": "assess", "title": "Assess the alert", "prompt": "Abnormal fuel loss is inconsistent with current load. What is the safest next step?", "options": ["CONTINUE_OPERATION", "REQUEST_HELP", "OPEN_ENGINE_BAY"], "correct": "REQUEST_HELP", "feedback": "Relay the evidence to support before taking any physical action."},
            {"id": "stop", "title": "Stabilize the machine", "prompt": "Support recommends a safe stop. What should you do?", "options": ["STOP_MACHINE", "INCREASE_LOAD", "CONTINUE_OPERATION"], "correct": "STOP_MACHINE", "feedback": "Stop movement before escalating the response."},
            {"id": "shutdown", "title": "Shut down safely", "prompt": "The machine is stationary. What completes the operator response?", "options": ["SHUTDOWN_ENGINE", "RESUME", "REDUCE_LOAD"], "correct": "SHUTDOWN_ENGINE", "feedback": "Shutdown is an operator action; maintenance escalation follows."},
            {"id": "verify", "title": "Verify and escalate", "prompt": "The engine is off. What should happen next?", "options": ["VERIFY_AND_ESCALATE", "RESTART_MACHINE", "DISMISS_ALERT"], "correct": "VERIFY_AND_ESCALATE", "feedback": "Verify RPM and fuel stabilization, then contact designated support."},
        ],
    },
    "thermal_response": {
        "title": "Thermal Escalation Response",
        "scenario": "POSSIBLE_ENGINE_OVERHEAT",
        "description": "Respond to rising temperature while accounting for load and environmental stress.",
        "steps": [
            {"id": "load", "title": "Reduce thermal stress", "prompt": "Temperature is rising under high load. What is the first safe action?", "options": ["REDUCE_LOAD", "INCREASE_LOAD", "IGNORE_WARNING"], "correct": "REDUCE_LOAD", "feedback": "Reducing load can slow the trajectory while support assesses the machine."},
            {"id": "stop", "title": "Move to safe state", "prompt": "The trend continues. What should you do?", "options": ["STOP_MACHINE", "CONTINUE_OPERATION", "RESTART_SENSORS"], "correct": "STOP_MACHINE", "feedback": "Stop safely if the thermal trend does not reverse."},
            {"id": "relay", "title": "Escalate", "prompt": "The machine is stable. What is the correct close-out?", "options": ["VERIFY_AND_ESCALATE", "DISMISS_ALERT", "RESUME"], "correct": "VERIFY_AND_ESCALATE", "feedback": "Record the event and escalate for maintenance assessment."},
        ],
    },
    "safe_reversing": {
        "title": "Safe Reversing and Proximity",
        "scenario": "PROXIMITY_HAZARD",
        "description": "Handle a closing proximity hazard without relying on a single warning light.",
        "steps": [
            {"id": "stop", "title": "Stop movement", "prompt": "An object enters the safety radius while reversing. What is your first action?", "options": ["STOP_MACHINE", "INCREASE_SPEED", "CONTINUE_REVERSING"], "correct": "STOP_MACHINE", "feedback": "Stop movement and maintain a safe state."},
            {"id": "relay", "title": "Confirm the area", "prompt": "The machine is stopped. What should happen before resuming?", "options": ["VERIFY_AND_ESCALATE", "RESUME", "DISMISS_ALERT"], "correct": "VERIFY_AND_ESCALATE", "feedback": "Confirm the area is clear and escalate if the hazard is unresolved."},
        ],
    },
}


class TrainingService:
    def __init__(self) -> None:
        self.sessions: dict[str, TrainingSession] = {}

    def modules(self) -> list[dict[str, Any]]:
        return [
            {
                "module_id": module_id,
                "title": data["title"],
                "scenario": data["scenario"],
                "description": data["description"],
                "step_count": len(data["steps"]),
            }
            for module_id, data in MODULES.items()
        ]

    def start(self, module_id: str, operator_id: str) -> dict[str, Any]:
        if module_id not in MODULES:
            raise KeyError(f"Unknown training module: {module_id}")
        session = TrainingSession(session_id=f"TRN-{uuid.uuid4().hex[:10].upper()}", module_id=module_id, operator_id=operator_id)
        self.sessions[session.session_id] = session
        return self._view(session, feedback="Training session started. Select the safest action.")

    def act(self, session_id: str, action: str) -> dict[str, Any]:
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError(f"Training session {session_id} not found")
        if session.complete:
            return self._view(session, feedback="Training session is already complete.")
        step = MODULES[session.module_id]["steps"][session.step_index]
        correct = action == step["correct"]
        session.actions.append({"step_id": step["id"], "action": action, "correct": correct})
        if correct:
            session.step_index += 1
            if session.step_index >= len(MODULES[session.module_id]["steps"]):
                session.complete = True
        else:
            session.mistakes += 1
        feedback = step["feedback"] if correct else "That action does not follow the safe response sequence. Review the evidence and choose again."
        return self._view(session, feedback=feedback, last_action=action, correct=correct)

    def recommendations(self, incidents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        recommendations: list[dict[str, Any]] = []
        mapping = {
            "POSSIBLE_FUEL_LEAK": "fuel_leak_response",
            "POSSIBLE_ENGINE_OVERHEAT": "thermal_response",
            "MULTI_FACTOR_THERMAL_RISK": "thermal_response",
            "PROXIMITY_HAZARD": "safe_reversing",
        }
        seen: set[str] = set()
        for incident in incidents:
            module_id = mapping.get(incident.get("incident_type"))
            if module_id and module_id not in seen:
                seen.add(module_id)
                module = MODULES[module_id]
                recommendations.append({"module_id": module_id, "title": module["title"], "reason": f"Recommended from {incident['incident_type'].replace('_', ' ').title()} history."})
        return recommendations or [{"module_id": "fuel_leak_response", "title": MODULES["fuel_leak_response"]["title"], "reason": "Core emergency response module for new operators."}]

    def _view(self, session: TrainingSession, **extra: Any) -> dict[str, Any]:
        module = MODULES[session.module_id]
        step = None if session.complete else module["steps"][session.step_index]
        safe_step = None
        if step:
            safe_step = {key: value for key, value in step.items() if key not in ("correct", "feedback")}
        score = max(0, 100 - session.mistakes * 15) if session.complete else None
        return {
            "session_id": session.session_id,
            "module_id": session.module_id,
            "operator_id": session.operator_id,
            "title": module["title"],
            "scenario": module["scenario"],
            "step_index": session.step_index,
            "step_count": len(module["steps"]),
            "step": safe_step,
            "mistakes": session.mistakes,
            "score": score,
            "complete": session.complete,
            "actions": session.actions,
            **extra,
        }
