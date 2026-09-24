"""Environmental engine (Phase 1: normal conditions).

Produces deterministic time-varying environment state from a daily diurnal
curve + site baseline. Weather *events* (rain/fog/heat) arrive in Phase 2 with
the scenario injectors — the interface already has a `weather_event` state.
"""
from __future__ import annotations

import math
import random

from app.schemas.telemetry import TerrainCondition, TerrainType, WeatherEvent
from app.simulation.catalog import SiteConfig


class EnvironmentEngine:
    def __init__(self, site: SiteConfig, rng: random.Random):
        self.site = site
        self.rng = rng
        self.t_s: float = 0.0
        # stable demo weather for Phase 1 normal sessions
        self.weather_event = WeatherEvent.NONE
        self.rainfall_mmh = 0.0
        self.visibility_m = site.visibility_m
        self.terrain_type = TerrainType(site.terrain_type)
        self.terrain_condition = TerrainCondition(site.terrain_condition)

    def step(self, dt: float, sim_time_s: float) -> dict:
        self.t_s = sim_time_s
        day_frac = (sim_time_s % 86400.0) / 86400.0
        # diurnal sinusoid peaking ~14:00 local
        phase = 2.0 * math.pi * (day_frac - 0.42)
        ambient = self.site.ambient_base_c + self.site.ambient_amp_c * math.cos(phase)
        ambient += self.rng.gauss(0.0, 0.15)

        humidity = self.site.humidity_base + self.rng.gauss(0.0, 1.2)
        humidity = float(max(15.0, min(100.0, humidity)))

        return {
            "ambient_temperature_c": round(ambient, 2),
            "humidity_pct": round(humidity, 1),
            "rainfall_mmh": self.rainfall_mmh,
            "visibility_m": self.visibility_m,
            "terrain_type": self.terrain_type,
            "terrain_condition": self.terrain_condition,
            "slope_deg": self.site.slope_deg,
            "work_zone": self.site.work_zone,
            "nearby_machine_count": self.site.nearby_machines,
            "weather_event": self.weather_event,
        }