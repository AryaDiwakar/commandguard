"""Demo catalog: machines, operators, work sites, task templates.

All numeric values are DEMO / SYNTHETIC parameters used only to drive a
software simulation of a generic heavy machine. They are not real-world
manufacturer specifications nor proprietary company data.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MachineConfig:
    machine_id: str
    model: str
    machine_class: str
    fuel_capacity_l: float = 760.0
    max_rpm: float = 2100.0
    idle_rpm: float = 780.0
    idle_fuel_lph: float = 6.5
    load_fuel_k: float = 62.0          # delta L/h per (load_pct/100)*(rpm/max)
    thermal_tau_s: float = 90.0
    coolant_tau_s: float = 150.0
    hyd_tau_s: float = 240.0
    battery_setpoint_v: float = 24.2
    cooling_perf_baseline: float = 0.93
    site_key: str = "QUARRY-NORTH"
    dem_operator_id: str = "OP-01"
    age_years: float = 5.0             # machine age for task-dataset causality


@dataclass
class OperatorConfig:
    operator_id: str
    name: str
    experience_years: float = 6.0
    efficiency: float = 1.0            # >1 faster cycles, <1 slower
    aggression: float = 0.25           # 0..1 harshness of inputs
    compliance: float = 0.99           # seatbelt / procedure adherence
    idle_prone: float = 0.05           # chance to take extra breaks
    refuel_threshold_pct: float = 18.0
    refuel_duration_s: float = 900.0
    skill_level: str = "INTERMEDIATE"  # EXPERT / INTERMEDIATE / BEGINNER (task-dataset)


@dataclass
class SiteConfig:
    site_key: str
    work_zone: str
    baseline_lat: float
    baseline_lon: float
    terrain_type: str = "FLAT"
    terrain_condition: str = "DRY"
    slope_deg: float = 2.0
    roughness: float = 0.30            # vibration multiplier
    ambient_base_c: float = 24.0
    ambient_amp_c: float = 4.0
    humidity_base: float = 52.0
    visibility_m: float = 8000.0
    nearby_machines: int = 2
    radius_m: float = 180.0            # work-zone loop radius


MACHINES: dict[str, MachineConfig] = {
    "MX-101": MachineConfig(machine_id="MX-101", model="DEMO HYD-EX 320", machine_class="EXCAVATOR", age_years=4.2),
    "MX-102": MachineConfig(machine_id="MX-102", model="DEMO HYD-EX 320", machine_class="EXCAVATOR", age_years=7.4),
    "MX-103": MachineConfig(
        machine_id="MX-103", model="DEMO HYD-EX 320", machine_class="EXCAVATOR",
        site_key="FOUNDATION-A", age_years=2.1,
    ),
}

OPERATORS: dict[str, OperatorConfig] = {
    "OP-01": OperatorConfig(
        operator_id="OP-01", name="A. Wakar", experience_years=12.0,
        efficiency=1.04, aggression=0.18, compliance=0.99, skill_level="EXPERT",
    ),
    "OP-02": OperatorConfig(
        operator_id="OP-02", name="S. Reyes", experience_years=6.0,
        efficiency=0.94, aggression=0.55, compliance=0.96, skill_level="INTERMEDIATE",
    ),
    "OP-03": OperatorConfig(
        operator_id="OP-03", name="M. Chen", experience_years=1.5,
        efficiency=0.86, aggression=0.30, compliance=0.97, skill_level="BEGINNER",
    ),
}

SITES: dict[str, SiteConfig] = {
    "QUARRY-NORTH": SiteConfig(
        site_key="QUARRY-NORTH",
        work_zone="QUARRY-NORTH",
        baseline_lat=-23.5505,
        baseline_lon=-46.6333,
    ),
    "FOUNDATION-A": SiteConfig(
        site_key="FOUNDATION-A",
        work_zone="FOUNDATION-A",
        baseline_lat=-23.5410,
        baseline_lon=-46.6285,
    ),
}

TASK_CATALOG = {
    "EXCAVATION": {
        "stages": ["DIG", "HAUL", "REVERSE", "DUMP"],
        "stage_ranges_s": {
            "DIG": (8, 14),
            "HAUL": (10, 18),
            "REVERSE": (4, 8),
            "DUMP": (5, 10),
        },
        "cycles_between_breaks": 10,
        "break_duration_s": (300, 480),
        "load_ranges": {"DIG": (75, 95), "HAUL": (30, 50), "REVERSE": (40, 60), "DUMP": (15, 30)},
        "hyd_ranges_bar": {"DIG": (150, 210), "HAUL": (60, 110), "REVERSE": (70, 120), "DUMP": (90, 150)},
        "speed_kph": {"DIG": (0.5, 3.0), "HAUL": (6.0, 10.0), "REVERSE": (2.5, 5.0), "DUMP": (0.0, 0.8)},
        "rpm_norm": {"DIG": (0.72, 0.92), "HAUL": (0.62, 0.8), "REVERSE": (0.5, 0.7), "DUMP": (0.4, 0.55)},
        "planned_minutes": 240,
    },
    # Follow-on shift jobs share the EXCAVATION stage cycle in the sim; these
    # entries only carry the realistic planned duration for ETA / ML lookups
    # when the live task plan rolls over from EXCAVATION.
    "LOADING": {"planned_minutes": 150},
    "TRENCHING": {"planned_minutes": 200},
    "HAULING": {"planned_minutes": 185},
    "GRADING": {"planned_minutes": 210},
}