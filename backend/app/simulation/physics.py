"""Physics-lite machine dynamics (normal-operation model).

Each physical quantity evolves from an underlying *state* via first-order
dynamics toward a demand-driven target, plus correlated noise. Fuel is a true
integral of the consumption rate (conservation is unit-tested). All values are
DEMO parameters for a generic heavy machine.

Phase 2 will layer the scenario injectors on top of these same ODEs.
"""
from __future__ import annotations

import math
import random

import numpy as np

from app.simulation.catalog import MachineConfig, OperatorConfig


def _smooth(current: float, target: float, dt: float, tau: float) -> float:
    """First-order approach toward a target."""
    if tau <= 0.0:
        return target
    return current + (target - current) * (1.0 - math.exp(-dt / tau))


class MachineDynamics:
    def __init__(
        self,
        cfg: MachineConfig,
        operator: OperatorConfig,
        rng: random.Random,
        start_fuel_pct: float = 72.0,
        start_engine_hours: float = 4120.0,
        start_operating_hours: float = 4185.0,
    ):
        self.cfg = cfg
        self.op = operator
        self.rng = rng
        self.nprng = np.random.default_rng(seed=rng.randrange(2**32))

        self.t_s = 0.0
        self.fuel_l = cfg.fuel_capacity_l * (start_fuel_pct / 100.0)
        self.fuel_used_session_l = 0.0
        self.fuel_leaked_l = 0.0
        self.fuel_level_pct = start_fuel_pct
        self.engine_hours = start_engine_hours
        self.operating_hours = start_operating_hours
        self.load_cycles = 128
        self.idle_seconds = 0.0
        self.idling_time_min = 0.0

        # smoothed signals
        self.rpm = cfg.idle_rpm
        self.engine_temp_c = 48.0
        self.coolant_temp_c = 46.0
        self.hyd_pressure_bar = 25.0
        self.hyd_temp_c = 30.0
        self.battery_v = cfg.battery_setpoint_v
        self.engine_load_pct = 5.0
        self.speed_kph = 0.0
        self.vibration_g = 0.08

        self.seatbelt_fastened = True
        self.proximity_m = 42.0
        self.heading_deg = 0.0
        self.lat = cfg.site_key  # placeholder, replaced by site coords in generator
        self.lon = 0.0
        self.engine_on = True
        self.machine_state = "IDLE"
        self.cooling_perf = cfg.cooling_perf_baseline

    # ------------------------------------------------------------------ step
    def step(
        self,
        dt: float,
        *,
        state: str,
        sim_time_s: float,
        ambient_c: float,
        terrain_roughness: float,
        slope_deg: float,
        rng: random.Random | None = None,
        params: dict | None = None,
    ) -> dict:
        params = params or {}
        rng = rng or self.rng
        self.t_s = sim_time_s
        cfg = self.cfg

        # ---- commanded operating point from the mission ---------------
        state = state.upper()
        if state in ("STOPPED", "SHUTDOWN"):
            state = "STOPPED"
        if params.get("engine_off"):
            self.engine_on = False
        elif params.get("engine_on"):
            self.engine_on = True
        if not self.engine_on:
            state = "STOPPED"
        self.machine_state = state

        idle = state in ("IDLE", "BREAK", "STOPPED")
        rpm_norm = params.get("rpm_norm", 0.35 if idle or state == "STOPPED" else 0.85)
        load_tgt = params.get("load_pct", 6.0 if idle or state == "STOPPED" else 80.0)
        speed_tgt = params.get("speed_kph", 0.0 if idle or state == "STOPPED" else 8.0)
        hyd_tgt = params.get("hyd_bar", 28.0 if idle or state == "STOPPED" else 150.0)
        reversing = state == "REVERSING"

        # ---- engine -----------------------------------------------------
        rpm_tgt = 0.0 if not self.engine_on else (cfg.idle_rpm if (idle or state == "STOPPED") else cfg.max_rpm * rpm_norm)
        rpm_tgt *= (1.0 + 0.02 * rng.gauss(0.0, 1.0) - 0.01 * rng.gauss(0.0, 1.0))
        self.rpm = _smooth(self.rpm, rpm_tgt, dt, 1.8)
        self.rpm = max(0.0, min(cfg.max_rpm * 1.06, self.rpm))

        load = (0.0 if not self.engine_on else load_tgt) + rng.gauss(0.0, 2.0)
        load = max(0.0, min(100.0, load))
        self.engine_load_pct = _smooth(self.engine_load_pct, load, dt, 1.2)

        # ---- fuel (conserved integral) ----------------------------------
        rpm_frac = self.rpm / cfg.max_rpm
        fuel_rate_lph = 0.0 if not self.engine_on else cfg.idle_fuel_lph + cfg.load_fuel_k * (self.engine_load_pct / 100.0) * rpm_frac
        fuel_rate_lph *= (1.0 + params.get("fuel_rate_bias", 0.0))
        fuel_rate_lph += rng.gauss(0.0, 0.25)
        fuel_rate_lph = max(0.0, fuel_rate_lph)
        self.fuel_con_rate_lph = fuel_rate_lph

        d_fuel_l = fuel_rate_lph * (dt / 3600.0)
        self.fuel_l = max(0.0, self.fuel_l - d_fuel_l)
        self.fuel_used_session_l += d_fuel_l

        # Fuel leak (Phase 2): drains the tank BEYOND reported consumption.
        leak_lph = 0.0 if params.get("suppress_fuel_leak") else max(0.0, params.get("fuel_leak_lph", 0.0))
        if leak_lph > 0.0:
            d_leak_l = leak_lph * (dt / 3600.0)
            self.fuel_l = max(0.0, self.fuel_l - d_leak_l)
            self.fuel_leaked_l += d_leak_l
        self.fuel_level_pct = (self.fuel_l / cfg.fuel_capacity_l) * 100.0

        # ---- thermal ------------------------------------------------------
        cooling_eff = cfg.cooling_perf_baseline * params.get("cooling_perf_mult", 1.0)
        self.cooling_perf = cooling_eff
        t_eq = (
            48.0
            + 0.38 * self.engine_load_pct
            + 10.0 * (self.rpm / cfg.max_rpm)
            + 0.3 * (ambient_c - 20.0)
            + (cfg.cooling_perf_baseline - cooling_eff) * 22.0  # cooling deficit == heat
        )
        t_eq += params.get("thermal_bias", 0.0)
        self.engine_temp_c = _smooth(self.engine_temp_c, t_eq, dt, cfg.thermal_tau_s * params.get("thermal_tau_mult", 1.0))
        self.engine_temp_c += rng.gauss(0.0, 0.08)
        self.engine_temp_c = max(-10.0, min(160.0, self.engine_temp_c))

        coolant_eq = self.engine_temp_c - 4.0 - 0.6 * (self.engine_load_pct / 100.0) * 6.0
        self.coolant_temp_c = _smooth(self.coolant_temp_c, coolant_eq, dt, cfg.coolant_tau_s)
        self.coolant_temp_c += rng.gauss(0.0, 0.06)
        self.coolant_temp_c = max(-10.0, min(160.0, self.coolant_temp_c))

        oil_pressure = 380.0 - 1.2 * max(0.0, self.engine_temp_c - 70.0)
        oil_pressure += rng.gauss(0.0, 3.0) + 40.0 * (self.engine_load_pct / 100.0)
        oil_pressure = max(90.0, min(520.0, oil_pressure))
        self.oil_pressure_kpa = oil_pressure

        # ---- hydraulics -----------------------------------------------------
        hyd_gain = 1.0 + params.get("hyd_gain_mult", 0.0)  # subtractive for failure in P2
        hyd_target = max(20.0, min(320.0, hyd_tgt * hyd_gain + rng.gauss(0.0, 2.5)))
        self.hyd_pressure_bar = _smooth(self.hyd_pressure_bar, hyd_target, dt, 1.4)
        hyd_temp_eq = 25.0 + 0.22 * self.hyd_pressure_bar + 0.15 * ambient_c
        hyd_temp_eq += params.get("hyd_temp_bias", 0.0)
        self.hyd_temp_c = _smooth(self.hyd_temp_c, hyd_temp_eq, dt, cfg.hyd_tau_s)
        self.hyd_temp_c += rng.gauss(0.0, 0.05)

        # ---- electrical ------------------------------------------------------
        self.battery_v = _smooth(
            self.battery_v,
            cfg.battery_setpoint_v - 0.4 * (self.engine_load_pct / 100.0) - 0.15 * (self.rpm / cfg.max_rpm) + params.get("battery_bias", 0.0),
            dt,
            4.0,
        )
        self.battery_v += rng.gauss(0.0, 0.04)
        self.battery_v = max(18.0, min(28.5, self.battery_v))

        # ---- motion --------------------------------------------------------
        speed = speed_tgt + rng.gauss(0.0, 0.15 if not idle else 0.02)
        speed = max(0.0, speed)
        self.speed_kph = _smooth(self.speed_kph, speed, dt, 1.6 if not idle else 0.8)
        if state == "STOPPED":
            self.speed_kph = 0.0

        self.vibration_g = (
            0.08
            + 0.010 * self.speed_kph
            + 0.02 * (self.engine_load_pct / 100.0) * 6.0
            + terrain_roughness
            + abs(math.sin(self.t_s / 7.0)) * 0.02
            + rng.gauss(0.0, 0.012)
        )
        self.vibration_g = max(0.02, min(3.0, self.vibration_g))

        # ---- motion / position (work-zone loop) -----------------------------
        if not idle and self.speed_kph > 0.1:
            if reversing:
                self.heading_deg = (self.heading_deg + 120.0) % 360.0
            deg_per_s = (self.speed_kph / 3.6) * (180.0 / (math.pi * 180.0)) * 360.0
            self.heading_deg = (self.heading_deg + 0.6) % 360.0 if not reversing else self.heading_deg
            self.heading_deg += deg_per_s * dt * 0.06
            self.heading_deg %= 360.0

        # ---- safety ---------------------------------------------------------
        # Normal operation: belt always fastened. Scenario injectors (Phase 2)
        # may force `Unfastened` while moving for SEATBELT_VIOLATION.
        self.seatbelt_fastened = not bool(params.get("seatbelt_off", False))

        if "proximity_target" in params:
            self.proximity_m = _smooth(self.proximity_m, max(0.5, params["proximity_target"]), dt, 4.0)
        else:
            self.proximity_m = float(max(8.0, self.proximity_m + rng.gauss(0.0, 1.2)))
        self.proximity_m = min(60.0, self.proximity_m)

        # ---- counters ----------------------------------------------------------
        self.engine_hours += (dt / 3600.0) if self.engine_on else 0.0
        self.operating_hours += dt / 3600.0
        if idle or state == "STOPPED":
            self.idle_seconds += dt
        else:
            if self.idle_seconds > 0.0:
                self.idle_seconds = 0.0
        self.idling_time_min = self.idle_seconds / 60.0
        if params.get("cycle_complete"):
            self.load_cycles += 1

        # GPS coarse position (server provides site coords + heading)
        return {
            "rpm": round(self.rpm, 1),
            "load_pct": round(self.engine_load_pct, 1),
            "fuel_rate_lph": round(self.fuel_con_rate_lph, 3),
            "fuel_level_pct": round(self.fuel_level_pct, 3),
            "engine_hours": round(self.engine_hours, 4),
            "operating_hours": round(self.operating_hours, 4),
            "fuel_used_session_l": round(self.fuel_used_session_l, 4),
            "load_cycles": self.load_cycles,
            "idling_time_min": round(self.idling_time_min, 3),
            "speed_kph": round(self.speed_kph, 2),
            "engine_temp_c": round(self.engine_temp_c, 2),
            "coolant_temp_c": round(self.coolant_temp_c, 2),
            "oil_pressure_kpa": round(self.oil_pressure_kpa, 1),
            "hyd_pressure_bar": round(self.hyd_pressure_bar, 1),
            "hyd_temp_c": round(self.hyd_temp_c, 2),
            "battery_v": round(self.battery_v, 2),
            "vibration_g": round(self.vibration_g, 3),
            "seatbelt_fastened": self.seatbelt_fastened,
            "proximity_m": round(self.proximity_m, 2),
            "state": self.machine_state,
            "engine_on": self.engine_on,
            "heading_deg": round(self.heading_deg % 360.0, 1),
        }
