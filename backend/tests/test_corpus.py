"""End-to-end corpus pipeline integration (mini corpus in tmp dir)."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from app.dataset import corpus
from app.dataset.tasks import REQUIRED_TASK_COLUMNS
from app.schemas.telemetry import REQUIRED_COLUMNS


@pytest.fixture(scope="module")
def mini(tmp_path_factory):
    out = tmp_path_factory.mktemp("corpus")
    m = corpus.generate_corpus(out, seed=11, mini=True)
    return out, m


def test_manifest_and_artifacts(mini):
    out, m = mini
    assert m["n_sessions"] > 10
    assert m["n_rows"] >= 10_000
    assert m["n_anomaly_rows"] > 1000
    for p in ["corpus.parquet", "corpus.csv", "task_history.parquet", "task_history.csv",
              "splits_manifest.json", "manifest.json", "data_dictionary.json", "data_dictionary.md"]:
        assert (out / p).exists(), p


def test_required_columns_in_corpus(mini):
    out, _ = mini
    df = pd.read_parquet(out / "corpus.parquet")
    for col in REQUIRED_COLUMNS:
        assert col in df.columns, col
    assert df["anomaly_label"].sum() > 1000


def test_task_required_columns(mini):
    out, _ = mini
    tf = pd.read_parquet(out / "task_history.parquet")
    for col in REQUIRED_TASK_COLUMNS:
        assert col in tf.columns, col


def test_splits_session_grouped_disjoint(mini):
    out, m = mini
    audit = m["leakage_audit"]
    assert audit["no_session_leakage"] is True
    assert audit["strict_no_feature_leakage"] is True
    assert audit["test_machines_unseen"], "holdout machine must be fully unseen"
    assert audit["unseen_test_configs"], "some scenario configs must be test-only"

    manifest = json.loads((out / "splits_manifest.json").read_text())
    train = set(manifest["splits"]["train"])
    test = set(manifest["splits"]["test"])
    val = set(manifest["splits"]["val"])
    assert not (train & test | train & val | val & test)

    for split in ("train", "val", "test"):
        part = pd.read_parquet(out / "splits" / f"{split}.parquet")
        assert not part.empty
        assert part["anomaly_label"].sum() >= 0


def test_reports_and_dictionary(mini):
    out, _ = mini
    rep = json.loads((out / "reports" / "summary.json").read_text())
    assert "n_rows" in rep and rep["n_rows"] > 0
    assert (out / "reports" / "class_balance.csv").exists()
    dd = json.loads((out / "data_dictionary.json").read_text())
    names = {d["name"] for d in dd}
    for col in REQUIRED_COLUMNS:
        assert col in names
    docs = (out / "docs" / "task_dataset_schema.md")
    assert docs.exists() and "Required telemetry columns" in docs.read_text()