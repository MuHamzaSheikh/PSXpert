"""Unit, artifact verification, startup caching, safety, and FastAPI endpoint tests for PSXpert ML models."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import app as app_mod
import src.ml.router as ml_router
from config.paths import (
    FUNDAMENTAL_ARTIFACTS_DIR,
    PREDICTIVE_DATA_DIR,
    TECHNICAL_ARTIFACTS_DIR,
)
from src.analysis.common import load_clean_symbol_prices, load_trading_calendar
from src.analysis.fundamental_engine import FundamentalAnalysisEngine
from src.database.connection import get_engine
from src.ml.fundamental_ml import (
    FUNDAMENTAL_ML_VERSION,
    PROPOSED_FUNDAMENTAL_TARGET_SPEC,
    FundamentalMLAdvisor,
)
from src.ml.service import MLAnalysisService
from src.ml.technical_ml import (
    LABEL_NAMES,
    TECHNICAL_FEATURE_COLS,
    TECHNICAL_MODEL_VERSION,
    TechnicalMLPredictor,
    TrainOnlyPreprocessor,
    compute_causal_technical_labels,
)


@pytest.fixture(scope="module")
def db_engine():
    return get_engine()


def test_causal_technical_labels_helper_zero_future_leakage():
    """Preserved causal structural label helper must remain strictly future-independent."""
    cols = ["symbol", "trading_date", "cal_idx", "adj_high", "adj_low", "adj_close", "dist_sma_200", "is_zero_volume"]
    df = pd.read_parquet("data/predictive/daily_features.parquet", columns=cols)
    df = df[df["symbol"].isin(["OGDC", "LUCK"])].sort_values(["symbol", "cal_idx"]).reset_index(drop=True)

    full_labels = compute_causal_technical_labels(df)
    cutoff_mask = pd.to_datetime(df["trading_date"]).dt.date <= date(2024, 6, 28)
    trunc_labels = compute_causal_technical_labels(df[cutoff_mask].reset_index(drop=True))

    full_slice = full_labels[cutoff_mask.to_numpy()].reset_index(drop=True)
    assert (full_slice["target_cls"] == trunc_labels["target_cls"]).all()
    assert (full_slice["target_valid"] == trunc_labels["target_valid"]).all()

    forbidden = {"pos_252d", "ker_90d", "ir_126d", "target_cls", "target_valid"}
    assert forbidden.isdisjoint(set(TECHNICAL_FEATURE_COLS))
    assert not any(c.startswith("target_") or c.startswith("fin_") for c in TECHNICAL_FEATURE_COLS)


def test_train_only_preprocessor_preserves_binary_flags_and_nan_policy():
    """TrainOnlyPreprocessor must preserve rare binary flags and match scikit-learn transform API."""
    n = 300
    train_df = pd.DataFrame(
        {
            col: (np.zeros(n, dtype=float) if col.startswith("is_") else np.linspace(-1.0, 1.0, n))
            for col in TECHNICAL_FEATURE_COLS
        }
    )
    train_df.loc[0, "is_bullish_pattern"] = 1.0
    train_df.loc[1, "is_doji_true_ohlc"] = 1.0
    train_df.loc[10:20, "rsi_14"] = np.nan

    pre_gbdt = TrainOnlyPreprocessor(TECHNICAL_FEATURE_COLS, impute_missing=False).fit(train_df)
    pre_imp = TrainOnlyPreprocessor(TECHNICAL_FEATURE_COLS, impute_missing=True).fit(train_df)

    probe = pd.DataFrame({col: [0.0] for col in TECHNICAL_FEATURE_COLS})
    probe["is_bullish_pattern"] = 1.0
    probe["is_doji_true_ohlc"] = 1.0
    probe["rsi_14"] = np.nan
    probe["ret_1d"] = 9999.0

    x_gbdt = pre_gbdt.transform(probe)
    x_imp = pre_imp.transform(probe)

    assert x_gbdt[0, TECHNICAL_FEATURE_COLS.index("is_bullish_pattern")] == pytest.approx(1.0)
    assert x_gbdt[0, TECHNICAL_FEATURE_COLS.index("is_doji_true_ohlc")] == pytest.approx(1.0)
    assert np.isnan(x_gbdt[0, TECHNICAL_FEATURE_COLS.index("rsi_14")])
    assert not np.isnan(x_imp[0, TECHNICAL_FEATURE_COLS.index("rsi_14")])
    assert x_gbdt[0, TECHNICAL_FEATURE_COLS.index("ret_1d")] < 2.0


def test_exported_pkl_artifacts_schema_checksums_and_selection():
    """Verify exported artifacts under artifacts/ match schema, checksums, and chronological VAL selection."""
    tech_dir = TECHNICAL_ARTIFACTS_DIR
    model_pkl = tech_dir / "technical_model.pkl"
    preproc_pkl = tech_dir / "technical_preprocessor.pkl"
    feat_json = tech_dir / "technical_features.json"
    meta_json = tech_dir / "technical_metadata.json"

    for p in (model_pkl, preproc_pkl, feat_json, meta_json):
        assert p.exists(), f"Missing artifact: {p}"
        assert p.stat().st_size > 500

    # Fundamental `.pkl` MUST NOT exist when blocked by insufficient reliable labels
    fund_dir = FUNDAMENTAL_ARTIFACTS_DIR
    assert not (fund_dir / "fundamental_model.pkl").exists()
    assert not (fund_dir / "fundamental_preprocessor.pkl").exists()
    assert (fund_dir / "fundamental_metadata.json").exists()
    assert (fund_dir / "fundamental_features.json").exists()

    meta = json.loads(meta_json.read_text(encoding="utf-8"))
    feat_schema = json.loads(feat_json.read_text(encoding="utf-8"))
    assert meta["version"] == TECHNICAL_MODEL_VERSION
    assert feat_schema["feature_count"] == 74
    assert feat_schema["feature_cols"] == TECHNICAL_FEATURE_COLS
    assert meta["feature_names"] == TECHNICAL_FEATURE_COLS

    # Check SHA-256 checksums match disk files
    for fname, p in (("technical_model.pkl", model_pkl), ("technical_preprocessor.pkl", preproc_pkl)):
        actual_hash = hashlib.sha256(p.read_bytes()).hexdigest()
        assert actual_hash == meta["artifact_checksums_sha256"][fname]

    # Verify XGBoost won strictly on VAL Macro-F1 and beat all baselines on untouched TEST
    val_m = meta["validation_metrics"]
    test_m = meta["final_test_metrics"]
    sel = meta["selected_model_name"]
    assert val_m[sel]["f1_macro"] >= max(val_m["lightgbm"]["f1_macro"], val_m["random_forest"]["f1_macro"])
    assert val_m[sel]["f1_macro"] > val_m["simple_ma_rsi_rule"]["f1_macro"]
    assert test_m[sel]["f1_macro"] > test_m["simple_ma_rsi_rule"]["f1_macro"]
    assert test_m[sel]["f1_macro"] > test_m["majority_baseline"]["f1_macro"]

    # Direct load & reproducible inference on real untouched TEST observation
    mdl = joblib.load(model_pkl)
    preproc = joblib.load(preproc_pkl)
    assert hasattr(mdl, "predict_proba")
    assert int(mdl.n_features_in_) == 74
    assert preproc.feature_cols == TECHNICAL_FEATURE_COLS

    obs_df = pd.read_parquet(
        PREDICTIVE_DATA_DIR / "daily_features.parquet",
        columns=TECHNICAL_FEATURE_COLS + ["symbol", "trading_date", "split"],
    )
    real_row = obs_df[(obs_df["symbol"] == "OGDC") & (obs_df["split"] == "TEST")].tail(1)
    assert len(real_row) == 1

    x1 = preproc.transform(real_row[TECHNICAL_FEATURE_COLS])
    p1 = mdl.predict_proba(x1)[0]
    p2 = mdl.predict_proba(x1)[0]
    np.testing.assert_allclose(p1, p2, rtol=1e-7, atol=1e-7)
    assert sum(p1) == pytest.approx(1.0, abs=1e-5)


def test_technical_ml_live_predictions_and_short_history(db_engine):
    """Live PIT PostgreSQL predictor must match direct `.pkl` outputs and handle short-history safely."""
    predictor = TechnicalMLPredictor()
    assert predictor.preload(verify_checksum=True) is True

    with db_engine.connect() as conn:
        for sym in ("OGDC", "MEBL", "LUCK", "SYS"):
            res = predictor.predict_for_symbol(conn, sym, as_of_date="2026-10-13")
            assert res["status"] == "OK"
            assert res["model_version"] == TECHNICAL_MODEL_VERSION
            assert res["predicted_condition"] in LABEL_NAMES
            assert sum(res["probabilities"].values()) == pytest.approx(1.0, abs=1e-2)
            assert len(res["top_contributing_features"]) == 8

        pit_res = predictor.predict_for_symbol(conn, "OGDC", as_of_date="2024-06-28")
        assert pit_res["status"] == "OK"
        assert pit_res["as_of_date"] <= "2024-06-28"

        cal_df = load_trading_calendar(conn, max_date=date(2026, 10, 13))
        adj_df, _, _ = load_clean_symbol_prices(conn, "OGDC", max_date=date(2026, 10, 13), cal_df=cal_df)
        hundredth_day = pd.to_datetime(adj_df["trading_date"].iloc[99]).date().isoformat()
        short_res = predictor.predict_for_symbol(conn, "OGDC", as_of_date=hundredth_day)
        assert short_res["status"] == "INSUFFICIENT_HISTORY"
        assert short_res["predicted_condition"] is None


def test_fundamental_ml_honest_blocker_and_rule_preservation(db_engine):
    """Fundamental ML remains honestly blocked without fake `.pkl` while rule assessments work cleanly."""
    advisor = FundamentalMLAdvisor()
    assert advisor.is_model_artifact_present() is False
    rep = advisor.get_readiness_report()
    assert rep["training_status"] == "BLOCKED_INSUFFICIENT_RELIABLE_LABELS"
    assert rep["model_exported"] is False
    assert rep["proposed_target_definition"] == PROPOSED_FUNDAMENTAL_TARGET_SPEC

    fund_eng = FundamentalAnalysisEngine()
    with db_engine.connect() as conn:
        mebl_rule = fund_eng.analyze(conn, "MEBL", as_of_date="2026-10-13")

    mebl_ml = advisor.assess_symbol(mebl_rule)
    assert mebl_ml["status"] == "BLOCKED_INSUFFICIENT_RELIABLE_LABELS"
    assert mebl_ml["model_available"] is False
    assert mebl_ml["predicted_health_category"] is None
    assert mebl_ml["available_metrics_snapshot"]["current_ratio"] is None


def test_fastapi_startup_loading_models_endpoints_and_corrupt_handling():
    """Verify FastAPI lifespan startup loads once, /api/models/* works end-to-end, and missing/corrupt files fail safely."""
    ml_router._ml_service = None
    with TestClient(app_mod.app) as client:
        svc = app_mod.app.state.ml_service
        assert svc._startup_loaded is True
        assert svc.tech_predictor._load_count == 1

        # 1. GET /api/models/status
        r_stat = client.get("/api/models/status")
        assert r_stat.status_code == 200
        st = r_stat.json()
        assert st["loaded_on_startup"] is True
        assert st["technical"]["artifact_exists"] is True
        assert st["technical"]["loaded_successfully"] is True
        assert st["technical"]["ready_for_inference"] is True
        assert st["technical"]["model_type"] == "xgboost"
        assert st["technical"]["version"] == TECHNICAL_MODEL_VERSION
        assert st["technical"]["training_date"] is not None

        assert st["fundamental"]["artifact_exists"] is False
        assert st["fundamental"]["loaded_successfully"] is False
        assert st["fundamental"]["ready_for_inference"] is False
        assert st["fundamental"]["status"] == "BLOCKED_INSUFFICIENT_RELIABLE_LABELS"

        # 2. POST /api/models/technical/predict by symbol (reuses startup load; load_count stays 1)
        r_pred1 = client.post("/api/models/technical/predict", json={"symbol": "OGDC", "as_of_date": "2026-10-13"})
        assert r_pred1.status_code == 200
        p1 = r_pred1.json()
        assert p1["status"] == "OK"
        assert p1["loaded_from_startup_cache"] is True
        assert p1["artifact_load_count"] == 1
        assert p1["predicted_condition"] in LABEL_NAMES

        # 3. POST /api/models/technical/predict by real raw historical feature row
        obs_df = pd.read_parquet(
            PREDICTIVE_DATA_DIR / "daily_features.parquet",
            columns=TECHNICAL_FEATURE_COLS + ["symbol", "trading_date"],
        )
        raw_row = obs_df[obs_df["symbol"] == "OGDC"].tail(1)[TECHNICAL_FEATURE_COLS].iloc[0]
        feat_payload = {k: (None if pd.isna(v) else float(v)) for k, v in raw_row.items()}

        r_pred2 = client.post("/api/models/technical/predict", json={"features": feat_payload})
        assert r_pred2.status_code == 200
        p2 = r_pred2.json()
        assert p2["predicted_condition"] == p1["predicted_condition"]
        assert p2["probabilities"] == p1["probabilities"]
        assert p2["artifact_load_count"] == 1
        assert svc.tech_predictor._load_count == 1  # Strictly zero per-request reload

        # 4. POST /api/models/fundamental/predict must safely return HTTP 503 blocker
        r_fund_pred = client.post("/api/models/fundamental/predict", json={"symbol": "MEBL", "as_of_date": "2026-10-13"})
        assert r_fund_pred.status_code == 503
        assert "BLOCKED_INSUFFICIENT_RELIABLE_LABELS" in r_fund_pred.json()["detail"]

        # 5. Legacy /api/analysis/ml/* and rule-based /api/analysis/* remain functional
        assert client.get("/api/analysis/ml/technical/OGDC?as_of_date=2026-10-13").status_code == 200
        legacy = client.get("/api/analysis/technical/OGDC")
        assert legacy.status_code == 200
        assert "ml_based_technical_assessment" not in legacy.json()

        # 6. Validation errors (400 / 404)
        assert client.post("/api/models/technical/predict", json={"symbol": "INVALID_TICKER_XYZ"}).status_code == 404
        assert client.post("/api/models/technical/predict", json={"features": {"ret_1d": 0.01}}).status_code == 400
        assert client.post("/api/models/technical/predict", json={}).status_code == 400

    # 7. Missing & Corrupt `.pkl` safe handling test in isolated temp dirs
    orig_svc = ml_router._ml_service
    try:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            svc_tmp = MLAnalysisService(engine=get_engine())
            svc_tmp.tech_predictor = TechnicalMLPredictor(model_dir=tdp / "missing", reports_dir=tdp / "missing")
            svc_tmp.fund_advisor = FundamentalMLAdvisor(model_dir=tdp / "missing", reports_dir=tdp / "missing")
            svc_tmp.preload_models()
            ml_router._ml_service = svc_tmp

            tc_tmp = TestClient(app_mod.app)
            assert tc_tmp.get("/api/models/status").json()["technical"]["artifact_exists"] is False
            assert tc_tmp.post("/api/models/technical/predict", json={"symbol": "OGDC"}).status_code == 503

            cdir = tdp / "corrupt"
            cdir.mkdir()
            (cdir / "technical_model.pkl").write_bytes(b"CORRUPT_PKL_BYTES")
            (cdir / "technical_preprocessor.pkl").write_bytes(b"CORRUPT_PREPROC")
            (cdir / "technical_metadata.json").write_text("{corrupt_json", encoding="utf-8")
            svc_tmp.tech_predictor = TechnicalMLPredictor(model_dir=cdir, reports_dir=cdir)
            assert svc_tmp.tech_predictor.preload() is False
            assert tc_tmp.get("/api/models/status").json()["technical"]["loaded_successfully"] is False
            assert tc_tmp.post("/api/models/technical/predict", json={"symbol": "OGDC"}).status_code == 503
    finally:
        ml_router._ml_service = orig_svc
