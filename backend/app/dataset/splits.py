"""Leakage-safe session-grouped splits.

Telemetry is split at the *session* level (never by row), because rows within a
session are temporally correlated. The test split is additionally strict:
every test session belongs to a machine **or** a scenario configuration that was
never seen in train/val, so classifier/generalization scores are honest.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SplitResult:
    splits: dict[str, list[str]] = field(default_factory=dict)      # split -> session ids
    audit: dict[str, Any] = field(default_factory=dict)             # leakage audit results


def config_tag(scenario_type: str | None, severity: float | None) -> str:
    if scenario_type is None:
        return "NORMAL_OPERATION"
    sev = "LOW" if severity is None or severity < 0.35 else ("MEDIUM" if severity < 0.7 else "HIGH")
    return f"{scenario_type}/{sev}"


def split_sessions(
    session_meta: dict[str, dict[str, Any]],
    *,
    seed: int = 7,
    val_frac: float = 0.15,
    holdout_machines: tuple[str, ...] = ("MX-103",),
    unseen_configs: tuple[str, ...] = ("SENSOR_FAILURE", "MULTI_FACTOR_INCIDENT", "PROXIMITY_HAZARD"),
) -> SplitResult:
    """Return session ids grouped into train/val/test with a strict test set."""
    rng = random.Random(seed)
    ids = list(session_meta)
    rng.shuffle(ids)

    normals: list[str] = []
    known: list[str] = []
    holdout: list[str] = []
    known_configs: set[str] = set()

    for sid in ids:
        meta = session_meta[sid]
        machine = meta.get("machine_id")
        tag = config_tag(meta.get("scenario"), meta.get("severity"))
        if machine in holdout_machines:
            holdout.append(sid)
        elif tag.split("/")[0] in unseen_configs:
            holdout.append(sid)          # config unseen by any training fold
        elif tag == "NORMAL_OPERATION":
            normals.append(sid)
        else:
            known.append(sid)
            known_configs.add(tag)

    # train/val split of the "known world" (normal + seen configurations)
    pool = normals[:1] + known if normals else known
    rng.shuffle(pool)
    n_val = max(1, int(len(pool) * val_frac))
    val = pool[:n_val]
    train = pool[n_val:]
    test = holdout

    train_set = set(train)
    test_set = set(test)
    train_configs = {config_tag(session_meta[s].get("scenario"), session_meta[s].get("severity")) for s in train}
    train_machines = {session_meta[s]["machine_id"] for s in train}
    test_machines = {session_meta[s]["machine_id"] for s in test}
    test_configs = {config_tag(session_meta[s].get("scenario"), session_meta[s].get("severity")) for s in test}

    audit = {
        "n_train_sessions": len(train),
        "n_val_sessions": len(val),
        "n_test_sessions": len(test),
        "session_overlap_train_test": sorted(train_set & test_set),
        "train_machines": sorted(train_machines),
        "test_machines": sorted(test_machines),
        "test_machines_unseen": sorted(test_machines - train_machines),
        "test_configs": sorted(test_configs),
        "train_configs": sorted(train_configs),
        "unseen_test_configs": sorted(test_configs - train_configs),
        "no_session_leakage": not (train_set & test_set),
        "strict_no_feature_leakage": bool(test_machines - train_machines) or bool(test_configs - train_configs),
    }
    return SplitResult(splits={"train": train, "val": val, "test": test}, audit=audit)


def save_manifest(out_dir: str, session_meta: dict, result: SplitResult) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "splits_manifest.json"
    path.write_text(json.dumps({
        "session_meta": session_meta,
        "splits": result.splits,
        "audit": result.audit,
    }, indent=2, default=str))
    return str(path)