"""
Daily Predictive Feature & Multi-Horizon Target Dataset Builder (Steps 2, 4, 5).

Produces one historical observation per (symbol, trading_date) aligned strictly
to the KSE-100 exchange calendar, incorporating all 8 required feature domains
and transaction-cost + volatility calibrated 3-class direction targets.
"""

import gc
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from sqlalchemy import text

from src.predictive_data.splits import build_chronological_splits
from src.predictive_data.regime_causal import CausalMarketRegimeHMM
from src.predictive_data.point_in_time import (
    load_clean_corporate_actions,
    adjust_splits_and_flag_glitches,
    build_point_in_time_fundamentals,
    build_point_in_time_news_features,
)


PSX_TX_COST_ROUNDTRIP = 0.0050  # 50 bps all-in PSX round-trip (brokerage, levies, tax, slippage)
VOL_MULTIPLIER_K = 0.35         # Causal threshold k * sigma_daily * sqrt(h)


def _compute_causal_wilder_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.where(~((avg_loss == 0.0) & (avg_gain > 0.0)), 100.0)
    rsi = rsi.where(~((avg_gain == 0.0) & (avg_loss > 0.0)), 0.0)
    rsi = rsi.where(~((avg_gain == 0.0) & (avg_loss == 0.0)), 50.0)
    return rsi


def _compute_stock_features_and_candlesticks(sym_df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes strictly causal technical indicators, liquidity/volatility metrics,
    and true-OHLC candlestick pattern features for a single symbol sorted chronologically.
    Zero .bfill() and strict min_periods warmup.
    """
    d = sym_df.copy()
    n = len(d)

    o = d["adj_open"]
    h = d["adj_high"]
    l = d["adj_low"]
    c = d["adj_close"]
    v = d["volume"].astype(np.float64)

    # Quality flags BEFORE indicator logic
    d["is_true_ohlc"] = (
        (d["raw_high"] > d["raw_low"])
        & (d["raw_open"] > 0)
        & (d["raw_high"] >= np.maximum(d["raw_open"], d["raw_close"]))
        & (d["raw_low"] <= np.minimum(d["raw_open"], d["raw_close"]))
    ).astype(np.int8)
    d["is_zero_volume"] = (v <= 0).astype(np.int8)

    # Strict bar-local OHLC envelope sanitation on adj_* (zero cross-date leakage)
    o = o.where(o > 0, c)
    h = np.maximum(h.where(h > 0, c), np.maximum(o, c))
    l = np.minimum(l.where(l > 0, c), np.minimum(o, c))
    d["adj_open"] = o
    d["adj_high"] = h
    d["adj_low"] = l

    # Mask multi-year trading gaps (> 15 missed sessions) so prev_close isn't stale years
    is_contiguous = d["calendar_gap_days"] <= 15
    prev_c = c.shift(1)
    prev_h = h.shift(1)
    prev_l = l.shift(1)

    # Group 8: Returns & Volatility (strictly guard multi-session listing/trading gaps)
    d["ret_1d"] = np.where(is_contiguous & (prev_c > 0), (c / prev_c) - 1.0, np.nan)
    d["log_ret_1d"] = np.where(is_contiguous & (prev_c > 0) & (c > 0), np.log(c / prev_c), np.nan)
    cal_s = d["cal_idx"]
    for k in (2, 5, 10, 20, 60):
        max_lag_span = k + max(3, k // 4)
        k_contiguous = (cal_s - cal_s.shift(k)) <= max_lag_span
        c_k = c.shift(k)
        d[f"ret_{k}d"] = np.where(k_contiguous & (c_k > 0), (c / c_k) - 1.0, np.nan)

    d["vol_5d"] = d["log_ret_1d"].rolling(5, min_periods=5).std()
    d["vol_20d"] = d["log_ret_1d"].rolling(20, min_periods=15).std()
    d["vol_60d"] = d["log_ret_1d"].rolling(60, min_periods=40).std()
    d["vol_ratio_5_20"] = d["vol_5d"] / d["vol_20d"].replace(0.0, np.nan)

    # Parkinson range volatility (masked if < 50% true OHLC bars in trailing 20d)
    hl_log_sq = (np.log(h / l.replace(0.0, np.nan))) ** 2
    park_daily = np.sqrt(hl_log_sq / (4.0 * np.log(2.0)))
    true_ohlc_share_20 = d["is_true_ohlc"].rolling(20, min_periods=10).mean()
    d["parkinson_vol_20d"] = np.where(
        true_ohlc_share_20 >= 0.50,
        park_daily.rolling(20, min_periods=10).mean(),
        np.nan,
    )

    d["overnight_gap_pct"] = np.where(
        (d["is_true_ohlc"] == 1) & is_contiguous & (prev_c > 0),
        (o - prev_c) / prev_c,
        np.nan,
    )
    d["intraday_ret_pct"] = np.where(
        (d["is_true_ohlc"] == 1) & (o > 0),
        (c - o) / o,
        np.nan,
    )

    # Group 8: Liquidity & Microstructure Proxies
    turnover = d["raw_close"] * v
    d["turnover_pkr"] = turnover
    d["log_volume"] = np.log1p(np.maximum(v, 0.0))
    d["log_turnover_pkr"] = np.log1p(np.maximum(turnover, 0.0))

    vol_sma20 = v.rolling(20, min_periods=10).mean()
    d["trailing_20d_adv_pkr"] = turnover.rolling(20, min_periods=10).mean()
    d["volume_ratio_20d"] = np.where(vol_sma20 > 0, v / vol_sma20, np.nan)

    # Amihud (2002) Illiquidity: |ret_1d| / (turnover_pkr in millions)
    amihud_daily = np.where(turnover > 1e3, np.abs(d["ret_1d"]) / (turnover / 1e6), np.nan)
    d["amihud_illiquidity_20d"] = pd.Series(amihud_daily, index=d.index).rolling(20, min_periods=10).mean()
    d["zero_volume_days_20d"] = d["is_zero_volume"].rolling(20, min_periods=5).sum()
    d["hl_spread_pct"] = np.where((d["is_true_ohlc"] == 1) & (c > 0), (h - l) / c, np.nan)

    # Group 2: Technical Indicators (strictly causal min_periods, NO .bfill())
    sma20 = c.rolling(20, min_periods=20).mean()
    sma50 = c.rolling(50, min_periods=50).mean()
    sma200 = c.rolling(200, min_periods=200).mean()
    ema12 = c.ewm(span=12, min_periods=12, adjust=False).mean()
    ema26 = c.ewm(span=26, min_periods=26, adjust=False).mean()
    ema20 = c.ewm(span=20, min_periods=20, adjust=False).mean()
    ema50 = c.ewm(span=50, min_periods=50, adjust=False).mean()
    ema200 = c.ewm(span=200, min_periods=200, adjust=False).mean()

    d["sma_20"] = sma20
    d["sma_50"] = sma50
    d["sma_200"] = sma200
    d["ema_12"] = ema12
    d["ema_26"] = ema26
    d["ema_20"] = ema20
    d["ema_50"] = ema50
    d["ema_200"] = ema200

    # Price-normalized stationary trend features
    d["dist_sma_20"] = (c / sma20) - 1.0
    d["dist_sma_50"] = (c / sma50) - 1.0
    d["dist_sma_200"] = (c / sma200) - 1.0
    d["dist_ema_20"] = (c / ema20) - 1.0
    d["ema_20_50_spread"] = (ema20 / ema50) - 1.0
    d["ema_50_200_spread"] = (ema50 / ema200) - 1.0

    # RSI (14)
    d["rsi_14"] = _compute_causal_wilder_rsi(c, 14)

    # MACD (12, 26, 9)
    macd_line = ema12 - ema26
    macd_signal = macd_line.ewm(span=9, min_periods=9, adjust=False).mean()
    macd_diff = macd_line - macd_signal
    d["macd_line"] = macd_line
    d["macd_signal"] = macd_signal
    d["macd_diff"] = macd_diff
    d["macd_diff_pct"] = np.where(c > 0, macd_diff / c, np.nan)

    # Bollinger Bands (20, 2)
    bb_mid = sma20
    bb_std = c.rolling(20, min_periods=20).std(ddof=0)
    bb_up = bb_mid + (2.0 * bb_std)
    bb_low = bb_mid - (2.0 * bb_std)
    bb_rng = (bb_up - bb_low).replace(0.0, np.nan)
    d["bb_middle"] = bb_mid
    d["bb_upper"] = bb_up
    d["bb_lower"] = bb_low
    d["bb_bandwidth"] = (bb_rng / bb_mid.replace(0.0, np.nan)) * 100.0
    d["bb_percent_b"] = (c - bb_low) / bb_rng

    # ATR (14) & ADX / DMI (14)
    tr1 = h - l
    tr2 = (h - prev_c).abs()
    tr3 = (l - prev_c).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    d["atr_14"] = tr.ewm(alpha=1.0 / 14.0, min_periods=14, adjust=False).mean()
    d["atr_pct"] = (d["atr_14"] / c.replace(0.0, np.nan)) * 100.0

    up_move = h - prev_h
    down_move = prev_l - l
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=d.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=d.index)
    sm_tr = tr.ewm(alpha=1.0 / 14.0, min_periods=14, adjust=False).mean().replace(0.0, np.nan)
    d["dmi_plus_14"] = (plus_dm.ewm(alpha=1.0 / 14.0, min_periods=14, adjust=False).mean() / sm_tr) * 100.0
    d["dmi_minus_14"] = (minus_dm.ewm(alpha=1.0 / 14.0, min_periods=14, adjust=False).mean() / sm_tr) * 100.0
    di_sum = (d["dmi_plus_14"] + d["dmi_minus_14"]).replace(0.0, np.nan)
    dx = ((d["dmi_plus_14"] - d["dmi_minus_14"]).abs() / di_sum) * 100.0
    d["adx_14"] = dx.ewm(alpha=1.0 / 14.0, min_periods=14, adjust=False).mean()
    d["dmi_diff"] = d["dmi_plus_14"] - d["dmi_minus_14"]

    # OBV (plus stationary z-score over 20d)
    p_diff = c.diff()
    v_dir = np.where(p_diff > 0, 1.0, np.where(p_diff < 0, -1.0, 0.0))
    if n > 0:
        v_dir[0] = 0.0
    obv = pd.Series(v_dir * v, index=d.index).cumsum()
    obv_sma20 = obv.rolling(20, min_periods=20).mean()
    obv_std20 = obv.rolling(20, min_periods=20).std().replace(0.0, np.nan)
    d["obv"] = obv
    d["obv_zscore_20"] = (obv - obv_sma20) / obv_std20

    # Stochastic Oscillator (14, 3, 3)
    low14 = l.rolling(14, min_periods=14).min()
    high14 = h.rolling(14, min_periods=14).max()
    fast_k = ((c - low14) / (high14 - low14).replace(0.0, np.nan)) * 100.0
    d["stoch_k"] = fast_k.rolling(3, min_periods=3).mean()
    d["stoch_d"] = d["stoch_k"].rolling(3, min_periods=3).mean()
    d["stoch_k_minus_d"] = d["stoch_k"] - d["stoch_d"]

    # Group 3: Vectorized Causal Candlestick Anatomy & Patterns (True-OHLC guarded)
    body = (c - o).abs()
    rng = (h - l)
    rng_safe = rng.replace(0.0, np.nan)
    up_sh = h - np.maximum(o, c)
    lo_sh = np.minimum(o, c) - l

    is_ohlc = d["is_true_ohlc"] == 1
    d["candle_body_pct"] = np.where(is_ohlc & (c > 0), (c - o) / c, np.nan)
    d["candle_range_pct"] = np.where(is_ohlc & (c > 0), rng / c, np.nan)
    d["upper_shadow_ratio"] = np.where(is_ohlc, up_sh / rng_safe, np.nan)
    d["lower_shadow_ratio"] = np.where(is_ohlc, lo_sh / rng_safe, np.nan)
    d["body_to_range_ratio"] = np.where(is_ohlc, body / rng_safe, np.nan)
    d["close_position_in_range"] = np.where(is_ohlc, (c - l) / rng_safe, np.nan)

    avg_body20 = body.rolling(20, min_periods=20).mean().fillna(body)
    is_green = c > o
    is_red = c < o
    is_doji = is_ohlc & (body <= (rng_safe * 0.10))
    trend_up = c > c.shift(3)
    trend_down = c < c.shift(3)

    # Lagged bars (strictly c1 = t-1, c2 = t-2)
    o1, h1, l1, c1, b1, g1, r1 = o.shift(1), h.shift(1), l.shift(1), c.shift(1), body.shift(1), is_green.shift(1, fill_value=False), is_red.shift(1, fill_value=False)
    o2, c2, b2, g2, r2, ab2 = o.shift(2), c.shift(2), body.shift(2), is_green.shift(2, fill_value=False), is_red.shift(2, fill_value=False), avg_body20.shift(2)
    ab1 = avg_body20.shift(1)
    u1, lo1 = up_sh.shift(1), lo_sh.shift(1)
    ohlc_3 = is_ohlc & (d["is_true_ohlc"].shift(1, fill_value=0) == 1) & (d["is_true_ohlc"].shift(2, fill_value=0) == 1)
    ohlc_2 = is_ohlc & (d["is_true_ohlc"].shift(1, fill_value=0) == 1)

    # Pattern masks matching CandlestickPatternDetector hierarchy
    morning_star = ohlc_3 & r2 & (b2 > ab2 * 0.7) & (b1 < b2 * 0.5) & (np.minimum(o1, c1) <= c2) & is_green & (c >= (o2 + c2) / 2.0)
    evening_star = ohlc_3 & g2 & (b2 > ab2 * 0.7) & (b1 < b2 * 0.5) & (np.maximum(o1, c1) >= c2) & is_red & (c <= (o2 + c2) / 2.0)
    three_white = ohlc_3 & g2 & g1 & is_green & (c > c1) & (c1 > c2) & (o > o1) & (o1 > o2) & (up_sh <= body * 0.4) & (u1 <= b1 * 0.4)
    three_black = ohlc_3 & r2 & r1 & is_red & (c < c1) & (c1 < c2) & (o < o1) & (o1 < o2) & (lo_sh <= body * 0.4) & (lo1 <= b1 * 0.4)

    bull_engulf = ohlc_2 & r1 & is_green & (o <= c1) & (c >= o1) & (body > b1)
    bear_engulf = ohlc_2 & g1 & is_red & (o >= c1) & (c <= o1) & (body > b1)
    piercing = ohlc_2 & r1 & is_green & (o < l1) & (c > (o1 + c1) / 2.0) & (c < o1)
    dark_cloud = ohlc_2 & g1 & is_red & (o > h1) & (c < (o1 + c1) / 2.0) & (c > o1)
    bull_harami = ohlc_2 & r1 & is_green & (b1 > ab1 * 0.8) & (o >= c1) & (c <= o1) & (body < b1 * 0.6)
    bear_harami = ohlc_2 & g1 & is_red & (b1 > ab1 * 0.8) & (o <= c1) & (c >= o1) & (body < b1 * 0.6)

    hammer = is_ohlc & (lo_sh >= 2.0 * body) & (up_sh <= rng * 0.15) & (body > 0) & trend_down
    inv_hammer = is_ohlc & (up_sh >= 2.0 * body) & (lo_sh <= rng * 0.15) & (body > 0) & trend_down
    shooting_star = is_ohlc & (up_sh >= 2.0 * body) & (lo_sh <= rng * 0.15) & (body > 0) & trend_up
    hanging_man = is_ohlc & (lo_sh >= 2.0 * body) & (up_sh <= rng * 0.15) & (body > 0) & trend_up
    bull_marubozu = is_ohlc & is_green & (body >= rng * 0.88) & (body >= avg_body20 * 1.3)
    bear_marubozu = is_ohlc & is_red & (body >= rng * 0.88) & (body >= avg_body20 * 1.3)
    dragonfly = is_doji & (lo_sh >= rng * 0.70) & (up_sh <= rng * 0.10)
    gravestone = is_doji & (up_sh >= rng * 0.70) & (lo_sh <= rng * 0.10)
    spinning_top = is_ohlc & (body <= rng * 0.30) & (up_sh >= rng * 0.25) & (lo_sh >= rng * 0.25)

    conds = [
        morning_star, evening_star, three_white, three_black,
        bull_engulf, bear_engulf, piercing, dark_cloud, bull_harami, bear_harami,
        hammer, inv_hammer, shooting_star, hanging_man, bull_marubozu, bear_marubozu,
        dragonfly, gravestone, is_doji, spinning_top,
    ]
    names = [
        "Morning Star", "Evening Star", "Three White Soldiers", "Three Black Crows",
        "Bullish Engulfing", "Bearish Engulfing", "Piercing Line", "Dark Cloud Cover", "Bullish Harami", "Bearish Harami",
        "Hammer", "Inverted Hammer", "Shooting Star", "Hanging Man", "Bullish Marubozu", "Bearish Marubozu",
        "Dragonfly Doji", "Gravestone Doji", "Doji", "Spinning Top",
    ]
    signals = [
        2, -2, 2, -2,
        1, -1, 1, -1, 1, -1,
        1, 1, -1, -1, 1, -1,
        1, -1, 0, 0,
    ]
    d["candlestick_pattern_name"] = np.select(conds, names, default="NONE")
    sig_series = pd.Series(np.select(conds, signals, default=0), index=d.index, dtype=np.int8)
    d["candlestick_pattern_signal_num"] = sig_series
    d["is_bullish_pattern"] = (sig_series > 0).astype(np.int8)
    d["is_bearish_pattern"] = (sig_series < 0).astype(np.int8)
    d["is_doji_true_ohlc"] = is_doji.astype(np.int8)
    d["bullish_patterns_5d"] = d["is_bullish_pattern"].rolling(5, min_periods=1).sum().astype(np.int8)
    d["bearish_patterns_5d"] = d["is_bearish_pattern"].rolling(5, min_periods=1).sum().astype(np.int8)

    # Drop duplicate raw OHLC names cleanly and downcast float64 indicators to float32
    for tmp_c in ("open", "high", "low", "close"):
        if tmp_c in d.columns:
            d = d.drop(columns=[tmp_c])
    keep_f64 = {"market_cap", "turnover_pkr", "trailing_20d_adv_pkr", "obv"}
    for col in d.columns:
        if col not in keep_f64 and pd.api.types.is_float_dtype(d[col]):
            d[col] = d[col].astype(np.float32)

    return d


def _build_targets_for_symbol(sym_df: pd.DataFrame) -> pd.DataFrame:
    """
    Constructs future 1d, 5d, and 20d return & 3-class direction targets using
    adjusted close prices, exact trading-calendar alignment checks, glitch masking,
    and causal trailing volatility + realistic PSX transaction-cost thresholds.
    """
    c = sym_df["adj_close"].to_numpy(dtype=np.float64)
    cal = sym_df["cal_idx"].to_numpy(dtype=np.int64)
    glitch = sym_df["has_price_glitch_flag"].to_numpy(dtype=bool)
    dates = sym_df["trading_date"].to_numpy()
    vol20 = sym_df["vol_20d"].to_numpy(dtype=np.float64)

    n = len(sym_df)
    sigma_causal = np.maximum(np.where(np.isnan(vol20), np.nan, vol20), 0.005)

    res = pd.DataFrame({
        "symbol": sym_df["symbol"].values,
        "trading_date": dates,
        "cal_idx": cal,
        "split": sym_df["split"].values,
        "fundamentals_regime_split": sym_df["fundamentals_regime_split"].values,
        "corp_action_adj_factor": sym_df["corp_action_adj_factor"].values,
        "is_corp_action_exdate": sym_df["is_corp_action_exdate"].astype(np.int8).values,
        "has_price_glitch_flag": glitch.astype(np.int8),
    })

    # Cumulative glitch prefix sum so checking any glitch in (t, t+h] is O(1)!
    glitch_cumsum = np.concatenate(([0], np.cumsum(glitch.astype(np.int32))))

    horizon_configs = [
        (1, 1),    # 1d: exact 1 PSX session forward
        (5, 6),    # 5d: <= 6 calendar sessions (tolerates 1 non-traded session max)
        (20, 23),  # 20d: <= 23 calendar sessions
    ]

    for h, max_cal_diff in horizon_configs:
        fut_c = np.full(n, np.nan, dtype=np.float64)
        fut_cal_diff = np.full(n, -1, dtype=np.int64)
        fut_end_date = np.full(n, None, dtype=object)
        has_fut_glitch = np.ones(n, dtype=bool)

        if n > h:
            fut_c[:-h] = c[h:]
            fut_cal_diff[:-h] = cal[h:] - cal[:-h]
            fut_end_date[:-h] = dates[h:]
            # Glitches strictly inside (t, t+h] -> glitch_cumsum[t+h+1] - glitch_cumsum[t+1]
            has_fut_glitch[:-h] = (glitch_cumsum[h + 1:] - glitch_cumsum[1:-h]) > 0

        raw_ret = np.where((c > 0) & (fut_c > 0), (fut_c / c) - 1.0, np.nan)
        thresh = PSX_TX_COST_ROUNDTRIP + VOL_MULTIPLIER_K * sigma_causal * np.sqrt(h)

        valid = (
            (fut_cal_diff >= h)
            & (fut_cal_diff <= max_cal_diff)
            & (~has_fut_glitch)
            & (~glitch)
            & (~np.isnan(raw_ret))
            & (~np.isnan(thresh))
        )

        # Mask anomalous returns where target_valid is False
        ret_clean = np.where(valid, raw_ret, np.nan)
        dir_num = np.where(
            ~valid,
            np.nan,
            np.where(ret_clean > thresh, 1.0, np.where(ret_clean < -thresh, -1.0, 0.0)),
        )
        dir_lbl = np.where(
            ~valid,
            None,
            np.where(dir_num == 1.0, "UP", np.where(dir_num == -1.0, "DOWN", "NEUTRAL")),
        )

        res[f"target_ret_{h}d"] = np.round(ret_clean, 6)
        res[f"target_log_ret_{h}d"] = np.where(valid, np.round(np.log1p(ret_clean), 6), np.nan)
        res[f"target_threshold_{h}d"] = np.round(thresh, 6)
        res[f"target_dir_{h}d"] = dir_num
        res[f"target_label_{h}d"] = dir_lbl
        res[f"target_valid_{h}d"] = valid.astype(np.int8)
        res[f"target_end_date_{h}d"] = fut_end_date
        res[f"target_actual_sessions_{h}d"] = fut_cal_diff

    # Overlapping label weights for multi-day horizons (Lopez de Prado concurrency weight 1/h)
    res["sample_uniqueness_5d"] = np.where(res["target_valid_5d"] == 1, 1.0 / 5.0, 0.0)
    res["sample_uniqueness_20d"] = np.where(res["target_valid_20d"] == 1, 1.0 / 20.0, 0.0)
    return res


def build_daily_forecasting_datasets(engine) -> Dict[str, Any]:
    """
    Executes the full Step 2, Step 4 & Step 5 Daily Forecasting Dataset pipeline.
    Returns (features_df, targets_df, metadata).
    """
    with engine.connect() as conn:
        # 1. Load real PSX KSE-100 Trading Calendar & Index
        df_idx = pd.read_sql(
            text("""
                SELECT trading_date, close, point_change, pct_change
                FROM market_indices
                WHERE index_symbol = 'KSE100'
                ORDER BY trading_date
            """),
            conn,
        )
        df_idx["trading_date"] = pd.to_datetime(df_idx["trading_date"]).dt.date

        # Chronological splits on KSE-100 calendar
        split_info = build_chronological_splits(df_idx["trading_date"])
        cal_df = split_info["calendar_df"]
        df_idx = df_idx.merge(cal_df[["trading_date", "cal_idx", "split", "fundamentals_regime_split"]], on="trading_date", how="inner")

        # 2. Causal Market-Regime HMM (fit ONLY on TRAIN split index rows!)
        hmm = CausalMarketRegimeHMM(n_states=3, random_state=42)
        hmm.fit(df_idx[df_idx["split"] == "TRAIN"])
        hmm_daily = hmm.filter_causal_probabilities(df_idx)

        # Build authentic KSE-100 daily market index features (using authentic close only!)
        idx_feats = df_idx.sort_values("trading_date").reset_index(drop=True)
        idx_close = pd.to_numeric(idx_feats["close"], errors="coerce")
        idx_feats["kse100_close"] = idx_close
        idx_feats["kse100_ret_1d"] = idx_close.pct_change(1)
        idx_feats["kse100_ret_5d"] = idx_close.pct_change(5)
        idx_feats["kse100_ret_20d"] = idx_close.pct_change(20)
        idx_feats["kse100_log_ret_1d"] = np.log(idx_close / idx_close.shift(1))
        idx_feats["kse100_vol_20d"] = idx_feats["kse100_log_ret_1d"].rolling(20, min_periods=20).std()
        idx_sma50 = idx_close.rolling(50, min_periods=50).mean()
        idx_sma200 = idx_close.rolling(200, min_periods=200).mean()
        idx_feats["kse100_dist_sma50"] = (idx_close / idx_sma50) - 1.0
        idx_feats["kse100_dist_sma200"] = (idx_close / idx_sma200) - 1.0
        idx_feats["kse100_rsi_14"] = _compute_causal_wilder_rsi(idx_close, 14)

        idx_daily = idx_feats.merge(hmm_daily, on="trading_date", how="left")

        # 3. Load equity prices joined strictly to real PSX KSE-100 trading calendar
        # Excludes debt/Sukuk/TFC (^P0..), ETFs, preference shares, and weekend phantom fills
        q_prices = text("""
            SELECT s.symbol, s.trading_date, s.open, s.high, s.low, s.close, s.volume, s.market_cap,
                   c.sector, c.is_kse100 AS is_current_kse100, c.is_active AS is_active_listing_snapshot,
                   c.is_shariah
            FROM stock_prices s
            JOIN companies c ON s.symbol = c.symbol
            JOIN market_indices m ON s.trading_date = m.trading_date AND m.index_symbol = 'KSE100'
            WHERE s.close > 0
              AND NOT (s.symbol ~ '^P[0-9]{2}')
              AND s.symbol NOT LIKE '%ETF%'
              AND s.symbol NOT LIKE '%CPS%'
              AND s.symbol NOT LIKE '%PREF%'
            ORDER BY s.symbol, s.trading_date
        """)
        df_sp = pd.read_sql(q_prices, conn)
        df_sp["trading_date"] = pd.to_datetime(df_sp["trading_date"]).dt.date
        df_sp["is_current_kse100"] = df_sp["is_current_kse100"].astype(np.int8)
        df_sp["is_active_listing_snapshot"] = df_sp["is_active_listing_snapshot"].astype(np.int8)
        df_sp["is_shariah"] = df_sp["is_shariah"].astype(np.int8)

        # Clean valid sectors
        invalid_sectors = {"OTHER / UNCLASSIFIED", "OTHER / PSX HISTORICAL", "", "NONE", "NAN"}
        df_sp["has_valid_sector"] = (~df_sp["sector"].astype(str).str.upper().isin(invalid_sectors)).astype(np.int8)

        # 4. Corporate actions split adjustment & glitch flagging
        payouts_df, ann_actions_df = load_clean_corporate_actions(conn)
        df_sp = adjust_splits_and_flag_glitches(df_sp, cal_df, payouts_df, ann_actions_df)

        # Merge split labels onto panel
        df_sp = df_sp.merge(cal_df[["trading_date", "split", "fundamentals_regime_split"]], on="trading_date", how="left")

        # 5. Compute per-symbol technical indicators, candlesticks, volatility & liquidity features
        sym_frames = []
        target_frames = []
        for sym, grp in df_sp.groupby("symbol", sort=False):
            feat_g = _compute_stock_features_and_candlesticks(grp)
            target_frames.append(_build_targets_for_symbol(feat_g))
            # Remove retrospective audit/mask columns before appending to causal features
            feat_g = feat_g.drop(columns=["corp_action_adj_factor", "is_corp_action_exdate", "has_price_glitch_flag"])
            sym_frames.append(feat_g)

        del df_sp
        gc.collect()

        df_all = pd.concat(sym_frames, ignore_index=True)
        del sym_frames
        targets_df = pd.concat(target_frames, ignore_index=True)
        del target_frames
        gc.collect()

        # Listing age in sessions (point-in-time)
        df_all["listing_age_sessions"] = (df_all.groupby("symbol", sort=False).cumcount() + 1).astype(np.int32)

        # Narrow keys table for ALL cross-sectional, index, fundamental & news merges
        # Avoids copying/sorting all 80+ feature columns!
        keys = df_all[[
            "symbol", "trading_date", "sector", "has_valid_sector",
            "market_cap", "adj_close", "ret_1d", "ret_5d", "ret_20d",
            "log_ret_1d", "dist_sma_50", "trailing_20d_adv_pkr",
        ]].copy()
        keys["_row_id"] = np.arange(len(keys), dtype=np.int64)

        keys["trailing_20d_adv_rank"] = (
            keys.groupby("trading_date")["trailing_20d_adv_pkr"]
            .rank(ascending=False, method="min")
            .astype(np.float32)
        )
        keys["is_trailing_top100_liquid"] = (
            keys["trailing_20d_adv_rank"].notna() & (keys["trailing_20d_adv_rank"] <= 100)
        ).astype(np.int8)

        # 6. Group 7: Cross-Sectional Market Breadth & Leave-One-Out Sector Features
        keys["_clean_ret_1d"] = np.where(keys["ret_1d"].abs() <= 0.35, keys["ret_1d"], np.nan)
        keys["_clean_ret_5d"] = np.where(keys["ret_5d"].abs() <= 1.00, keys["ret_5d"], np.nan)
        keys["_clean_ret_20d"] = np.where(keys["ret_20d"].abs() <= 2.00, keys["ret_20d"], np.nan)
        keys["_above_sma50"] = np.where(keys["dist_sma_50"].notna(), (keys["dist_sma_50"] > 0).astype(float), np.nan)

        mkt_breadth = (
            keys.groupby("trading_date")
            .agg(
                mkt_adv_count=("_clean_ret_1d", lambda x: int((x > 0).sum())),
                mkt_dec_count=("_clean_ret_1d", lambda x: int((x < 0).sum())),
                mkt_valid_cnt=("_clean_ret_1d", "count"),
                mkt_median_ret_1d=("_clean_ret_1d", "median"),
                mkt_pct_above_sma50=("_above_sma50", "mean"),
            )
            .reset_index()
        )
        mkt_breadth["mkt_adv_decline_ratio"] = np.where(
            mkt_breadth["mkt_valid_cnt"] > 0,
            (mkt_breadth["mkt_adv_count"] - mkt_breadth["mkt_dec_count"]) / np.maximum(mkt_breadth["mkt_valid_cnt"], 1),
            np.nan,
        ).astype(np.float32)
        mkt_breadth["mkt_median_ret_1d"] = mkt_breadth["mkt_median_ret_1d"].astype(np.float32)
        mkt_breadth["mkt_pct_above_sma50"] = mkt_breadth["mkt_pct_above_sma50"].astype(np.float32)
        mkt_breadth = mkt_breadth.drop(columns=["mkt_adv_count", "mkt_dec_count", "mkt_valid_cnt"])

        valid_sec_rows = keys[keys["has_valid_sector"] == 1]
        sec_stats = (
            valid_sec_rows.groupby(["sector", "trading_date"])
            .agg(
                _sec_sum1=("_clean_ret_1d", "sum"),
                _sec_cnt1=("_clean_ret_1d", "count"),
                _sec_sum5=("_clean_ret_5d", "sum"),
                _sec_cnt5=("_clean_ret_5d", "count"),
                _sec_sum20=("_clean_ret_20d", "sum"),
                _sec_cnt20=("_clean_ret_20d", "count"),
            )
            .reset_index()
        )
        keys = keys.merge(sec_stats, on=["sector", "trading_date"], how="left")

        for col_sum, col_cnt, ret_c, out_c in [
            ("_sec_sum1", "_sec_cnt1", "_clean_ret_1d", "sector_ret_1d"),
            ("_sec_sum5", "_sec_cnt5", "_clean_ret_5d", "sector_ret_5d"),
            ("_sec_sum20", "_sec_cnt20", "_clean_ret_20d", "sector_ret_20d"),
        ]:
            has_self = pd.notna(keys[ret_c])
            peer_cnt = np.where(has_self, keys[col_cnt] - 1, keys[col_cnt])
            peer_sum = np.where(has_self, keys[col_sum] - keys[ret_c].fillna(0.0), keys[col_sum])
            keys[out_c] = np.where(
                (keys["has_valid_sector"] == 1) & (peer_cnt >= 2),
                peer_sum / np.maximum(peer_cnt, 1),
                np.nan,
            ).astype(np.float32)

        keys["stock_minus_sector_ret_5d"] = (keys["_clean_ret_5d"] - keys["sector_ret_5d"]).astype(np.float32)
        keys = keys.drop(columns=["_clean_ret_1d", "_clean_ret_5d", "_clean_ret_20d", "_above_sma50",
                                  "_sec_sum1", "_sec_cnt1", "_sec_sum5", "_sec_cnt5", "_sec_sum20", "_sec_cnt20"])

        idx_cols = [
            "trading_date", "kse100_close", "kse100_ret_1d", "kse100_ret_5d", "kse100_ret_20d",
            "kse100_log_ret_1d", "kse100_vol_20d", "kse100_dist_sma50", "kse100_dist_sma200", "kse100_rsi_14",
            "hmm_mkt_prob_bullish", "hmm_mkt_prob_bearish", "hmm_mkt_prob_sideways",
            "hmm_mkt_regime_id", "hmm_mkt_entropy", "hmm_mkt_regime_duration",
        ]
        keys = keys.merge(idx_daily[idx_cols], on="trading_date", how="left")
        keys = keys.merge(mkt_breadth, on="trading_date", how="left")

        keys["rel_strength_kse100_5d"] = (keys["ret_5d"] - keys["kse100_ret_5d"]).astype(np.float32)
        keys["rel_strength_kse100_20d"] = (keys["ret_20d"] - keys["kse100_ret_20d"]).astype(np.float32)

        # Causal 60d trailing Beta & Correlation vs KSE100 on narrow keys sorted by _row_id (symbol, trading_date)
        keys = keys.sort_values("_row_id").reset_index(drop=True)
        pair_valid = keys["log_ret_1d"].notna() & keys["kse100_log_ret_1d"].notna()
        keys["_px"] = np.where(pair_valid, keys["log_ret_1d"].astype(np.float64), np.nan)
        keys["_py"] = np.where(pair_valid, keys["kse100_log_ret_1d"].astype(np.float64), np.nan)
        keys["_pxy"] = keys["_px"] * keys["_py"]
        keys["_px2"] = keys["_px"] ** 2
        keys["_py2"] = keys["_py"] ** 2

        g_sym = keys.groupby("symbol", sort=False)
        cnt60 = g_sym["_px"].rolling(60, min_periods=40).count().reset_index(level=0, drop=True)
        sx = g_sym["_px"].rolling(60, min_periods=40).sum().reset_index(level=0, drop=True)
        sy = g_sym["_py"].rolling(60, min_periods=40).sum().reset_index(level=0, drop=True)
        sxy = g_sym["_pxy"].rolling(60, min_periods=40).sum().reset_index(level=0, drop=True)
        sx2 = g_sym["_px2"].rolling(60, min_periods=40).sum().reset_index(level=0, drop=True)
        sy2 = g_sym["_py2"].rolling(60, min_periods=40).sum().reset_index(level=0, drop=True)

        cov_num = sxy - (sx * sy) / cnt60
        varx_num = np.maximum(sx2 - (sx ** 2) / cnt60, 0.0)
        vary_num = np.maximum(sy2 - (sy ** 2) / cnt60, 0.0)
        keys["rolling_beta_60d"] = np.where(vary_num > 1e-12, cov_num / vary_num, np.nan).astype(np.float32)
        denom_corr = np.sqrt(varx_num * vary_num)
        keys["rolling_corr_kse100_60d"] = np.where(denom_corr > 1e-12, np.clip(cov_num / denom_corr, -1.0, 1.0), np.nan).astype(np.float32)
        keys = keys.drop(columns=["_px", "_py", "_pxy", "_px2", "_py2"])

        # 7. Group 6: Point-in-Time Financial Ratios on narrow keys
        fin_pit = build_point_in_time_fundamentals(conn, max_price_date=str(df_idx["trading_date"].max()))
        if not fin_pit.empty:
            keys["_td_dt"] = pd.to_datetime(keys["trading_date"])
            fin_pit["_pub_dt"] = pd.to_datetime(fin_pit["effective_pub_date"])
            keys = keys.sort_values(["_td_dt", "symbol"]).reset_index(drop=True)
            fin_pit = fin_pit.sort_values(["_pub_dt", "symbol"]).reset_index(drop=True)

            keys = pd.merge_asof(
                keys,
                fin_pit,
                by="symbol",
                left_on="_td_dt",
                right_on="_pub_dt",
                direction="backward",
                allow_exact_matches=True,
            )
            keys["has_fundamentals"] = keys["effective_pub_date"].notna().astype(np.int8)
            keys["fin_staleness_days"] = np.where(
                keys["has_fundamentals"] == 1,
                (keys["_td_dt"] - keys["_pub_dt"]).dt.days,
                np.nan,
            ).astype(np.float32)
            mcap_est = keys["market_cap"].where(
                keys["market_cap"].notna() & (keys["market_cap"] > 0),
                keys["adj_close"].astype(np.float64) * keys["fin_shares_post_split"],
            )
            keys["market_cap_missing_flag"] = keys["market_cap"].isna().astype(np.int8)
            keys["fin_earnings_yield_pit"] = np.where(mcap_est > 1e6, keys["fin_net_income_pkr"] / mcap_est, np.nan).astype(np.float32)
            keys["fin_book_to_price_pit"] = np.where(mcap_est > 1e6, keys["fin_equity_pkr"] / mcap_est, np.nan).astype(np.float32)
            keys["fin_sales_to_price_pit"] = np.where(mcap_est > 1e6, keys["fin_revenue_pkr"] / mcap_est, np.nan).astype(np.float32)
            keys["fin_fcf_yield_pit"] = np.where(mcap_est > 1e6, keys["fin_fcf_pkr"] / mcap_est, np.nan).astype(np.float32)
            keys = keys.drop(columns=["_td_dt", "_pub_dt", "fin_shares_post_split", "fin_basic_eps_post_split",
                                      "fin_revenue_pkr", "fin_net_income_pkr", "fin_equity_pkr", "fin_fcf_pkr"])
        else:
            keys["has_fundamentals"] = np.int8(0)
            keys["market_cap_missing_flag"] = keys["market_cap"].isna().astype(np.int8)

        # 8. Group 5: Point-in-Time News Sentiment (FinBERT) on narrow keys
        sym_sector_map = dict(zip(keys["symbol"], keys["sector"]))
        mkt_news, stock_news, sector_news, news_audit = build_point_in_time_news_features(
            conn,
            trading_dates=df_idx["trading_date"].to_numpy(),
            sym_sector_map=sym_sector_map,
        )
        keys = keys.merge(mkt_news, on="trading_date", how="left")
        if not stock_news.empty:
            keys = keys.merge(stock_news, on=["symbol", "trading_date"], how="left")
        else:
            keys["news_stock_count_1d"] = 0
            keys["news_stock_sent_mean_1d"] = np.nan
            keys["news_stock_count_7d"] = 0
            keys["news_stock_sent_mean_7d"] = np.nan
            keys["has_stock_news_7d"] = 0
        keys["news_stock_count_1d"] = keys["news_stock_count_1d"].fillna(0).astype(np.int32)
        keys["news_stock_count_7d"] = keys["news_stock_count_7d"].fillna(0).astype(np.int32)
        keys["has_stock_news_7d"] = keys["has_stock_news_7d"].fillna(0).astype(np.int8)

        if not sector_news.empty:
            keys = keys.merge(sector_news, on=["sector", "trading_date"], how="left")
        else:
            keys["news_sector_count_7d"] = 0
            keys["news_sector_sent_mean_7d"] = np.nan
            keys["has_sector_news_7d"] = 0
        keys["news_sector_count_7d"] = keys["news_sector_count_7d"].fillna(0).astype(np.int32)
        keys["has_sector_news_7d"] = keys["has_sector_news_7d"].fillna(0).astype(np.int8)

        # Align narrow keys back to exact df_all row order (_row_id) and concatenate in one shot
        keys = keys.sort_values("_row_id").reset_index(drop=True)
        base_cols = set(df_all.columns)
        new_cols_dict = {}
        for col in keys.columns:
            if col == "_row_id" or col in base_cols:
                continue
            vals = keys[col]
            if pd.api.types.is_float_dtype(vals):
                new_cols_dict[col] = vals.astype(np.float32).to_numpy()
            else:
                new_cols_dict[col] = vals.to_numpy()

        del keys
        gc.collect()
        if new_cols_dict:
            df_all = pd.concat([df_all, pd.DataFrame(new_cols_dict, index=df_all.index)], axis=1)
            del new_cols_dict
            gc.collect()

        metadata = {
            "total_rows": int(len(df_all)),
            "distinct_symbols": int(df_all["symbol"].nunique()),
            "kse100_current_symbols": int(df_all.loc[df_all["is_current_kse100"] == 1, "symbol"].nunique()),
            "date_min": str(df_all["trading_date"].min()),
            "date_max": str(df_all["trading_date"].max()),
            "total_feature_columns": int(len(df_all.columns)),
            "total_target_columns": int(len(targets_df.columns)),
            "splits": split_info["summary"],
            "hmm_train_metadata": hmm.get_model_metadata(),
            "news_alignment_audit": news_audit,
            "tx_cost_roundtrip_bps": int(PSX_TX_COST_ROUNDTRIP * 10000),
            "threshold_formula": "0.0050 + 0.35 * max(vol_20d, 0.005) * sqrt(h)",
        }
        return df_all, targets_df, metadata
