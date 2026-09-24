"""Corpus reports + data dictionary writers (Phase 2)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from app.schemas.telemetry import REQUIRED_COLUMNS
from app.dataset.tasks import REQUIRED_TASK_COLUMNS

# field name -> {source, desc, unit, values?}
_FIELD_META: dict[str, Any] = {
    "Timestamp": dict(source="TelemetryFrame.timestamp", unit="ISO8601 UTC", desc="Observation time of the frame."),
    "Machine_ID": dict(source="TelemetryFrame.machine_id", desc="Asset identifier (synthetic fleet)."),
    "Operator_ID": dict(source="TelemetryFrame.operator_id", desc="Operator identifier."),
    "Engine_Hours": dict(source="TelemetryFrame.engine_hours", unit="h", desc="Cumulative engine hours."),
    "Fuel_Used_L": dict(source="TelemetryFrame.fuel_used_l", unit="L", desc="Cumulative liters consumed this session (not leaked)."),
    "Load_Cycles": dict(source="TelemetryFrame.load_cycles", unit="cycles", desc="Completed work cycles."),
    "Idling_Time_min": dict(source="TelemetryFrame.idling_time_min", unit="min", desc="Rolling idle minutes (resets on motion)."),
    "Seatbelt_Status": dict(source="TelemetryFrame.seatbelt_status", values="Fastened|Unfastened", desc="Seatbelt sensor state."),
    "Safety_Alert_Triggered": dict(source="TelemetryFrame.safety_alert_triggered", desc="Machine-level safety alert flag."),
    "session_id": dict(source="TelemetryFrame.session_id", desc="Session grouping key (split unit)."),
    "task_id": dict(source="TelemetryFrame.task_id", desc="Linked task id."),
    "current_task_type": dict(source="TelemetryFrame.current_task_type", desc="Task being performed."),
    "fuel_level_pct": dict(source="TelemetryFrame.fuel_level_pct", unit="%", desc="Observed tank level (may be sensor-biased)."),
    "fuel_consumption_rate_lph": dict(source="TelemetryFrame.fuel_consumption_rate_lph", unit="L/h", desc="Reported consumption rate."),
    "engine_rpm": dict(source="TelemetryFrame.engine_rpm", unit="rpm", desc="Engine speed."),
    "engine_temperature_c": dict(source="TelemetryFrame.engine_temperature_c", unit="C", desc="Engine temperature (observed)."),
    "coolant_temperature_c": dict(source="TelemetryFrame.coolant_temperature_c", unit="C", desc="Coolant temperature."),
    "oil_pressure_kpa": dict(source="TelemetryFrame.oil_pressure_kpa", unit="kPa", desc="Engine oil pressure."),
    "hydraulic_pressure_bar": dict(source="TelemetryFrame.hydraulic_pressure_bar", unit="bar", desc="Hydraulic system pressure."),
    "hydraulic_temperature_c": dict(source="TelemetryFrame.hydraulic_temperature_c", unit="C", desc="Hydraulic oil temperature."),
    "battery_voltage_v": dict(source="TelemetryFrame.battery_voltage_v", unit="V", desc="Electrical system voltage."),
    "engine_load_pct": dict(source="TelemetryFrame.engine_load_pct", unit="%", desc="Engine load."),
    "machine_speed_kph": dict(source="TelemetryFrame.machine_speed_kph", unit="km/h", desc="Ground speed."),
    "vibration_g": dict(source="TelemetryFrame.vibration_g", unit="g", desc="Chassis vibration."),
    "proximity_distance_m": dict(source="TelemetryFrame.proximity_distance_m", unit="m", desc="Distance to nearest object/asset."),
    "operating_hours": dict(source="TelemetryFrame.operating_hours", unit="h", desc="Cumulative operating hours."),
    "latitude": dict(source="TelemetryFrame.latitude", desc="Work-zone loop latitude (synthetic)."),
    "longitude": dict(source="TelemetryFrame.longitude", desc="Work-zone loop longitude (synthetic)."),
    "ambient_temperature_c": dict(source="TelemetryFrame.ambient_temperature_c", unit="C", desc="Ambient temperature."),
    "humidity_pct": dict(source="TelemetryFrame.humidity_pct", unit="%", desc="Relative humidity."),
    "rainfall_mmh": dict(source="TelemetryFrame.rainfall_mmh", unit="mm/h", desc="Rainfall intensity."),
    "visibility_m": dict(source="TelemetryFrame.visibility_m", unit="m", desc="Visibility."),
    "terrain_type": dict(source="TelemetryFrame.terrain_type", desc="Site terrain type."),
    "terrain_condition": dict(source="TelemetryFrame.terrain_condition", desc="Site terrain condition (affected by weather)."),
    "slope_deg": dict(source="TelemetryFrame.slope_deg", unit="deg", desc="Work area slope."),
    "work_zone": dict(source="TelemetryFrame.work_zone", desc="Site zone."),
    "nearby_machine_count": dict(source="TelemetryFrame.nearby_machine_count", desc="Nearby assets."),
    "weather_event": dict(source="TelemetryFrame.weather_event", desc="Active weather event."),
    "machine_state": dict(source="TelemetryFrame.machine_state", values="ACTIVE|IDLE|BREAK|REVERSING|...", desc="Raw machine state."),
    "task_progress_pct": dict(source="TelemetryFrame.task_progress_pct", unit="%", desc="Task progress estimate."),
    "efficiency": dict(source="TelemetryFrame.efficiency", desc="Operator cycle efficiency factor."),
    "aggression_index": dict(source="TelemetryFrame.aggression_index", desc="Operator input harshness."),
    "compliance": dict(source="TelemetryFrame.compliance", desc="Procedure adherence."),
    "cooling_performance_pct": dict(source="TelemetryFrame.cooling_performance_pct", unit="%", desc="Cooling system effectiveness."),
    "diagnostics_consistency": dict(source="TelemetryFrame.diagnostics_consistency", unit="0..1", desc="Cross-signal consistency; <1 flags sensor/cross-check anomalies."),
    "scenario_type": dict(source="ground_truth", values="NORMAL_OPERATION|FUEL_LEAK|...", desc="EVAL ONLY: injected incident type."),
    "phase": dict(source="ground_truth", values="NORMAL|ONSET|ANOMALY|RESPONSE|RESOLVED", desc="EVAL ONLY: incident lifecycle phase."),
    "anomaly_label": dict(source="ground_truth", desc="EVAL ONLY: True during ONSET/ANOMALY/RESPONSE."),
    "incident_type": dict(source="ground_truth", desc="EVAL ONLY: incident class during anomaly windows."),
    "incident_severity": dict(source="ground_truth", values="LOW|MEDIUM|HIGH", desc="EVAL ONLY: severity bucket."),
    "anomaly_onset_t": dict(source="ground_truth", unit="ISO8601 UTC", desc="EVAL ONLY: injected onset time."),
    "detect_t": dict(source="ground_truth", desc="EVAL ONLY: engine detection time (populated in Phase 3)."),
    "resolve_t": dict(source="ground_truth", unit="ISO8601 UTC", desc="EVAL ONLY: injected resolution time."),
    "refuel_event": dict(source="ground_truth", desc="EVAL ONLY: refuel event flag."),
    "scenario_params": dict(source="ground_truth", desc="EVAL ONLY: injected details."),
    "split_id": dict(source="evaluation", values="train|val|test", desc="Session-grouped split label."),
    # ------- task table columns ---------------------------------------------
    "Task_ID": dict(source="Task dataset", desc="Task identifier."),
    "Task_Type": dict(source="Task dataset", values="EXCAVATION|LOADING|HAULING|GRADING|COMPACTING|LIFTING|TRENCHING", desc="Type of work."),
    "Weather": dict(source="Task dataset", values="NONE|RAIN|HEAVY_RAIN|FOG|HOT|HIGH_WIND", desc="Weather during the task."),
    "Operator_Skill": dict(source="Task dataset", values="EXPERT|INTERMEDIATE|BEGINNER", desc="Operator skill band."),
    "Machine_Age_yrs": dict(source="Task dataset", unit="yr", desc="Machine age (synthetic)."),
    "Estimated_Time_min": dict(source="Task dataset", unit="min", desc="Planned duration (drawn before task)."),
    "Actual_Time_min": dict(source="Task dataset", unit="min", desc="Realized duration (causal outcome)."),
    "Task_Zone": dict(source="Task dataset", desc="Work zone."),
    "Task_Priority": dict(source="Task dataset", values="LOW|MEDIUM|HIGH|CRITICAL", desc="Priority."),
    "Material_Type": dict(source="Task dataset", desc="Material being handled."),
    "Terrain_Condition": dict(source="Task dataset", desc="Terrain condition."),
    "Ambient_Temp_C": dict(source="Task dataset", unit="C", desc="Ambient temperature."),
    "Rainfall_mmh": dict(source="Task dataset", unit="mm/h", desc="Rainfall."),
    "Visibility_m": dict(source="Task dataset", unit="m", desc="Visibility."),
    "Shift": dict(source="Task dataset", values="DAY|NIGHT", desc="Shift."),
    "Required_Equipment": dict(source="Task dataset", desc="Equipment required."),
    "Reference_Time_min": dict(source="Task dataset", unit="min", desc="Typical duration for the conditions (weather-normalized)."),
    "Delay_Reason": dict(source="Task dataset", desc="Dominant delay cause (causal rule)."),
    "Efficiency_Factor": dict(source="Task dataset", desc="Actual/Reference - schedule adherence."),
}


def _dtype_name(col: str, pdf: pd.DataFrame) -> str:
    if pdf[col].dtype.kind in "if":
        return "numeric"
    if pdf[col].dtype.kind in "b":
        return "boolean"
    if pdf[col].dtype.kind == "M":
        return "datetime"
    return "categorical/string"


def generate_reports(
    df: pd.DataFrame,
    task_df: pd.DataFrame,
    session_meta: dict[str, Any],
    split_result: Any,
    out: Path,
) -> dict[str, Any]:
    reports_dir = out / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # class balance (scenario × phase)
    if "anomaly_label" in df.columns:
        bal = (
            df.groupby(["scenario_type", "phase", "anomaly_label"], dropna=False)
            .size()
            .reset_index(name="n_rows")
        )
        bal.to_csv(reports_dir / "class_balance.csv", index=False)

        scen = (
            df[df["anomaly_label"]]
            .groupby(["incident_type", "incident_severity"], dropna=False)
            .size()
            .reset_index(name="n_anomaly_rows")
            .rename(columns={"incident_type": "scenario_type"})
        )
        scen.to_csv(reports_dir / "scenario_counts.csv", index=False)

    # missing values
    miss = df.isna()
    missing = pd.DataFrame(
        {
            "column": df.columns,
            "missing_n": miss.sum().astype(int).values,
            "missing_pct": miss.mean().round(3).values,
        }
    ).query("missing_n > 0")
    missing.to_csv(reports_dir / "missing.csv", index=False)

    # correlations (normal vs anomalous) for numeric cols
    num_cols = df.select_dtypes(include="number").columns.tolist()
    norm = df[df.get("anomaly_label", pd.Series(index=df.index)) == False][num_cols] if "anomaly_label" in df.columns else df[num_cols]
    anom = df[df.get("anomaly_label", pd.Series(index=df.index)) == True][num_cols] if "anomaly_label" in df.columns else df[num_cols]
    corr_rows: list[dict] = []
    for subset, label in ((norm, "normal"), (anom, "anomaly")):
        if len(subset) > 1:
            c = subset.corr().abs().unstack().reset_index()
            c.columns = ["colA", "colB", "corr_abs"]
            c = c[c["colA"] != c["colB"]].sort_values("corr_abs", ascending=False).head(25)
            c["window"] = label
            corr_rows.append(c)
    if corr_rows:
        pd.concat(corr_rows).to_csv(reports_dir / "correlations.csv", index=False)

    # task report
    task_summary = {
        "n_tasks": int(len(task_df)),
        "mean_estimated_min": float(task_df["Estimated_Time_min"].mean()),
        "mean_actual_min": float(task_df["Actual_Time_min"].mean()),
        "pct_over_estimate": float((task_df["Actual_Time_min"] > task_df["Estimated_Time_min"]).mean() * 100.0),
        "mean_efficiency_factor": float(task_df["Efficiency_Factor"].mean()),
        "delay_reason_counts": task_df["Delay_Reason"].value_counts().to_dict(),
        "task_type_counts": task_df["Task_Type"].value_counts().to_dict(),
    }

    summary = {
        "n_rows": int(len(df)),
        "n_sessions": len(session_meta),
        "n_machines": int(df["Machine_ID"].nunique()),
        "n_operators": int(df["Operator_ID"].nunique()),
        "n_columns": int(df.shape[1]),
        "rows_per_second_hz": 1.0,
        "anomaly_row_fraction": float(df["anomaly_label"].mean()) if "anomaly_label" in df.columns else None,
        "scenario_phase_distribution": (
            df.groupby(["scenario_type", "phase"], dropna=False).size()
            .reset_index()
            .assign(k=lambda r: r["scenario_type"].astype(str) + "|" + r["phase"].astype(str))
            .set_index("k")[0].to_dict()
            if "phase" in df.columns else {}
        ),
        "task": task_summary,
        "splits_audit": getattr(split_result, "audit", {}),
    }
    (reports_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    return summary


def data_dictionary(df: pd.DataFrame, task_df: pd.DataFrame) -> list[dict[str, Any]]:
    out_rows: list[dict[str, Any]] = []
    for col in df.columns:
        meta = _FIELD_META.get(col, {})
        out_rows.append({
            "name": col,
            "challenge_required": col in REQUIRED_COLUMNS,
            "dtype": _dtype_name(col, df),
            "source": meta.get("source", "telemetry"),
            "unit": meta.get("unit"),
            "values": meta.get("values"),
            "description": meta.get("desc", ""),
            "ground_truth_only": "ground_truth" in meta.get("source", ""),
            "in_required_challenge_schema": col in REQUIRED_COLUMNS,
        })
    for col in REQUIRED_TASK_COLUMNS + (
        [c for c in task_df.columns if c not in REQUIRED_TASK_COLUMNS]
    ):
        meta = _FIELD_META.get(col, {})
        out_rows.append({
            "name": col,
            "challenge_required": col in REQUIRED_TASK_COLUMNS,
            "dtype": _dtype_name(col, task_df),
            "source": meta.get("source", "task"),
            "unit": meta.get("unit"),
            "values": meta.get("values"),
            "description": meta.get("desc", ""),
            "ground_truth_only": False,
            "in_required_challenge_schema": col in REQUIRED_TASK_COLUMNS,
        })
    return out_rows


def write_dictionary(out: Path, dictionary: list[dict[str, Any]]) -> None:
    (out / "data_dictionary.json").write_text(json.dumps(dictionary, indent=2, default=str))
    lines = ["# CAT Smart Operator Assistant — Data Dictionary\n", "",
             "> This is a SYNTHETIC dataset. Nothing in it is real Caterpillar hardware data.\n", ""]
    lines.append("| column | challenge-required | dtype | source | unit | values | description |")
    lines.append("|---|---|---|---|---|---|---|")
    for d in dictionary:
        lines.append(
            f"| {d['name']} | {'yes' if d['challenge_required'] else ''} | {d['dtype']} | "
            f"{d['source']} | {d.get('unit') or ''} | {d.get('values') or ''} | {d['description']} |"
        )
    (out / "data_dictionary.md").write_text("\n".join(lines))

    docs = Path(out) / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    schema_md = f"""# Task Dataset Schema

Two schemas are preserved VERBATIM from the challenge.

## 1 · Required telemetry columns (in `corpus.parquet`)

    {', '.join(REQUIRED_COLUMNS)}

## 2 · Required task-dataset columns (in `task_history.parquet`)

    {', '.join(REQUIRED_TASK_COLUMNS)}

All other columns are our additive, documented extension columns (see
`data_dictionary.md`). Every `ground_truth` column is evaluation metadata for a
software simulation — it is never claimed to be real machine data.
"""
    (docs / "task_dataset_schema.md").write_text(schema_md)