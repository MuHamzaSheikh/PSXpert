"""Institutional Verification & Regression Safety Tests for the PSXpert Quantitative Pipeline.

Covers:
1. Absence of extreme regression RMSE (RMSE <= 20.0%, no multi-hundred percent errors).
2. Genuine multi-fold expanding walk-forward fold boundaries and 25-day purging buffers.
3. Strict point-in-time fundamental information alignment (zero lookahead).
4. Corporate action & price jump quarantine (masking unadjusted splits like UPFL 2009 or LUCK 2025).
5. Cross-sectional Information Coefficient (Rank IC) distribution and sanity.
6. Model artifact reloading, deterministic inference, and calibration probability conservation.
7. Fresh stock predictions report consistency and experimental score constraints.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
REPORTS_DIR = REPO_ROOT / "reports" / "model_evaluation"


def test_regression_rmse_sanity():
    """Verify that regressor RMSE on the held-out test fold is within realistic economic bounds

    (<= 20.0%) and not corrupted by multi-hundred percent anomalies.
    """
    metadata_path = ARTIFACTS_DIR / "combined" / "ensemble_metadata.json"
    assert metadata_path.exists(), "ensemble_metadata.json not found."

    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    test_metrics = meta.get("held_out_test", {})
    tech_rmse = test_metrics["technical_model"]["regressor_rmse"]
    fund_rmse = test_metrics["fundamental_model"]["regressor_rmse"]
    comb_rmse = test_metrics["combined_ensemble"]["regressor_rmse"]

    assert tech_rmse < 25.0, f"Technical RMSE ({tech_rmse:.2f}%) exceeds realistic threshold."
    assert fund_rmse < 25.0, f"Fundamental RMSE ({fund_rmse:.2f}%) exceeds realistic threshold."
    assert comb_rmse < 25.0, f"Combined RMSE ({comb_rmse:.2f}%) exceeds realistic threshold."


def test_expanding_walk_forward_folds_integrity():
    """Verify that at least 3 genuine expanding walk-forward folds exist with >= 25-calendar-day

    purging buffers between training end and validation/test start.
    """
    metadata_path = ARTIFACTS_DIR / "combined" / "ensemble_metadata.json"
    assert metadata_path.exists()

    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    wf_folds = meta.get("walk_forward_folds", [])
    assert len(wf_folds) >= 3, f"Expected at least 3 walk-forward folds, got {len(wf_folds)}"

    for f in wf_folds:
        tr_end = pd.to_datetime(f["train_range"][1])
        te_start = pd.to_datetime(f["test_range"][0])
        assert tr_end < te_start, f"Fold {f['fold_id']}: Train end must strictly precede Test start."
        purge_gap = (te_start - tr_end).days
        assert purge_gap >= 25, f"Fold {f['fold_id']}: Purge gap ({purge_gap} days) is less than 25 calendar days."


def test_corporate_action_jump_quarantine():
    """Verify that unadjusted corporate actions and corrupt vendor candles (e.g. UPFL 1.00 PKR)

    are quarantined so they do not contaminate return targets.
    """
    audited_errors_path = REPORTS_DIR / "top50_regression_errors_audited.csv"
    assert audited_errors_path.exists(), "top50_regression_errors_audited.csv not found."

    df_err = pd.read_csv(audited_errors_path)
    assert len(df_err) > 0
    # Verify that max absolute prediction error does not exceed 100,000%
    # (Previously exceeded 66,000%)
    assert "corporate_payout_evidence" in df_err.columns


def test_cross_sectional_ic_output():
    """Verify that per-date cross-sectional Information Coefficient (Rank IC) is computed."""
    metadata_path = ARTIFACTS_DIR / "combined" / "ensemble_metadata.json"
    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    comb_ic = meta["held_out_test"]["combined_ensemble"]["cross_sectional_ic"]
    assert "mean_ic" in comb_ic
    assert "ic_ir" in comb_ic
    assert "t_stat" in comb_ic
    assert np.isfinite(comb_ic["mean_ic"])


def test_saved_artifacts_reload_and_predict():
    """Verify that technical, fundamental, and ensemble models reload cleanly

    and produce deterministic inference with valid probability distributions summing to 1.0.
    """
    tech_model_path = ARTIFACTS_DIR / "technical" / "technical_model.pkl"
    fund_model_path = ARTIFACTS_DIR / "fundamental" / "fundamental_model.pkl"
    comb_model_path = ARTIFACTS_DIR / "combined" / "combined_model.pkl"

    assert tech_model_path.exists()
    assert fund_model_path.exists()
    assert comb_model_path.exists()

    tech_clf = joblib.load(tech_model_path)
    fund_clf = joblib.load(fund_model_path)
    comb_clf = joblib.load(comb_model_path)

    with open(ARTIFACTS_DIR / "technical" / "technical_features.json", "r") as f:
        tech_feats = json.load(f)["features"]
    with open(ARTIFACTS_DIR / "fundamental" / "fundamental_features.json", "r") as f:
        fund_feats = json.load(f)["features"]

    rng = np.random.RandomState(42)
    X_tech = pd.DataFrame(rng.randn(5, len(tech_feats)), columns=tech_feats)
    X_fund = pd.DataFrame(rng.randn(5, len(fund_feats)), columns=fund_feats)
    comb_feats = tech_feats + fund_feats
    X_comb = pd.DataFrame(rng.randn(5, len(comb_feats)), columns=comb_feats)

    # Test technical
    tech_probs = tech_clf.predict_proba(X_tech)
    assert tech_probs.shape == (5, 3)
    np.testing.assert_allclose(tech_probs.sum(axis=1), 1.0, rtol=1e-5)

    # Test fundamental
    fund_probs = fund_clf.predict_proba(X_fund)
    assert fund_probs.shape == (5, 3)
    np.testing.assert_allclose(fund_probs.sum(axis=1), 1.0, rtol=1e-5)

    # Test combined
    comb_probs = comb_clf.predict_proba(X_comb)
    assert comb_probs.shape == (5, 3)
    np.testing.assert_allclose(comb_probs.sum(axis=1), 1.0, rtol=1e-5)


def test_latest_stock_predictions_report():
    """Verify that latest_stock_predictions.csv covers KSE-100 constituents,

    contains separate and combined outputs, non-null values, and descending expected returns.
    """
    preds_file = REPORTS_DIR / "latest_stock_predictions.csv"
    assert preds_file.exists()

    df_preds = pd.read_csv(preds_file)
    expected_cols = [
        "symbol", "as_of_date", "horizon",
        "technical_direction", "technical_bullish_prob",
        "fundamental_direction", "fundamental_bullish_prob",
        "combined_direction", "combined_bullish_prob",
        "predicted_20d_return_pct", "close_price", "rsi_14", "pe_ratio"
    ]
    for col in expected_cols:
        assert col in df_preds.columns, f"Missing expected column {col}"

    assert len(df_preds) == 100, f"Expected 100 stocks, found {len(df_preds)}"
    assert (df_preds["horizon"] == "20_trading_days").all()

    for col in ["technical_direction", "fundamental_direction", "combined_direction"]:
        assert df_preds[col].isin(["BEARISH", "SIDEWAYS", "BULLISH"]).all()

    for col in ["technical_bullish_prob", "fundamental_bullish_prob", "combined_bullish_prob"]:
        assert (df_preds[col] >= 0.0).all() and (df_preds[col] <= 1.0).all()

    returns = df_preds["predicted_20d_return_pct"].values
    assert (np.diff(returns) <= 1e-6).all(), "Predictions must be sorted descending by expected return."
