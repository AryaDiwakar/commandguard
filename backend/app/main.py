"""FastAPI application & WebSocket telemetry stream."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.middleware.cors import CORSMiddleware

from app.api import analytics, assistant, auth, dashboard, demo, fleet, incidents, knowledge, onboard, operator, practice, safety, simulation, state, system, tasks, thresholds, training, whatif
from app.config import settings
from app.auth import AuthService
from app.db import init_db
from app.simulation.service import SimService
from app.training.service import TrainingService
from app.predictive.config import ThresholdStore
from app.ws.manager import ConnectionManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.ws_manager = ConnectionManager()
    app.state.sim = SimService(settings, app.state.ws_manager)
    app.state.training = TrainingService()
    app.state.auth = AuthService()
    app.state.thresholds = ThresholdStore()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="CommandGuard — Smart Operator Assistant API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allow_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(system.router)
    app.include_router(simulation.router)
    app.include_router(state.router)
    app.include_router(onboard.router)
    app.include_router(incidents.router)
    app.include_router(tasks.router)
    app.include_router(training.router)
    app.include_router(safety.router)
    app.include_router(analytics.router)
    app.include_router(assistant.router)
    app.include_router(knowledge.router)
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(whatif.router)
    app.include_router(demo.router)
    app.include_router(fleet.router)
    app.include_router(thresholds.router)
    app.include_router(operator.router)
    app.include_router(practice.router)

    @app.websocket("/ws/telemetry")
    async def ws_telemetry(ws: WebSocket, machine_id: str = settings.default_machine_id):
        manager: ConnectionManager = app.state.ws_manager
        topic = f"machine:{machine_id}"
        await manager.connect(topic, ws)
        try:
            while True:
                await ws.receive_text()  # keepalive; server pushes frames
        except WebSocketDisconnect:
            manager.disconnect(topic, ws)

    return app


app = create_app()
