"""Grounded machine-aware assistant responses."""
from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.knowledge.base import search
from app.knowledge.llm import generate as llm_generate

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

LLM_SYSTEM = (
    "You are CAT CommandGuard, a machine operator co-pilot. "
    "Answer ONLY from the Retrieve context and Live truth provided. "
    "Never invent sensor values, maintenance claims, or numbers. "
    "Be concise (3-5 sentences), plain language, first person for the operator ('you'). "
    "If the context has no answer, say you cannot confirm it from the live context."
)


class AssistantRequest(BaseModel):
    machine_id: str = "MX-101"
    message: str = Field(min_length=1, max_length=500)


@router.post("/message")
async def assistant_message(body: AssistantRequest, request: Request):
    sim = request.app.state.sim
    frame = sim.latest(body.machine_id)
    situation = sim.latest_situation(body.machine_id)
    if frame is None or situation is None:
        return {
            "message": "I do not have a current telemetry frame for this machine. Start a synthetic session before asking for machine guidance.",
            "grounded": True,
            "sources": ["session state"],
            "suggested_actions": ["Start a simulation session"],
        }

    incidents = [item for item in sim.incidents(body.machine_id) if item.get("status") == "ACTIVE"]
    query = body.message.lower()
    evidence = [item for incident in incidents for item in incident.get("evidence", [])]
    sources = ["current telemetry", "machine situation", "synthetic safety procedures"]
    knowledge = search(body.message)
    if knowledge:
        sources.append("approved operator guidance")

    # Deterministic fallback answer + suggested actions (keep working offline).
    if any(term in query for term in ("why", "warning", "alert", "happening")) and incidents:
        incident = incidents[-1]
        details = " ".join(item["observation"] for item in evidence[:3])
        fallback_message = f"The current {incident['incident_type'].replace('_', ' ').lower()} assessment is {incident['confidence']:.2f} confidence. {details} Recommended action: {incident['recommended_action']}"
        actions = [incident["recommended_action"], "Request live assistance"]
    elif any(term in query for term in ("safe", "continue", "proceed")):
        if situation.safety_state != "SAFE" or situation.current_risk in ("HIGH", "CRITICAL"):
            fallback_message = f"I do not recommend continuing in the current state. Safety is {situation.safety_state.lower()} and current risk is {situation.current_risk.lower()}. {incidents[-1]['recommended_action'] if incidents else 'Move to a safe state and request support.'}"
            actions = ["Stop machine safely", "Request live assistance"]
        else:
            fallback_message = "The current observed state is within the synthetic safe operating bands. Continue only while monitoring the live trend and task conditions."
            actions = ["Continue monitoring"]
    elif any(term in query for term in ("eta", "time", "finish", "task")):
        fallback_message = f"The current task is {situation.task}. Estimated remaining time is {situation.eta_minutes:.1f} minutes versus a {situation.eta_baseline_minutes:.1f} minute baseline."
        if situation.eta_reasons:
            fallback_message += f" The estimate is being extended by {', '.join(situation.eta_reasons)}."
        actions = ["Open Tasks"]
    elif any(term in query for term in ("forecast", "future", "what if", "happen")):
        if situation.predicted_risks:
            risk = situation.predicted_risks[0]
            fallback_message = risk["message"]
            actions = ["Reduce machine load", "Review response guide"]
        else:
            fallback_message = "No immediate threshold crossing is forecast from the current telemetry trend. I will continue monitoring the next operating window."
            actions = ["Continue monitoring"]
    elif any(term in query for term in ("help", "support", "maintenance")):
        fallback_message = "Live help can receive the current machine context, evidence, and incident timeline. Use the Live Help Relay on the Live Machine page to request assistance."
        actions = ["Open Live Help Relay"]
    else:
        fallback_message = f"Machine {frame.machine_id} is {situation.operating_state.lower()} on {situation.task.lower()}. Health is {situation.machine_health.lower()}, safety is {situation.safety_state.lower()}, and current risk is {situation.current_risk.lower()}."
        actions = ["Ask why this state exists", "Ask whether it is safe to continue"]

    # RAG: retrieve the approved guidance into the prompt, then ask the local
    # free LLM to paraphrase an answer strictly from that context.
    documents = "\n".join(
        f"- {item['title']} ({item['source']}): {item['excerpt']}" for item in knowledge
    ) or "- (no matching approved guidance)"
    live_truth = json.dumps(
        {
            "machine_id": frame.machine_id,
            "operating_state": situation.operating_state,
            "task": situation.task,
            "task_progress_pct": situation.task_progress_pct,
            "shift_remaining_minutes": situation.shift_remaining_minutes,
            "health": situation.machine_health,
            "safety_state": situation.safety_state,
            "current_risk": situation.current_risk,
            "eta_minutes": situation.eta_minutes,
            "eta_reasons": situation.eta_reasons,
            "active_incidents": [
                {"type": item["incident_type"], "severity": item.get("severity"), "recommended_action": item.get("recommended_action")}
                for item in incidents
            ],
        },
        default=str,
    )
    user_prompt = (
        f"Retrieve context (approved operator guidance):\n{documents}\n\n"
        f"Live truth (current telemetry-derived state):\n{live_truth}\n\n"
        f"Operator question: {body.message}\n\n"
        f"Answer the question using the context above."
    )
    answer = await run_in_threadpool(llm_generate, LLM_SYSTEM, user_prompt)
    model = None
    message = fallback_message
    if answer is not None:
        model, message = answer
        sources.append(model)

    return {
        "message": message,
        "grounded": True,
        "sources": sources,
        "suggested_actions": actions,
        "knowledge": knowledge,
        "model": model,
        "context": {
            "machine_id": frame.machine_id,
            "timestamp_ms": frame.timestamp_ms,
            "operating_state": situation.operating_state,
            "machine_health": situation.machine_health,
            "safety_state": situation.safety_state,
            "current_risk": situation.current_risk,
            "active_incidents": [item["incident_type"] for item in incidents],
        },
    }
