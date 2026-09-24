"""Synthetic task-dataset generator.

Produces a task-level dataset with the challenge's REQUIRED columns preserved
verbatim:

    Task_ID, Task_Type, Weather, Operator_Skill, Machine_Age_yrs,
    Estimated_Time_min, Actual_Time_min

...plus our additive columns (Task_Zone, Task_Priority, Material_Type,
Terrain_Condition, Ambient_Temp_C, Rainfall_mmh, Visibility_m, Shift,
Required_Equipment, Machine_ID, Operator_ID, Scheduled_Start_Time,
Reference_Time_min, Delay_Reason, Efficiency_Factor).

The drives are *causal*: a baseline duration is multiplied by condition factors
(material, terrain, weather, operator skill, machine age) plus lognormal noise,
so `Actual_Time_min` is explainable and regression models can recover the truth.
The planning estimate is drawn independently of the realized noise (it is set
before the job runs), mirroring real planning.

All values are DEMO / SYNTHETIC — not real Caterpillar production data.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from app.simulation.catalog import MACHINES, OPERATORS
from app.schemas.telemetry import TerrainCondition, WeatherEvent

TASK_TYPES = ["EXCAVATION", "LOADING", "HAULING", "GRADING", "COMPACTING", "LIFTING", "TRENCHING"]

ZONES = ["QUARRY-NORTH", "FOUNDATION-A", "CRUSHER-PAD", "SOUTH-ACCESS"]

# baseline duration (min), plausible equipment, allowed materials
TASK_SPECS: dict[str, dict[str, Any]] = {
    "EXCAVATION": dict(base=240.0, equipment="EXCAVATOR",
                       materials=("OVERBURDEN", "LOAM", "GRAVEL", "ROCKY", "COMPACTED")),
    "LOADING":    dict(base=150.0, equipment="LOADER",
                       materials=("OVERBURDEN", "GRAVEL", "LOAM", "MUDDY_SOIL")),
    "HAULING":    dict(base=185.0, equipment="HAULER",
                       materials=("OVERBURDEN", "GRAVEL", "ROCKY", "MUDDY_SOIL")),
    "GRADING":    dict(base=210.0, equipment="MOTOR GRADER",
                       materials=("COMPACTED", "LOAM", "GRAVEL", "OVERBURDEN")),
    "COMPACTING": dict(base=175.0, equipment="COMPACTOR",
                       materials=("COMPACTED", "LOAM", "GRAVEL")),
    "LIFTING":    dict(base=120.0, equipment="LIFT TRUCK",
                       materials=("STEEL", "PIPING", "PALLETS", "CONCRETE")),
    "TRENCHING":  dict(base=200.0, equipment="TRENCHER",
                       materials=("LOAM", "MUDDY_SOIL", "ROCKY", "COMPACTED")),
}

MATERIAL_FACTOR = {
    "OVERBURDEN": 1.00, "LOAM": 1.10, "GRAVEL": 1.15, "ROCKY": 1.35,
    "COMPACTED": 1.05, "MUDDY_SOIL": 1.50, "STEEL": 1.00, "PIPING": 1.05,
    "PALLETS": 0.98, "CONCRETE": 1.20,
}

TERRAIN_FACTOR = {
    TerrainCondition.DRY: 1.00, TerrainCondition.WET: 1.12,
    TerrainCondition.PACKED: 1.00, TerrainCondition.MUDDY: 1.30,
    TerrainCondition.ICY: 1.42,
}

WEATHER_FACTOR = {
    WeatherEvent.NONE: 1.00, WeatherEvent.RAIN: 1.16, WeatherEvent.HEAVY_RAIN: 1.32,
    WeatherEvent.FOG: 1.10, WeatherEvent.HOT: 1.12, WeatherEvent.HIGH_WIND: 1.14,
}

SKILL_FACTOR = {"EXPERT": 0.92, "INTERMEDIATE": 1.00, "BEGINNER": 1.15}

# -------- weather → environment numerics (for additive columns) ------------
WEATHER_NUMERIC = {
    WeatherEvent.NONE: dict(rainfall=0.0, visibility=8000.0, ambient=26.0),
    WeatherEvent.RAIN: dict(rainfall=8.0, visibility=3000.0, ambient=22.0),
    WeatherEvent.HEAVY_RAIN: dict(rainfall=18.0, visibility=900.0, ambient=20.0),
    WeatherEvent.FOG: dict(rainfall=0.0, visibility=420.0, ambient=21.0),
    WeatherEvent.HOT: dict(rainfall=0.0, visibility=8000.0, ambient=36.0),
    WeatherEvent.HIGH_WIND: dict(rainfall=0.0, visibility=6000.0, ambient=27.0),
}

WEATHER_CHOICES = (
    WeatherEvent.NONE, WeatherEvent.RAIN, WeatherEvent.NONE, WeatherEvent.FOG,
    WeatherEvent.NONE, WeatherEvent.RAIN, WeatherEvent.NONE, WeatherEvent.HIGH_WIND,
    WeatherEvent.HOT, WeatherEvent.NONE, WeatherEvent.HEAVY_RAIN, WeatherEvent.HOT,
)

REQUIRED_TASK_COLUMNS = [
    "Task_ID", "Task_Type", "Weather", "Operator_Skill", "Machine_Age_yrs",
    "Estimated_Time_min", "Actual_Time_min",
]

ADDITIONAL_TASK_COLUMNS = [
    "Task_Zone", "Task_Priority", "Material_Type", "Terrain_Condition",
    "Ambient_Temp_C", "Rainfall_mmh", "Visibility_m", "Shift",
    "Required_Equipment", "Machine_ID", "Operator_ID", "Scheduled_Start_Time",
    "Reference_Time_min", "Delay_Reason", "Efficiency_Factor",
]

PRIORITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
SHIFTS = ("DAY", "NIGHT")


def _task_id(i: int) -> str:
    return f"T{10000 + i}"


def age_factor(years: float) -> float:
    return 1.0 + 0.006 * max(0.0, years - 2.0)


def reference_minutes(
    task_type: str,
    material: str,
    terrain: TerrainCondition,
    skill: str,
    age_yrs: float,
) -> float:
    spec = TASK_SPECS[task_type]
    return (
        spec["base"]
        * MATERIAL_FACTOR[material]
        * TERRAIN_FACTOR[terrain]
        * SKILL_FACTOR[skill]
        * age_factor(age_yrs)
    )


def generate_task_history(
    seed: int = 2026,
    n_days: int = 90,
    tasks_per_day_lo: int = 6,
    tasks_per_day_hi: int = 12,
    start_date: str = "2026-04-01",
) -> pd.DataFrame:
    """Generate a multi-day task-history corpus across machines/operators."""
    rng = random.Random(seed)
    machines = list(MACHINES)
    operators = list(OPERATORS)
    skill_by_op = {op: OPERATORS[op].skill_level for op in operators}
    day0 = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    rows: list[dict] = []
    i = 0
    # deterministic days-to-tasks count offsets so each day varies cleanly
    for d in range(n_days):
        date = day0 + timedelta(days=d, hours=7)
        n_tasks = rng.randint(tasks_per_day_lo, tasks_per_day_hi)
        for _ in range(n_tasks):
            task_type = rng.choice(TASK_TYPES)
            spec = TASK_SPECS[task_type]
            machine_id = rng.choice(machines)
            operator_id = rng.choice(operators)
            machine_age = MACHINES[machine_id].age_years
            skill = skill_by_op[operator_id]
            terrain = _sample_terrain(rng, forecast=False)
            material = rng.choice(spec["materials"])
            weather = rng.choice(WEATHER_CHOICES)
            shift = rng.choice(SHIFTS)
            priority = rng.choices(PRIORITIES, weights=(0.35, 0.30, 0.25, 0.10))[0]
            zone = rng.choice(ZONES)

            ref = reference_minutes(task_type, material, terrain, skill, machine_age)
            # realized outcome = reference * lognormal(0, 0.08) * weather factor
            weather_f = WEATHER_FACTOR[weather]
            noise = math.exp(rng.gauss(0.0, 0.08))
            actual = max(15.0, ref * weather_f * noise * (1.0 + rng.uniform(-0.02, 0.02)))
            actual = round(actual, 1)

            # planning estimate drawn independent of the realized noise
            est_bias = max(-0.15, min(0.25, rng.gauss(0.0, 0.06)))
            estimated = max(10.0, round(ref * (1.0 + est_bias), 1))

            rows.append(
                _task_row(
                    i=i,
                    rng=rng,
                    task_type=task_type,
                    machine_id=machine_id,
                    operator_id=operator_id,
                    skill=skill,
                    machine_age=machine_age,
                    material=material,
                    terrain=terrain,
                    weather=weather,
                    priority=priority,
                    zone=zone,
                    shift=shift,
                    date=date,
                    actual=actual,
                    ref=ref,
                    estimated=estimated,
                )
            )
            date += timedelta(minutes=rng.randint(20, 120))
            i += 1

    return pd.DataFrame(rows)


def generate_shift_schedule(
    seed: int = 2026,
    n_days: int = 1,
    start_date: str = "2026-09-23",
    machines: tuple[str, ...] = ("MX-101",),
    tasks_per_machine: int = 5,
    demo_time_scale: float = 0.022,
) -> pd.DataFrame:
    """Generate today's (or next n days') planned task schedule with 4-5 tasks per machine/operator.

    ``demo_time_scale`` compresses the realistic base durations so the five-job
    shift totals about 10 minutes, matching the generator's DEMO_TASK_PLAN.
    All values remain SYNTHETIC.
    """
    rng = random.Random(seed)
    day0 = datetime.strptime(start_date, "%Y-%m-%d").replace(
        hour=7, minute=0, second=0, tzinfo=timezone.utc
    )
    shift_sequence = ("EXCAVATION", "LOADING", "TRENCHING", "HAULING", "GRADING")
    rows: list[dict] = []
    i = 0
    for d in range(n_days):
        for machine_id in machines:
            operator_id = OPERATORS[MACHINES[machine_id].dem_operator_id].operator_id
            skill = OPERATORS[operator_id].skill_level
            machine_age = MACHINES[machine_id].age_years
            t = day0 + timedelta(days=d)

            for task_idx in range(tasks_per_machine):
                task_type = shift_sequence[task_idx % len(shift_sequence)]
                spec = TASK_SPECS[task_type]
                material = rng.choice(spec["materials"])
                terrain = TerrainCondition(_sample_terrain_str(rng, forecast=True))
                weather = rng.choice(WEATHER_CHOICES)
                ref = reference_minutes(task_type, material, terrain, skill, machine_age)
                est_bias = max(-0.15, min(0.25, rng.gauss(0.0, 0.05)))
                # Scale base task minutes so 5 tasks fit realistically in an 8-hour shift
                duration_scale = 0.45 if task_idx > 0 else 0.55
                estimated = max(1.0, round(ref * duration_scale * demo_time_scale * (1.0 + est_bias), 1))

                if task_idx == 0:
                    priority = "CRITICAL"
                elif task_idx == 1:
                    priority = "HIGH"
                elif task_idx == 2:
                    priority = "MEDIUM"
                else:
                    priority = rng.choice(["MEDIUM", "LOW"])

                zone = ZONES[task_idx % len(ZONES)]

                rows.append(
                    _task_row(
                        i=i,
                        rng=rng,
                        task_type=task_type,
                        machine_id=machine_id,
                        operator_id=operator_id,
                        skill=skill,
                        machine_age=machine_age,
                        material=material,
                        terrain=terrain,
                        weather=weather,
                        priority=priority,
                        zone=zone,
                        shift="DAY",
                        date=t,
                        actual=estimated,  # scheduled, actual not yet realized
                        ref=round(ref * duration_scale * demo_time_scale, 1),
                        estimated=estimated,
                    )
                )
                i += 1
                t += timedelta(minutes=int(estimated + rng.randint(15, 25)))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
def _sample_terrain(rng: random.Random, forecast: bool) -> TerrainCondition:
    choices = ("DRY", "DRY", "PACKED", "PACKED", "WET", "MUDDY", "ICY")
    return TerrainCondition(rng.choice(choices))


def _sample_terrain_str(rng: random.Random, forecast: bool) -> str:
    return _sample_terrain(rng, forecast).value


def _task_row(
    i: int,
    rng: random.Random,
    task_type: str,
    machine_id: str,
    operator_id: str,
    skill: str,
    machine_age: float,
    material: str,
    terrain: TerrainCondition,
    weather: WeatherEvent,
    priority: str,
    zone: str,
    shift: str,
    date: datetime,
    actual: float,
    ref: float,
    estimated: float,
) -> dict:
    eff = actual / ref
    if weather is not WeatherEvent.NONE and eff > 1.06:
        delay_reason = "WEATHER"
    elif material in ("ROCKY", "MUDDY_SOIL") and eff > 1.06:
        delay_reason = "MATERIAL_CONDITION"
    elif terrain in (TerrainCondition.MUDDY, TerrainCondition.ICY) and eff > 1.06:
        delay_reason = "TERRAIN_CONDITION"
    elif skill == "BEGINNER" and eff > 1.12:
        delay_reason = "OPERATOR_EFFICIENCY"
    elif machine_age > 8.0 and eff > 1.08:
        delay_reason = "MACHINE_AGE"
    elif eff > 1.15:
        delay_reason = "SCHEDULING"
    else:
        delay_reason = "NONE"

    num = WEATHER_NUMERIC[weather]
    return {
        "Task_ID": _task_id(i),
        "Task_Type": task_type,
        "Weather": weather.value,
        "Operator_Skill": skill,
        "Machine_Age_yrs": round(machine_age, 1),
        "Estimated_Time_min": estimated,
        "Actual_Time_min": actual,
        "Task_Zone": zone,
        "Task_Priority": priority,
        "Material_Type": material,
        "Terrain_Condition": terrain.value,
        "Ambient_Temp_C": num["ambient"],
        "Rainfall_mmh": num["rainfall"],
        "Visibility_m": num["visibility"],
        "Shift": shift,
        "Required_Equipment": TASK_SPECS[task_type]["equipment"],
        "Machine_ID": machine_id,
        "Operator_ID": operator_id,
        "Scheduled_Start_Time": date.isoformat(),
        "Reference_Time_min": round(ref, 1),
        "Delay_Reason": delay_reason,
        "Efficiency_Factor": round(eff, 3),
    }


__all__ = ["REQUIRED_TASK_COLUMNS", "ADDITIONAL_TASK_COLUMNS", "generate_task_history", "generate_shift_schedule", "reference_minutes"]