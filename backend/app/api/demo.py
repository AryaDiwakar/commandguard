"""Deterministic hackathon demonstration controls."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.simulation.scenarios import ScenarioType, make_spec

router = APIRouter(prefix="/api/demo", tags=["demo"])

# Fleet boot plan: one live scenario arc per machine so the Commander view
# shows a coherent, explainable set of working conditions.
# Fleet boot plan: one coherent scenario arc per machine. Scenario names are
# resolved into full ScenarioSpecs (same path the inject endpoint uses) so the
# deterministic handler creates a real, live session — never a fake string.
BOOT_PLAN = [
    {"machine_id": "MX-101", "operator_id": "OP-01", "seed": 2117, "speed": 5.0, "scenario_type": "FUEL_LEAK", "severity": 0.85},
    {"machine_id": "MX-102", "operator_id": "OP-02", "seed": 4088, "speed": 4.0, "scenario_type": "SEATBELT_VIOLATION", "severity": 0.9},
    {"machine_id": "MX-103", "operator_id": "OP-03", "seed": 9023, "speed": 5.0, "scenario_type": "UNSAFE_OPERATION", "severity": 0.8},
]



@router.post("/reset")
async def reset_demo(request: Request):
    await request.app.state.sim.reset_demo()
    return {"reset": True, "message": "All synthetic sessions stopped. Demo state is ready for a deterministic restart."}


@router.post("/boot")
async def boot_demo(request: Request):
    """Start a coherent session for every machine on the fleet for a live demo."""
    sim = request.app.state.sim
    for plan in BOOT_PLAN:
        try:
            await sim.start(
                machine_id=plan["machine_id"],
                operator_id=plan["operator_id"],
                seed=plan["seed"],
                speed=plan["speed"],
                scenario=make_spec(ScenarioType(plan["scenario_type"]), severity=plan["severity"]),
            )
        except RuntimeError:
            continue  # already running — keep going so the fleet is fully live
    return {
        "booted": True,
        "machines": [
            bool(sim.sessions.get(plan["machine_id"]) and sim.sessions[plan["machine_id"]].running)
            for plan in BOOT_PLAN
        ],
    }
