"""Task-dataset causality tests (Phase 2)."""
from __future__ import annotations

import pandas as pd
import pytest

from app.dataset import tasks

ATTRS = ["Task_ID", "Task_Type", "Weather", "Operator_Skill", "Machine_Age_yrs",
         "Estimated_Time_min", "Actual_Time_min"]


def test_required_columns_present_verbatim():
    df = tasks.generate_task_history(seed=7, n_days=5)
    for col in ATTRS:
        assert col in df.columns, col
    extras = ["Task_Zone", "Task_Priority", "Material_Type", "Terrain_Condition",
              "Ambient_Temp_C", "Rainfall_mmh", "Visibility_m", "Shift",
              "Required_Equipment", "Machine_ID", "Operator_ID", "Scheduled_Start_Time",
              "Reference_Time_min", "Delay_Reason", "Efficiency_Factor"]
    for col in extras:
        assert col in df.columns, col
    assert df[ATTRS].notna().all().all()


def test_dtypes_and_valid_domains():
    df = tasks.generate_task_history(seed=7, n_days=5)
    assert (df["Actual_Time_min"] > 0).all()
    assert (df["Estimated_Time_min"] > 0).all()
    assert (df["Estimated_Time_min"] / df["Actual_Time_min"]).between(0.5, 2.0).all()
    assert set(df["Weather"]) <= {"NONE", "RAIN", "HEAVY_RAIN", "FOG", "HOT", "HIGH_WIND"}
    assert set(df["Operator_Skill"]) <= {"EXPERT", "INTERMEDIATE", "BEGINNER"}
    assert set(df["Task_Type"]) <= set(tasks.TASK_TYPES)


def test_causal_structure_actual_tracks_reference():
    df = tasks.generate_task_history(seed=7, n_days=30)
    corr = df[["Actual_Time_min", "Reference_Time_min"]].corr().iloc[0, 1]
    assert corr > 0.85
    eff = df["Efficiency_Factor"]
    assert (eff > 0.5).all() and (eff < 2.0).all()
    # weather delays dominate the slowest tasks
    heavy = df[df["Weather"] != "NONE"]
    assert heavy["Efficiency_Factor"].mean() > df["Efficiency_Factor"].mean()
    # delay reasons are the rule we encoded
    assert set(df["Delay_Reason"]) >= {"NONE", "WEATHER"}


def test_planning_estimate_independent_of_realized_noise():
    df = tasks.generate_task_history(seed=7, n_days=20)
    df2 = df.assign(est_bias=(df["Estimated_Time_min"] / df["Reference_Time_min"]) - 1.0)
    assert df2["est_bias"].between(-0.25, 0.3).all()


def test_task_generation_deterministic():
    a = tasks.generate_task_history(seed=1234, n_days=4)
    b = tasks.generate_task_history(seed=1234, n_days=4)
    c = tasks.generate_task_history(seed=4321, n_days=4)
    pd.testing.assert_frame_equal(a, b)
    assert not a.equals(c)


def test_machine_age_reflects_catalog():
    from app.simulation.catalog import MACHINES
    df = tasks.generate_task_history(seed=7, n_days=6)
    for mid, config in MACHINES.items():
        sub = df[df["Machine_ID"] == mid]
        assert (sub["Machine_Age_yrs"] == round(config.age_years, 1)).all(), mid
