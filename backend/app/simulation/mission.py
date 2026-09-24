"""Mission scheduler: turns a task plan into per-tick operator commands.

Drives the work-cycle stage machine (DIG → HAUL → REVERSE → DUMP) for normal
operation and, in Phase 1, returns deterministic commands the dynamics step
consumes. Deterministic given the session RNG.
"""
from __future__ import annotations

import random

from app.simulation.catalog import TASK_CATALOG


class MissionScheduler:
    def __init__(self, task_type: str, operator_factor: float, rng: random.Random):
        spec = TASK_CATALOG[task_type]
        self.task_type = task_type
        self.spec = spec
        self.rng = rng
        self.operator_factor = operator_factor  # efficiency multiplier
        self.stage = "DIG"
        self.stage_remaining_s = self._roll_stage_duration()
        self.cycle_count = 0
        self.since_break = 0
        self.in_break = False
        self.break_remaining_s = 0.0

    def _roll_stage_duration(self) -> float:
        lo, hi = self.spec["stage_ranges_s"][self.stage]
        return self.rng.uniform(lo, hi) / max(0.6, self.operator_factor)

    def step(self, dt: float) -> dict:
        """Advance one sim tick; return a command dict for the dynamics."""
        self.stage_remaining_s -= dt

        if self.in_break:
            self.break_remaining_s -= dt
            if self.break_remaining_s <= 0.0:
                self.in_break = False
                self.stage = "DIG"
                self.stage_remaining_s = self._roll_stage_duration()
            return self._idle_command_marker(idle=True)

        if self.stage_remaining_s <= 0.0:
            self._advance_stage()

        spec = self.spec
        lo, hi = spec["load_ranges"][self.stage]
        load = self.rng.uniform(lo, hi)
        hlo, hhi = spec["hyd_ranges_bar"][self.stage]
        hyd = self.rng.uniform(hlo, hhi)
        slo, shi = spec["speed_kph"][self.stage]
        speed = self.rng.uniform(slo, shi)
        rlo, rhi = spec["rpm_norm"][self.stage]
        rpm_norm = self.rng.uniform(rlo, rhi)

        state = {
            "DIG": "ACTIVE",
            "HAUL": "ACTIVE",
            "REVERSE": "REVERSING",
            "DUMP": "ACTIVE",
        }[self.stage]

        return {
            "state": state,
            "load_pct": load,
            "hyd_bar": hyd,
            "speed_kph": speed,
            "rpm_norm": rpm_norm,
            "stage": self.stage,
            "cycle_count": self.cycle_count,
        }

    def _advance_stage(self) -> None:
        order = self.spec["stages"]
        idx = order.index(self.stage)
        if self.stage == "DUMP":
            # cycle complete
            self.cycle_count += 1
            self.since_break += 1
            if self.since_break >= self.spec["cycles_between_breaks"]:
                self.since_break = 0
                self.in_break = True
                bl, bh = self.spec["break_duration_s"]
                self.break_remaining_s = self.rng.uniform(bl, bh)
                self.stage = "DUMP"
                self.stage_remaining_s = 0.1
                return
            self.stage = order[0]
        else:
            self.stage = order[idx + 1]
        self.stage_remaining_s = self._roll_stage_duration()

    def _idle_command_marker(self, idle: bool) -> dict:
        return {
            "state": "IDLE",
            "load_pct": 5.0,
            "hyd_bar": 28.0,
            "speed_kph": 0.0,
            "rpm_norm": 0.35,
            "stage": "BREAK",
            "cycle_count": self.cycle_count,
        }