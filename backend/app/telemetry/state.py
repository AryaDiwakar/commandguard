"""In-memory rolling telemetry state used by live intelligence."""
from __future__ import annotations

from collections import defaultdict, deque

from app.schemas.telemetry import TelemetryFrame


class TelemetryStateStore:
    """Keep bounded per-machine windows without coupling to a database."""

    def __init__(self, window_size: int = 3600):
        self.window_size = window_size
        self._windows: dict[str, deque[TelemetryFrame]] = defaultdict(
            lambda: deque(maxlen=self.window_size)
        )

    def append(self, frame: TelemetryFrame) -> None:
        self._windows[frame.machine_id].append(frame)

    def latest(self, machine_id: str) -> TelemetryFrame | None:
        window = self._windows.get(machine_id)
        return window[-1] if window else None

    def window(self, machine_id: str, size: int | None = None) -> list[TelemetryFrame]:
        values = list(self._windows.get(machine_id, ()))
        return values[-size:] if size is not None else values

    def clear(self, machine_id: str) -> None:
        self._windows.pop(machine_id, None)
