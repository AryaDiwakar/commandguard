"""Data-source contracts shared by simulation, replay, and future live feeds."""
from __future__ import annotations

from collections import deque
from typing import Iterable, Protocol

import httpx

from app.schemas.telemetry import TelemetryFrame
from app.simulation.generator import MachineGenerator


class TelemetrySource(Protocol):
    """Minimal source interface consumed by the real-time pipeline."""

    mode: str

    def next_frame(self) -> TelemetryFrame:
        ...

    def apply_operator_action(self, action: str) -> None:
        ...


class SimulationDataSource:
    """Adapter around the existing causal simulator.

    Replay and live adapters can implement the same protocol without changing
    the intelligence or operator-facing layers.
    """

    mode = "SIMULATION"

    def __init__(self, generator: MachineGenerator):
        self.generator = generator

    def next_frame(self) -> TelemetryFrame:
        return self.generator.step()

    def apply_operator_action(self, action: str) -> None:
        self.generator.apply_operator_action(action)


class ReplayDataSource:
    """Deterministic source for historical frames and incident replay."""

    mode = "REPLAY"

    def __init__(self, frames: Iterable[TelemetryFrame], repeat: bool = False):
        self._frames = list(frames)
        self._cursor = 0
        self.repeat = repeat

    def next_frame(self) -> TelemetryFrame:
        if not self._frames:
            raise StopIteration("Replay has no telemetry frames")
        if self._cursor >= len(self._frames):
            if not self.repeat:
                raise StopIteration("Replay complete")
            self._cursor = 0
        frame = self._frames[self._cursor]
        self._cursor += 1
        return frame

    def apply_operator_action(self, action: str) -> None:
        # Historical data is read-only; the command is intentionally ignored.
        return None

    def reset(self) -> None:
        self._cursor = 0


class LiveDataSourceStub:
    """Queue-backed contract test double for a future live telemetry gateway."""

    mode = "LIVE_STUB"

    def __init__(self):
        self._queue: deque[TelemetryFrame] = deque()
        self._last: TelemetryFrame | None = None

    def push(self, frame: TelemetryFrame) -> None:
        self._queue.append(frame)

    def next_frame(self) -> TelemetryFrame:
        if self._queue:
            self._last = self._queue.popleft()
        if self._last is None:
            raise StopIteration("Live stub has no telemetry frame")
        return self._last

    def apply_operator_action(self, action: str) -> None:
        # Real command delivery requires an approved machine-control gateway.
        return None


class HttpLiveDataSource:
    """Opt-in read-only adapter for an approved telemetry gateway.

    The gateway contract is intentionally generic. It expects
    ``GET /telemetry/latest`` to return one normalized frame. No CAT endpoint,
    hardware credential, or proprietary field mapping is embedded here.
    """

    mode = "LIVE"

    def __init__(self, base_url: str, token: str | None = None, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.client = client or httpx.Client(timeout=5.0)

    def next_frame(self) -> TelemetryFrame:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        response = self.client.get(f"{self.base_url}/telemetry/latest", headers=headers)
        response.raise_for_status()
        payload = response.json()
        return self._normalize(payload)

    def apply_operator_action(self, action: str) -> None:
        raise RuntimeError("LIVE telemetry adapter is read-only; machine commands require an approved control gateway")

    @staticmethod
    def _normalize(payload: dict) -> TelemetryFrame:
        aliases = {
            "Timestamp": "timestamp",
            "Machine_ID": "machine_id",
            "Operator_ID": "operator_id",
            "Engine_Hours": "engine_hours",
            "Fuel_Used_L": "fuel_used_l",
            "Load_Cycles": "load_cycles",
            "Idling_Time_min": "idling_time_min",
            "Seatbelt_Status": "seatbelt_status",
            "Safety_Alert_Triggered": "safety_alert_triggered",
        }
        normalized = {aliases.get(key, key): value for key, value in payload.items()}
        return TelemetryFrame(**normalized)
