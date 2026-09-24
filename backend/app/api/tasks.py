"""Task schedule and ETA-facing endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.simulation.catalog import MACHINES
from app.dataset.tasks import generate_shift_schedule
from app.ml.eta import eta_model
from app.config import settings

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/today")
async def today_tasks(machine_id: str = Query(default=settings.default_machine_id)):
    if machine_id not in MACHINES:
        raise HTTPException(status_code=404, detail=f"Unknown machine {machine_id}")
    frame = generate_shift_schedule(machines=(machine_id,))
    model = eta_model()
    records = frame.to_dict(orient="records")
    for record in records:
        record["model_predicted_min"] = model.predict_task(record)
    return {
        "machine_id": machine_id,
        "tasks": records,
        "data_mode": "SYNTHETIC_SCHEDULE",
        "eta_model": {
            "model_name": model.status.model_name,
            "training_rows": model.status.training_rows,
            "holdout_mae_minutes": model.status.holdout_mae_minutes,
            "holdout_rmse_minutes": model.status.holdout_rmse_minutes,
        },
    }
