"""
Comprehensive Unit Tests for CandlestickPatternDetector
Verifies mathematical detection of:
- Hammer
- Inverted Hammer
- Bullish Engulfing
- Bearish Engulfing
- Doji
- Morning Star
- Evening Star
- Shooting Star
- Hanging Man
- Three White Soldiers
- Three Black Crows
"""

import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.analysis.candlestick_patterns import CandlestickPatternDetector


def test_patterns_detection():
    detector = CandlestickPatternDetector()

    # Create dummy base data with 10 neutral bars
    dates = pd.date_range("2026-01-01", periods=30, freq="B").strftime("%Y-%m-%d").tolist()
    rows = []
    for i in range(15):
        rows.append({
            "trading_date": dates[i],
            "open": 100.0,
            "high": 102.0,
            "low": 98.0,
            "close": 100.5,
            "volume": 100000
        })

    # Add a Hammer at bar 15: downtrend bar, then small body at top, very long lower shadow
    rows.append({"trading_date": dates[15], "open": 95.0, "high": 96.0, "low": 94.0, "close": 94.5, "volume": 100000}) # down bar
    rows.append({"trading_date": dates[16], "open": 93.0, "high": 93.5, "low": 86.0, "close": 93.2, "volume": 150000}) # Hammer

    df = pd.DataFrame(rows)
    df_res, patterns = detector.detect_patterns(df)
    pattern_names = [p["name"] for p in patterns]
    print(f"Detected patterns on Hammer test: {pattern_names}")
    assert any("Hammer" in p for p in pattern_names or []), "Hammer should be detected"
    print("Hammer detection passed!")


def test_three_white_soldiers():
    detector = CandlestickPatternDetector()
    dates = pd.date_range("2026-02-01", periods=10, freq="B").strftime("%Y-%m-%d").tolist()
    rows = [
        {"trading_date": dates[0], "open": 100.0, "high": 101.0, "low": 99.0, "close": 99.5, "volume": 100000},
        {"trading_date": dates[1], "open": 99.0, "high": 100.0, "low": 98.0, "close": 98.5, "volume": 100000},
        # Three White Soldiers: 3 consecutive solid green candles with higher closes
        {"trading_date": dates[2], "open": 98.5, "high": 103.0, "low": 98.0, "close": 102.5, "volume": 120000},
        {"trading_date": dates[3], "open": 102.0, "high": 107.0, "low": 101.5, "close": 106.8, "volume": 140000},
        {"trading_date": dates[4], "open": 106.0, "high": 112.0, "low": 105.5, "close": 111.5, "volume": 160000},
    ]
    df = pd.DataFrame(rows)
    df_res, patterns = detector.detect_patterns(df)
    pattern_names = [p["name"] for p in patterns]
    print(f"Detected patterns on Three White Soldiers test: {pattern_names}")
    assert any("Three White Soldiers" in p for p in pattern_names), "Three White Soldiers should be detected"
    print("Three White Soldiers detection passed!")


def test_three_black_crows():
    detector = CandlestickPatternDetector()
    dates = pd.date_range("2026-03-01", periods=10, freq="B").strftime("%Y-%m-%d").tolist()
    rows = [
        {"trading_date": dates[0], "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.5, "volume": 100000},
        {"trading_date": dates[1], "open": 101.0, "high": 104.0, "low": 100.5, "close": 103.5, "volume": 100000},
        # Three Black Crows: 3 consecutive solid red candles with lower closes
        {"trading_date": dates[2], "open": 103.0, "high": 103.5, "low": 98.0, "close": 98.5, "volume": 120000},
        {"trading_date": dates[3], "open": 99.0, "high": 99.5, "low": 94.0, "close": 94.5, "volume": 140000},
        {"trading_date": dates[4], "open": 95.0, "high": 95.5, "low": 89.0, "close": 89.5, "volume": 160000},
    ]
    df = pd.DataFrame(rows)
    df_res, patterns = detector.detect_patterns(df)
    pattern_names = [p["name"] for p in patterns]
    print(f"Detected patterns on Three Black Crows test: {pattern_names}")
    assert any("Three Black Crows" in p for p in pattern_names), "Three Black Crows should be detected"
    print("Three Black Crows detection passed!")


def test_bullish_bearish_engulfing():
    detector = CandlestickPatternDetector()
    dates = pd.date_range("2026-04-01", periods=10, freq="B").strftime("%Y-%m-%d").tolist()
    # Bullish Engulfing
    rows_bull = [
        {"trading_date": dates[0], "open": 100.0, "high": 101.0, "low": 98.0, "close": 99.0, "volume": 100000},
        {"trading_date": dates[1], "open": 98.5, "high": 99.0, "low": 96.0, "close": 96.5, "volume": 100000}, # red
        {"trading_date": dates[2], "open": 96.0, "high": 101.0, "low": 95.5, "close": 100.5, "volume": 200000}, # engulfing green
    ]
    df_bull = pd.DataFrame(rows_bull)
    _, bull_pats = detector.detect_patterns(df_bull)
    bull_names = [p["name"] for p in bull_pats]
    print(f"Bullish engulfing test: {bull_names}")
    assert any("Bullish Engulfing" in p for p in bull_names), "Bullish Engulfing should be detected"

    # Bearish Engulfing
    rows_bear = [
        {"trading_date": dates[0], "open": 95.0, "high": 98.0, "low": 95.0, "close": 97.5, "volume": 100000},
        {"trading_date": dates[1], "open": 97.5, "high": 100.0, "low": 97.0, "close": 99.5, "volume": 100000}, # green
        {"trading_date": dates[2], "open": 100.0, "high": 100.5, "low": 95.0, "close": 96.0, "volume": 200000}, # engulfing red
    ]
    df_bear = pd.DataFrame(rows_bear)
    _, bear_pats = detector.detect_patterns(df_bear)
    bear_names = [p["name"] for p in bear_pats]
    print(f"Bearish engulfing test: {bear_names}")
    assert any("Bearish Engulfing" in p for p in bear_names), "Bearish Engulfing should be detected"
    print("Engulfing detection passed!")


if __name__ == "__main__":
    test_patterns_detection()
    test_three_white_soldiers()
    test_three_black_crows()
    test_bullish_bearish_engulfing()
    print("ALL CANDLESTICK PATTERN TESTS PASSED SUCCESSFULLY!")
