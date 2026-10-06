"""DEMO threshold bands shared by the simulator, detectors, and evaluations.

All values are synthetic tuning parameters for a software simulation of a
generic heavy machine - NOT real-world manufacturer specifications.
"""
from __future__ import annotations

# --- fuel ------------------------------------------------------------------
FUEL_CRITICAL_PCT = 18.0
FUEL_LOW_PCT = 30.0

# --- thermal ---------------------------------------------------------------
ENGINE_TEMP_WARN_C = 98.0
ENGINE_TEMP_HIGH_C = 108.0
COOLANT_TEMP_WARN_C = 102.0

# --- hydraulics --------------------------------------------------------------
HYD_PRESSURE_MIN_BAR = 60.0       # min working pressure while engaged
HYD_PRESSURE_SAG_BAR = 90.0       # strong sag indicator (vs DIG-range baseline)
HYD_TEMP_WARN_C = 62.0

# --- electrical --------------------------------------------------------------
BATTERY_LOW_V = 22.0

# --- safety -------------------------------------------------------------------
PROXIMITY_UNSAFE_M = 8.0
PROXIMITY_DANGER_M = 4.0
IDLE_EXCESS_S = 240.0             # sustained idle beyond this is excessive
SPEED_REF_KPH = 12.0              # in-zone operating reference

# --- vibration / sensor -------------------------------------------------------
VIBRATION_HIGH_G = 0.9
DIAG_CONSISTENCY_LOW = 0.87       # below this: sensor/cross-check anomaly

# --- severity buckets ----------------------------------------------------------
def severity_bucket(severity: float) -> str:
    if severity < 0.35:
        return "LOW"
    if severity < 0.7:
        return "MEDIUM"
    return "HIGH"