"""Application-level configuration for the Smart Operator Assistant backend.

All tuning values below are DEMO / SYNTHETIC thresholds, not real Caterpillar
specifications. They are used only to drive a software simulation.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _origins() -> tuple[str, ...]:
    raw = os.environ.get("CAT_CORS_ORIGINS", "")
    if raw.strip():
        return tuple(o.strip() for o in raw.split(",") if o.strip())
    return ("http://localhost:5173", "http://127.0.0.1:5173")


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    allow_origins: tuple[str, ...] = field(default_factory=_origins)

    default_machine_id: str = "MX-101"
    default_operator_id: str = "OP-01"
    default_speed: float = 1.0       # sim frames emitted per real second
    max_speed: float = 60.0

    sim_dt_s: float = 1.0            # one frame == one simulated second
    ring_size: int = 3600            # per-machine telemetry ring buffer size

    db_url: str = field(
        default_factory=lambda: os.environ.get(
            "CAT_DB_URL", "sqlite:///./data/caterpillar.db"
        )
    )


settings = Settings()