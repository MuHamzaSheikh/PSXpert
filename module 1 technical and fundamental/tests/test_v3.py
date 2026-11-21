import numpy as np
import pandas as pd
import pytest
from m1.v3 import (
    metrics, calibration_fit, calibrate, calibration_allowed,
    fit_model, predict_probs, BoundedSearchStudy
)


def test_metrics_computation():
    y = np.array([0, 1, 2, 0, 1, 2])
    p = np.array([
        [0.7, 0.2, 0.1],
        [0.1, 0.8, 0.1],
        [0.2, 0.2, 0.6],
        [0.6, 0.3, 0.1],
        [0.2, 0.5, 0.3],
        [0.1, 0.2, 0.7]
    ])
    res = metrics(y, p)
    assert res["rows"] == 6
    assert res["accuracy"] == 1.0
    assert res["balanced_accuracy"] == 1.0
    assert res["macro_f1"] == 1.0
    assert res["per_class_recall"]["BEARISH"] == 1.0
    assert res["per_class_precision"]["BULLISH"] == 1.0
    assert res["log_loss"] > 0


def test_model_families_fit_and_predict():
    rng = np.random.default_rng(42)
    n = 120
    frame = pd.DataFrame({
        "feat1": rng.standard_normal(n),
        "feat2": rng.standard_normal(n),
        "future_direction": rng.choice(["BEARISH", "SIDEWAYS", "BULLISH"], size=n)
    })
    feature_names = ["feat1", "feat2"]
    
    # 1. Majority
    m_maj = fit_model(frame, feature_names, {"kind": "majority"})
    p_maj = predict_probs(m_maj, frame, feature_names)
    assert p_maj.shape == (n, 3)
    np.testing.assert_allclose(p_maj.sum(axis=1), 1.0, rtol=1e-5, atol=1e-6)
    
    # 2. Logistic
    m_log = fit_model(frame, feature_names, {"kind": "logistic", "C": 0.1, "weighted": False})
    p_log = predict_probs(m_log, frame, feature_names)
    assert p_log.shape == (n, 3)
    np.testing.assert_allclose(p_log.sum(axis=1), 1.0, rtol=1e-5, atol=1e-6)
    
    # 3. XGBoost
    m_xgb = fit_model(frame, feature_names, {
        "kind": "xgboost", "max_depth": 2, "learning_rate": 0.05, "n_estimators": 10,
        "subsample": 0.85, "colsample_bytree": 0.85, "reg_lambda": 10.0, "min_child_weight": 5, "weighted": False
    })
    p_xgb = predict_probs(m_xgb, frame, feature_names)
    assert p_xgb.shape == (n, 3)
    np.testing.assert_allclose(p_xgb.sum(axis=1), 1.0, rtol=1e-5, atol=1e-6)
    
    # 4. LightGBM
    m_lgb = fit_model(frame, feature_names, {
        "kind": "lightgbm", "num_leaves": 7, "max_depth": 2, "learning_rate": 0.05,
        "n_estimators": 10, "subsample": 0.85, "colsample_bytree": 0.85, "reg_lambda": 10.0,
        "min_child_samples": 10, "weighted": False
    })
    p_lgb = predict_probs(m_lgb, frame, feature_names)
    assert p_lgb.shape == (n, 3)
    np.testing.assert_allclose(p_lgb.sum(axis=1), 1.0, rtol=1e-5, atol=1e-6)
    
    # 5. CatBoost
    m_cat = fit_model(frame, feature_names, {
        "kind": "catboost", "depth": 2, "learning_rate": 0.05, "iterations": 10,
        "l2_leaf_reg": 5.0, "subsample": 0.85, "weighted": False
    })
    p_cat = predict_probs(m_cat, frame, feature_names)
    assert p_cat.shape == (n, 3)
    np.testing.assert_allclose(p_cat.sum(axis=1), 1.0, rtol=1e-5, atol=1e-6)


def test_temperature_calibration_preserves_ranking():
    rng = np.random.default_rng(42)
    p = rng.dirichlet([1, 1, 1], size=60)
    y = np.tile([0, 1, 2], 20)
    temp = calibration_fit(p, y, "temperature")
    cal_p = calibrate(p, temp)
    np.testing.assert_array_equal(p.argmax(axis=1), cal_p.argmax(axis=1))
    np.testing.assert_allclose(cal_p.sum(axis=1), 1.0)


def test_bounded_search_study_reproducibility():
    s1 = BoundedSearchStudy(name="study1", seed=42)
    s2 = BoundedSearchStudy(name="study2", seed=42)
    
    p1 = s1.sample_parameters("xgboost")
    p2 = s2.sample_parameters("xgboost")
    assert p1 == p2
    
    p_cat1 = s1.sample_parameters("catboost")
    p_cat2 = s2.sample_parameters("catboost")
    assert p_cat1 == p_cat2
