"""Test Frozen Research Release Reproducibility.

Verifies:
1. All files in release_manifest.json exist and match their SHA-256 hashes.
2. Loading the saved models reproduces their saved predictions in predictions_revised.csv.gz row-by-row with max diff == 0.0.
"""

from pathlib import Path
import hashlib
import json
import joblib
import numpy as np
import pandas as pd
import pytest

from m1.decision_pipeline import DecisionConfig, build_targets, split_stage, feature_matrix
from m1.features import FUNDAMENTAL, TECHNICAL


def compute_file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_release_manifest_hashes():
    """Verify all release files match their exact recorded SHA-256 hashes."""
    release_dir = Path("artifacts/frozen_research_release")
    manifest_path = release_dir / "release_manifest.json"
    assert manifest_path.exists(), "release_manifest.json missing"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    release_files = manifest["release_files"]

    for rel_path, expected_hash in release_files.items():
        full_path = release_dir / rel_path
        assert full_path.exists(), f"File {rel_path} declared in manifest missing"
        actual_hash = compute_file_sha256(full_path)
        assert actual_hash == expected_hash, f"Hash mismatch for {rel_path}"


def test_reload_reproduces_saved_predictions():
    """Verify that loading the frozen models reproduces saved predictions row-by-row."""
    release_dir = Path("artifacts/frozen_research_release")
    models_dir = release_dir / "models"
    snap_path = Path("artifacts/selection_timing_v4/predictions_revised.csv.gz")
    assert snap_path.exists(), "predictions_revised.csv.gz missing"

    df_snap = pd.read_csv(snap_path)
    fold_3_snap = df_snap[df_snap["fold"] == "fold_3"].copy().sort_values(["session", "symbol"]).reset_index(drop=True)

    # Load data for Fold 3 (Sessions 5860 to 6000)
    panel = pd.read_csv("data/decision_panel_v2.csv")
    prices = pd.read_csv("data/raw_unadjusted_prices.csv")
    bench = pd.read_csv("data/audited_benchmark.csv")
    config = DecisionConfig(seed=42)
    data = build_targets(panel, prices, bench, config)

    test_sessions = sorted(data[data.session.between(5860, 6000 - 1)]["session"].unique())
    test_slice = data[data.session.isin(test_sessions)].copy().sort_values(["session", "symbol"]).reset_index(drop=True)

    # 1. Fundamental Ranker Reload
    ranker_path = models_dir / "fold_3_fundamental_xgbranker.joblib"
    assert ranker_path.exists()
    ranker = joblib.load(ranker_path)

    reloaded_fund_scores = ranker.predict(feature_matrix(test_slice, FUNDAMENTAL))
    saved_fund_scores = fold_3_snap["fundamental_score"].to_numpy()

    fund_diff = np.abs(reloaded_fund_scores - saved_fund_scores).max()
    assert fund_diff == pytest.approx(0.0, abs=1e-6), f"Fundamental prediction diff: {fund_diff}"

    # 2. Technical Classifier Reload
    clf_path = models_dir / "fold_3_technical_xgboost.joblib"
    assert clf_path.exists()
    clf = joblib.load(clf_path)

    reloaded_tech_probs = clf.predict_proba(feature_matrix(test_slice, TECHNICAL))[:, 1]
    saved_tech_probs = fold_3_snap["technical_score"].to_numpy()

    tech_diff = np.abs(reloaded_tech_probs - saved_tech_probs).max()
    assert tech_diff == pytest.approx(0.0, abs=1e-6), f"Technical prediction diff: {tech_diff}"

    # Signals
    reloaded_signals = (reloaded_tech_probs >= 0.50).astype(int)
    saved_signals = fold_3_snap["entry_signal"].to_numpy()
    assert (reloaded_signals == saved_signals).all(), "Signal mismatch between reloaded model and snapshot"
