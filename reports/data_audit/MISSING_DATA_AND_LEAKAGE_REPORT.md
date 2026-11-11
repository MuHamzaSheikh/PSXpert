# Missing-Data & Anti-Leakage Verification Report

## 1. Summary of Missingness & Coverage Characteristics
- **Daily Feature Table**: `2,024,340` observations x `158` columns (`2002-01-01` -> `2026-10-13`).
- **Expected Structural Missingness (Honest NaN / Masked — NOT Backfilled)**:
  - **Indicator Warmup Bars**: First `14..200` sessions per stock listing remain `NaN` (`min_periods=20/50/200`); `.bfill()` is strictly forbidden.
  - **True-OHLC Masked Features** (`candle_*`, `parkinson_vol_20d`, `hl_spread_pct`, `overnight_gap_pct`): Explicitly set to `NaN` when `is_true_ohlc == 0` (~19% of raw bars) to prevent flat-bar phantom signals.
  - **Financial Ratios (`fin_*`)**: Available only from `~2022` onward across ~140 audited IFRS firms (`has_fundamentals = 1`). Historical rows prior to first disclosed filing remain `NaN`; a dedicated `FUND_TRAIN/VAL/TEST` preprocessing profile is fitted on `FUND_TRAIN` (`2022–2024`) alongside full-history `TRAIN` (`2002–2021`).
  - **News Sentiment (`news_*`)**: Extremely sparse pre-Oct 2026 (`118` total aligned articles; `131` post-`2026-10-13` articles excluded). Accompanied by `has_stock_news_7d`, `has_sector_news_7d`, and `has_mkt_news_7d` masks.
  - **Sector Returns (`sector_ret_*`)**: Masked `NaN` for `711` companies lacking genuine PSX sector classifications or single-peer sectors.
  - **Intraday Dataset**: `0` rows (`UNAVAILABLE_NO_HISTORICAL_INTRADAY_SOURCE`).

## 2. Target Class Distribution & Valid Sample Counts
Calibrated using causal threshold `theta_h = 0.0050 (50 bps PSX round-trip cost) + 0.35 * max(vol_20d[t], 0.005) * sqrt(h)`:

| Horizon | Valid Targets | Masked Invalid Targets | UP % | NEUTRAL % | DOWN % |
| :--- | ---: | ---: | ---: | ---: | ---: |
| **1-Day** | 1,782,766 | 241,574 | 26.32% | 47.96% | 25.73% |
| **5-Day** | 1,618,949 | 405,391 | 29.97% | 40.89% | 29.14% |
| **20-Day** | 1,424,875 | 599,465 | 34.22% | 34.96% | 30.82% |

## 3. Data-Leakage Safeguards Implemented
1. **No Future-Smoothed HMM States**: `CausalMarketRegimeHMM` fits parameters exclusively on `split == 'TRAIN'` and computes filtered probabilities $P(S_t | X_{1:t})$ via forward-only recursion in log space.
2. **Financial Publication Dates Enforced**: All fundamentals merge backward via `merge_asof` on `effective_pub_date <= trading_date` (never `period_end_date`), using verified PSX `Earnings Announcements` or a conservative `+100d` lag fallback.
3. **News Session Cutoff Enforced**: Articles published after `15:30 PKT` roll forward to the next open session; Oct 14–20 news after `2026-10-13` is completely excluded.
4. **Train-Only Preprocessing & Feature Screening**: Quantile clipping (`1%/99%`), median imputation, scaling parameters, and Mutual Information / Spearman screening (`train_feature_screening.csv`) are computed strictly on `TRAIN` (`1,552,063` rows, excluding `206,146` `VAL` and `246,397` `TEST` rows).
5. **Overlapping Target Purging**: 25 trading-day purge buffers (`PURGE_TRAIN_VAL` and `PURGE_VAL_TEST`) prevent 20-day target horizons (<=23 sessions max calendar span) inside Train/Val from touching the subsequent evaluation split, supplemented by sample concurrency weights (`sample_uniqueness_5d`, `sample_uniqueness_20d`).
6. **Historical Universe Preserved**: All `726` historical equity tickers (including inactive/delisted stocks prior to 2026) remain in the panel alongside causal `is_trailing_top100_liquid` to mitigate survivorship bias.

## 4. Unresolved Data-Quality Issues Requiring Future Ingestion
1. **Zero Historical Intraday Feed**: Multi-year 1m/5m historical bars do not exist in PSXpert sources; scheduled live intraday scraping must accumulate history before `30m`/`60m` intraday forecasting is viable.
2. **Historical News Density (Pre-Oct 2026)**: Only 64 archive articles span 2002–2024 on synthetic `June 15` dates. Full historical Dawn/Business Recorder date-by-date backfills are needed before relying heavily on NLP features in multi-decade backtests.
3. **711 Unclassified Sectors (`companies`)**: Non-KSE-100 companies from `Immad-Baber/PSX-Data-` lack industry tags (`OTHER / UNCLASSIFIED`).
4. **No Point-in-Time Historical KSE-100 Constituents**: `companies.is_kse100` reflects October 2026 constituency only. Use causal `is_trailing_top100_liquid` when selecting liquid universes historically.
5. **Corporate Payouts Placeholder Table**: Raw DB `corporate_payouts` still contains 1,381 upstream `'type'` junk rows (filtered out by predictive pipeline; source DB left untouched per scope rules).
