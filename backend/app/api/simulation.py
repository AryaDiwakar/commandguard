"""Simulation control + live state endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request

from app.schemas.telemetry import ScenarioType, WeatherEvent
from app.simulation.scenarios import ScenarioSpec, default_plan, make_spec

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


class ScenarioScript(BaseModel):
    type: ScenarioType
    severity: float = Field(default=0.7, ge=0.0, le=1.0)
    onset_offset_s: float | None = Field(default=None, ge=30.0, description="Bigger than 30 so a normal lead-in exists")
    ramp_s: float | None = Field(default=None, ge=1.0)
    duration_s: float | None = Field(default=None, ge=1.0)
    abate_s: float | None = Field(default=None, ge=1.0)
    weather: WeatherEvent = WeatherEvent.NONE
    params: dict = Field(default_factory=dict)

    def to_spec(self) -> ScenarioSpec:
        overrides = {
            key: value
            for key, value in {
                "onset_offset_s": self.onset_offset_s,
                "ramp_s": self.ramp_s,
                "duration_s": self.duration_s,
                "abate_s": self.abate_s,
            }.items()
            if value is not None
        }
        return make_spec(
            self.type,
            severity=self.severity,
            weather=self.weather,
            params=self.params,
            **overrides,
        )


class StartRequest(BaseModel):
    machine_id: str | None = None
    operator_id: str | None = None
    seed: int | None = None
    speed: float | None = Field(default=None, ge=1.0, le=60.0)
    scenario: ScenarioScript | None = None


class StopRequest(BaseModel):
    machine_id: str


class SpeedRequest(BaseModel):
    speed: float = Field(default=1.0, ge=1.0, le=60.0)


class ScenarioInjectRequest(BaseModel):
    machine_id: str
    scenario: ScenarioScript


@router.post("/start")
async def start_session(req: StartRequest, request: Request):
    sim = request.app.state.sim
    try:
        session = await sim.start(
            machine_id=req.machine_id,
            operator_id=req.operator_id,
            seed=req.seed,
            speed=req.speed,
            scenario=req.scenario.to_spec() if req.scenario else None,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return session.info()


@router.post("/stop")
async def stop_session(req: StopRequest, request: Request):
    sim = request.app.state.sim
    await sim.stop(req.machine_id)
    return {"stopped": req.machine_id}


@router.patch("/{machine_id}/speed")
async def change_speed(machine_id: str, req: SpeedRequest, request: Request):
    sim = request.app.state.sim
    try:
        session = sim.set_speed(machine_id, req.speed)
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return session.info()


@router.post("/scenario")
async def inject_scenario(req: ScenarioInjectRequest, request: Request):
    sim = request.app.state.sim
    try:
        session = sim.inject(req.machine_id, req.scenario.to_spec())
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    spec = req.scenario.to_spec()
    return {
        "machine_id": req.machine_id,
        "injected": True,
        "scenario_type": spec.scenario_type.value,
        "severity": spec.severity,
        "onset_s": spec.onset_offset_s,
        "resolve_s": spec.end_s,
    }


@router.get("/status")
async def sim_status(request: Request):
    return request.app.state.sim.status()


@router.get("/scenarios")
async def scenario_catalog():
    return {
        "scenarios": [
            {
                "type": scenario.value,
                "label": scenario.value.replace("_", " ").title(),
                "default_plan": default_plan(scenario),
            }
            for scenario in ScenarioType
            if scenario is not ScenarioType.NORMAL_OPERATION
        ]
    }
