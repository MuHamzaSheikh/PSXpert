"""Unit tests for centralized paths config, technical indicators math, zero-lookahead invariance, and patterns."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from config.paths import (
    ARTIFACTS_DIR,
    CHARTS_REPORTS_DIR,
    DATA_AUDIT_REPORTS_DIR,
    DATA_DIR,
    FUNDAMENTAL_ARTIFACTS_DIR,
    ML_REPORTS_DIR,
    PREDICTIVE_DATA_DIR,
    PROCESSED_DATA_DIR,
    PROJECT_ROOT,
    RAW_DATA_DIR,
    REPORTS_DIR,
    STATIC_DIR,
    TECHNICAL_ARTIFACTS_DIR,
)
from src.analysis.candlestick_patterns import CandlestickPatternDetector
from src.analysis.technical_indicators import TechnicalIndicatorCalculator


def _sample_ohlcv_df(n: int = 25) -> pd.DataFrame:
    """Deterministic ascending/volatile OHLCV fixture for indicator unit tests."""
    dates = pd.date_range("2026-09-01", periods=n, freq="B").strftime("%Y-%m-%d").tolist()
    closes = [100.0 + (i * 0.6) + (1.5 if i % 3 == 0 else -0.4) for i in range(n)]
    opens = [c - 0.5 if i % 2 == 0 else c + 0.4 for i, c in enumerate(closes)]
    highs = [max(o, c) + 1.2 for o, c in zip(opens, closes)]
    lows = [min(o, c) - 1.1 for o, c in zip(opens, closes)]
    vols = [10000 + i * 500 for i in range(n)]
    return pd.DataFrame(
        {
            "symbol": ["TEST_SYM"] * n,
            "trading_date": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": vols,
        }
    )


def test_centralized_paths_config_layout():
    """Verify config.paths constants resolve consistently under PROJECT_ROOT."""
    assert (PROJECT_ROOT / "app.py").is_file()
    assert DATA_DIR == PROJECT_ROOT / "data"
    assert RAW_DATA_DIR == DATA_DIR / "raw"
    assert PROCESSED_DATA_DIR == DATA_DIR / "processed"
    assert PREDICTIVE_DATA_DIR == DATA_DIR / "predictive"
    assert ARTIFACTS_DIR == PROJECT_ROOT / "artifacts"
    assert TECHNICAL_ARTIFACTS_DIR == ARTIFACTS_DIR / "technical"
    assert FUNDAMENTAL_ARTIFACTS_DIR == ARTIFACTS_DIR / "fundamental"
    assert REPORTS_DIR == PROJECT_ROOT / "reports"
    assert DATA_AUDIT_REPORTS_DIR == REPORTS_DIR / "data_audit"
    assert ML_REPORTS_DIR == REPORTS_DIR / "model_evaluation"
    assert CHARTS_REPORTS_DIR == REPORTS_DIR / "charts"
    assert STATIC_DIR == PROJECT_ROOT / "static"
    assert (STATIC_DIR / "index.html").is_file()


def test_technical_indicator_empty_input():
    """Empty OHLCV DataFrame must return cleanly without exceptions."""
    calc = TechnicalIndicatorCalculator()
    empty = pd.DataFrame(columns=["symbol", "trading_date", "open", "high", "low", "close", "volume"])
    out = calc.compute_all_indicators(empty)
    assert out.empty


def test_technical_indicators_first_principles_and_causality():
    """Verify exact SMA-20, EMA-20, OBV, RSI bounds, and zero future lookahead leakage."""
    calc = TechnicalIndicatorCalculator()
    df = _sample_ohlcv_df(25)
    out = calc.compute_all_indicators(df)

    expected_cols = {
        "sma_20",
        "sma_50",
        "sma_200",
        "ema_20",
        "rsi_14",
        "macd_line",
        "macd_signal",
        "macd_diff",
        "bb_middle",
        "bb_upper",
        "bb_lower",
        "atr_14",
        "obv",
        "stoch_k",
        "stoch_d",
    }
    assert expected_cols.issubset(out.columns)

    # First-principles check on final bar's SMA-20 and EMA-20
    closes = df["close"].tolist()
    manual_sma20 = sum(closes[-20:]) / 20.0
    assert math.isclose(float(out.iloc[-1]["sma_20"]), manual_sma20, abs_tol=1e-3)

    alpha = 2.0 / 21.0
    ema20 = closes[0]
    for c in closes[1:]:
        ema20 = c * alpha + ema20 * (1.0 - alpha)
    assert math.isclose(float(out.iloc[-1]["ema_20"]), ema20, abs_tol=1e-3)

    last_rsi = float(out.iloc[-1]["rsi_14"])
    assert 0.0 <= last_rsi <= 100.0

    # Zero-lookahead check: altering final row must not alter earlier rows
    perturbed = df.copy()
    perturbed.loc[perturbed.index[-1], "close"] = 999.0
    perturbed.loc[perturbed.index[-1], "high"] = 1010.0
    perturbed.loc[perturbed.index[-1], "volume"] = 9_999_999
    out_pert = calc.compute_all_indicators(perturbed)

    check_cols = ["sma_20", "ema_20", "rsi_14", "macd_line", "bb_upper", "atr_14", "obv"]
    pd.testing.assert_frame_equal(
        out.iloc[:-1][check_cols].reset_index(drop=True),
        out_pert.iloc[:-1][check_cols].reset_index(drop=True),
    )

    diag = calc.generate_analytical_interpretation(out.iloc[-1])
    assert diag["symbol"] == "TEST_SYM"
    assert len(diag["diagnostics"]) >= 3
    assert "Not financial advice" in diag["disclaimer"]


def test_candlestick_pattern_detector_smoke():
    """Verify CandlestickPatternDetector computes geometry and detects patterns without crashing."""
    detector = CandlestickPatternDetector()
    df = _sample_ohlcv_df(10)
    # Inject an unambiguous Bullish Engulfing pair at indices 8 -> 9
    df.loc[8, ["open", "high", "low", "close"]] = [105.0, 105.5, 99.5, 100.0]
    df.loc[9, ["open", "high", "low", "close"]] = [99.0, 108.0, 98.5, 107.0]

    enriched, events = detector.detect_patterns(df)
    assert len(enriched) == len(df)
    assert "pattern_name" in enriched.columns
    assert isinstance(events, list)
    assert any(ev["pattern"] == "Bullish Engulfing" for ev in events)

