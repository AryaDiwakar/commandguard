"""WebSocket connection manager with per-machine topics."""
from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._topics: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, topic: str, ws: WebSocket) -> None:
        await ws.accept()
        self._topics[topic].add(ws)

    def disconnect(self, topic: str, ws: WebSocket) -> None:
        self._topics[topic].discard(ws)

    def clients(self, topic: str) -> set[WebSocket]:
        return set(self._topics.get(topic, set()))

    async def broadcast(self, topic: str, payload: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self.clients(topic):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(topic, ws)