# PSXpert Daily & Intraday Feature Dictionary

**Total Daily Feature Columns Cataloged:** 158 | **Daily Rows:** 2,024,340 | **Intraday Rows:** 0 (schema only)

## Daily Features by Domain

| Feature | Domain Group | Type | Causality & Point-in-Time Policy | Description |
| :--- | :--- | :--- | :--- | :--- |
| `symbol` | `0_Keys_Metadata` | `string` | Static ID | PSX equity ticker symbol. |
| `trading_date` | `0_Keys_Metadata` | `date` | Calendar Key | PSX genuine Mon-Fri exchange session date aligned to KSE-100 calendar. |
| `cal_idx` | `0_Keys_Metadata` | `int64` | Calendar Key | 0-based sequential index over PSX exchange trading days. |
| `sector` | `0_Keys_Metadata` | `string` | Static Snapshot | PSX sector classification (711 non-KSE100 firms are unclassified). |
| `has_valid_sector` | `0_Keys_Metadata` | `int8` | Metadata Flag | 1 if symbol has a true PSX industry sector (excludes OTHER/UNCLASSIFIED). |
| `is_current_kse100` | `0_Keys_Metadata` | `int8` | WARNING: Current Snapshot | 1 if symbol is in KSE-100 as of Oct 2026 (NOT historical constituency; do not filter historical universe strictly on this flag). |
| `is_active_listing_snapshot` | `0_Keys_Metadata` | `int8` | WARNING: Current Snapshot | Active status as of 2026 snapshot; included for reference only. |
| `is_shariah` | `0_Keys_Metadata` | `int8` | Static Snapshot | 1 if Shariah-compliant KMI indicator flag is set in directory. |
| `split` | `0_Keys_Metadata` | `string` | Split Label | Chronological partition: TRAIN, PURGE_TRAIN_VAL, VAL, PURGE_VAL_TEST, or TEST. |
| `fundamentals_regime_split` | `0_Keys_Metadata` | `string` | Split Label | Sub-split (2022-2026) where audited IFRS statements exist (FUND_TRAIN/VAL/TEST + purges). |
| `listing_age_sessions` | `0_Keys_Metadata` | `int64` | Causal Point-in-Time | Cumulative trading sessions observed for symbol up to trading_date. |
| `trailing_20d_adv_rank` | `0_Keys_Metadata` | `float64` | Causal Point-in-Time | Daily cross-sectional rank by trailing 20-day average PKR turnover (1 = most liquid). |
| `is_trailing_top100_liquid` | `0_Keys_Metadata` | `int8` | Causal Point-in-Time | Leak-free point-in-time liquid universe proxy: 1 if trailing_20d_adv_rank <= 100. |
| `is_true_ohlc` | `0_Keys_Metadata` | `int8` | Bar Quality Flag | 1 when raw bar has genuine spread (high > low) and valid OHLC envelope. |
| `is_zero_volume` | `0_Keys_Metadata` | `int8` | Bar Quality Flag | 1 when daily volume <= 0. |
| `calendar_gap_days` | `0_Keys_Metadata` | `int32` | Causal Point-in-Time | PSX sessions elapsed since symbol's previous observation (1 = consecutive day). |
| `raw_open` | `1_Stock_OHLCV` | `float64` | Causal EOD | Nominal unadjusted opening price in PKR. |
| `raw_high` | `1_Stock_OHLCV` | `float64` | Causal EOD | Nominal unadjusted session high in PKR. |
| `raw_low` | `1_Stock_OHLCV` | `float64` | Causal EOD | Nominal unadjusted session low in PKR. |
| `raw_close` | `1_Stock_OHLCV` | `float64` | Causal EOD | Nominal unadjusted closing price in PKR. |
| `adj_open` | `1_Stock_OHLCV` | `float64` | Split-Adjusted Reference | Split-adjusted open price for return/indicator continuity. |
| `adj_high` | `1_Stock_OHLCV` | `float64` | Split-Adjusted Reference | Split-adjusted high price. |
| `adj_low` | `1_Stock_OHLCV` | `float64` | Split-Adjusted Reference | Split-adjusted low price. |
| `adj_close` | `1_Stock_OHLCV` | `float64` | Split-Adjusted Reference | Split-adjusted close price (scale-invariant ratios computed from adj_* have zero leak). |
| `volume` | `1_Stock_OHLCV` | `int64` | Causal EOD | Daily traded share volume. |
| `turnover_pkr` | `1_Stock_OHLCV` | `float64` | Causal EOD | Approximate daily rupee traded value (raw_close * volume). |
| `market_cap` | `1_Stock_OHLCV` | `float64` | Causal EOD (KSE-100 only) | Historical point-in-time market capitalization in PKR (populated on 100 Sarmaaya symbols). |
| `market_cap_missing_flag` | `1_Stock_OHLCV` | `int8` | Missingness Flag | 1 if historical market_cap was NULL (requiring share-count fallback for valuation ratios). |
| `sma_20` | `2_Technical_Indicators` | `float64` | Causal min_periods=20 | 20-day Simple Moving Average of adj_close. |
| `sma_50` | `2_Technical_Indicators` | `float64` | Causal min_periods=50 | 50-day Simple Moving Average of adj_close. |
| `sma_200` | `2_Technical_Indicators` | `float64` | Causal min_periods=200 | 200-day Simple Moving Average of adj_close. |
| `ema_12` | `2_Technical_Indicators` | `float64` | Causal min_periods=12 | 12-day Exponential Moving Average of adj_close. |
| `ema_26` | `2_Technical_Indicators` | `float64` | Causal min_periods=26 | 26-day Exponential Moving Average of adj_close. |
| `ema_20` | `2_Technical_Indicators` | `float64` | Causal min_periods=20 | 20-day Exponential Moving Average of adj_close. |
| `ema_50` | `2_Technical_Indicators` | `float64` | Causal min_periods=50 | 50-day Exponential Moving Average of adj_close. |
| `ema_200` | `2_Technical_Indicators` | `float64` | Causal min_periods=200 | 200-day Exponential Moving Average of adj_close. |
| `dist_sma_20` | `2_Technical_Indicators` | `float64` | Causal Stationary | Relative distance from 20-day SMA: (adj_close / sma_20) - 1. |
| `dist_sma_50` | `2_Technical_Indicators` | `float64` | Causal Stationary | Relative distance from 50-day SMA: (adj_close / sma_50) - 1. |
| `dist_sma_200` | `2_Technical_Indicators` | `float64` | Causal Stationary | Relative distance from 200-day SMA: (adj_close / sma_200) - 1. |
| `dist_ema_20` | `2_Technical_Indicators` | `float64` | Causal Stationary | Relative distance from 20-day EMA: (adj_close / ema_20) - 1. |
| `ema_20_50_spread` | `2_Technical_Indicators` | `float64` | Causal Stationary | Medium-term trend spread: (ema_20 / ema_50) - 1. |
| `ema_50_200_spread` | `2_Technical_Indicators` | `float64` | Causal Stationary | Long-term golden/death cross spread: (ema_50 / ema_200) - 1. |
| `rsi_14` | `2_Technical_Indicators` | `float64` | Causal min_periods=14 | 14-period Wilder Relative Strength Index [0..100]. |
| `macd_line` | `2_Technical_Indicators` | `float64` | Causal | ema_12 - ema_26. |
| `macd_signal` | `2_Technical_Indicators` | `float64` | Causal min_periods=9 | 9-day EMA of macd_line. |
| `macd_diff` | `2_Technical_Indicators` | `float64` | Causal | MACD Histogram (macd_line - macd_signal). |
| `macd_diff_pct` | `2_Technical_Indicators` | `float64` | Causal Stationary | Price-normalized MACD histogram (macd_diff / adj_close). |
| `bb_middle` | `2_Technical_Indicators` | `float64` | Causal min_periods=20 | 20-day Bollinger middle band (sma_20). |
| `bb_upper` | `2_Technical_Indicators` | `float64` | Causal min_periods=20 | 20-day Bollinger upper band (+2 std). |
| `bb_lower` | `2_Technical_Indicators` | `float64` | Causal min_periods=20 | 20-day Bollinger lower band (-2 std). |
| `bb_bandwidth` | `2_Technical_Indicators` | `float64` | Causal Stationary | Normalized Bollinger band width (%) relative to bb_middle. |
| `bb_percent_b` | `2_Technical_Indicators` | `float64` | Causal Stationary | Bollinger %B relative position: (close - lower) / (upper - lower). |
| `atr_14` | `2_Technical_Indicators` | `float64` | Causal min_periods=14 | 14-period Wilder Average True Range in PKR. |
| `atr_pct` | `2_Technical_Indicators` | `float64` | Causal Stationary | ATR as % of adj_close (volatility normalized). |
| `dmi_plus_14` | `2_Technical_Indicators` | `float64` | Causal min_periods=14 | 14-period Positive Directional Indicator (+DI). |
| `dmi_minus_14` | `2_Technical_Indicators` | `float64` | Causal min_periods=14 | 14-period Negative Directional Indicator (-DI). |
| `adx_14` | `2_Technical_Indicators` | `float64` | Causal min_periods=14 | 14-period Average Directional Index (trend strength). |
| `dmi_diff` | `2_Technical_Indicators` | `float64` | Causal Stationary | Directional balance (+DI - -DI). |
| `obv` | `2_Technical_Indicators` | `float64` | Causal Cumulative | Cumulative On-Balance Volume. |
| `obv_zscore_20` | `2_Technical_Indicators` | `float64` | Causal Stationary | 20-day rolling z-score of OBV measuring recent accumulation/distribution surge. |
| `stoch_k` | `2_Technical_Indicators` | `float64` | Causal min_periods=14 | Slow Stochastic %K (14, 3). |
| `stoch_d` | `2_Technical_Indicators` | `float64` | Causal min_periods=14 | Slow Stochastic %D (3-day SMA of %K). |
| `stoch_k_minus_d` | `2_Technical_Indicators` | `float64` | Causal Stationary | Stochastic momentum oscillator spread (%K - %D). |
| `candle_body_pct` | `3_Candlestick_Patterns` | `float64` | Causal (True OHLC only) | Signed body relative to close: (close - open) / close; NaN on flat EOD bars. |
| `candle_range_pct` | `3_Candlestick_Patterns` | `float64` | Causal (True OHLC only) | High-low range relative to close; NaN when is_true_ohlc == 0. |
| `upper_shadow_ratio` | `3_Candlestick_Patterns` | `float64` | Causal (True OHLC only) | Upper shadow divided by total high-low candle range. |
| `lower_shadow_ratio` | `3_Candlestick_Patterns` | `float64` | Causal (True OHLC only) | Lower shadow divided by total high-low candle range. |
| `body_to_range_ratio` | `3_Candlestick_Patterns` | `float64` | Causal (True OHLC only) | Absolute body size divided by total high-low candle range. |
| `close_position_in_range` | `3_Candlestick_Patterns` | `float64` | Causal (True OHLC only) | (close - low) / (high - low) in [0, 1]. |
| `candlestick_pattern_name` | `3_Candlestick_Patterns` | `string` | Causal (True OHLC only) | Detected classical candlestick formation matching CandlestickPatternDetector; NONE on flat bars. |
| `candlestick_pattern_signal_num` | `3_Candlestick_Patterns` | `int8` | Causal (True OHLC only) | Encoded formation signal: +2 Strong Buy, +1 Buy, 0 Neutral/None, -1 Sell, -2 Strong Sell. |
| `is_bullish_pattern` | `3_Candlestick_Patterns` | `int8` | Causal (True OHLC only) | 1 if bullish candlestick formation detected today. |
| `is_bearish_pattern` | `3_Candlestick_Patterns` | `int8` | Causal (True OHLC only) | 1 if bearish candlestick formation detected today. |
| `is_doji_true_ohlc` | `3_Candlestick_Patterns` | `int8` | Causal (True OHLC only) | 1 if genuine Doji on a true OHLC bar (fixes flat-bar false Doji bug). |
| `bullish_patterns_5d` | `3_Candlestick_Patterns` | `int8` | Causal | Rolling 5-session count of bullish candlestick formations. |
| `bearish_patterns_5d` | `3_Candlestick_Patterns` | `int8` | Causal | Rolling 5-session count of bearish candlestick formations. |
| `hmm_mkt_prob_bullish` | `4_HMM_Regimes` | `float64` | Strictly Filtered P(S_t|X_1:t) | Causal forward-filtered probability of Bullish KSE-100 regime (Train-fitted HMM, zero smoothing). |
| `hmm_mkt_prob_bearish` | `4_HMM_Regimes` | `float64` | Strictly Filtered P(S_t|X_1:t) | Causal forward-filtered probability of Bearish KSE-100 regime. |
| `hmm_mkt_prob_sideways` | `4_HMM_Regimes` | `float64` | Strictly Filtered P(S_t|X_1:t) | Causal forward-filtered probability of Sideways KSE-100 regime. |
| `hmm_mkt_regime_id` | `4_HMM_Regimes` | `float64` | Strictly Filtered | Argmax filtered state: 1=BULLISH, 0=SIDEWAYS, -1=BEARISH. |
| `hmm_mkt_entropy` | `4_HMM_Regimes` | `float64` | Strictly Filtered | Shannon entropy of filtered HMM state probabilities (regime transition uncertainty). |
| `hmm_mkt_regime_duration` | `4_HMM_Regimes` | `float64` | Strictly Filtered | Consecutive trading days spent in the current causal HMM regime. |
| `news_mkt_count_1d` | `5_News_Sentiment` | `int32` | Causal PKT 15:30 cutoff | Count of market/macro articles observable by 15:30 PKT on trading_date. |
| `news_mkt_sent_mean_1d` | `5_News_Sentiment` | `float64` | Causal PKT 15:30 cutoff | Mean FinBERT score [-1, +1] of market articles observable on trading_date. |
| `news_mkt_count_7d` | `5_News_Sentiment` | `int32` | Causal 7-session window | Trailing 7-session count of observable FinBERT news articles. |
| `news_mkt_sent_mean_7d` | `5_News_Sentiment` | `float64` | Causal 7-session window | Trailing 7-session mean market FinBERT sentiment score. |
| `news_mkt_neg_share_7d` | `5_News_Sentiment` | `float64` | Causal 7-session window | Fraction of trailing 7-session market news classified NEGATIVE by FinBERT. |
| `has_mkt_news_7d` | `5_News_Sentiment` | `int8` | Availability Mask | 1 if >= 1 market article exists in trailing 7 sessions (prevents confusing missing coverage with neutral 0). |
| `news_stock_count_1d` | `5_News_Sentiment` | `int32` | Causal PKT 15:30 cutoff | 1-day count of articles mentioning or sector-targeting symbol. |
| `news_stock_sent_mean_1d` | `5_News_Sentiment` | `float64` | Causal PKT 15:30 cutoff | 1-day stock-linked mean FinBERT sentiment score. |
| `news_stock_count_7d` | `5_News_Sentiment` | `int32` | Causal 7-session window | Trailing 7-session stock-linked article count. |
| `news_stock_sent_mean_7d` | `5_News_Sentiment` | `float64` | Causal 7-session window | Trailing 7-session stock-linked mean FinBERT sentiment score. |
| `has_stock_news_7d` | `5_News_Sentiment` | `int8` | Availability Mask | 1 if >= 1 stock-linked article exists in trailing 7 sessions. |
| `news_sector_count_7d` | `5_News_Sentiment` | `int32` | Causal 7-session window | Trailing 7-session article count targeting symbol's PSX sector. |
| `news_sector_sent_mean_7d` | `5_News_Sentiment` | `float64` | Causal 7-session window | Trailing 7-session sector mean FinBERT sentiment score. |
| `has_sector_news_7d` | `5_News_Sentiment` | `int8` | Availability Mask | 1 if >= 1 sector-linked article exists in trailing 7 sessions. |
| `fin_period_end_date` | `6_Financial_Ratios_PIT` | `date` | Audit Metadata | Fiscal accounting close date of most recently disclosed IFRS statement. |
| `effective_pub_date` | `6_Financial_Ratios_PIT` | `date` | Causal Publication Gate | Matched PSX Earnings Announcement posting date (or period_end + 100d conservative fallback). |
| `fin_pub_verified_flag` | `6_Financial_Ratios_PIT` | `float64` | Audit Metadata | 1 if exact PSX announcement date matched; 0 if +100d statutory lag fallback applied. |
| `has_fundamentals` | `6_Financial_Ratios_PIT` | `int8` | Availability Mask | 1 if audited IFRS filing has been published as of trading_date. |
| `fin_staleness_days` | `6_Financial_Ratios_PIT` | `float64` | Causal Point-in-Time | Calendar days elapsed since effective_pub_date. |
| `fin_gross_margin` | `6_Financial_Ratios_PIT` | `float64` | As-of effective_pub_date | Gross Profit / Total Revenue. |
| `fin_operating_margin` | `6_Financial_Ratios_PIT` | `float64` | As-of effective_pub_date | Operating Income / Total Revenue. |
| `fin_net_margin` | `6_Financial_Ratios_PIT` | `float64` | As-of effective_pub_date | Net Income / Total Revenue. |
| `fin_roe` | `6_Financial_Ratios_PIT` | `float64` | As-of effective_pub_date | Return on Equity: Net Income / Stockholders Equity. |
| `fin_roa` | `6_Financial_Ratios_PIT` | `float64` | As-of effective_pub_date | Return on Assets: Net Income / Total Assets. |
| `fin_fcf_margin` | `6_Financial_Ratios_PIT` | `float64` | As-of effective_pub_date | Free Cash Flow / Total Revenue. |
| `fin_ocf_to_ni` | `6_Financial_Ratios_PIT` | `float64` | As-of effective_pub_date | Earnings quality ratio: Operating Cash Flow / Net Income. |
| `fin_debt_to_equity` | `6_Financial_Ratios_PIT` | `float64` | As-of effective_pub_date | Total Debt / Stockholders Equity. |
| `fin_debt_to_assets` | `6_Financial_Ratios_PIT` | `float64` | As-of effective_pub_date | Total Debt / Total Assets. |
| `fin_current_ratio` | `6_Financial_Ratios_PIT` | `float64` | As-of effective_pub_date | Current Assets / Current Liabilities. |
| `fin_revenue_yoy_growth` | `6_Financial_Ratios_PIT` | `float64` | As-of effective_pub_date | YoY revenue growth relative to previously disclosed statement. |
| `fin_net_income_yoy_growth` | `6_Financial_Ratios_PIT` | `float64` | As-of effective_pub_date | YoY net income growth relative to previously disclosed statement. |
| `fin_earnings_yield_pit` | `6_Financial_Ratios_PIT` | `float64` | Split-Invariant PIT | Disclosed Net Income / current Market Cap (E/P inverse P/E, split-invariant). |
| `fin_book_to_price_pit` | `6_Financial_Ratios_PIT` | `float64` | Split-Invariant PIT | Disclosed Stockholders Equity / current Market Cap (B/P inverse P/B). |
| `fin_sales_to_price_pit` | `6_Financial_Ratios_PIT` | `float64` | Split-Invariant PIT | Disclosed Total Revenue / current Market Cap (S/P inverse P/S). |
| `fin_fcf_yield_pit` | `6_Financial_Ratios_PIT` | `float64` | Split-Invariant PIT | Disclosed Free Cash Flow / current Market Cap. |
| `kse100_close` | `7_Market_And_Sector` | `float64` | Causal Index Close | KSE-100 index daily closing level (reference scale only; use stationary features for modeling). |
| `kse100_ret_1d` | `7_Market_And_Sector` | `float64` | Causal Index Close | 1-day KSE-100 index return. |
| `kse100_ret_5d` | `7_Market_And_Sector` | `float64` | Causal Index Close | 5-day KSE-100 index return. |
| `kse100_ret_20d` | `7_Market_And_Sector` | `float64` | Causal Index Close | 20-day KSE-100 index return. |
| `kse100_log_ret_1d` | `7_Market_And_Sector` | `float64` | Causal Index Close | Daily KSE-100 log return. |
| `kse100_vol_20d` | `7_Market_And_Sector` | `float64` | Causal min_periods=20 | 20-day KSE-100 log-return realized volatility. |
| `kse100_dist_sma50` | `7_Market_And_Sector` | `float64` | Causal min_periods=50 | KSE-100 close distance from 50-day SMA. |
| `kse100_dist_sma200` | `7_Market_And_Sector` | `float64` | Causal min_periods=200 | KSE-100 close distance from 200-day SMA. |
| `kse100_rsi_14` | `7_Market_And_Sector` | `float64` | Causal min_periods=14 | 14-period Wilder RSI of KSE-100. |
| `mkt_median_ret_1d` | `7_Market_And_Sector` | `float64` | Causal Cross-Section | Median daily return across clean equity universe on trading_date. |
| `mkt_pct_above_sma50` | `7_Market_And_Sector` | `float64` | Causal Cross-Section | Fraction of PSX equities trading above their 50-day SMA. |
| `mkt_adv_decline_ratio` | `7_Market_And_Sector` | `float64` | Causal Cross-Section | (Advances - Declines) / Active equities on trading_date. |
| `sector_ret_1d` | `7_Market_And_Sector` | `float64` | Causal Leave-One-Out | Equal-weighted 1-day return of sector peers (min 2 peers, excludes self & unclassified). |
| `sector_ret_5d` | `7_Market_And_Sector` | `float64` | Causal Leave-One-Out | Equal-weighted 5-day return of sector peers. |
| `sector_ret_20d` | `7_Market_And_Sector` | `float64` | Causal Leave-One-Out | Equal-weighted 20-day return of sector peers. |
| `stock_minus_sector_ret_5d` | `7_Market_And_Sector` | `float64` | Causal Relative | Stock 5-day outperformance relative to sector peers. |
| `rel_strength_kse100_5d` | `7_Market_And_Sector` | `float64` | Causal Relative | Stock 5-day return minus KSE-100 5-day return. |
| `rel_strength_kse100_20d` | `7_Market_And_Sector` | `float64` | Causal Relative | Stock 20-day return minus KSE-100 20-day return. |
| `rolling_beta_60d` | `7_Market_And_Sector` | `float64` | Causal min_periods=40 | 60-session trailing OLS Beta vs KSE-100 log returns. |
| `rolling_corr_kse100_60d` | `7_Market_And_Sector` | `float64` | Causal min_periods=40 | 60-session trailing Pearson correlation with KSE-100 log returns. |
| `ret_1d` | `8_Liquidity_Volatility` | `float64` | Causal EOD | 1-day simple split-adjusted return (NaN after gaps > 15 sessions). |
| `log_ret_1d` | `8_Liquidity_Volatility` | `float64` | Causal EOD | 1-day log split-adjusted return. |
| `ret_2d` | `8_Liquidity_Volatility` | `float64` | Causal Gap-Guarded | 2-session split-adjusted return. |
| `ret_5d` | `8_Liquidity_Volatility` | `float64` | Causal Gap-Guarded | 5-session split-adjusted return. |
| `ret_10d` | `8_Liquidity_Volatility` | `float64` | Causal Gap-Guarded | 10-session split-adjusted return. |
| `ret_20d` | `8_Liquidity_Volatility` | `float64` | Causal Gap-Guarded | 20-session split-adjusted return. |
| `ret_60d` | `8_Liquidity_Volatility` | `float64` | Causal Gap-Guarded | 60-session split-adjusted return. |
| `vol_5d` | `8_Liquidity_Volatility` | `float64` | Causal min_periods=5 | 5-day realized daily log-return std. |
| `vol_20d` | `8_Liquidity_Volatility` | `float64` | Causal min_periods=15 | 20-day realized daily log-return std (also drives causal target threshold). |
| `vol_60d` | `8_Liquidity_Volatility` | `float64` | Causal min_periods=40 | 60-day realized daily log-return std. |
| `vol_ratio_5_20` | `8_Liquidity_Volatility` | `float64` | Causal | Short-to-medium volatility ratio (vol_5d / vol_20d). |
| `parkinson_vol_20d` | `8_Liquidity_Volatility` | `float64` | Causal True-OHLC>=50% | 20-day Parkinson range volatility; masked NaN if <50% true OHLC bars. |
| `overnight_gap_pct` | `8_Liquidity_Volatility` | `float64` | Causal True-OHLC | (adj_open_t - adj_close_{t-1}) / adj_close_{t-1}. |
| `intraday_ret_pct` | `8_Liquidity_Volatility` | `float64` | Causal True-OHLC | (adj_close_t - adj_open_t) / adj_open_t. |
| `log_volume` | `8_Liquidity_Volatility` | `float64` | Causal | log1p(volume). |
| `log_turnover_pkr` | `8_Liquidity_Volatility` | `float64` | Causal | log1p(turnover_pkr). |
| `trailing_20d_adv_pkr` | `8_Liquidity_Volatility` | `float64` | Causal min_periods=10 | Trailing 20-day mean PKR turnover. |
| `volume_ratio_20d` | `8_Liquidity_Volatility` | `float64` | Causal | Volume surge ratio: volume / 20d SMA(volume). |
| `amihud_illiquidity_20d` | `8_Liquidity_Volatility` | `float64` | Causal | 20-day Amihud illiquidity: mean(|ret_1d| / (turnover_pkr / 1e6)). |
| `zero_volume_days_20d` | `8_Liquidity_Volatility` | `float64` | Causal | Count of zero-volume days inside trailing 20 sessions. |
| `hl_spread_pct` | `8_Liquidity_Volatility` | `float64` | Causal True-OHLC | (high - low) / close intraday trading range proxy. |

## Target Label Schema (`daily_targets.parquet`)

| Column Pattern | Horizons | Definition |
| :--- | :--- | :--- |
| `target_ret_{h}d` | `1d, 5d, 20d` | Split-adjusted forward return `adj_close[t+h]/adj_close[t] - 1` (masked NaN if `target_valid_{h}d == 0`) |
| `target_log_ret_{h}d` | `1d, 5d, 20d` | Forward log return `ln(1 + target_ret_{h}d)` |
| `target_threshold_{h}d` | `1d, 5d, 20d` | Causal volatility + PSX transaction-cost band: `0.0050 + 0.35 * max(vol_20d[t], 0.005) * sqrt(h)` |
| `target_dir_{h}d` | `1d, 5d, 20d` | 3-class direction: `1` (UP), `0` (NEUTRAL), `-1` (DOWN) |
| `target_label_{h}d` | `1d, 5d, 20d` | Text label: `UP`, `NEUTRAL`, `DOWN` |
| `target_valid_{h}d` | `1d, 5d, 20d` | `1` iff exact trading-day horizon, non-glitch horizon window, and valid `vol_20d[t]` |
| `sample_uniqueness_{h}d` | `5d, 20d` | Overlap concurrency weight `1/h` accounting for multi-day overlapping targets |

## Intraday Schema (`intraday_features.parquet` & `intraday_targets.parquet` — 0 Historical Rows)
Strict 5-minute bar schema (Asia/Karachi PKT, right-labeled & right-closed) isolated from daily data:

- **Features (`24` columns)**: `symbol`, `timestamp_pkt`, `trading_date`, `session_id`, `bar_frequency_min`, `open`, `high`, `low`, `close`, `volume`, `vwap_session`, `dist_vwap_pct`, `ret_1bar_5m`, `ret_3bar_15m`, `ret_6bar_30m`, `ret_12bar_60m`, `rsi_14_bar`, `realized_vol_12bar`, `parkinson_vol_12bar`, `volume_ratio_12bar`, `minutes_since_session_open`, `kse100_intraday_ret_5m`, `kse100_intraday_ret_30m`, `rel_strength_kse100_30m`.
- **Targets (`16` columns)**: `symbol`, `timestamp_pkt`, `trading_date`, `session_id`, plus `target_ret_{h}`, `target_threshold_{h}`, `target_dir_{h}`, `target_label_{h}`, `target_valid_{h}`, `target_end_ts_{h}` for `30m` (`6` bars) and `60m` (`12` bars) restricted strictly within the same `session_id`.