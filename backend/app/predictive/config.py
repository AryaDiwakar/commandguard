"""Runtime-configurable synthetic thresholds for supervisor profiles."""
from __future__ import annotations

from copy import deepcopy


DEFAULT_THRESHOLDS = {
    "engine_temperature_warn_c": 98.0,
    "hydraulic_pressure_sag_bar": 90.0,
    "proximity_unsafe_m": 8.0,
    "battery_low_v": 22.0,
    "rolling_z_score_warning": 2.5,
    "fatigue_break_minutes": 90.0,
}


class ThresholdStore:
    def __init__(self):
        self._profiles: dict[str, dict[str, float]] = {"DEFAULT": deepcopy(DEFAULT_THRESHOLDS)}

    def get(self, profile: str = "DEFAULT") -> dict[str, float]:
        return deepcopy(self._profiles.get(profile, self._profiles["DEFAULT"]))

    def update(self, profile: str, values: dict[str, float]) -> dict[str, float]:
        current = self.get(profile)
        for key, value in values.items():
            if key in DEFAULT_THRESHOLDS:
                current[key] = float(value)
        self._profiles[profile] = current
        return deepcopy(current)

    def profiles(self) -> dict[str, dict[str, float]]:
        return {key: deepcopy(value) for key, value in self._profiles.items()}
