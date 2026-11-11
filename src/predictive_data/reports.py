"""
Predictive Dataset Documentation & Deliverable Reports Generator (Step 6).

Generates Deliverables 1, 5, 6, and 7 in Markdown, CSV, and JSON:
1. DATA_AUDIT_REPORT.md
5. FEATURE_DICTIONARY.md & feature_dictionary.csv
6. MISSING_DATA_AND_LEAKAGE_REPORT.md
7. CHRONOLOGICAL_SPLITS_AND_OVERLAP_POLICY.md & chronological_splits.json
"""

import json
from pathlib import Path
from typing import Dict, List, Any
import pandas as pd


FEATURE_CATALOG_SPECS: List[Dict[str, str]] = [
    # Group 0: Keys & Universe Metadata
    {"feature": "symbol", "group": "0_Keys_Metadata", "dtype": "string", "source": "stock_prices / companies", "causality": "Static ID", "explanation": "PSX equity ticker symbol."},
    {"feature": "trading_date", "group": "0_Keys_Metadata", "dtype": "date", "source": "market_indices", "causality": "Calendar Key", "explanation": "PSX genuine Mon-Fri exchange session date aligned to KSE-100 calendar."},
    {"feature": "cal_idx", "group": "0_Keys_Metadata", "dtype": "int64", "source": "splits.py", "causality": "Calendar Key", "explanation": "0-based sequential index over PSX exchange trading days."},
    {"feature": "sector", "group": "0_Keys_Metadata", "dtype": "string", "source": "companies", "causality": "Static Snapshot", "explanation": "PSX sector classification (711 non-KSE100 firms are unclassified)."},
    {"feature": "has_valid_sector", "group": "0_Keys_Metadata", "dtype": "int8", "source": "companies", "causality": "Metadata Flag", "explanation": "1 if symbol has a true PSX industry sector (excludes OTHER/UNCLASSIFIED)."},
    {"feature": "is_current_kse100", "group": "0_Keys_Metadata", "dtype": "int8", "source": "companies", "causality": "WARNING: Current Snapshot", "explanation": "1 if symbol is in KSE-100 as of Oct 2026 (NOT historical constituency; do not filter historical universe strictly on this flag)."},
    {"feature": "is_active_listing_snapshot", "group": "0_Keys_Metadata", "dtype": "int8", "source": "companies", "causality": "WARNING: Current Snapshot", "explanation": "Active status as of 2026 snapshot; included for reference only."},
    {"feature": "is_shariah", "group": "0_Keys_Metadata", "dtype": "int8", "source": "companies", "causality": "Static Snapshot", "explanation": "1 if Shariah-compliant KMI indicator flag is set in directory."},
    {"feature": "split", "group": "0_Keys_Metadata", "dtype": "string", "source": "splits.py", "causality": "Split Label", "explanation": "Chronological partition: TRAIN, PURGE_TRAIN_VAL, VAL, PURGE_VAL_TEST, or TEST."},
    {"feature": "fundamentals_regime_split", "group": "0_Keys_Metadata", "dtype": "string", "source": "splits.py", "causality": "Split Label", "explanation": "Sub-split (2022-2026) where audited IFRS statements exist (FUND_TRAIN/VAL/TEST + purges)."},
    {"feature": "listing_age_sessions", "group": "0_Keys_Metadata", "dtype": "int64", "source": "daily_builder", "causality": "Causal Point-in-Time", "explanation": "Cumulative trading sessions observed for symbol up to trading_date."},
    {"feature": "trailing_20d_adv_rank", "group": "0_Keys_Metadata", "dtype": "float64", "source": "daily_builder", "causality": "Causal Point-in-Time", "explanation": "Daily cross-sectional rank by trailing 20-day average PKR turnover (1 = most liquid)."},
    {"feature": "is_trailing_top100_liquid", "group": "0_Keys_Metadata", "dtype": "int8", "source": "daily_builder", "causality": "Causal Point-in-Time", "explanation": "Leak-free point-in-time liquid universe proxy: 1 if trailing_20d_adv_rank <= 100."},
    {"feature": "is_true_ohlc", "group": "0_Keys_Metadata", "dtype": "int8", "source": "daily_builder", "causality": "Bar Quality Flag", "explanation": "1 when raw bar has genuine spread (high > low) and valid OHLC envelope."},
    {"feature": "is_zero_volume", "group": "0_Keys_Metadata", "dtype": "int8", "source": "daily_builder", "causality": "Bar Quality Flag", "explanation": "1 when daily volume <= 0."},
    {"feature": "calendar_gap_days", "group": "0_Keys_Metadata", "dtype": "int32", "source": "daily_builder", "causality": "Causal Point-in-Time", "explanation": "PSX sessions elapsed since symbol's previous observation (1 = consecutive day)."},

    # Group 1: Stock OHLCV
    {"feature": "raw_open", "group": "1_Stock_OHLCV", "dtype": "float64", "source": "stock_prices", "causality": "Causal EOD", "explanation": "Nominal unadjusted opening price in PKR."},
    {"feature": "raw_high", "group": "1_Stock_OHLCV", "dtype": "float64", "source": "stock_prices", "causality": "Causal EOD", "explanation": "Nominal unadjusted session high in PKR."},
    {"feature": "raw_low", "group": "1_Stock_OHLCV", "dtype": "float64", "source": "stock_prices", "causality": "Causal EOD", "explanation": "Nominal unadjusted session low in PKR."},
    {"feature": "raw_close", "group": "1_Stock_OHLCV", "dtype": "float64", "source": "stock_prices", "causality": "Causal EOD", "explanation": "Nominal unadjusted closing price in PKR."},
    {"feature": "adj_open", "group": "1_Stock_OHLCV", "dtype": "float64", "source": "point_in_time", "causality": "Split-Adjusted Reference", "explanation": "Split-adjusted open price for return/indicator continuity."},
    {"feature": "adj_high", "group": "1_Stock_OHLCV", "dtype": "float64", "source": "point_in_time", "causality": "Split-Adjusted Reference", "explanation": "Split-adjusted high price."},
    {"feature": "adj_low", "group": "1_Stock_OHLCV", "dtype": "float64", "source": "point_in_time", "causality": "Split-Adjusted Reference", "explanation": "Split-adjusted low price."},
    {"feature": "adj_close", "group": "1_Stock_OHLCV", "dtype": "float64", "source": "point_in_time", "causality": "Split-Adjusted Reference", "explanation": "Split-adjusted close price (scale-invariant ratios computed from adj_* have zero leak)."},
    {"feature": "volume", "group": "1_Stock_OHLCV", "dtype": "int64", "source": "stock_prices", "causality": "Causal EOD", "explanation": "Daily traded share volume."},
    {"feature": "turnover_pkr", "group": "1_Stock_OHLCV", "dtype": "float64", "source": "daily_builder", "causality": "Causal EOD", "explanation": "Approximate daily rupee traded value (raw_close * volume)."},
    {"feature": "market_cap", "group": "1_Stock_OHLCV", "dtype": "float64", "source": "stock_prices", "causality": "Causal EOD (KSE-100 only)", "explanation": "Historical point-in-time market capitalization in PKR (populated on 100 Sarmaaya symbols)."},
    {"feature": "market_cap_missing_flag", "group": "1_Stock_OHLCV", "dtype": "int8", "source": "daily_builder", "causality": "Missingness Flag", "explanation": "1 if historical market_cap was NULL (requiring share-count fallback for valuation ratios)."},

    # Group 2: Technical Indicators
    {"feature": "sma_20", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=20", "explanation": "20-day Simple Moving Average of adj_close."},
    {"feature": "sma_50", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=50", "explanation": "50-day Simple Moving Average of adj_close."},
    {"feature": "sma_200", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=200", "explanation": "200-day Simple Moving Average of adj_close."},
    {"feature": "ema_12", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=12", "explanation": "12-day Exponential Moving Average of adj_close."},
    {"feature": "ema_26", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=26", "explanation": "26-day Exponential Moving Average of adj_close."},
    {"feature": "ema_20", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=20", "explanation": "20-day Exponential Moving Average of adj_close."},
    {"feature": "ema_50", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=50", "explanation": "50-day Exponential Moving Average of adj_close."},
    {"feature": "ema_200", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=200", "explanation": "200-day Exponential Moving Average of adj_close."},
    {"feature": "dist_sma_20", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal Stationary", "explanation": "Relative distance from 20-day SMA: (adj_close / sma_20) - 1."},
    {"feature": "dist_sma_50", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal Stationary", "explanation": "Relative distance from 50-day SMA: (adj_close / sma_50) - 1."},
    {"feature": "dist_sma_200", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal Stationary", "explanation": "Relative distance from 200-day SMA: (adj_close / sma_200) - 1."},
    {"feature": "dist_ema_20", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal Stationary", "explanation": "Relative distance from 20-day EMA: (adj_close / ema_20) - 1."},
    {"feature": "ema_20_50_spread", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal Stationary", "explanation": "Medium-term trend spread: (ema_20 / ema_50) - 1."},
    {"feature": "ema_50_200_spread", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal Stationary", "explanation": "Long-term golden/death cross spread: (ema_50 / ema_200) - 1."},
    {"feature": "rsi_14", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=14", "explanation": "14-period Wilder Relative Strength Index [0..100]."},
    {"feature": "macd_line", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal", "explanation": "ema_12 - ema_26."},
    {"feature": "macd_signal", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=9", "explanation": "9-day EMA of macd_line."},
    {"feature": "macd_diff", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal", "explanation": "MACD Histogram (macd_line - macd_signal)."},
    {"feature": "macd_diff_pct", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal Stationary", "explanation": "Price-normalized MACD histogram (macd_diff / adj_close)."},
    {"feature": "bb_middle", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=20", "explanation": "20-day Bollinger middle band (sma_20)."},
    {"feature": "bb_upper", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=20", "explanation": "20-day Bollinger upper band (+2 std)."},
    {"feature": "bb_lower", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=20", "explanation": "20-day Bollinger lower band (-2 std)."},
    {"feature": "bb_bandwidth", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal Stationary", "explanation": "Normalized Bollinger band width (%) relative to bb_middle."},
    {"feature": "bb_percent_b", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal Stationary", "explanation": "Bollinger %B relative position: (close - lower) / (upper - lower)."},
    {"feature": "atr_14", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=14", "explanation": "14-period Wilder Average True Range in PKR."},
    {"feature": "atr_pct", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal Stationary", "explanation": "ATR as % of adj_close (volatility normalized)."},
    {"feature": "dmi_plus_14", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=14", "explanation": "14-period Positive Directional Indicator (+DI)."},
    {"feature": "dmi_minus_14", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=14", "explanation": "14-period Negative Directional Indicator (-DI)."},
    {"feature": "adx_14", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=14", "explanation": "14-period Average Directional Index (trend strength)."},
    {"feature": "dmi_diff", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal Stationary", "explanation": "Directional balance (+DI - -DI)."},
    {"feature": "obv", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal Cumulative", "explanation": "Cumulative On-Balance Volume."},
    {"feature": "obv_zscore_20", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal Stationary", "explanation": "20-day rolling z-score of OBV measuring recent accumulation/distribution surge."},
    {"feature": "stoch_k", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=14", "explanation": "Slow Stochastic %K (14, 3)."},
    {"feature": "stoch_d", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=14", "explanation": "Slow Stochastic %D (3-day SMA of %K)."},
    {"feature": "stoch_k_minus_d", "group": "2_Technical_Indicators", "dtype": "float64", "source": "daily_builder", "causality": "Causal Stationary", "explanation": "Stochastic momentum oscillator spread (%K - %D)."},

    # Group 3: Candlestick Patterns
    {"feature": "candle_body_pct", "group": "3_Candlestick_Patterns", "dtype": "float64", "source": "daily_builder", "causality": "Causal (True OHLC only)", "explanation": "Signed body relative to close: (close - open) / close; NaN on flat EOD bars."},
    {"feature": "candle_range_pct", "group": "3_Candlestick_Patterns", "dtype": "float64", "source": "daily_builder", "causality": "Causal (True OHLC only)", "explanation": "High-low range relative to close; NaN when is_true_ohlc == 0."},
    {"feature": "upper_shadow_ratio", "group": "3_Candlestick_Patterns", "dtype": "float64", "source": "daily_builder", "causality": "Causal (True OHLC only)", "explanation": "Upper shadow divided by total high-low candle range."},
    {"feature": "lower_shadow_ratio", "group": "3_Candlestick_Patterns", "dtype": "float64", "source": "daily_builder", "causality": "Causal (True OHLC only)", "explanation": "Lower shadow divided by total high-low candle range."},
    {"feature": "body_to_range_ratio", "group": "3_Candlestick_Patterns", "dtype": "float64", "source": "daily_builder", "causality": "Causal (True OHLC only)", "explanation": "Absolute body size divided by total high-low candle range."},
    {"feature": "close_position_in_range", "group": "3_Candlestick_Patterns", "dtype": "float64", "source": "daily_builder", "causality": "Causal (True OHLC only)", "explanation": "(close - low) / (high - low) in [0, 1]."},
    {"feature": "candlestick_pattern_name", "group": "3_Candlestick_Patterns", "dtype": "string", "source": "daily_builder", "causality": "Causal (True OHLC only)", "explanation": "Detected classical candlestick formation matching CandlestickPatternDetector; NONE on flat bars."},
    {"feature": "candlestick_pattern_signal_num", "group": "3_Candlestick_Patterns", "dtype": "int8", "source": "daily_builder", "causality": "Causal (True OHLC only)", "explanation": "Encoded formation signal: +2 Strong Buy, +1 Buy, 0 Neutral/None, -1 Sell, -2 Strong Sell."},
    {"feature": "is_bullish_pattern", "group": "3_Candlestick_Patterns", "dtype": "int8", "source": "daily_builder", "causality": "Causal (True OHLC only)", "explanation": "1 if bullish candlestick formation detected today."},
    {"feature": "is_bearish_pattern", "group": "3_Candlestick_Patterns", "dtype": "int8", "source": "daily_builder", "causality": "Causal (True OHLC only)", "explanation": "1 if bearish candlestick formation detected today."},
    {"feature": "is_doji_true_ohlc", "group": "3_Candlestick_Patterns", "dtype": "int8", "source": "daily_builder", "causality": "Causal (True OHLC only)", "explanation": "1 if genuine Doji on a true OHLC bar (fixes flat-bar false Doji bug)."},
    {"feature": "bullish_patterns_5d", "group": "3_Candlestick_Patterns", "dtype": "int8", "source": "daily_builder", "causality": "Causal", "explanation": "Rolling 5-session count of bullish candlestick formations."},
    {"feature": "bearish_patterns_5d", "group": "3_Candlestick_Patterns", "dtype": "int8", "source": "daily_builder", "causality": "Causal", "explanation": "Rolling 5-session count of bearish candlestick formations."},

    # Group 4: Causal HMM Market-Regime Probabilities
    {"feature": "hmm_mkt_prob_bullish", "group": "4_HMM_Regimes", "dtype": "float64", "source": "regime_causal.py", "causality": "Strictly Filtered P(S_t|X_1:t)", "explanation": "Causal forward-filtered probability of Bullish KSE-100 regime (Train-fitted HMM, zero smoothing)."},
    {"feature": "hmm_mkt_prob_bearish", "group": "4_HMM_Regimes", "dtype": "float64", "source": "regime_causal.py", "causality": "Strictly Filtered P(S_t|X_1:t)", "explanation": "Causal forward-filtered probability of Bearish KSE-100 regime."},
    {"feature": "hmm_mkt_prob_sideways", "group": "4_HMM_Regimes", "dtype": "float64", "source": "regime_causal.py", "causality": "Strictly Filtered P(S_t|X_1:t)", "explanation": "Causal forward-filtered probability of Sideways KSE-100 regime."},
    {"feature": "hmm_mkt_regime_id", "group": "4_HMM_Regimes", "dtype": "float64", "source": "regime_causal.py", "causality": "Strictly Filtered", "explanation": "Argmax filtered state: 1=BULLISH, 0=SIDEWAYS, -1=BEARISH."},
    {"feature": "hmm_mkt_entropy", "group": "4_HMM_Regimes", "dtype": "float64", "source": "regime_causal.py", "causality": "Strictly Filtered", "explanation": "Shannon entropy of filtered HMM state probabilities (regime transition uncertainty)."},
    {"feature": "hmm_mkt_regime_duration", "group": "4_HMM_Regimes", "dtype": "float64", "source": "regime_causal.py", "causality": "Strictly Filtered", "explanation": "Consecutive trading days spent in the current causal HMM regime."},

    # Group 5: Point-in-Time News Sentiment (FinBERT)
    {"feature": "news_mkt_count_1d", "group": "5_News_Sentiment", "dtype": "int32", "source": "news_articles / news_sentiment", "causality": "Causal PKT 15:30 cutoff", "explanation": "Count of market/macro articles observable by 15:30 PKT on trading_date."},
    {"feature": "news_mkt_sent_mean_1d", "group": "5_News_Sentiment", "dtype": "float64", "source": "news_sentiment (FinBERT)", "causality": "Causal PKT 15:30 cutoff", "explanation": "Mean FinBERT score [-1, +1] of market articles observable on trading_date."},
    {"feature": "news_mkt_count_7d", "group": "5_News_Sentiment", "dtype": "int32", "source": "news_sentiment (FinBERT)", "causality": "Causal 7-session window", "explanation": "Trailing 7-session count of observable FinBERT news articles."},
    {"feature": "news_mkt_sent_mean_7d", "group": "5_News_Sentiment", "dtype": "float64", "source": "news_sentiment (FinBERT)", "causality": "Causal 7-session window", "explanation": "Trailing 7-session mean market FinBERT sentiment score."},
    {"feature": "news_mkt_neg_share_7d", "group": "5_News_Sentiment", "dtype": "float64", "source": "news_sentiment (FinBERT)", "causality": "Causal 7-session window", "explanation": "Fraction of trailing 7-session market news classified NEGATIVE by FinBERT."},
    {"feature": "has_mkt_news_7d", "group": "5_News_Sentiment", "dtype": "int8", "source": "point_in_time.py", "causality": "Availability Mask", "explanation": "1 if >= 1 market article exists in trailing 7 sessions (prevents confusing missing coverage with neutral 0)."},
    {"feature": "news_stock_count_1d", "group": "5_News_Sentiment", "dtype": "int32", "source": "news_entities / impact_analyzer", "causality": "Causal PKT 15:30 cutoff", "explanation": "1-day count of articles mentioning or sector-targeting symbol."},
    {"feature": "news_stock_sent_mean_1d", "group": "5_News_Sentiment", "dtype": "float64", "source": "news_sentiment (FinBERT)", "causality": "Causal PKT 15:30 cutoff", "explanation": "1-day stock-linked mean FinBERT sentiment score."},
    {"feature": "news_stock_count_7d", "group": "5_News_Sentiment", "dtype": "int32", "source": "news_entities / impact_analyzer", "causality": "Causal 7-session window", "explanation": "Trailing 7-session stock-linked article count."},
    {"feature": "news_stock_sent_mean_7d", "group": "5_News_Sentiment", "dtype": "float64", "source": "news_sentiment (FinBERT)", "causality": "Causal 7-session window", "explanation": "Trailing 7-session stock-linked mean FinBERT sentiment score."},
    {"feature": "has_stock_news_7d", "group": "5_News_Sentiment", "dtype": "int8", "source": "point_in_time.py", "causality": "Availability Mask", "explanation": "1 if >= 1 stock-linked article exists in trailing 7 sessions."},
    {"feature": "news_sector_count_7d", "group": "5_News_Sentiment", "dtype": "int32", "source": "news_entities / impact_analyzer", "causality": "Causal 7-session window", "explanation": "Trailing 7-session article count targeting symbol's PSX sector."},
    {"feature": "news_sector_sent_mean_7d", "group": "5_News_Sentiment", "dtype": "float64", "source": "news_sentiment (FinBERT)", "causality": "Causal 7-session window", "explanation": "Trailing 7-session sector mean FinBERT sentiment score."},
    {"feature": "has_sector_news_7d", "group": "5_News_Sentiment", "dtype": "int8", "source": "point_in_time.py", "causality": "Availability Mask", "explanation": "1 if >= 1 sector-linked article exists in trailing 7 sessions."},

    # Group 6: Point-in-Time Financial Ratios
    {"feature": "fin_period_end_date", "group": "6_Financial_Ratios_PIT", "dtype": "date", "source": "company_financials", "causality": "Audit Metadata", "explanation": "Fiscal accounting close date of most recently disclosed IFRS statement."},
    {"feature": "effective_pub_date", "group": "6_Financial_Ratios_PIT", "dtype": "date", "source": "point_in_time.py", "causality": "Causal Publication Gate", "explanation": "Matched PSX Earnings Announcement posting date (or period_end + 100d conservative fallback)."},
    {"feature": "fin_pub_verified_flag", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "corporate_announcements", "causality": "Audit Metadata", "explanation": "1 if exact PSX announcement date matched; 0 if +100d statutory lag fallback applied."},
    {"feature": "has_fundamentals", "group": "6_Financial_Ratios_PIT", "dtype": "int8", "source": "point_in_time.py", "causality": "Availability Mask", "explanation": "1 if audited IFRS filing has been published as of trading_date."},
    {"feature": "fin_staleness_days", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "point_in_time.py", "causality": "Causal Point-in-Time", "explanation": "Calendar days elapsed since effective_pub_date."},
    {"feature": "fin_gross_margin", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "INCOME_STATEMENT", "causality": "As-of effective_pub_date", "explanation": "Gross Profit / Total Revenue."},
    {"feature": "fin_operating_margin", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "INCOME_STATEMENT", "causality": "As-of effective_pub_date", "explanation": "Operating Income / Total Revenue."},
    {"feature": "fin_net_margin", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "INCOME_STATEMENT", "causality": "As-of effective_pub_date", "explanation": "Net Income / Total Revenue."},
    {"feature": "fin_roe", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "INCOME_STATEMENT / BALANCE_SHEET", "causality": "As-of effective_pub_date", "explanation": "Return on Equity: Net Income / Stockholders Equity."},
    {"feature": "fin_roa", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "INCOME_STATEMENT / BALANCE_SHEET", "causality": "As-of effective_pub_date", "explanation": "Return on Assets: Net Income / Total Assets."},
    {"feature": "fin_fcf_margin", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "CASH_FLOW / INCOME_STATEMENT", "causality": "As-of effective_pub_date", "explanation": "Free Cash Flow / Total Revenue."},
    {"feature": "fin_ocf_to_ni", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "CASH_FLOW / INCOME_STATEMENT", "causality": "As-of effective_pub_date", "explanation": "Earnings quality ratio: Operating Cash Flow / Net Income."},
    {"feature": "fin_debt_to_equity", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "BALANCE_SHEET", "causality": "As-of effective_pub_date", "explanation": "Total Debt / Stockholders Equity."},
    {"feature": "fin_debt_to_assets", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "BALANCE_SHEET", "causality": "As-of effective_pub_date", "explanation": "Total Debt / Total Assets."},
    {"feature": "fin_current_ratio", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "BALANCE_SHEET", "causality": "As-of effective_pub_date", "explanation": "Current Assets / Current Liabilities."},
    {"feature": "fin_revenue_yoy_growth", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "INCOME_STATEMENT", "causality": "As-of effective_pub_date", "explanation": "YoY revenue growth relative to previously disclosed statement."},
    {"feature": "fin_net_income_yoy_growth", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "INCOME_STATEMENT", "causality": "As-of effective_pub_date", "explanation": "YoY net income growth relative to previously disclosed statement."},
    {"feature": "fin_earnings_yield_pit", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "daily_builder", "causality": "Split-Invariant PIT", "explanation": "Disclosed Net Income / current Market Cap (E/P inverse P/E, split-invariant)."},
    {"feature": "fin_book_to_price_pit", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "daily_builder", "causality": "Split-Invariant PIT", "explanation": "Disclosed Stockholders Equity / current Market Cap (B/P inverse P/B)."},
    {"feature": "fin_sales_to_price_pit", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "daily_builder", "causality": "Split-Invariant PIT", "explanation": "Disclosed Total Revenue / current Market Cap (S/P inverse P/S)."},
    {"feature": "fin_fcf_yield_pit", "group": "6_Financial_Ratios_PIT", "dtype": "float64", "source": "daily_builder", "causality": "Split-Invariant PIT", "explanation": "Disclosed Free Cash Flow / current Market Cap."},

    # Group 7: KSE-100 & Sector Market Features
    {"feature": "kse100_close", "group": "7_Market_And_Sector", "dtype": "float64", "source": "market_indices", "causality": "Causal Index Close", "explanation": "KSE-100 index daily closing level (reference scale only; use stationary features for modeling)."},
    {"feature": "kse100_ret_1d", "group": "7_Market_And_Sector", "dtype": "float64", "source": "market_indices", "causality": "Causal Index Close", "explanation": "1-day KSE-100 index return."},
    {"feature": "kse100_ret_5d", "group": "7_Market_And_Sector", "dtype": "float64", "source": "market_indices", "causality": "Causal Index Close", "explanation": "5-day KSE-100 index return."},
    {"feature": "kse100_ret_20d", "group": "7_Market_And_Sector", "dtype": "float64", "source": "market_indices", "causality": "Causal Index Close", "explanation": "20-day KSE-100 index return."},
    {"feature": "kse100_log_ret_1d", "group": "7_Market_And_Sector", "dtype": "float64", "source": "market_indices", "causality": "Causal Index Close", "explanation": "Daily KSE-100 log return."},
    {"feature": "kse100_vol_20d", "group": "7_Market_And_Sector", "dtype": "float64", "source": "market_indices", "causality": "Causal min_periods=20", "explanation": "20-day KSE-100 log-return realized volatility."},
    {"feature": "kse100_dist_sma50", "group": "7_Market_And_Sector", "dtype": "float64", "source": "market_indices", "causality": "Causal min_periods=50", "explanation": "KSE-100 close distance from 50-day SMA."},
    {"feature": "kse100_dist_sma200", "group": "7_Market_And_Sector", "dtype": "float64", "source": "market_indices", "causality": "Causal min_periods=200", "explanation": "KSE-100 close distance from 200-day SMA."},
    {"feature": "kse100_rsi_14", "group": "7_Market_And_Sector", "dtype": "float64", "source": "market_indices", "causality": "Causal min_periods=14", "explanation": "14-period Wilder RSI of KSE-100."},
    {"feature": "mkt_median_ret_1d", "group": "7_Market_And_Sector", "dtype": "float64", "source": "daily_builder", "causality": "Causal Cross-Section", "explanation": "Median daily return across clean equity universe on trading_date."},
    {"feature": "mkt_pct_above_sma50", "group": "7_Market_And_Sector", "dtype": "float64", "source": "daily_builder", "causality": "Causal Cross-Section", "explanation": "Fraction of PSX equities trading above their 50-day SMA."},
    {"feature": "mkt_adv_decline_ratio", "group": "7_Market_And_Sector", "dtype": "float64", "source": "daily_builder", "causality": "Causal Cross-Section", "explanation": "(Advances - Declines) / Active equities on trading_date."},
    {"feature": "sector_ret_1d", "group": "7_Market_And_Sector", "dtype": "float64", "source": "daily_builder", "causality": "Causal Leave-One-Out", "explanation": "Equal-weighted 1-day return of sector peers (min 2 peers, excludes self & unclassified)."},
    {"feature": "sector_ret_5d", "group": "7_Market_And_Sector", "dtype": "float64", "source": "daily_builder", "causality": "Causal Leave-One-Out", "explanation": "Equal-weighted 5-day return of sector peers."},
    {"feature": "sector_ret_20d", "group": "7_Market_And_Sector", "dtype": "float64", "source": "daily_builder", "causality": "Causal Leave-One-Out", "explanation": "Equal-weighted 20-day return of sector peers."},
    {"feature": "stock_minus_sector_ret_5d", "group": "7_Market_And_Sector", "dtype": "float64", "source": "daily_builder", "causality": "Causal Relative", "explanation": "Stock 5-day outperformance relative to sector peers."},
    {"feature": "rel_strength_kse100_5d", "group": "7_Market_And_Sector", "dtype": "float64", "source": "daily_builder", "causality": "Causal Relative", "explanation": "Stock 5-day return minus KSE-100 5-day return."},
    {"feature": "rel_strength_kse100_20d", "group": "7_Market_And_Sector", "dtype": "float64", "source": "daily_builder", "causality": "Causal Relative", "explanation": "Stock 20-day return minus KSE-100 20-day return."},
    {"feature": "rolling_beta_60d", "group": "7_Market_And_Sector", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=40", "explanation": "60-session trailing OLS Beta vs KSE-100 log returns."},
    {"feature": "rolling_corr_kse100_60d", "group": "7_Market_And_Sector", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=40", "explanation": "60-session trailing Pearson correlation with KSE-100 log returns."},

    # Group 8: Liquidity & Volatility Features
    {"feature": "ret_1d", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal EOD", "explanation": "1-day simple split-adjusted return (NaN after gaps > 15 sessions)."},
    {"feature": "log_ret_1d", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal EOD", "explanation": "1-day log split-adjusted return."},
    {"feature": "ret_2d", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal Gap-Guarded", "explanation": "2-session split-adjusted return."},
    {"feature": "ret_5d", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal Gap-Guarded", "explanation": "5-session split-adjusted return."},
    {"feature": "ret_10d", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal Gap-Guarded", "explanation": "10-session split-adjusted return."},
    {"feature": "ret_20d", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal Gap-Guarded", "explanation": "20-session split-adjusted return."},
    {"feature": "ret_60d", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal Gap-Guarded", "explanation": "60-session split-adjusted return."},
    {"feature": "vol_5d", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=5", "explanation": "5-day realized daily log-return std."},
    {"feature": "vol_20d", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=15", "explanation": "20-day realized daily log-return std (also drives causal target threshold)."},
    {"feature": "vol_60d", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=40", "explanation": "60-day realized daily log-return std."},
    {"feature": "vol_ratio_5_20", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal", "explanation": "Short-to-medium volatility ratio (vol_5d / vol_20d)."},
    {"feature": "parkinson_vol_20d", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal True-OHLC>=50%", "explanation": "20-day Parkinson range volatility; masked NaN if <50% true OHLC bars."},
    {"feature": "overnight_gap_pct", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal True-OHLC", "explanation": "(adj_open_t - adj_close_{t-1}) / adj_close_{t-1}."},
    {"feature": "intraday_ret_pct", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal True-OHLC", "explanation": "(adj_close_t - adj_open_t) / adj_open_t."},
    {"feature": "log_volume", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal", "explanation": "log1p(volume)."},
    {"feature": "log_turnover_pkr", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal", "explanation": "log1p(turnover_pkr)."},
    {"feature": "trailing_20d_adv_pkr", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal min_periods=10", "explanation": "Trailing 20-day mean PKR turnover."},
    {"feature": "volume_ratio_20d", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal", "explanation": "Volume surge ratio: volume / 20d SMA(volume)."},
    {"feature": "amihud_illiquidity_20d", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal", "explanation": "20-day Amihud illiquidity: mean(|ret_1d| / (turnover_pkr / 1e6))."},
    {"feature": "zero_volume_days_20d", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal", "explanation": "Count of zero-volume days inside trailing 20 sessions."},
    {"feature": "hl_spread_pct", "group": "8_Liquidity_Volatility", "dtype": "float64", "source": "daily_builder", "causality": "Causal True-OHLC", "explanation": "(high - low) / close intraday trading range proxy."},
]


def write_all_deliverable_reports(
    reports_dir: Path,
    data_dir: Path,
    audit_res: Dict[str, Any],
    daily_meta: Dict[str, Any],
    intraday_meta: Dict[str, Any],
    prep_meta: Dict[str, Any],
    target_stats: Dict[str, Any],
) -> List[str]:
    """Writes all Markdown, CSV, and JSON documentation deliverables."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    created_files: List[str] = []

    # 1. Chronological Splits JSON
    splits_json = data_dir / "chronological_splits.json"
    splits_json.write_text(json.dumps(daily_meta["splits"], indent=2), encoding="utf-8")
    created_files.append(str(splits_json))

    # 2. Feature Dictionary CSV & Markdown
    dict_df = pd.DataFrame(FEATURE_CATALOG_SPECS)
    dict_csv = data_dir / "feature_dictionary.csv"
    dict_df.to_csv(dict_csv, index=False)
    created_files.append(str(dict_csv))

    dict_md = reports_dir / "FEATURE_DICTIONARY.md"
    md_lines = [
        "# PSXpert Daily & Intraday Feature Dictionary",
        "",
        f"**Total Daily Feature Columns Cataloged:** {len(dict_df)} | **Daily Rows:** {daily_meta['total_rows']:,} | **Intraday Rows:** 0 (schema only)",
        "",
        "## Daily Features by Domain",
        "",
        "| Feature | Domain Group | Type | Causality & Point-in-Time Policy | Description |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    for _, row in dict_df.iterrows():
        md_lines.append(f"| `{row['feature']}` | `{row['group']}` | `{row['dtype']}` | {row['causality']} | {row['explanation']} |")

    md_lines.extend([
        "",
        "## Target Label Schema (`daily_targets.parquet`)",
        "",
        "| Column Pattern | Horizons | Definition |",
        "| :--- | :--- | :--- |",
        "| `target_ret_{h}d` | `1d, 5d, 20d` | Split-adjusted forward return `adj_close[t+h]/adj_close[t] - 1` (masked NaN if `target_valid_{h}d == 0`) |",
        "| `target_log_ret_{h}d` | `1d, 5d, 20d` | Forward log return `ln(1 + target_ret_{h}d)` |",
        "| `target_threshold_{h}d` | `1d, 5d, 20d` | Causal volatility + PSX transaction-cost band: `0.0050 + 0.35 * max(vol_20d[t], 0.005) * sqrt(h)` |",
        "| `target_dir_{h}d` | `1d, 5d, 20d` | 3-class direction: `1` (UP), `0` (NEUTRAL), `-1` (DOWN) |",
        "| `target_label_{h}d` | `1d, 5d, 20d` | Text label: `UP`, `NEUTRAL`, `DOWN` |",
        "| `target_valid_{h}d` | `1d, 5d, 20d` | `1` iff exact trading-day horizon, non-glitch horizon window, and valid `vol_20d[t]` |",
        "| `sample_uniqueness_{h}d` | `5d, 20d` | Overlap concurrency weight `1/h` accounting for multi-day overlapping targets |",
        "",
        "## Intraday Schema (`intraday_features.parquet` & `intraday_targets.parquet` — 0 Historical Rows)",
        "Strict 5-minute bar schema (Asia/Karachi PKT, right-labeled & right-closed) isolated from daily data:",
        "",
        "- **Features (`24` columns)**: `symbol`, `timestamp_pkt`, `trading_date`, `session_id`, `bar_frequency_min`, `open`, `high`, `low`, `close`, `volume`, `vwap_session`, `dist_vwap_pct`, `ret_1bar_5m`, `ret_3bar_15m`, `ret_6bar_30m`, `ret_12bar_60m`, `rsi_14_bar`, `realized_vol_12bar`, `parkinson_vol_12bar`, `volume_ratio_12bar`, `minutes_since_session_open`, `kse100_intraday_ret_5m`, `kse100_intraday_ret_30m`, `rel_strength_kse100_30m`.",
        "- **Targets (`16` columns)**: `symbol`, `timestamp_pkt`, `trading_date`, `session_id`, plus `target_ret_{h}`, `target_threshold_{h}`, `target_dir_{h}`, `target_label_{h}`, `target_valid_{h}`, `target_end_ts_{h}` for `30m` (`6` bars) and `60m` (`12` bars) restricted strictly within the same `session_id`.",
    ])
    dict_md.write_text("\n".join(md_lines), encoding="utf-8")
    created_files.append(str(dict_md))

    # 3. Data Audit Report (Deliverable 1)
    sp = audit_res["stock_prices"]
    comp = audit_res["companies"]
    mi = audit_res["market_indices"]
    na = audit_res["news_articles"]
    intr = audit_res["intraday_availability"]

    audit_md = reports_dir / "DATA_AUDIT_REPORT.md"
    cf_rows = "\n".join(
        f"| `{r['statement_type']}` | {r['rows']:,} | {r['syms']} | {r['min_end']} -> {r['max_end']} | {r['pub_eq_end']:,} | {r['pub_lt_end']:,} | {r['future_period_end']:,} | {r['sentinel_12121_rows']:,} |"
        for r in audit_res["company_financials"]
    )
    tbl_rows = "\n".join(f"| `{k}` | {v:,} |" for k, v in audit_res["table_counts"].items())

    audit_text = f"""# PSXpert Predictive Data Audit Report (Step 1)

## 1. Executive Audit Summary
- **Active Database**: `{audit_res['database_dialect'].upper()}` (`localhost:5432/psxpert`)
- **Daily Universe & Range**: {comp['total']} companies in directory ({comp['kse100_true']} flagged `is_kse100` snapshot); `{sp['min_date']}` to `{sp['max_date']}` (`{sp['total_rows']:,}` raw `stock_prices` rows).
- **Cleaned Equity Panel Built**: **`{daily_meta['total_rows']:,}` rows** across **`{daily_meta['distinct_symbols']}` equities** (`{daily_meta['date_min']}` to `{daily_meta['date_max']}`).
- **Intraday Availability**: **`0` historical sub-daily bars** exist in PostgreSQL, SQLite (`data/psxpert.db`), CSV archives, or tested API endpoints (`/timeseries/int/*` returned HTTP 404). Intraday forecasting horizons (`30m` / `60m`) cannot be populated with historical data until a live sub-daily bar collector runs over multiple months.

## 2. Database Table Inventory
| Table | Raw Row Count |
| :--- | ---: |
{tbl_rows}

## 3. Critical Raw Data & Codebase Defects Found
1. **Forward-Filled Non-Trading Weekend/Holiday Rows in `stock_prices`**:
   - While `market_indices` (`KSE100`) contains `{mi['total_rows']:,}` genuine Monday–Friday trading sessions (`weekend_rows = {mi['weekend_rows']}`), raw `stock_prices` contains **`{sp['weekend_phantom_rows']:,}` Saturday/Sunday rows** and **`{sp['non_kse100_calendar_rows_since_2002']:,}` extra non-exchange-day rows** where Sarmaaya API (`source_id=2`) duplicated Friday's close and volume onto weekends/holidays (inflating 2024 KSE-100 dates from 246 to 347!).
   - *Fix applied*: Daily predictive panel inner-joins onto genuine `KSE100` trading sessions (`market_indices`).
2. **OHLC & Debt-Ticker Pollution in `stock_prices` / `companies`**:
   - Raw `stock_prices`: `{sp['nonpos_close']:,}` non-positive `close <= 0`, `{sp['bad_hl']:,}` inverted `high < low`, `{sp['flat_hl']:,}` flat `high == low` bars, `{sp['ohlc_envelope_violations']:,}` envelope violations, `{sp['zero_vol']:,}` zero-volume rows.
   - `companies`: `{comp['debt_sukuk_tickers']}` fixed-income/PIB/Sukuk tickers (`^P[0-9]{{2}}`), `{comp['etf_pref_tickers']}` ETF/pref symbols, `{comp['unclassified_sector']}/{comp['total']}` lacking true sector metadata.
   - *Fix applied*: Excluded debt/ETF/pref tickers and `close <= 0`; clamped single-bar OHLC envelopes causally; gated candlestick & Parkinson volatility features strictly on `is_true_ohlc`.
3. **Unadjusted Corporate Splits & Source Glitches**:
   - Raw `stock_prices` lacks split adjustments across major sub-divisions/reverse-splits (`BML +1626.5%`, `SRVI -90.4%`, `MARI -88.2%`, `SYS -81.0%`, `LUCK -79.5%`, `UBL -50.1%`, `MTL -48.6%`, `BAFL -48.4%`). Early data also has source glitches (`UPFL` `1.00 <-> 1350`, `ATLH` `295 <-> 58.35`).
   - *Fix applied*: `point_in_time.adjust_splits_and_flag_glitches` separates persistent corporate-action steps from oscillating 1-bar glitches, produces split-continuous `adj_*` series, and masks glitch horizons (`target_valid_* = 0`).
4. **Synthetic OHLC & Zero Volume in `market_indices` (`KSE100`)**:
   - `enrich_ohlc.py` generated `KSE100` Open/High/Low synthetically from `close` and `point_change`, and `volume == 0` for `{mi['zero_vol_rows']:,}/{mi['total_rows']:,}` rows.
   - *Fix applied*: `daily_builder.py` and `CausalMarketRegimeHMM` use ONLY authentic `KSE100` `close` returns and volatility.
5. **Financial Statement Unit Mismatches, Sentinel `12121`, and Publication-Date Leakage**:

| Statement Type | Rows | Syms | Period Range | `pub == end` | `pub < end` | Future End (`>2026-10-13`) | `12121` Sentinel |
| :--- | ---: | ---: | :--- | ---: | ---: | ---: | ---: |
{cf_rows}

   - Audited IFRS tables (`INCOME_STATEMENT`, `BALANCE_SHEET`, `CASH_FLOW`) store full PKR (`1x`) but set **`100%` of `publication_date == period_end_date`**. Meanwhile `ANNUAL` suffered repeated dummy scrape values (`435451.1` / `168643.2`) and `QUARTERLY` suffered `2,262` sentinel `12121.0` rows plus future fiscal year bugs (`2027-09-30`). `kse100_financial_ratios.csv` lacks any date column (`fiscal_year` only) and embeds snapshot market prices.
   - *Fix applied*: Built point-in-time IFRS fundamental ratios exclusively from `INCOME_STATEMENT`, `BALANCE_SHEET`, and `CASH_FLOW`, recovering genuine filing dates from `corporate_announcements` (`Earnings Announcements`, empirical lag `p50=53d, p95=96d`) and applying a conservative **`+100 day` lag fallback** when unmatched. Valuation yields use split-invariant aggregate PKR items over daily `market_cap`.
6. **News Archive & Timestamp Limitations**:
   - Only `{na['total_articles']}` articles exist (`{na['articles_2026']}` in 2026, `{na['articles_archive']}` in 2002–2024). All `{na['articles_archive']}` archive rows carry synthetic `YYYY-06-15 00:00` sampling dates, and `{na['post_price_cutoff_articles']}` Oct 14–20 articles fall *after* the latest price session (`2026-10-13`).
   - *Fix applied*: Enforced `published_at <= 15:30 PKT` cutoff (post-close articles roll forward to next session; post-Oct-13 excluded) with explicit `has_*_news_7d` coverage masks.
7. **Existing Quantitative Modules Audit (`regime_hmm.py`, `walk_forward.py`, `candlestick_patterns.py`, `technical_indicators.py`)**:
   - `MarketRegimeHMM.predict_regimes()` uses `hmmlearn.predict_proba()` (**smoothed** posteriors over $X_{{1:T}}$) and `predict()` (Viterbi path) and truncates `history_sample` to `[-180:]`.
   - `WalkForwardEngine` indexes `history_sample[-180:]` (dropping >60% of 450+ train bars and shifting indices by 10 warmup NaNs).
   - `TechnicalIndicatorCalculator` calls `.bfill()` on line 63 and uses `min_periods=1`.
   - `CandlestickPatternDetector` marks `high == low` bars as `Doji`.
   - *Fix applied*: Existing backend/dashboard left intact; dedicated leak-free modules created in `src/predictive_data/` using causal log-space HMM forward filtering, strict `min_periods`, zero `.bfill()`, and true-OHLC pattern guards.
"""
    audit_md.write_text(audit_text, encoding="utf-8")
    created_files.append(str(audit_md))

    # 4. Missing-Data & Leakage Report (Deliverable 6)
    leak_md = reports_dir / "MISSING_DATA_AND_LEAKAGE_REPORT.md"
    t1 = target_stats.get("1d", {})
    t5 = target_stats.get("5d", {})
    t20 = target_stats.get("20d", {})
    leak_text = f"""# Missing-Data & Anti-Leakage Verification Report

## 1. Summary of Missingness & Coverage Characteristics
- **Daily Feature Table**: `{daily_meta['total_rows']:,}` observations x `{daily_meta['total_feature_columns']}` columns (`{daily_meta['date_min']}` -> `{daily_meta['date_max']}`).
- **Expected Structural Missingness (Honest NaN / Masked — NOT Backfilled)**:
  - **Indicator Warmup Bars**: First `14..200` sessions per stock listing remain `NaN` (`min_periods=20/50/200`); `.bfill()` is strictly forbidden.
  - **True-OHLC Masked Features** (`candle_*`, `parkinson_vol_20d`, `hl_spread_pct`, `overnight_gap_pct`): Explicitly set to `NaN` when `is_true_ohlc == 0` (~19% of raw bars) to prevent flat-bar phantom signals.
  - **Financial Ratios (`fin_*`)**: Available only from `~2022` onward across ~140 audited IFRS firms (`has_fundamentals = 1`). Historical rows prior to first disclosed filing remain `NaN`; a dedicated `FUND_TRAIN/VAL/TEST` preprocessing profile is fitted on `FUND_TRAIN` (`2022–2024`) alongside full-history `TRAIN` (`2002–2021`).
  - **News Sentiment (`news_*`)**: Extremely sparse pre-Oct 2026 (`{daily_meta['news_alignment_audit']['usable_aligned_articles']}` total aligned articles; `{daily_meta['news_alignment_audit']['excluded_post_cutoff']}` post-`2026-10-13` articles excluded). Accompanied by `has_stock_news_7d`, `has_sector_news_7d`, and `has_mkt_news_7d` masks.
  - **Sector Returns (`sector_ret_*`)**: Masked `NaN` for `711` companies lacking genuine PSX sector classifications or single-peer sectors.
  - **Intraday Dataset**: `0` rows (`{intr['status']}`).

## 2. Target Class Distribution & Valid Sample Counts
Calibrated using causal threshold `theta_h = 0.0050 (50 bps PSX round-trip cost) + 0.35 * max(vol_20d[t], 0.005) * sqrt(h)`:

| Horizon | Valid Targets | Masked Invalid Targets | UP % | NEUTRAL % | DOWN % |
| :--- | ---: | ---: | ---: | ---: | ---: |
| **1-Day** | {t1.get('valid_count', 0):,} | {t1.get('invalid_count', 0):,} | {t1.get('up_pct', 0):.2f}% | {t1.get('neutral_pct', 0):.2f}% | {t1.get('down_pct', 0):.2f}% |
| **5-Day** | {t5.get('valid_count', 0):,} | {t5.get('invalid_count', 0):,} | {t5.get('up_pct', 0):.2f}% | {t5.get('neutral_pct', 0):.2f}% | {t5.get('down_pct', 0):.2f}% |
| **20-Day** | {t20.get('valid_count', 0):,} | {t20.get('invalid_count', 0):,} | {t20.get('up_pct', 0):.2f}% | {t20.get('neutral_pct', 0):.2f}% | {t20.get('down_pct', 0):.2f}% |

## 3. Data-Leakage Safeguards Implemented
1. **No Future-Smoothed HMM States**: `CausalMarketRegimeHMM` fits parameters exclusively on `split == 'TRAIN'` and computes filtered probabilities $P(S_t | X_{{1:t}})$ via forward-only recursion in log space.
2. **Financial Publication Dates Enforced**: All fundamentals merge backward via `merge_asof` on `effective_pub_date <= trading_date` (never `period_end_date`), using verified PSX `Earnings Announcements` or a conservative `+100d` lag fallback.
3. **News Session Cutoff Enforced**: Articles published after `15:30 PKT` roll forward to the next open session; Oct 14–20 news after `2026-10-13` is completely excluded.
4. **Train-Only Preprocessing & Feature Screening**: Quantile clipping (`1%/99%`), median imputation, scaling parameters, and Mutual Information / Spearman screening (`train_feature_screening.csv`) are computed strictly on `TRAIN` (`{prep_meta['train_row_count']:,}` rows, excluding `{prep_meta['val_row_count_excluded_from_fit']:,}` `VAL` and `{prep_meta['test_row_count_excluded_from_fit']:,}` `TEST` rows).
5. **Overlapping Target Purging**: 25 trading-day purge buffers (`PURGE_TRAIN_VAL` and `PURGE_VAL_TEST`) prevent 20-day target horizons (<=23 sessions max calendar span) inside Train/Val from touching the subsequent evaluation split, supplemented by sample concurrency weights (`sample_uniqueness_5d`, `sample_uniqueness_20d`).
6. **Historical Universe Preserved**: All `{daily_meta['distinct_symbols']}` historical equity tickers (including inactive/delisted stocks prior to 2026) remain in the panel alongside causal `is_trailing_top100_liquid` to mitigate survivorship bias.

## 4. Unresolved Data-Quality Issues Requiring Future Ingestion
1. **Zero Historical Intraday Feed**: Multi-year 1m/5m historical bars do not exist in PSXpert sources; scheduled live intraday scraping must accumulate history before `30m`/`60m` intraday forecasting is viable.
2. **Historical News Density (Pre-Oct 2026)**: Only 64 archive articles span 2002–2024 on synthetic `June 15` dates. Full historical Dawn/Business Recorder date-by-date backfills are needed before relying heavily on NLP features in multi-decade backtests.
3. **711 Unclassified Sectors (`companies`)**: Non-KSE-100 companies from `Immad-Baber/PSX-Data-` lack industry tags (`OTHER / UNCLASSIFIED`).
4. **No Point-in-Time Historical KSE-100 Constituents**: `companies.is_kse100` reflects October 2026 constituency only. Use causal `is_trailing_top100_liquid` when selecting liquid universes historically.
5. **Corporate Payouts Placeholder Table**: Raw DB `corporate_payouts` still contains 1,381 upstream `'type'` junk rows (filtered out by predictive pipeline; source DB left untouched per scope rules).
"""
    leak_md.write_text(leak_text, encoding="utf-8")
    created_files.append(str(leak_md))

    # 5. Chronological Splits & Overlap Policy Report (Deliverable 7)
    sp_md = reports_dir / "CHRONOLOGICAL_SPLITS_AND_OVERLAP_POLICY.md"
    splits_meta = daily_meta["splits"]
    prim_rows = "\n".join(
        f"| `{s['name']}` | `{s['start_date']}` | `{s['end_date']}` | {s['trading_days']:,} | {s['purpose']} |"
        for s in splits_meta["primary_splits"]
    )
    fund_rows = "\n".join(
        f"| `{s['name']}` | `{s['start_date']}` | `{s['end_date']}` | {s['trading_days']:,} |"
        for s in splits_meta["fundamentals_subsplits"]
    )
    wf_rows = "\n".join(
        f"| Fold {f['fold']} | `{f['train_start']}..{f['train_effective_end']}` ({f['train_sessions']:,}d) | `{f['purge_start']}..{f['purge_end']}` ({f['purge_days']}d) | `{f['test_start']}..{f['test_end']}` ({f['test_sessions']:,}d) |"
        for f in splits_meta["walk_forward_folds"]
    )

    sp_text = f"""# Chronological Split Definitions & Overlapping-Label Purge Policy

## 1. Primary Full-History Chronological Splits (2002–2026)
- **Calendar**: `{splits_meta['calendar_source']}` ({splits_meta['total_trading_days']:,} trading sessions from `{splits_meta['start_date']}` to `{splits_meta['end_date']}`).
- **Purge Policy**: **{splits_meta['max_target_horizon_days']} trading days** (`25`-session buffer covering max `<=23`-session calendar span of `20d` targets) purged strictly before Validation and before Test so ZERO future-return targets overlap into subsequent splits.

| Split Name | Start Date | End Date | Trading Days | Purpose |
| :--- | :--- | :--- | ---: | :--- |
{prim_rows}

## 2. Fundamentals-Dense Sub-Regime Splits (2022–2026)
For forecasting models requiring audited IFRS accounting ratios (`fin_*`, populated 2022–2026):

| Sub-Split | Start Date | End Date | Trading Days |
| :--- | :--- | :--- | ---: |
{fund_rows}

## 3. Rolling Expanding Walk-Forward Validation Folds (With 25-Day Purge)
| Fold | Effective Train Window | Purged Buffer | Out-of-Sample Test Window |
| :--- | :--- | :--- | :--- |
{wf_rows}
"""
    sp_md.write_text(sp_text, encoding="utf-8")
    created_files.append(str(sp_md))

    return created_files
