"""Comparable synthetic operating-practice projections."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/practice", tags=["practice"])


class PracticeRequest(BaseModel):
    machine_id: str = "MX-101"


PROFILES = {
    "ECO": {"time": 1.12, "fuel": 0.82, "wear": 0.78, "risk": "LOW", "description": "Lowest fuel and wear, with a longer task time."},
    "BALANCED": {"time": 1.0, "fuel": 1.0, "wear": 1.0, "risk": "LOW", "description": "Best balance of output, fuel, time, and machine health."},
    "HIGH_PRODUCTIVITY": {"time": 0.91, "fuel": 1.18, "wear": 1.12, "risk": "MEDIUM", "description": "Faster completion with higher fuel and component stress."},
    "AGGRESSIVE": {"time": 0.82, "fuel": 1.48, "wear": 1.38, "risk": "HIGH", "description": "Fastest projected completion but not recommended for routine work."},
}


@router.post("/compare")
async def compare(body: PracticeRequest, request: Request):
    situation = request.app.state.sim.latest_situation(body.machine_id)
    frame = request.app.state.sim.latest(body.machine_id)
    if situation is None or frame is None:
        raise HTTPException(status_code=404, detail="No live machine session")
    baseline_eta = max(1.0, situation.eta_minutes)
    baseline_fuel = max(1.0, frame.fuel_consumption_rate_lph * baseline_eta / 60.0)
    base_output = max(1.0, frame.task_target_quantity - frame.task_output_quantity)
    comparisons = []
    for name, profile in PROFILES.items():
        time_minutes = baseline_eta * profile["time"]
        fuel_liters = baseline_fuel * profile["fuel"]
        output_per_min = base_output / time_minutes
        fuel_efficiency = base_output / fuel_liters
        safety_penalty = 0 if profile["risk"] == "LOW" else 12 if profile["risk"] == "MEDIUM" else 28
        score = max(0.0, min(100.0, 100.0 - (time_minutes / baseline_eta - 1.0) * 20.0 - (profile["fuel"] - 1.0) * 25.0 - (profile["wear"] - 1.0) * 20.0 - safety_penalty))
        comparisons.append({
            "profile": name,
            "description": profile["description"],
            "task_time_minutes": round(time_minutes, 1),
            "fuel_liters": round(fuel_liters, 1),
            "output_quantity": round(base_output, 1),
            "output_unit": frame.task_output_unit,
            "output_per_minute": round(output_per_min, 3),
            "fuel_efficiency_output_per_l": round(fuel_efficiency, 3),
            "wear_multiplier": profile["wear"],
            "risk": profile["risk"],
            "score": round(score, 1),
        })
    recommended = min((item for item in comparisons if item["risk"] != "HIGH"), key=lambda item: (-item["score"], item["fuel_liters"]))
    return {
        "machine_id": body.machine_id,
        "task": situation.task,
        "grounded": True,
        "recommendation": recommended["profile"],
        "reason": f"{recommended['profile'].title()} offers the best safe tradeoff for the current task and machine state.",
        "comparisons": comparisons,
    }
