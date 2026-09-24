"""Offline telemetry corpus generator.

Builds a multi-session synthetic corpus (normal + all scenario arcs), streams
per-session parquet shards, then produces the combined dataset, leakage-safe
session splits, reports and the data dictionary.

CLI:    .venv/bin/python -m app.dataset.product --out ../data/phase2
Tests:  call :func:`generate_corpus` with ``mini=True``.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.dataset import reports, splits, tasks
from app.schemas.telemetry import ScenarioType, WeatherEvent
from app.simulation.generator import MachineGenerator
from app.simulation.scenarios import ScenarioSpec, make_spec

SESSION_SECONDS = 28800  # 8 h

# (scenario_type, severity, weather) recipes per machine/operator block
MX101_RECIPES: list[tuple[ScenarioType | None, float, WeatherEvent]] = [
    (None, 0.0, WeatherEvent.NONE),
    (ScenarioType.FUEL_LEAK, 0.4, WeatherEvent.NONE),
    (ScenarioType.FUEL_LEAK, 0.85, WeatherEvent.NONE),
    (ScenarioType.ENGINE_OVERHEAT, 0.5, WeatherEvent.NONE),
    (ScenarioType.HYDRAULIC_FAILURE, 0.5, WeatherEvent.RAIN),
    (ScenarioType.EXCESSIVE_IDLE, 0.7, WeatherEvent.NONE),
    (ScenarioType.UNSAFE_OPERATION, 0.65, WeatherEvent.NONE),
    (ScenarioType.SENSOR_FAILURE, 0.45, WeatherEvent.NONE),
    (ScenarioType.BATTERY_ANOMALY, 0.55, WeatherEvent.NONE),
    (ScenarioType.SEATBELT_VIOLATION, 0.6, WeatherEvent.NONE),
    (ScenarioType.MULTI_FACTOR_INCIDENT, 0.5, WeatherEvent.NONE),
]

MX102_RECIPES: list[tuple[ScenarioType | None, float, WeatherEvent]] = [
    (ScenarioType.NORMAL_OPERATION, 0.0, WeatherEvent.NONE),
    (ScenarioType.FUEL_LEAK, 0.6, WeatherEvent.RAIN),
    (ScenarioType.ENGINE_OVERHEAT, 0.85, WeatherEvent.HOT),
    (ScenarioType.HYDRAULIC_FAILURE, 0.8, WeatherEvent.NONE),
    (ScenarioType.EXCESSIVE_IDLE, 0.4, WeatherEvent.FOG),
    (ScenarioType.UNSAFE_OPERATION, 0.8, WeatherEvent.NONE),
    (ScenarioType.SENSOR_FAILURE, 0.3, WeatherEvent.NONE),
    (ScenarioType.SEATBELT_VIOLATION, 0.85, WeatherEvent.NONE),
    (ScenarioType.PROXIMITY_HAZARD, 0.8, WeatherEvent.NONE),
    (ScenarioType.BATTERY_ANOMALY, 0.55, WeatherEvent.NONE),
]

# Holdout machine (test-only): unseen configs
MX103_RECIPES: list[tuple[ScenarioType | None, float, WeatherEvent]] = [
    (ScenarioType.NORMAL_OPERATION, 0.0, WeatherEvent.NONE),
    (ScenarioType.NORMAL_OPERATION, 0.0, WeatherEvent.NONE),
    (ScenarioType.FUEL_LEAK, 0.9, WeatherEvent.HEAVY_RAIN),
    (ScenarioType.SENSOR_FAILURE, 0.8, WeatherEvent.NONE),
    (ScenarioType.MULTI_FACTOR_INCIDENT, 0.9, WeatherEvent.HOT),
    (ScenarioType.PROXIMITY_HAZARD, 0.4, WeatherEvent.NONE),
]

HOLDOUT_MACHINES = ("MX-103",)
UNSEEN_CONFIGS = ("SENSOR_FAILURE", "MULTI_FACTOR_INCIDENT", "PROXIMITY_HAZARD")


@dataclass
class SessionPlanEntry:
    machine_id: str
    operator_id: str
    seed: int
    start_time: datetime
    duration_s: float
    session_id: str
    recipe: tuple[Any, float, WeatherEvent]

    @property
    def scenario(self) -> ScenarioSpec | None:
        st, sev, weather = self.recipe
        if st is None or st is ScenarioType.NORMAL_OPERATION:
            return None
        onset = min(1200.0, int(self.duration_s * 0.35))
        dur = max(200.0, min(1500.0, int(self.duration_s * 0.55)))
        return make_spec(
            st, severity=sev, onset_offset_s=onset, ramp_s=25.0, duration_s=dur, abate_s=60.0, weather=weather
        )


def build_session_plan(seed: int, mini: bool = False) -> list[SessionPlanEntry]:
    base = ["MX-101", "MX-102", "MX-103"]
    block_minutes = [210, 300, 330]
    plan: list[SessionPlanEntry] = []
    recipes = {
        "MX-101": MX101_RECIPES,
        "MX-102": MX102_RECIPES,
        "MX-103": MX103_RECIPES,
    }
    i = 0
    for midx, machine in enumerate(base):
        op = {0: "OP-01", 1: "OP-02", 2: "OP-03"}[midx]
        day = 0
        for recipe in recipes[machine]:
            start = datetime(2026, 9, 1, 7, 0, 0, tzinfo=timezone.utc) + timedelta(days=day * 3 + midx)
            dur = SESSION_SECONDS if not mini else 720.0
            plan.append(
                SessionPlanEntry(
                    machine_id=machine,
                    operator_id=op,
                    seed=seed + i,
                    start_time=start,
                    duration_s=dur,
                    session_id=f"S-{machine}-{i:03d}",
                    recipe=recipe,
                )
            )
            day += 1
            i += 1
    return plan


def _run_session(entry: SessionPlanEntry) -> pd.DataFrame:
    gen = MachineGenerator(
        machine_id=entry.machine_id,
        operator_id=entry.operator_id,
        seed=entry.seed,
        session_id=entry.session_id,
        start_time=entry.start_time,
        scenario=entry.scenario,
    )
    rows: list[dict] = []
    for _ in range(int(entry.duration_s)):
        rows.append(gen.step().to_dict())
    df = pd.DataFrame(rows)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    return df


def generate_corpus(out_dir: str | Path, seed: int = 2026, mini: bool = False) -> dict[str, Any]:
    """Generate the full offline corpus + artifacts. Returns an output manifest."""
    out = Path(out_dir)
    (out / "sessions").mkdir(parents=True, exist_ok=True)
    (out / "splits").mkdir(parents=True, exist_ok=True)
    (out / "reports").mkdir(parents=True, exist_ok=True)

    plan = build_session_plan(seed, mini=mini)
    session_meta: dict[str, dict[str, Any]] = {}
    shards: list[pd.DataFrame] = []

    for entry in plan:
        df = _run_session(entry)
        st, sev, weather = entry.recipe
        st_name = None if st is None else st.value
        shard_path = out / "sessions" / f"{entry.session_id}.parquet"
        df.to_parquet(shard_path, index=False)
        shards.append(df)

        n_anom = int(df["anomaly_label"].sum()) if "anomaly_label" in df else 0
        session_meta[entry.session_id] = {
            "machine_id": entry.machine_id,
            "operator_id": entry.operator_id,
            "seed": entry.seed,
            "start_time": entry.start_time.isoformat(),
            "duration_s": int(entry.duration_s),
            "scenario": st_name,
            "severity": sev,
            "weather": weather.value,
            "n_frames": int(len(df)),
            "n_anomaly_frames": n_anom,
        }

    corpus = pd.concat(shards, ignore_index=True)
    corpus.to_parquet(out / "corpus.parquet", index=False)
    corpus.to_csv(out / "corpus.csv", index=False)

    # leakage-safe splits -------------------------------------------------
    result = splits.split_sessions(
        session_meta,
        seed=seed,
        holdout_machines=HOLDOUT_MACHINES,
        unseen_configs=UNSEEN_CONFIGS,
    )
    splits.save_manifest(out, session_meta, result)

    if "anomaly_label" in corpus.columns:
        split_labels = {s: g for g, ss in result.splits.items() for s in ss}
        corpus["split_id"] = corpus["session_id"].map(lambda s: split_labels.get(s, "unset"))
        for g in result.splits:
            part = corpus[corpus["split_id"] == g]
            part.to_parquet(out / "splits" / f"{g}.parquet", index=False)

    # task history (challenge-required columns + extras) -------------------
    task_history = tasks.generate_task_history(seed=seed)
    task_history.to_parquet(out / "task_history.parquet", index=False)
    task_history.to_csv(out / "task_history.csv", index=False)

    # reports + dictionary ----------------------------------------------------
    summary = reports.generate_reports(corpus, task_history, session_meta, result, out)
    dictionary = reports.data_dictionary(corpus.drop(columns=["split_id"]), task_history)
    reports.write_dictionary(out, dictionary)

    manifest = {
        "out_dir": str(out),
        "n_sessions": len(plan),
        "n_rows": int(len(corpus)),
        "n_anomaly_rows": int(corpus["anomaly_label"].sum(axis=0)) if "anomaly_label" in corpus else None,
        "n_machines": int(corpus["Machine_ID"].nunique()),
        "n_operators": int(corpus["Operator_ID"].nunique()),
        "scenario_counts": corpus["scenario_type"].value_counts().to_dict(),
        "task_rows": int(len(task_history)),
        "splits": result.splits,
        "leakage_audit": result.audit,
        "summary": str(out / "reports" / "summary.json"),
    }
    (out / "manifest.json").write_text(__import__("json").dumps(manifest, indent=2, default=str))
    return manifest


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Generate the Phase 2 offline corpus.")
    ap.add_argument("--out", default="../data/phase2")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--mini", action="store_true", help="tiny corpus for smoke/tests")
    args = ap.parse_args()
    m = generate_corpus(out_dir=args.out, seed=args.seed, mini=args.mini)
    print(f"corpus generated: sessions={m['n_sessions']} rows={m['n_rows']} tasks={m['task_rows']}")
    print(f"  anomaly rows = {m['n_anomaly_rows']}")
    print(f"  leak audit   = {m['leakage_audit']['no_session_leakage']} / strict={m['leakage_audit']['strict_no_feature_leakage']}")
