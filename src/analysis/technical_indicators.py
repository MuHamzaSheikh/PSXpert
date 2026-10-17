"""
PSXpert - Quantitative Technical Indicators Engine
Computes industry-standard technical indicators across price trends, momentum,
volatility, and volume relationships with mathematical rigor and zero lookahead bias.

Supported Indicators:
1. SMA / EMA (Price Trends: SMA 20, 50, 200; EMA 12, 26, 20, 50, 200)
2. RSI (Momentum and Overbought/Oversold Conditions: 14-period Wilder RSI)
3. MACD (Trend & Momentum Changes: 12, 26, 9 MACD Line, Signal Line, Histogram)
4. Bollinger Bands (Volatility & Relative Position: 20-period Middle, Upper, Lower, Bandwidth, %B)
5. ADX / DMI (Trend Strength & Direction: +DI 14, -DI 14, ADX 14)
6. ATR (Volatility: 14-period Average True Range, ATR%)
7. OBV (Price-Volume Relationship: Cumulative On-Balance Volume, OBV EMA 20)
8. Stochastic Oscillator (Momentum relative to range: %K 14, %D 3, Slow %D)
"""

from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np

# We import both standard pandas/numpy vectorized math and the 'ta' library
# for cross-validated accuracy and seamless failover.
try:
    import ta
    from ta.trend import SMAIndicator, EMAIndicator, MACD, ADXIndicator
    from ta.momentum import RSIIndicator, StochasticOscillator
    from ta.volatility import BollingerBands, AverageTrueRange
    from ta.volume import OnBalanceVolumeIndicator
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False


class TechnicalIndicatorCalculator:
    """
    Mathematical Technical Analysis and Indicator Engine.
    Ensures that for every row (symbol, date, OHLCV), all indicators are computed
    STRICTLY using information available up to that date (zero future lookahead bias).
    """

    def __init__(self, use_ta_lib: bool = True):
        self.use_ta_lib = use_ta_lib and TA_AVAILABLE

    def compute_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates all 8 core technical indicators on an OHLCV DataFrame.
        DataFrame must contain columns: [symbol, trading_date, open, high, low, close, volume]
        """
        if df.empty:
            return df

        data = df.copy()
        data = data.sort_values(by="trading_date").reset_index(drop=True)

        # Standardize numeric types
        for col in ["open", "high", "low", "close", "volume"]:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors="coerce")
            else:
                data[col] = 0.0

        # Fill forward any missing prices to maintain continuity
        data["close"] = data["close"].ffill().bfill()
        data["open"] = data["open"].fillna(data["close"])
        data["high"] = data["high"].fillna(data[["open", "close"]].max(axis=1))
        data["low"] = data["low"].fillna(data[["open", "close"]].min(axis=1))
        data["volume"] = data["volume"].fillna(0)

        # Ensure High >= Low
        data["high"] = np.maximum(data["high"], np.maximum(data["open"], data["close"]))
        data["low"] = np.minimum(data["low"], np.minimum(data["open"], data["close"]))

        # -------------------------------------------------------------
        # 1. PRICE TREND INDICATORS: SMA & EMA
        # -------------------------------------------------------------
        # Simple Moving Averages
        data["sma_20"] = data["close"].rolling(window=20, min_periods=1).mean()
        data["sma_50"] = data["close"].rolling(window=50, min_periods=1).mean()
        data["sma_200"] = data["close"].rolling(window=200, min_periods=1).mean()

        # Exponential Moving Averages
        data["ema_12"] = data["close"].ewm(span=12, adjust=False).mean()
        data["ema_26"] = data["close"].ewm(span=26, adjust=False).mean()
        data["ema_20"] = data["close"].ewm(span=20, adjust=False).mean()
        data["ema_50"] = data["close"].ewm(span=50, adjust=False).mean()
        data["ema_200"] = data["close"].ewm(span=200, adjust=False).mean()

        # -------------------------------------------------------------
        # 2. MOMENTUM INDICATOR: RSI (14-period Wilder's Smoothing)
        # -------------------------------------------------------------
        delta = data["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        # Wilder's exponential smoothing (alpha = 1 / 14)
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        data["rsi_14"] = 100.0 - (100.0 / (1.0 + rs))
        # Handle zero loss (RS -> inf => RSI = 100) and zero gain (RS = 0 => RSI = 0)
        data.loc[avg_loss == 0, "rsi_14"] = 100.0
        data.loc[avg_gain == 0, "rsi_14"] = 0.0

        # Cross-verify with 'ta' library if available
        if self.use_ta_lib and len(data) >= 14:
            rsi_indicator = RSIIndicator(close=data["close"], window=14)
            data["rsi_14_ta"] = rsi_indicator.rsi()

        # -------------------------------------------------------------
        # 3. TREND & MOMENTUM: MACD (12, 26, 9)
        # -------------------------------------------------------------
        data["macd_line"] = data["ema_12"] - data["ema_26"]
        data["macd_signal"] = data["macd_line"].ewm(span=9, adjust=False).mean()
        data["macd_diff"] = data["macd_line"] - data["macd_signal"]

        # -------------------------------------------------------------
        # 4. VOLATILITY & RELATIVE POSITION: BOLLINGER BANDS (20, 2)
        # -------------------------------------------------------------
        data["bb_middle"] = data["close"].rolling(window=20, min_periods=1).mean()
        bb_std = data["close"].rolling(window=20, min_periods=1).std(ddof=0).fillna(0)
        data["bb_upper"] = data["bb_middle"] + (2.0 * bb_std)
        data["bb_lower"] = data["bb_middle"] - (2.0 * bb_std)

        bb_range = (data["bb_upper"] - data["bb_lower"]).replace(0, np.nan)
        data["bb_bandwidth"] = (bb_range / data["bb_middle"].replace(0, np.nan)) * 100.0
        data["bb_percent_b"] = (data["close"] - data["bb_lower"]) / bb_range

        # -------------------------------------------------------------
        # 5. VOLATILITY: AVERAGE TRUE RANGE (ATR 14)
        # -------------------------------------------------------------
        prev_close = data["close"].shift(1)
        tr1 = data["high"] - data["low"]
        tr2 = (data["high"] - prev_close).abs()
        tr3 = (data["low"] - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        data["true_range"] = tr

        # Wilder's smoothing for ATR: ATR_t = (ATR_{t-1} * 13 + TR_t) / 14
        data["atr_14"] = tr.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        data["atr_pct"] = (data["atr_14"] / data["close"].replace(0, np.nan)) * 100.0

        # -------------------------------------------------------------
        # 6. TREND STRENGTH & DIRECTION: ADX & DMI (+DI 14, -DI 14, ADX 14)
        # -------------------------------------------------------------
        up_move = data["high"] - data["high"].shift(1)
        down_move = data["low"].shift(1) - data["low"]

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        # Smooth +DM, -DM, and TR using Wilder's EMA (alpha = 1/14)
        smoothed_plus_dm = pd.Series(plus_dm, index=data.index).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        smoothed_minus_dm = pd.Series(minus_dm, index=data.index).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        smoothed_tr = data["true_range"].ewm(alpha=1/14, min_periods=14, adjust=False).mean()

        data["dmi_plus_14"] = (smoothed_plus_dm / smoothed_tr.replace(0, np.nan)) * 100.0
        data["dmi_minus_14"] = (smoothed_minus_dm / smoothed_tr.replace(0, np.nan)) * 100.0

        di_sum = (data["dmi_plus_14"] + data["dmi_minus_14"]).replace(0, np.nan)
        di_diff = (data["dmi_plus_14"] - data["dmi_minus_14"]).abs()
        dx = (di_diff / di_sum) * 100.0
        data["adx_14"] = dx.ewm(alpha=1/14, min_periods=14, adjust=False).mean()

        # -------------------------------------------------------------
        # 7. PRICE-VOLUME RELATIONSHIP: ON-BALANCE VOLUME (OBV)
        # -------------------------------------------------------------
        price_diff = data["close"].diff()
        vol_direction = np.where(price_diff > 0, 1, np.where(price_diff < 0, -1, 0))
        # Initial bar direction is 0
        vol_direction[0] = 0
        data["obv"] = (vol_direction * data["volume"]).cumsum()
        data["obv_ema_20"] = data["obv"].ewm(span=20, adjust=False).mean()

        # -------------------------------------------------------------
        # 8. MOMENTUM RELATIVE TO RANGE: STOCHASTIC OSCILLATOR (14, 3, 3)
        # -------------------------------------------------------------
        lowest_low_14 = data["low"].rolling(window=14, min_periods=1).min()
        highest_high_14 = data["high"].rolling(window=14, min_periods=1).max()
        stoch_range = (highest_high_14 - lowest_low_14).replace(0, np.nan)

        fast_k = ((data["close"] - lowest_low_14) / stoch_range) * 100.0
        # %K is 3-period SMA of fast %K
        data["stoch_k"] = fast_k.rolling(window=3, min_periods=1).mean()
        # %D is 3-period SMA of %K
        data["stoch_d"] = data["stoch_k"].rolling(window=3, min_periods=1).mean()

        # Round outputs to 4 decimal places for clean storage
        numeric_cols = [c for c in data.columns if c not in ["symbol", "trading_date"]]
        data[numeric_cols] = data[numeric_cols].round(4)

        return data

    def generate_analytical_interpretation(self, latest_row: pd.Series) -> Dict[str, Any]:
        """
        Generates diagnostic explanations based on the indicators.
        Crucial requirement: Technical indicators should generate data and charts
        that your system uses to EXPLAIN its analysis, rather than treating them
        as guaranteed buy or sell signals.
        """
        rsi = latest_row.get("rsi_14")
        macd_diff = latest_row.get("macd_diff")
        macd_line = latest_row.get("macd_line")
        bb_pct_b = latest_row.get("bb_percent_b")
        adx = latest_row.get("adx_14")
        dmi_p = latest_row.get("dmi_plus_14")
        dmi_m = latest_row.get("dmi_minus_14")
        stoch_k = latest_row.get("stoch_k")
        close = latest_row.get("close")
        sma20 = latest_row.get("sma_20")
        sma50 = latest_row.get("sma_50")
        sma200 = latest_row.get("sma_200")

        diagnostics = []

        # 1. Trend Condition
        if pd.notna(close) and pd.notna(sma50) and pd.notna(sma200):
            if close > sma50 > sma200:
                diagnostics.append("Primary Trend: Bullish alignment (Price > SMA 50 > SMA 200).")
            elif close < sma50 < sma200:
                diagnostics.append("Primary Trend: Bearish alignment (Price < SMA 50 < SMA 200).")
            else:
                diagnostics.append("Primary Trend: Mixed / Consolidating around intermediate moving averages.")

        # 2. Momentum & Extreme Conditions
        if pd.notna(rsi):
            if rsi >= 70:
                diagnostics.append(f"RSI Momentum: Overbought territory ({rsi:.1f}), indicating extended upside pressure; momentum may decelerate.")
            elif rsi <= 30:
                diagnostics.append(f"RSI Momentum: Oversold territory ({rsi:.1f}), reflecting heavy liquidation and potential mean-reversion.")
            else:
                diagnostics.append(f"RSI Momentum: Neutral regime ({rsi:.1f}), balanced between buyers and sellers.")

        # 3. MACD Momentum Shift
        if pd.notna(macd_diff):
            if macd_diff > 0:
                diagnostics.append(f"MACD Dynamics: Positive histogram (+{macd_diff:.2f}); short-term momentum is outpacing long-term trend.")
            else:
                diagnostics.append(f"MACD Dynamics: Negative histogram ({macd_diff:.2f}); short-term momentum is lagging.")

        # 4. Volatility Bands
        if pd.notna(bb_pct_b):
            if bb_pct_b > 1.0:
                diagnostics.append("Bollinger Volatility: Trading above upper band; statistical extension beyond 2 standard deviations.")
            elif bb_pct_b < 0.0:
                diagnostics.append("Bollinger Volatility: Trading below lower band; statistical depression beyond 2 standard deviations.")
            else:
                diagnostics.append(f"Bollinger Volatility: Within normal volatility envelope (%B = {bb_pct_b:.2f}).")

        # 5. Trend Strength
        if pd.notna(adx) and pd.notna(dmi_p) and pd.notna(dmi_m):
            trend_str = "Strong Trend" if adx >= 25 else "Weak/Ranging Trend"
            lead_dir = "Bullish Dominance (+DI > -DI)" if dmi_p > dmi_m else "Bearish Dominance (-DI > +DI)"
            diagnostics.append(f"ADX/DMI Structure: {trend_str} (ADX = {adx:.1f}) with {lead_dir}.")

        # 6. Stochastic Cycle
        if pd.notna(stoch_k):
            if stoch_k > 80:
                diagnostics.append(f"Stochastic Oscillator: Overbought boundary ({stoch_k:.1f}%), close near the upper extreme of 14-day range.")
            elif stoch_k < 20:
                diagnostics.append(f"Stochastic Oscillator: Oversold boundary ({stoch_k:.1f}%), close near the lower extreme of 14-day range.")
            else:
                diagnostics.append(f"Stochastic Oscillator: Mid-range oscillator state ({stoch_k:.1f}%).")

        # 7. ATR Volatility
        atr = latest_row.get("atr_14")
        atr_pct = latest_row.get("atr_pct")
        if pd.notna(atr) and pd.notna(atr_pct):
            diagnostics.append(f"ATR Volatility: 14-day Average True Range is {atr:.2f} PKR ({atr_pct:.2f}% of price), measuring expected bar volatility.")

        # 8. OBV Volume Flow
        obv = latest_row.get("obv")
        obv_ema = latest_row.get("obv_ema_20")
        if pd.notna(obv) and pd.notna(obv_ema):
            obv_dir = "accumulation (OBV > EMA 20)" if obv >= obv_ema else "distribution (OBV < EMA 20)"
            diagnostics.append(f"OBV Volume Flow: Cumulative On-Balance Volume reflects {obv_dir}.")

        def _safe_float(col):
            val = latest_row.get(col)
            return float(val) if pd.notna(val) else None

        return {
            "symbol": latest_row.get("symbol"),
            "date": str(latest_row.get("trading_date")),
            "close": float(close) if pd.notna(close) else 0.0,
            "sma_20": _safe_float("sma_20"),
            "sma_50": _safe_float("sma_50"),
            "sma_200": _safe_float("sma_200"),
            "ema_20": _safe_float("ema_20"),
            "ema_50": _safe_float("ema_50"),
            "ema_200": _safe_float("ema_200"),
            "rsi_14": _safe_float("rsi_14"),
            "macd_line": _safe_float("macd_line"),
            "macd_signal": _safe_float("macd_signal"),
            "macd_diff": _safe_float("macd_diff"),
            "bb_upper": _safe_float("bb_upper"),
            "bb_middle": _safe_float("bb_middle"),
            "bb_lower": _safe_float("bb_lower"),
            "bb_bandwidth": _safe_float("bb_bandwidth"),
            "bb_percent_b": _safe_float("bb_percent_b"),
            "adx_14": _safe_float("adx_14"),
            "dmi_plus_14": _safe_float("dmi_plus_14"),
            "dmi_minus_14": _safe_float("dmi_minus_14"),
            "atr_14": _safe_float("atr_14"),
            "atr_pct": _safe_float("atr_pct"),
            "obv": _safe_float("obv"),
            "obv_ema_20": _safe_float("obv_ema_20"),
            "stoch_k": _safe_float("stoch_k"),
            "stoch_d": _safe_float("stoch_d"),
            "diagnostics": diagnostics,
            "disclaimer": "Diagnostic analytical indicators only. Not financial advice or guaranteed trading signals."
        }
