"""
PSXpert - Candlestick Pattern Recognition Engine
Detects single, double, and triple candlestick patterns with mathematical rigor on real OHLCV data.
Supports both individual equities and market indices (KSE-100).
"""

from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np


class CandlestickPatternDetector:
    """
    Mathematical Candlestick Pattern Recognition System.
    Identifies 20+ classic technical analysis candlestick patterns:
    - Bullish: Hammer, Inverted Hammer, Bullish Engulfing, Morning Star,
               Piercing Line, Bullish Harami, Three White Soldiers, Bullish Marubozu, Dragonfly Doji
    - Bearish: Shooting Star, Hanging Man, Bearish Engulfing, Evening Star,
               Dark Cloud Cover, Bearish Harami, Three Black Crows, Bearish Marubozu, Gravestone Doji
    - Neutral: Doji, Long-Legged Doji, Spinning Top
    """

    def __init__(self, doji_threshold: float = 0.10):
        self.doji_threshold = doji_threshold

    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculates trend filters and indicators: EMAs, SMAs, body and wick metrics."""
        data = df.copy()
        data = data.sort_values(by="trading_date").reset_index(drop=True)

        # Basic candle geometry
        data["open"] = pd.to_numeric(data["open"], errors="coerce")
        data["high"] = pd.to_numeric(data["high"], errors="coerce")
        data["low"] = pd.to_numeric(data["low"], errors="coerce")
        data["close"] = pd.to_numeric(data["close"], errors="coerce")
        data["volume"] = pd.to_numeric(data.get("volume", 0), errors="coerce").fillna(0)

        data["body"] = (data["close"] - data["open"]).abs()
        data["candle_range"] = data["high"] - data["low"]
        # Avoid division by zero
        data["candle_range"] = data["candle_range"].replace(0, 0.0001)

        data["upper_shadow"] = data["high"] - data[["open", "close"]].max(axis=1)
        data["lower_shadow"] = data[["open", "close"]].min(axis=1) - data["low"]

        data["is_green"] = data["close"] > data["open"]
        data["is_red"] = data["close"] < data["open"]
        data["is_doji"] = data["body"] <= (data["candle_range"] * self.doji_threshold)

        # Moving Averages & Trend Context
        data["ema20"] = data["close"].ewm(span=20, adjust=False).mean()
        data["ema50"] = data["close"].ewm(span=50, adjust=False).mean()
        data["ema200"] = data["close"].ewm(span=200, adjust=False).mean()
        data["sma20"] = data["close"].rolling(window=20).mean()
        data["avg_body20"] = data["body"].rolling(window=20).mean().fillna(data["body"])

        # Trend flags:
        # Uptrend if close > ema20 and ema20 > ema50 or 5-day return > 0
        data["trend_short"] = np.where(data["close"] > data["close"].shift(3), "UP", "DOWN")
        return data

    def detect_patterns(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """
        Scans DataFrame and tags all detected candlestick patterns per bar.
        Returns the enriched DataFrame with pattern columns, plus a structured list of pattern events.
        """
        data = self.calculate_technical_indicators(df)
        n = len(data)
        patterns_detected = []

        # Initialize pattern columns
        data["pattern_name"] = None
        data["pattern_type"] = None   # BULLISH, BEARISH, NEUTRAL
        data["pattern_signal"] = None # BUY, SELL, HOLD
        data["pattern_desc"] = None

        for i in range(2, n):
            c0 = data.iloc[i]     # Current candle
            c1 = data.iloc[i - 1] # 1 bar ago
            c2 = data.iloc[i - 2] # 2 bars ago

            patterns_for_bar = []

            # ------------------------------------------------------------------
            # 1. THREE-CANDLE PATTERNS
            # ------------------------------------------------------------------
            # Morning Star (Bullish Reversal after downtrend)
            if (c2["is_red"] and c2["body"] > c2["avg_body20"] * 0.7 and
                c1["body"] < c2["body"] * 0.5 and min(c1["open"], c1["close"]) <= c2["close"] and
                c0["is_green"] and c0["close"] >= (c2["open"] + c2["close"]) / 2):
                patterns_for_bar.append({
                    "name": "Morning Star",
                    "type": "BULLISH",
                    "signal": "STRONG BUY",
                    "desc": "3-candle bullish reversal: tall red, indecisive star gap, tall green closing > 50% into Day 1."
                })

            # Evening Star (Bearish Reversal after uptrend)
            elif (c2["is_green"] and c2["body"] > c2["avg_body20"] * 0.7 and
                  c1["body"] < c2["body"] * 0.5 and max(c1["open"], c1["close"]) >= c2["close"] and
                  c0["is_red"] and c0["close"] <= (c2["open"] + c2["close"]) / 2):
                patterns_for_bar.append({
                    "name": "Evening Star",
                    "type": "BEARISH",
                    "signal": "STRONG SELL",
                    "desc": "3-candle bearish reversal: tall green, indecisive star gap, tall red closing > 50% into Day 1."
                })

            # Three White Soldiers (Strong Bullish Continuation)
            elif (c2["is_green"] and c1["is_green"] and c0["is_green"] and
                  c0["close"] > c1["close"] > c2["close"] and
                  c0["open"] > c1["open"] and c1["open"] > c2["open"] and
                  c0["upper_shadow"] <= c0["body"] * 0.4 and c1["upper_shadow"] <= c1["body"] * 0.4):
                patterns_for_bar.append({
                    "name": "Three White Soldiers",
                    "type": "BULLISH",
                    "signal": "STRONG BUY",
                    "desc": "3 consecutive advancing green candles closing near highs: persistent institutional accumulation."
                })

            # Three Black Crows (Strong Bearish Continuation)
            elif (c2["is_red"] and c1["is_red"] and c0["is_red"] and
                  c0["close"] < c1["close"] < c2["close"] and
                  c0["open"] < c1["open"] and c1["open"] < c2["open"] and
                  c0["lower_shadow"] <= c0["body"] * 0.4 and c1["lower_shadow"] <= c1["body"] * 0.4):
                patterns_for_bar.append({
                    "name": "Three Black Crows",
                    "type": "BEARISH",
                    "signal": "STRONG SELL",
                    "desc": "3 consecutive declining red candles closing near lows: aggressive selling pressure."
                })

            # ------------------------------------------------------------------
            # 2. TWO-CANDLE PATTERNS
            # ------------------------------------------------------------------
            # Bullish Engulfing
            if (c1["is_red"] and c0["is_green"] and
                c0["open"] <= c1["close"] and c0["close"] >= c1["open"] and
                c0["body"] > c1["body"]):
                patterns_for_bar.append({
                    "name": "Bullish Engulfing",
                    "type": "BULLISH",
                    "signal": "BUY",
                    "desc": "Bullish reversal: large green body completely envelops previous day's red body."
                })

            # Bearish Engulfing
            elif (c1["is_green"] and c0["is_red"] and
                  c0["open"] >= c1["close"] and c0["close"] <= c1["open"] and
                  c0["body"] > c1["body"]):
                patterns_for_bar.append({
                    "name": "Bearish Engulfing",
                    "type": "BEARISH",
                    "signal": "SELL",
                    "desc": "Bearish reversal: large red body completely envelops previous day's green body."
                })

            # Piercing Line (Bullish Reversal)
            elif (c1["is_red"] and c0["is_green"] and
                  c0["open"] < c1["low"] and c0["close"] > (c1["open"] + c1["close"]) / 2 and
                  c0["close"] < c1["open"]):
                patterns_for_bar.append({
                    "name": "Piercing Line",
                    "type": "BULLISH",
                    "signal": "BUY",
                    "desc": "Bullish reversal: opens below prior low and surges to close > 50% into prior red candle."
                })

            # Dark Cloud Cover (Bearish Reversal)
            elif (c1["is_green"] and c0["is_red"] and
                  c0["open"] > c1["high"] and c0["close"] < (c1["open"] + c1["close"]) / 2 and
                  c0["close"] > c1["open"]):
                patterns_for_bar.append({
                    "name": "Dark Cloud Cover",
                    "type": "BEARISH",
                    "signal": "SELL",
                    "desc": "Bearish reversal: opens above prior high and plunges to close > 50% into prior green candle."
                })

            # Bullish Harami
            elif (c1["is_red"] and c0["is_green"] and
                  c1["body"] > c1["avg_body20"] * 0.8 and
                  c0["open"] >= c1["close"] and c0["close"] <= c1["open"] and
                  c0["body"] < c1["body"] * 0.6):
                patterns_for_bar.append({
                    "name": "Bullish Harami",
                    "type": "BULLISH",
                    "signal": "BUY",
                    "desc": "Bullish deceleration: small green body contained within preceding large red body."
                })

            # Bearish Harami
            elif (c1["is_green"] and c0["is_red"] and
                  c1["body"] > c1["avg_body20"] * 0.8 and
                  c0["open"] <= c1["close"] and c0["close"] >= c1["open"] and
                  c0["body"] < c1["body"] * 0.6):
                patterns_for_bar.append({
                    "name": "Bearish Harami",
                    "type": "BEARISH",
                    "signal": "SELL",
                    "desc": "Bearish deceleration: small red body contained within preceding large green body."
                })

            # ------------------------------------------------------------------
            # 3. SINGLE-CANDLE PATTERNS
            # ------------------------------------------------------------------
            # Hammer (Bullish Reversal in Downtrend)
            if (c0["lower_shadow"] >= 2.0 * c0["body"] and
                c0["upper_shadow"] <= c0["candle_range"] * 0.15 and
                c0["body"] > 0 and
                c0["trend_short"] == "DOWN"):
                patterns_for_bar.append({
                    "name": "Hammer",
                    "type": "BULLISH",
                    "signal": "BUY",
                    "desc": "Bullish reversal: long lower wick (2x body) proves buyers rejected intraday lows."
                })

            # Inverted Hammer (Bullish Reversal in Downtrend)
            elif (c0["upper_shadow"] >= 2.0 * c0["body"] and
                  c0["lower_shadow"] <= c0["candle_range"] * 0.15 and
                  c0["body"] > 0 and
                  c0["trend_short"] == "DOWN"):
                patterns_for_bar.append({
                    "name": "Inverted Hammer",
                    "type": "BULLISH",
                    "signal": "BUY",
                    "desc": "Bullish reversal: long upper wick shows strong buyer testing after extended downtrend."
                })

            # Shooting Star (Bearish Reversal in Uptrend)
            elif (c0["upper_shadow"] >= 2.0 * c0["body"] and
                  c0["lower_shadow"] <= c0["candle_range"] * 0.15 and
                  c0["body"] > 0 and
                  c0["trend_short"] == "UP"):
                patterns_for_bar.append({
                    "name": "Shooting Star",
                    "type": "BEARISH",
                    "signal": "SELL",
                    "desc": "Bearish reversal: long upper wick (2x body) indicates exhausted rally and overhead selling."
                })

            # Hanging Man (Bearish Reversal in Uptrend)
            elif (c0["lower_shadow"] >= 2.0 * c0["body"] and
                  c0["upper_shadow"] <= c0["candle_range"] * 0.15 and
                  c0["body"] > 0 and
                  c0["trend_short"] == "UP"):
                patterns_for_bar.append({
                    "name": "Hanging Man",
                    "type": "BEARISH",
                    "signal": "SELL",
                    "desc": "Bearish warning at highs: lower wick reveals intraday support cracking despite late recovery."
                })

            # Bullish Marubozu (Strong Bullish Continuation)
            elif (c0["is_green"] and
                  c0["body"] >= c0["candle_range"] * 0.88 and
                  c0["body"] >= c0["avg_body20"] * 1.3):
                patterns_for_bar.append({
                    "name": "Bullish Marubozu",
                    "type": "BULLISH",
                    "signal": "BUY",
                    "desc": "Powerful bullish impulse: open equals low and close equals high with zero hesitation."
                })

            # Bearish Marubozu (Strong Bearish Continuation)
            elif (c0["is_red"] and
                  c0["body"] >= c0["candle_range"] * 0.88 and
                  c0["body"] >= c0["avg_body20"] * 1.3):
                patterns_for_bar.append({
                    "name": "Bearish Marubozu",
                    "type": "BEARISH",
                    "signal": "SELL",
                    "desc": "Severe bearish impulse: open equals high and close equals low with continuous selling."
                })

            # Dragonfly Doji (Bullish Reversal / Support)
            elif (c0["is_doji"] and
                  c0["lower_shadow"] >= c0["candle_range"] * 0.70 and
                  c0["upper_shadow"] <= c0["candle_range"] * 0.10):
                patterns_for_bar.append({
                    "name": "Dragonfly Doji",
                    "type": "BULLISH",
                    "signal": "BUY",
                    "desc": "Bullish rejection: session opened and closed near high after extreme lower shadow."
                })

            # Gravestone Doji (Bearish Reversal / Resistance)
            elif (c0["is_doji"] and
                  c0["upper_shadow"] >= c0["candle_range"] * 0.70 and
                  c0["lower_shadow"] <= c0["candle_range"] * 0.10):
                patterns_for_bar.append({
                    "name": "Gravestone Doji",
                    "type": "BEARISH",
                    "signal": "SELL",
                    "desc": "Bearish exhaustion: session opened and closed near low after failed upward breakout."
                })

            # Classic Doji (Neutral / Indecision)
            elif c0["is_doji"]:
                patterns_for_bar.append({
                    "name": "Doji",
                    "type": "NEUTRAL",
                    "signal": "NEUTRAL",
                    "desc": "Market equilibrium: buyers and sellers completely balanced; watch for upcoming breakout."
                })

            # Spinning Top
            elif (c0["body"] <= c0["candle_range"] * 0.30 and
                  c0["upper_shadow"] >= c0["candle_range"] * 0.25 and
                  c0["lower_shadow"] >= c0["candle_range"] * 0.25):
                patterns_for_bar.append({
                    "name": "Spinning Top",
                    "type": "NEUTRAL",
                    "signal": "NEUTRAL",
                    "desc": "Indecision candle: symmetrical upper and lower shadows indicate hesitation."
                })

            # If any pattern matched, record the highest conviction pattern
            if patterns_for_bar:
                # Prioritize multi-candle patterns over single-candle
                best_pattern = patterns_for_bar[0]
                data.at[i, "pattern_name"] = best_pattern["name"]
                data.at[i, "pattern_type"] = best_pattern["type"]
                data.at[i, "pattern_signal"] = best_pattern["signal"]
                data.at[i, "pattern_desc"] = best_pattern["desc"]

                patterns_detected.append({
                    "index": i,
                    "date": str(c0["trading_date"]),
                    "symbol": c0.get("symbol", c0.get("index_symbol", "UNKNOWN")),
                    "open": float(c0["open"]),
                    "high": float(c0["high"]),
                    "low": float(c0["low"]),
                    "close": float(c0["close"]),
                    "volume": int(c0["volume"]),
                    "pattern": best_pattern["name"],
                    "type": best_pattern["type"],
                    "signal": best_pattern["signal"],
                    "description": best_pattern["desc"]
                })

        return data, patterns_detected
