"""MachineGenerator: assembles deterministic TelemetryFrames each sim tick.

Phase 2: scenario injectors (``simulation/scenarios``) plug in here between the
mission/environment step and the physics step. The generator merges their
perturbations into the command/environment/physics inputs, applies observed
sensor bias, and stamps the ground-truth evaluation fields.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

from app.schemas.telemetry import (
    MachineState,
    Phase,
    ScenarioType,
    TelemetryFrame,
)
from app.simulation.catalog import MACHINES, OPERATORS, SITES, MachineConfig, OperatorConfig, SiteConfig
from app.simulation.environment import EnvironmentEngine
from app.simulation.mission import MissionScheduler
from app.simulation.physics import MachineDynamics
from app.simulation.scenarios import ScenarioInjector, ScenarioSpec, build_injector, make_spec
from app.simulation.thresholds import severity_bucket

_ANOMALY_PHASES = (Phase.ONSET, Phase.ANOMALY, Phase.RESPONSE)

# Demo-compressed shift plan: five tasks summing to a 10-minute shift so the
# Home page reads 10.0 min and ticks down as each job completes. All values
# remain SYNTHETIC.
DEMO_TASK_PLAN = (
    {"task_id": "EXC-0712", "task_type": "EXCAVATION", "planned_min": 3.0, "target": 1000.0, "unit": "m3"},
    {"task_id": "LOD-0711", "task_type": "LOADING", "planned_min": 2.0, "target": 850.0, "unit": "m3"},
    {"task_id": "TRN-0709", "task_type": "TRENCHING", "planned_min": 2.0, "target": 700.0, "unit": "m3"},
    {"task_id": "HUL-0710", "task_type": "HAULING", "planned_min": 2.0, "target": 950.0, "unit": "m3"},
    {"task_id": "GRD-0715", "task_type": "GRADING", "planned_min": 1.0, "target": 600.0, "unit": "m3"},
)


class MachineGenerator:
    def __init__(
        self,
        machine_id: str = "MX-101",
        operator_id: str = "OP-01",
        seed: int = 7,
        session_id: str = "S1",
        start_time: datetime | None = None,
        speed: float = 1.0,
        site_key: str | None = None,
        scenario: ScenarioSpec | None = None,
    ):
        self.machine_id = machine_id
        self.operator_id = operator_id
        self.session_id = session_id
        self.speed = speed
        self.dt = 1.0  # sim seconds per tick

        self.machine_cfg: MachineConfig = MACHINES[machine_id]
        self.op_cfg: OperatorConfig = OPERATORS[operator_id]
        site_key = site_key or self.machine_cfg.site_key
        self.site: SiteConfig = SITES[site_key]

        self.rng = random.Random(seed)
        self.env = EnvironmentEngine(self.site, self.rng)
        self.dynamics = MachineDynamics(self.machine_cfg, self.op_cfg, self.rng)
        self.scheduler = MissionScheduler("EXCAVATION", self.op_cfg.efficiency, self.rng)

        if start_time is None:
            start_time = datetime(2026, 9, 23, 7, 0, 0, tzinfo=timezone.utc)
        self.start_time = start_time
        self.sim_time_s = 0.0
        self.last_frame: TelemetryFrame | None = None
        self.task_start_s = 0.0
        self.task_index = 0
        self.task_plan = list(DEMO_TASK_PLAN)
        _first = self.task_plan[0]
        self.current_task_type = _first["task_type"]
        self.task_planned_s = _first["planned_min"] * 60.0
        self.task_id = _first["task_id"]
        self.task_target_quantity = _first["target"]
        self.task_output_unit = _first["unit"]
        self.task_output_quantity = 0.0
        self.task_output_rate_per_min = 0.0
        self.shift_total_minutes = round(sum(entry["planned_min"] for entry in self.task_plan), 1)
        self._last_completed_task_id: str | None = None
        self._last_completed_task_type: str | None = None
        self._last_stage: str | None = None
        self.seatbelt_override: bool | None = None

        self.injector: ScenarioInjector | None = None
        self.injector_start_s = 0.0
        if scenario is not None:
            self.inject(scenario)
        self.operator_command: str | None = None

        # operator motion: work-zone loop start
        self.pos_angle = self.rng.uniform(0.0, 360.0)

    # ------------------------------------------------------------ injectors
    def inject(self, scenario: ScenarioSpec | None) -> None:
        if scenario is None or scenario.scenario_type is ScenarioType.NORMAL_OPERATION:
            self.injector = None
            self.injector_start_s = self.sim_time_s
            return
        self.injector = build_injector(scenario)
        # Scenario timelines are relative to the moment the operator starts
        # the practice, not to an earlier session that may still be running.
        self.injector_start_s = self.sim_time_s

    def inject_by_type(
        self,
        scenario_type: ScenarioType,
        severity: float = 0.7,
        onset_offset_s: float | None = None,
        **overrides,
    ) -> None:
        self.inject(make_spec(scenario_type, severity=severity, onset_offset_s=onset_offset_s, **overrides))

    def apply_operator_action(self, action: str) -> None:
        """Apply a simulated operator command to subsequent physics ticks."""
        allowed = {"STOP_MACHINE", "SHUTDOWN_ENGINE", "REDUCE_LOAD", "RESUME", "FASTEN_SEATBELT", "UNFASTEN_SEATBELT", "TOGGLE_SEATBELT"}
        if action not in allowed:
            raise ValueError(f"Unsupported operator action: {action}")
        if action == "FASTEN_SEATBELT":
            self.seatbelt_override = True
        elif action == "UNFASTEN_SEATBELT":
            self.seatbelt_override = False
        elif action == "TOGGLE_SEATBELT":
            self.seatbelt_override = not (self.seatbelt_override if self.seatbelt_override is not None else True)
        else:
            self.operator_command = None if action == "RESUME" else action

    def resume_after_safety(self) -> None:
        """Resume clean simulated work after a verified practice stop."""
        self.operator_command = None
        self.injector = None
        self.injector_start_s = self.sim_time_s

    @property
    def active_scenario_type(self) -> ScenarioType:
        return self.injector.scenario_type if self.injector else ScenarioType.NORMAL_OPERATION

    # ------------------------------------------------------------------ run
    def step(self) -> TelemetryFrame:
        dt = self.dt
        self.sim_time_s += dt

        cmd = self.scheduler.step(dt)
        env = self.env.step(dt, self.sim_time_s)

        params: dict = {}
        sensor_bias: dict[str, float] = {}
        seatbelt_off = False
        proximity_override: float | None = None
        nearby_override: int | None = None

        scenario_time_s = self.sim_time_s - self.injector_start_s
        if self.injector is not None:
            pert = self.injector.perturb(scenario_time_s, self.rng, cmd, env, self.dynamics)
            params.update(pert.params)
            for k, v in pert.cmd_add.items():
                cmd[k] = cmd.get(k, 0.0) + v
            cmd.update(pert.cmd)
            for k, v in pert.env_add.items():
                env[k] = env.get(k, 0.0) + v
            env.update(pert.env)
            sensor_bias = pert.sensor_bias
            seatbelt_off = pert.seatbelt_off
            proximity_override = pert.proximity_override
            nearby_override = pert.nearby_override

        # Operator actions are applied after scenario perturbations so a
        # response command can safely override the scripted operating point.
        if self.operator_command in ("STOP_MACHINE", "SHUTDOWN_ENGINE"):
            cmd.update({"state": "STOPPED", "load_pct": 0.0, "speed_kph": 0.0, "rpm_norm": 0.0})
            # A safe stop isolates a detected fuel-loss source in the
            # simulation. It contains the hazard; it is not a repair or an
            # engine shutdown.
            params["suppress_fuel_leak"] = True
            if self.operator_command == "SHUTDOWN_ENGINE":
                params["engine_off"] = True
        elif self.operator_command == "REDUCE_LOAD":
            cmd["load_pct"] = max(0.0, float(cmd.get("load_pct", 0.0)) - 20.0)

        if proximity_override is not None:
            params["proximity_target"] = proximity_override
        if seatbelt_off:
            params["seatbelt_off"] = True
        if self.seatbelt_override is not None:
            params["seatbelt_off"] = not self.seatbelt_override

        current_stage = str(cmd.get("stage", ""))
        if self._last_stage == "DUMP" and current_stage != "DUMP":
            params["cycle_complete"] = True
        self._last_stage = current_stage

        # The mission command IS the commanded operating point (load/speed/
        # hyd/rpm); scenario biases layer on top. `state` is passed separately.
        physics_params: dict = dict(cmd)
        physics_params.update(params)

        phys = self.dynamics.step(
            dt,
            state=cmd["state"],
            sim_time_s=self.sim_time_s,
            ambient_c=env["ambient_temperature_c"],
            terrain_roughness=self.site.roughness,
            slope_deg=env["slope_deg"],
            rng=self.rng,
            params=physics_params,
        )

        if phys["state"] == "REVERSING":
            mstate = MachineState.REVERSING
        elif phys["state"] == "STOPPED":
            mstate = MachineState.SHUTDOWN if not phys["engine_on"] else MachineState.STOPPED
        elif phys["state"] in ("IDLE", "BREAK"):
            mstate = MachineState.BREAK if cmd.get("stage") == "BREAK" and cmd["state"] == "IDLE" else MachineState.IDLE
        else:
            mstate = MachineState.ACTIVE

        # ---- position on a work-zone loop -----------------------------------
        heading = phys["heading_deg"]
        self.pos_angle = (self.pos_angle + (phys["speed_kph"] / 3.6) * dt * 0.9 / max(20.0, self.site.radius_m)) % 360.0
        lat = self.site.baseline_lat + (self.site.radius_m / 111320.0) * math.cos(math.radians(self.pos_angle))
        lon = self.site.baseline_lon + (self.site.radius_m / 111320.0) * math.sin(math.radians(self.pos_angle)) / max(
            0.5, math.cos(math.radians(self.site.baseline_lat))
        )

        # rate of cycle completions → task progress
        raw_progress = ((self.sim_time_s - self.task_start_s) / self.task_planned_s) * 100.0
        completing = raw_progress >= 100.0
        has_next = self.task_index < len(self.task_plan) - 1
        task_completed = completing and has_next
        progress = 100.0 if completing else min(100.0, raw_progress)
        previous_output = self.task_output_quantity
        if cmd["state"] == "ACTIVE":
            output_rate_per_s = max(0.0, (phys["load_pct"] / 100.0) * (0.045 if current_stage != "DUMP" else 0.12) * self.op_cfg.efficiency)
            self.task_output_quantity = min(self.task_target_quantity, self.task_output_quantity + output_rate_per_s * dt)
        self.task_output_rate_per_min = max(0.0, (self.task_output_quantity - previous_output) * 60.0 / max(dt, 0.001))

        # Snapshot the framing task BEFORE rollover so the frame that reports
        # "COMPLETED" still identifies the finished job (not the next one).
        task_id = self.task_id
        task_type = self.current_task_type
        task_planned_minutes = self.task_planned_s / 60.0
        task_index = self.task_index
        shift_remaining_minutes = round(sum(entry["planned_min"] for entry in self.task_plan[task_index:]), 1)

        # Task rollover: when the planned time elapses the framing task is
        # marked COMPLETED and the sim advances to the next job in the plan.
        next_task = self.task_plan[self.task_index + 1] if has_next else None
        if task_completed:
            self._last_completed_task_id = task_id
            self._last_completed_task_type = task_type
            self.task_index += 1
            entry = self.task_plan[self.task_index]
            self.task_id = entry["task_id"]
            self.current_task_type = entry["task_type"]
            self.task_planned_s = entry["planned_min"] * 60.0
            self.task_target_quantity = entry["target"]
            self.task_output_unit = entry["unit"]
            self.task_start_s = self.sim_time_s
            self.task_output_quantity = 0.0

        timestamp = self.start_time + timedelta(seconds=self.sim_time_s)
        ts_ms = int(timestamp.timestamp() * 1000)

        # ---- ground-truth scenario stamping (evaluation metadata only) ------
        inj = self.injector
        scenario_type = inj.scenario_type if inj else ScenarioType.NORMAL_OPERATION
        phase = inj.phase(scenario_time_s) if inj else Phase.NORMAL
        anomaly_active = phase in _ANOMALY_PHASES
        if inj is not None:
            spec = inj.spec
            max_ramp = max(0.0, min(1.0, inj.envelope(max(spec.onset_offset_s, spec.end_s - spec.abate_s / 2.0))))
            sev = severity_bucket(spec.severity)
        else:
            sev = None
        onset_t = (self.start_time + timedelta(seconds=self.injector_start_s + spec.onset_offset_s)) if inj else None
        resolve_t = (self.start_time + timedelta(seconds=self.injector_start_s + spec.end_s)) if inj else None

        scenario_params = dict(inj.spec.params) if inj else {}
        scenario_params.setdefault("severity", inj.spec.severity if inj else 0.0)
        scenario_params.setdefault("sim_onset_s", inj.spec.onset_offset_s if inj else None)
        scenario_params.setdefault("sim_resolve_s", inj.spec.end_s if inj else None)

        # ---- assemble frame (observed values may be sensor-biased) ----------
        sp = {
            "timestamp": timestamp,
            "timestamp_ms": ts_ms,
            "machine_id": self.machine_id,
            "operator_id": self.operator_id,
            "session_id": self.session_id,
            "task_id": task_id,
            "current_task_type": task_type,
            "task_index": task_index,
            "task_count": len(self.task_plan),
            "task_status": "COMPLETED" if task_completed or (completing and not has_next) else "IN_PROGRESS",
            "task_planned_minutes": round(task_planned_minutes, 1),
            "task_completed": task_completed,
            "completed_task_type": task_type if task_completed else self._last_completed_task_type,
            "completed_task_id": task_id if task_completed else self._last_completed_task_id,
            "next_task_type": next_task["task_type"] if next_task else "",
            "next_task_id": next_task["task_id"] if next_task else "",
            "shift_total_minutes": self.shift_total_minutes,
            "shift_remaining_minutes": shift_remaining_minutes,
            "engine_hours": phys["engine_hours"],
            "fuel_used_l": phys["fuel_used_session_l"],
            "load_cycles": phys["load_cycles"],
            "idling_time_min": phys["idling_time_min"],
            "seatbelt_status": "Fastened" if phys["seatbelt_fastened"] else "Unfastened",
            "safety_alert_triggered": (
                (not phys["seatbelt_fastened"] and phys["speed_kph"] > 0.1)
                or phys["proximity_m"] < 8.0
            ),
            "fuel_level_pct": phys["fuel_level_pct"],
            "fuel_consumption_rate_lph": phys["fuel_rate_lph"],
            "engine_rpm": phys["rpm"],
            "engine_temperature_c": phys["engine_temp_c"],
            "coolant_temperature_c": phys["coolant_temp_c"],
            "oil_pressure_kpa": phys["oil_pressure_kpa"],
            "hydraulic_pressure_bar": phys["hyd_pressure_bar"],
            "hydraulic_temperature_c": phys["hyd_temp_c"],
            "battery_voltage_v": phys["battery_v"],
            "engine_load_pct": phys["load_pct"],
            "machine_speed_kph": phys["speed_kph"],
            "vibration_g": phys["vibration_g"],
            "proximity_distance_m": phys["proximity_m"],
            "operating_hours": phys["operating_hours"],
            "latitude": lat,
            "longitude": lon,
            "ambient_temperature_c": env["ambient_temperature_c"],
            "humidity_pct": env["humidity_pct"],
            "rainfall_mmh": env["rainfall_mmh"],
            "visibility_m": env["visibility_m"],
            "terrain_type": env["terrain_type"],
            "terrain_condition": env["terrain_condition"],
            "slope_deg": env["slope_deg"],
            "work_zone": env["work_zone"],
            "nearby_machine_count": nearby_override if nearby_override is not None else env["nearby_machine_count"],
            "weather_event": env["weather_event"],
            "machine_state": mstate,
            "task_progress_pct": round(progress, 1),
            "task_output_quantity": round(self.task_output_quantity, 3),
            "task_target_quantity": self.task_target_quantity,
            "task_output_unit": self.task_output_unit,
            "productivity_rate_per_min": round(self.task_output_rate_per_min, 3),
            "fuel_efficiency_output_per_l": round(self.task_output_quantity / max(0.01, phys["fuel_used_session_l"]), 3),
            "hydraulic_cycle_count": phys["load_cycles"],
            "efficiency": self.op_cfg.efficiency,
            "aggression_index": self.op_cfg.aggression,
            "compliance": self.op_cfg.compliance,
            "cooling_performance_pct": round(self.dynamics.cooling_perf * 100.0, 1),
            "diagnostics_consistency": 1.0,
            "scenario_type": scenario_type,
            "phase": phase,
            "anomaly_label": anomaly_active,
            "incident_type": scenario_type.value if anomaly_active else None,
            "incident_severity": sev if anomaly_active else None,
            "anomaly_onset_t": onset_t,
            "detect_t": None,
            "resolve_t": resolve_t,
            "refuel_event": False,
            "scenario_params": scenario_params,
        }

        if sensor_bias:
            for field, bias in sensor_bias.items():
                if field in sp and isinstance(sp[field], (int, float)):
                    sp[field] = max(0.0, sp[field] + bias)
            e_now = inj.envelope(self.sim_time_s) if inj else 0.0
            sp["diagnostics_consistency"] = round(max(0.55, 1.0 - 0.35 * (inj.spec.severity if inj else 0.0) * e_now), 3)

        frame = TelemetryFrame(**sp)
        self.last_frame = frame
        return frame
