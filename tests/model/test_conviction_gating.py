"""Unit and integration tests for Selective Conviction Gating and Dynamic Volatility Barriers."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import app as app_mod
from src.database.connection import get_engine
from src.ml.conviction_filter import (
    ConvictionTier,
    SelectiveAction,
    classify_conviction,
    compute_dynamic_barriers,
    filter_predictions_by_conviction,
)
from src.ml.service import MLAnalysisService
from src.ml.technical_ml import TECHNICAL_FEATURE_COLS, TechnicalMLPredictor


def test_classify_conviction_noise_filtering():
    """Unconditional predictions with low confidence (< 0.42) must be gated into cash."""
    # Bullish but low confidence (40% in a 3-class model is near random walk)
    res_bullish_noise = classify_conviction("Bullish", 0.40)
    assert res_bullish_noise["tier"] == ConvictionTier.LOW_CONVICTION_NOISE
    assert res_bullish_noise["is_actionable"] is False
    assert res_bullish_noise["selective_action"] == SelectiveAction.HOLD_CASH_NO_TRADE
    assert res_bullish_noise["historical_expected_win_rate_pct"] == 44.1
    assert "Filtered out as noise" in res_bullish_noise["execution_guidance"]

    # Bearish but low confidence (38%)
    res_bearish_noise = classify_conviction("Bearish", 0.38)
    assert res_bearish_noise["tier"] == ConvictionTier.LOW_CONVICTION_NOISE
    assert res_bearish_noise["is_actionable"] is False
    assert res_bearish_noise["selective_action"] == SelectiveAction.HOLD_CASH_NO_TRADE


def test_classify_conviction_tiering_and_actionability():
    """High and Ultra-High conviction predictions unlock verified win rates."""
    # Ultra-High Conviction Bullish (>= 0.55) -> 82.1% win rate
    res_ultra = classify_conviction("Bullish", 0.58)
    assert res_ultra["tier"] == ConvictionTier.ULTRA_HIGH_CONVICTION
    assert res_ultra["is_actionable"] is True
    assert res_ultra["selective_action"] == SelectiveAction.ACTIONABLE_BULLISH
    assert res_ultra["historical_expected_win_rate_pct"] == 82.1
    assert res_ultra["alpha_expectation_pct"] == pytest.approx(5.70)

    # High Conviction Bearish (>= 0.50) -> 62.9% win rate
    res_high_bear = classify_conviction("Bearish", 0.52)
    assert res_high_bear["tier"] == ConvictionTier.HIGH_CONVICTION
    assert res_high_bear["is_actionable"] is True
    assert res_high_bear["selective_action"] == SelectiveAction.ACTIONABLE_BEARISH
    assert res_high_bear["historical_expected_win_rate_pct"] == 62.9

    # Moderate Conviction (>= 0.42) -> 51.4% win rate
    res_mod = classify_conviction("Bullish", 0.46)
    assert res_mod["tier"] == ConvictionTier.MODERATE_CONVICTION
    assert res_mod["is_actionable"] is True
    assert res_mod["selective_action"] == SelectiveAction.ACTIONABLE_BULLISH
    assert res_mod["historical_expected_win_rate_pct"] == 51.4

    # Neutral condition is always non-directional -> HOLD CASH
    res_neutral = classify_conviction("Neutral", 0.65)
    assert res_neutral["is_actionable"] is False
    assert res_neutral["selective_action"] == SelectiveAction.HOLD_CASH_NO_TRADE
    assert "Non-directional regime" in res_neutral["execution_guidance"]


def test_dynamic_volatility_barriers_heteroskedastic_scaling():
    """Dynamic barriers must scale with realized ATR to fit stock volatility."""
    # Case A: Low-volatility stock (ATR = 1.5%, e.g., MCB) at 100 PKR
    barriers_low = compute_dynamic_barriers(
        close_price=100.0,
        atr_pct=0.015,
        direction="Bullish",
        multiplier_tp=1.5,
        multiplier_sl=1.0,
    )
    assert barriers_low["atr_pct"] == 0.015
    assert barriers_low["take_profit_target_pct"] == pytest.approx(0.0225)  # +2.25%
    assert barriers_low["stop_loss_limit_pct"] == pytest.approx(-0.0150)   # -1.50%
    assert barriers_low["take_profit_price"] == pytest.approx(102.25)
    assert barriers_low["stop_loss_price"] == pytest.approx(98.50)
    assert barriers_low["risk_reward_ratio"] == pytest.approx(1.50)

    # Case B: High-volatility stock (ATR = 5.0%, e.g., CPHL) at 100 PKR
    barriers_high = compute_dynamic_barriers(
        close_price=100.0,
        atr_pct=0.050,
        direction="Bullish",
        multiplier_tp=1.5,
        multiplier_sl=1.0,
    )
    assert barriers_high["take_profit_target_pct"] == pytest.approx(0.0750)  # +7.50%
    assert barriers_high["stop_loss_limit_pct"] == pytest.approx(-0.0500)   # -5.00%
    assert barriers_high["take_profit_price"] == pytest.approx(107.50)
    assert barriers_high["stop_loss_price"] == pytest.approx(95.00)
    assert barriers_high["risk_reward_ratio"] == pytest.approx(1.50)

    # High-volatility barriers are 3.33x wider than low-volatility barriers, preventing premature stop-out
    assert barriers_high["take_profit_target_pct"] > barriers_low["take_profit_target_pct"]

    # Case C: Bearish trade (short / hedging direction)
    barriers_bear = compute_dynamic_barriers(
        close_price=100.0,
        atr_pct=0.020,
        direction="Bearish",
        multiplier_tp=1.5,
        multiplier_sl=1.0,
    )
    assert barriers_bear["take_profit_target_pct"] == pytest.approx(-0.0300)  # TP is lower
    assert barriers_bear["stop_loss_limit_pct"] == pytest.approx(0.0200)    # SL is higher
    assert barriers_bear["take_profit_price"] == pytest.approx(97.00)
    assert barriers_bear["stop_loss_price"] == pytest.approx(102.00)


def test_filter_predictions_by_conviction():
    """Batch filtering preserves only high-conviction predictions."""
    preds = [
        {"symbol": "OGDC", "conviction_tier": ConvictionTier.ULTRA_HIGH_CONVICTION},
        {"symbol": "LUCK", "conviction_tier": ConvictionTier.LOW_CONVICTION_NOISE},
        {"symbol": "ENGRO", "conviction_tier": ConvictionTier.HIGH_CONVICTION},
        {"symbol": "HUBC", "conviction_tier": ConvictionTier.MODERATE_CONVICTION},
    ]

    high_conv = filter_predictions_by_conviction(preds, min_tier=ConvictionTier.HIGH_CONVICTION)
    symbols = [p["symbol"] for p in high_conv]
    assert symbols == ["OGDC", "ENGRO"]

    ultra_conv = filter_predictions_by_conviction(preds, min_tier=ConvictionTier.ULTRA_HIGH_CONVICTION)
    assert [p["symbol"] for p in ultra_conv] == ["OGDC"]


def test_technical_ml_predictor_produces_conviction_and_barriers():
    """TechnicalMLPredictor inference must return conviction gating and dynamic barriers."""
    predictor = TechnicalMLPredictor()
    assert predictor.preload(verify_checksum=True)

    # Create dummy observation matching TECHNICAL_FEATURE_COLS
    obs = {col: 0.0 for col in TECHNICAL_FEATURE_COLS}
    obs["rsi_14"] = 65.0
    obs["adx_14"] = 28.5
    obs["atr_pct"] = 0.028

    pred = predictor.predict_from_features(obs, close_price=150.0)
    assert pred["status"] == "OK"
    assert "conviction_tier" in pred
    assert "is_actionable" in pred
    assert "selective_action" in pred
    assert "historical_expected_win_rate_pct" in pred
    assert "take_profit_target_pct" in pred
    assert "stop_loss_limit_pct" in pred

    # Check nested conviction_gating and dynamic_volatility_barriers objects
    cg = pred["conviction_gating"]
    assert cg["tier"] in (
        ConvictionTier.ULTRA_HIGH_CONVICTION,
        ConvictionTier.HIGH_CONVICTION,
        ConvictionTier.MODERATE_CONVICTION,
        ConvictionTier.LOW_CONVICTION_NOISE,
    )
    assert isinstance(cg["is_actionable"], bool)

    barriers = pred["dynamic_volatility_barriers"]
    assert barriers["atr_pct"] == pytest.approx(0.028)
    assert barriers["risk_reward_ratio"] == pytest.approx(1.50)
    assert barriers["take_profit_price"] is not None
    assert barriers["stop_loss_price"] is not None


def test_fastapi_endpoints_expose_conviction_gating():
    """Verify FastAPI exposes conviction gating in both POST /api/models and GET /api/analysis."""
    client = TestClient(app_mod.app)

    # 1. POST /api/models/technical/predict with raw features
    obs = {col: 0.0 for col in TECHNICAL_FEATURE_COLS}
    obs["rsi_14"] = 55.0
    obs["adx_14"] = 22.0
    obs["atr_pct"] = 0.024

    resp = client.post("/api/models/technical/predict", json={"features": obs})
    assert resp.status_code == 200
    data = resp.json()
    assert "conviction_tier" in data
    assert "is_actionable" in data
    assert "selective_action" in data
    assert "conviction_gating" in data
    assert "dynamic_volatility_barriers" in data

    # 2. GET /api/analysis/ml/technical/OGDC includes conviction metadata in rule comparison
    resp_comp = client.get("/api/analysis/ml/technical/OGDC?as_of_date=2026-10-13")
    assert resp_comp.status_code == 200
    comp_data = resp_comp.json()
    assert "rule_vs_ml_comparison" in comp_data
    rule_ml = comp_data["rule_vs_ml_comparison"]
    assert "ml_conviction_tier" in rule_ml
    assert "ml_is_actionable" in rule_ml
    assert "ml_selective_action" in rule_ml

    ml_tech = comp_data["ml_based_technical_assessment"]
    assert "conviction_tier" in ml_tech
    assert "dynamic_volatility_barriers" in ml_tech
