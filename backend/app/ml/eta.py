"""Dependency-light ETA regression trained from the synthetic task history."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.dataset.tasks import WEATHER_FACTOR, generate_task_history
from app.schemas.telemetry import TerrainCondition, TelemetryFrame, WeatherEvent
from app.simulation.catalog import MACHINES, TASK_CATALOG


@dataclass
class ETAStatus:
    model_name: str
    training_rows: int
    holdout_mae_minutes: float
    holdout_rmse_minutes: float


class ETAModel:
    def __init__(self) -> None:
        history = generate_task_history(seed=2026, n_days=90)
        split = max(1, int(len(history) * 0.8))
        train = history.iloc[:split]
        holdout = history.iloc[split:]
        x_train = self._matrix(train)
        y_train = train["Actual_Time_min"].to_numpy(dtype=float)
        self._weights = np.linalg.lstsq(x_train, y_train, rcond=None)[0]
        predictions = self._matrix(holdout) @ self._weights
        errors = predictions - holdout["Actual_Time_min"].to_numpy(dtype=float)
        self.status = ETAStatus(
            model_name="synthetic_eta_ridge_numpy",
            training_rows=int(len(train)),
            holdout_mae_minutes=round(float(np.abs(errors).mean()), 2),
            holdout_rmse_minutes=round(float(np.sqrt((errors**2).mean())), 2),
        )

    @staticmethod
    def _matrix(frame) -> np.ndarray:
        weather = frame["Weather"].map(lambda value: WEATHER_FACTOR[WeatherEvent(value)]).to_numpy(dtype=float)
        return np.column_stack(
            [
                np.ones(len(frame)),
                frame["Estimated_Time_min"].to_numpy(dtype=float),
                frame["Reference_Time_min"].to_numpy(dtype=float),
                frame["Machine_Age_yrs"].to_numpy(dtype=float),
                weather,
                frame["Rainfall_mmh"].to_numpy(dtype=float),
                1.0 / np.maximum(frame["Visibility_m"].to_numpy(dtype=float), 100.0),
            ]
        )

    def predict_remaining(self, frame: TelemetryFrame) -> float:
        machine_age = MACHINES[frame.machine_id].age_years
        catalog_planned = float(TASK_CATALOG.get(frame.current_task_type, {}).get("planned_minutes", 240))
        # The live plan is demo-compressed (first task ~5 min). The model was
        # trained on realistic tasks, so its absolute prediction is rescaled
        # onto the current task's actual planned minutes.
        planned = float(frame.task_planned_minutes or catalog_planned)
        scale = 1.0 if catalog_planned <= 0 else planned / catalog_planned
        weather = WEATHER_FACTOR.get(frame.weather_event, 1.0)
        terrain = {
            TerrainCondition.DRY: 1.0,
            TerrainCondition.PACKED: 1.0,
            TerrainCondition.WET: 1.12,
            TerrainCondition.MUDDY: 1.30,
            TerrainCondition.ICY: 1.42,
        }[frame.terrain_condition]
        estimated = catalog_planned * terrain
        values = np.array([[1.0, estimated, catalog_planned, machine_age, weather, frame.rainfall_mmh, 1.0 / max(frame.visibility_m, 100.0)]])
        raw_total = max(15.0, float(values @ self._weights))
        total = max(planned * 0.5, raw_total * scale)
        return max(0.0, total * (1.0 - frame.task_progress_pct / 100.0))

    def predict_task(self, row: dict) -> float:
        """Predict total minutes for a scheduled task from its schedule row."""
        weather = WEATHER_FACTOR.get(WeatherEvent(row["Weather"]), 1.0)
        values = np.array(
            [
                [
                    1.0,
                    float(row["Estimated_Time_min"]),
                    float(row["Reference_Time_min"]),
                    float(row["Machine_Age_yrs"]),
                    weather,
                    float(row["Rainfall_mmh"]),
                    1.0 / max(float(row["Visibility_m"]), 100.0),
                ]
            ]
        )
        raw = float(values @ self._weights)
        # Schedule rows are demo-compressed (a few minutes); rescale the
        # realistic-scale model output onto the row's own planned duration.
        planned = float(TASK_CATALOG.get(row["Task_Type"], {}).get("planned_minutes", 240))
        ratio = max(0.05, float(row["Estimated_Time_min"]) / planned)
        estimate = float(row["Estimated_Time_min"])
        pred = max(0.85 * estimate, min(1.6 * estimate, max(15.0, raw) * ratio))
        return round(pred, 1)


_MODEL: ETAModel | None = None


def eta_model() -> ETAModel:
    global _MODEL
    if _MODEL is None:
        _MODEL = ETAModel()
    return _MODEL
