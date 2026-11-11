# PSXpert — Technical & Fundamental Analysis Engines Methodology & Audit Report

> **Scope Note**: This document covers the independent, point-in-time **Technical Analysis Engine** and **Fundamental Analysis Engine**, PostgreSQL persistence/caching, and FastAPI endpoints. Predictive forecasting models are **not** implemented in this phase.

---

## 1. Architecture & Independence

The analysis layer is organized under `src/analysis/` into decoupled modules so each engine can be invoked independently or together by the API, future forecasting pipelines, or screener workflows:

- [`common.py`](file:///c:/Users/HP/psxpert/src/analysis/common.py) — Company metadata resolution, KSE-100 trading calendar alignment, weekend phantom/non-positive price filtering, causal split adjustment helpers, JSON sanitization (`NaN`/`Inf`/`Decimal` protection).
- [`technical_engine.py`](file:///c:/Users/HP/psxpert/src/analysis/technical_engine.py) — `TechnicalAnalysisEngine` implementing 7 causal technical pillars + composite deterministic scoring. Reuses `TechnicalIndicatorCalculator`, `CandlestickPatternDetector`, `load_clean_corporate_actions`, `adjust_splits_and_flag_glitches`, and `CausalMarketRegimeHMM`.
- [`fundamental_engine.py`](file:///c:/Users/HP/psxpert/src/analysis/fundamental_engine.py) — `FundamentalAnalysisEngine` implementing 7 point-in-time fundamental pillars + composite deterministic scoring. Reuses `load_clean_corporate_actions` and `parse_ended_date_from_title`.
- [`persistence.py`](file:///c:/Users/HP/psxpert/src/analysis/persistence.py) — PostgreSQL `analysis_results` schema, SHA-256 `compute_source_fingerprint`, cache lookup, and transactional upserts (`ENGINE_VERSION = "psxpert_analysis_v1.1"`).
- [`service.py`](file:///c:/Users/HP/psxpert/src/analysis/service.py) — `AnalysisService` facade coordinating Technical-only, Fundamental-only, and Combined executions with cache validation.
- [`router.py`](file:///c:/Users/HP/psxpert/src/analysis/router.py) — FastAPI `APIRouter` mounted in [`app.py`](file:///c:/Users/HP/psxpert/app.py).

---

## 2. Technical Analysis Engine (`TechnicalAnalysisEngine`)

### 2.1 Data Hygiene & Point-in-Time Causal Controls
1. **Calendar & Phantom Filtering**: `stock_prices` rows are inner-joined onto active KSE-100 trading days (`market_indices` where `index_symbol = 'KSE100'` and `trading_date <= as_of_date`), excluding `close <= 0` and stripping 13,424 weekend phantom duplicate bars (`source_id = 2`) present in raw `stock_prices`.
2. **Causal Corporate Action Adjustment**: Corporate splits (`load_clean_corporate_actions`) are filtered strictly `<= as_of_date` before calling `adjust_splits_and_flag_glitches`, producing continuous `adj_open/high/low/close` series for indicator calculation while preserving nominal `raw_close` for spot quoting.
3. **Warmup Masking**: Even though `TechnicalIndicatorCalculator` fills short rolling windows via `min_periods=1`, `TechnicalAnalysisEngine` explicitly masks long-window indicators as `None` when insufficient history exists:
   - `< 20` sessions: `sma_20`, `ema_20`, Bollinger Bands, `rsi_14` masked (`None`)
   - `< 50` sessions: `sma_50`, `ema_50` masked (`None`); `long_term_trend = "INSUFFICIENT_HISTORY"`
   - `< 200` sessions: `sma_200`, `ema_200` masked (`None`)
4. **Flat-Bar Candlestick Guard**: Bars where `|High - Low| <= max(1e-6, |Close| * 1e-6)` (`is_flat_ohlc_bar`) are flagged and patterns generated on those bars inside `CandlestickPatternDetector` (notably synthetic `Doji` triggers when `High == Low`) are suppressed and counted cleanly in `suppressed_flat_bar_patterns`.

### 2.2 Seven Technical Pillars

| Domain | Indicators & Analytical Outputs |
|---|---|
| **1. Trend** | Short-term (`Close vs EMA 20`, `EMA 12 vs EMA 26`, 5-bar `EMA 20` slope), Long-term (`Close vs SMA 50/200`, `SMA 50 vs SMA 200` Golden/Death alignment & 10-bar crossovers), Trend Strength via `ADX (14)` (`>=40` Very Strong, `>=25` Strong, `>=18` Moderate, `<18` Weak/Range-bound) + `+DI / -DI` directional balance |
| **2. Momentum** | Wilder `RSI (14)` regime (`>=70` Overbought, `58-70` Bullish, `42-58` Neutral, `30-42` Bearish, `<=30` Oversold) + 5d change + causal 35-day bullish/bearish RSI divergence; `MACD (12,26,9)` line vs signal + histogram slope + 5-bar crossovers; `Stochastic (14,3,3)` `%K / %D` |
| **3. Volatility** | 20d & 60d annualized log-return volatility (`std * sqrt(252)`), empirical 252-day volatility percentile rank, `ATR (14)` & `ATR%` vs 20d avg (`EXPANDING` / `CONTRACTING` / `STABLE`), `Bollinger Bands (20,2)` width, `%B`, and 126-day squeeze (`<=20th` pct) / breakout detection |
| **4. Volume** | Daily volume vs `SMA 20` & `SMA 60` (`UNUSUAL_SURGE >= 2.0x`, `ABOVE_AVERAGE >= 1.3x`, `LOW_DRY_UP <= 0.6x`), 20d avg PKR turnover (`close * volume`), `OBV vs OBV EMA 20` accumulation/distribution state, and 20-day Price-vs-OBV divergence |
| **5. Candlesticks** | Trailing 10 sessions from `CandlestickPatternDetector` on non-flat OHLC bars, graded `STRONG` (3-candle / engulfing / marubozu), `MODERATE` (elevated-volume single/2-candle reversals), or `WEAK`, plus trailing 5d pattern bias |
| **6. Causal Support & Resistance** | Strictly causal zones from `<= as_of_date`: confirmed swing fractals (`k=3` needing `t+3 <= as_of_idx`), rolling extrema (`20d/60d/252d`), `SMA 50/200`, and trailing 252d volume-weighted price cluster nodes, merged within `1.5%` tolerance (`support_levels`, `resistance_levels`, 52W range position `%`) |
| **7. HMM Market Context** | `CausalMarketRegimeHMM` (`n_states=3`) fitted on KSE-100 index `<= min(as_of_date, 2021-11-26)`, outputting strictly forward-filtered state probabilities `P(S_t | X_{1:t})` (`bullish`, `sideways`, `bearish`), regime duration, entropy, and stock trailing 60-day Beta & Correlation to KSE-100 |

### 2.3 Deterministic Technical Score (`[-100, +100]`)

Each sub-score is bounded in `[-100, +100]` and combined transparently:

| Component | Weight | Key Inputs |
|---|---|---|
| `trend_structure` | `35%` | Short-term alignment (`±40`), Long-term SMA alignment (`±40`), `ADX >= 20` `+DI/-DI` directional confirmation (`±20`) |
| `momentum_signals` | `25%` | `RSI (14)` zone (`±40`, capped `+15/-15` in Overbought/Oversold extremes), `MACD diff` sign (`±35`), recent MACD cross (`±15`), causal RSI divergence (`±10`) |
| `volume_flow` | `15%` | `OBV vs OBV EMA 20` (`±50`), heavy-volume up/down bar (`±35`), 20d OBV divergence (`±15`) |
| `candlestick_and_levels` | `10%` | Recent (`<= 3` bars) valid non-flat patterns (`±45` Strong, `±25` Moderate) + immediate S/R proximity (`<= 2%`: `±20`) |
| `hmm_market_regime` | `15%` | `(P(Bullish) - P(Bearish)) * 100` from causal KSE-100 HMM filter |

- **Rating Bands**: `STRONG_BULLISH` (`>= +45`), `BULLISH` (`[+15, +45)`), `NEUTRAL` (`(-15, +15)`), `BEARISH` (`(-45, -15]`), `STRONG_BEARISH` (`<= -45`).

---

## 3. Fundamental Analysis Engine (`FundamentalAnalysisEngine`)

### 3.1 Accounting Hygiene & Point-in-Time Disclosure Controls
1. **Verified Statement Scope**: Uses audited IFRS `INCOME_STATEMENT`, `BALANCE_SHEET`, and `CASH_FLOW` records stored in full PKR (`1x`). Excludes legacy `ANNUAL` and `QUARTERLY` statement types due to sentinel corruption (`12121.0`, `435451.1`) and unit-scaling anomalies in those legacy tables.
2. **Public Disclosure Lag (`effective_pub_date <= as_of_date`)**: Reconstructs actual public availability by matching each statement's `period_end_date` to `corporate_announcements` (`category = 'Earnings Announcements'`) via `parse_ended_date_from_title` (`[period_end, period_end + 180d]`), falling back to `+100` calendar days statutory SECP/PSX lag when unmatched.
3. **Partial Filing Safeguards**: Incomplete annual filings lacking core Balance Sheet or Revenue rows (e.g., `OGDC 2025-06-30`) are excluded as primary balance-sheet/margin snapshots so ratios fall back cleanly to the latest complete disclosure (`has_complete_core`), with discrepancies noted explicitly in `data_quality_notes`.
4. **Derived EPS Disclosure Transparency**: When IFRS `basic_eps` is missing while `net_income` and `ordinary_shares_number > 0` exist (e.g., `OGDC 2026-06-30`), EPS is computed as `net_income / ordinary_shares_number` and tagged `eps_source = "derived_net_income_over_shares"`.
5. **Banking IFRS Safeguards**: For `COMMERCIAL BANKS` (`sector_category = "Banks"`), industrial `Operating Margin`, `Current Ratio`, and `Interest Coverage Ratio` are explicitly returned as `None` (never `0`) because deposit markup is operational cost of funds rather than corporate debt service.
6. **Split-Invariant Valuation & Repaired Dividends**:
   - **P/E & P/B**: Computed via `market_cap / net_income` and `market_cap / common_stock_equity` using point-in-time `stock_prices.market_cap <= as_of_date`, avoiding 5x errors when Yahoo-sourced IFRS historical EPS/shares were retrospectively split-restated (`LUCK`, `SYS`). Undefined (`None`) when Net Income `<= 0` or Equity `<= 0`.
   - **Dividends**: Validates `corporate_payouts` (`payout_type = 'dividend'`, `announcement_date <= as_of_date`) against `payout_percentage * face_value / 100` (fixing 12 scraper face-value errors where Rs 2/5 par shares were scaled by Rs 10), split-adjusts pre-split announcements to cutoff share basis, and pairs TTM announced yield with multi-year `CASH_FLOW.cash_dividends_paid` payout ratios & FCF coverage.

### 3.2 Seven Fundamental Pillars

| Domain | Metrics & Formula Definitions |
|---|---|
| **1. Profitability** | `EPS` (reported or derived), `ROE = Net Income / Common Equity`, `ROA = Net Income / Total Assets`, `Net Margin = Net Income / Total Revenue`, `Operating Margin` & `Gross Margin` (non-bank) |
| **2. Valuation** | Point-in-time `P/E`, `P/B`, `Earnings Yield = 1 / P/E`, `Dividend Yield` (primary: TTM split-adjusted announced DPS / spot price; fallback: `|cash_dividends_paid| / Market Cap`) |
| **3. Financial Health** | `Debt/Equity = Total Debt / Common Equity`, `Debt/Assets`, `Equity/Assets`, `Current Ratio = Current Assets / Current Liabilities` (non-bank), `Interest Coverage = EBIT / |Interest Expense|` (non-bank, `operating_income` fallback when `ebit` missing) |
| **4. Growth** | Strictly 1Y YoY (`300–430d` spacing) `Revenue YoY`, `Net Income YoY`, `EPS YoY`, plus multi-year CAGR (`>= 3` complete periods) |
| **5. Cash Flow** | `Operating Cash Flow`, `CapEx`, `Free Cash Flow` (`reported` or `OCF - |CapEx|`), `FCF Margin`, `Earnings Quality (OCF / Net Income)`, multi-year OCF trend |
| **6. Dividends** | Historical cash announcements + 4–5Y `CASH_FLOW.cash_dividends_paid`, payout ratio, FCF dividend coverage, payout consistency classification |
| **7. Sector Comparison** | Same-sector peer medians where peer's latest complete period is within `+/- 370` calendar days of target's `period_end_date` and minimum `>= 2` valid peers exist; otherwise `INSUFFICIENT_SECTOR_DATA` |

### 3.3 Deterministic Fundamental Score (`[0, 100]`)

Weighted across observable applicable domains (automatically renormalizing weights if an industrial domain such as Banking Operating Margin/Current Ratio/Interest Coverage or Growth is N/A):
- `profitability` (`30%`): ROE (`25%` anchor), ROA (`2%` banks / `12%` corporates anchor), Net Margin (`20%` anchor), Operating Margin (`25%` anchor)
- `valuation` (`20%`): P/E attractiveness + P/B attractiveness
- `financial_health` (`20%`): Debt/Equity, Current Ratio (non-bank), Interest Coverage (non-bank)
- `growth` (`15%`): Revenue YoY & Net Income YoY
- `cash_flow_and_dividends` (`15%`): OCF/NI cash conversion, positive FCF check, Dividend Yield
- **Rating Bands**: `STRONG` (`>= 72`), `CONSTRUCTIVE` (`[55, 72)`), `MODERATE` (`[40, 55)`), `WEAK` (`< 40`), or `INSUFFICIENT_FUNDAMENTAL_DATA` (`None` when IFRS statements absent).

---

## 4. FastAPI Integration & PostgreSQL Caching

- **Database Table (`analysis_results`)**: Automatically provisioned idempotently by `ensure_analysis_results_table`, storing `symbol`, `analysis_type` (`TECHNICAL`, `FUNDAMENTAL`, `COMBINED`), `as_of_date`, `analysis_timestamp`, `data_cutoff_timestamp`, `source_fingerprint`, `overall_assessment`, `score`, `metrics_and_findings` (JSONB), and `data_source_references` (JSONB).
- **Zero-Redundancy Caching**: `compute_source_fingerprint` hashes `ENGINE_VERSION` alongside PostgreSQL row counts, max dates, and latest close/market_cap/peer counts `<= as_of_date`. Subsequent identical requests return `cache.hit = True` without recalculation; underlying data changes or `force_refresh = true` trigger fresh execution.
- **API Endpoints** (all accept optional `?as_of_date=YYYY-MM-DD` and `?force_refresh=bool`):
  - `GET /api/analysis/technical/{symbol}`
  - `GET /api/analysis/fundamental/{symbol}`
  - `GET /api/analysis/combined/{symbol}`
  - `GET /api/analysis/{symbol}?mode=both|technical|fundamental`

---

## 5. Verified Sample Results Across PSX Sectors

All outputs below were exported directly to [`sample_analysis_results.json`](file:///c:/Users/HP/psxpert/reports/analysis/sample_analysis_results.json):

| Symbol | As-Of Date | Sector | Tech Score / Stance | Close (PKR) | RSI (14) | Fund Score / Stance | P/E | P/B | Div Yield | ROE (%) | Sector Peers |
|---|---|---|---|---:|---:|---|---:|---:|---:|---:|---|
| **OGDC** | `2026-10-13` | Oil & Gas Exploration | `-39.4` (`BEARISH`) | `298.96` | `30.57` | `87.9` (`STRONG`) | `5.32x` | `0.85x` | `7.35%` | `15.95%` | `1` (`INSUFFICIENT_SECTOR_DATA` — `POL/PPL` FY24 stale) |
| **OGDC** | `2024-11-01` | Oil & Gas Exploration | `+38.2` (`BULLISH`) | `179.49` | `72.90` | `82.1` (`STRONG`) | `3.69x` | `0.62x` | `4.45%` | `16.71%` | `3` (`OK` — `MARI, POL, PPL`) |
| **MEBL** | `2026-10-13` | Commercial Banks | `-37.6` (`BEARISH`) | `542.81` | `41.09` | `69.9` (`CONSTRUCTIVE`) | `10.81x` | `3.43x` | `5.43%` | `31.76%` | `11` (`OK` — bank N/A rules applied) |
| **LUCK** | `2026-10-13` | Cement | `-49.1` (`STRONG_BEARISH`) | `395.95` | `30.97` | `76.8` (`STRONG`) | `6.51x` | `1.35x` | `1.26%` | `20.78%` | `6` (`OK` — post-5:1 split) |
| **LUCK** | `2024-10-15` | Cement | `-40.5` (`BEARISH`) | `844.18` | `38.57` | `75.8` (`STRONG`) | `3.77x` | `0.90x` | `2.20%` | `23.96%` | `7` (`OK` — pre-split split-invariant P/E) |
| **SYS** | `2026-10-13` | Technology & Comm. | `-52.1` (`STRONG_BEARISH`) | `113.60` | `30.89` | `72.5` (`STRONG`) | `15.13x` | `3.44x` | `1.76%` | `22.73%` | `1` (`INSUFFICIENT_SECTOR_DATA` — `AIRLINK/TRG` stale) |
| **FFC** | `2026-10-13` | Fertilizer | `-44.4` (`BEARISH`) | `532.91` | `41.17` | `73.7` (`STRONG`) | `9.22x` | `2.95x` | `7.69%` | `32.01%` | `2` (`OK` — `EFERT, FATIMA`) |
| **AICL** | `2026-10-13` | Insurance | `+26.1` (`BULLISH`) | `94.38` | `48.40` | `67.5` (`CONSTRUCTIVE`) | `5.93x` | `0.65x` | `5.30%` | `10.97%` | `0` (`INSUFFICIENT_SECTOR_DATA` — solo peer) |
| **TELE** | `2026-10-13` | Other / Unclassified | `-49.1` (`STRONG_BEARISH`) | `7.24` | `38.91` | `None` (`INSUFFICIENT`) | `—` | `—` | `—` | `—` | `—` (`NO_FINANCIAL_STATEMENTS`) |

---

## 6. Missing Data Sources & Warehouse Limitations Discovered

1. **Missing Fundamental Coverage for Non-KSE-100 Equities**: Only `140` of `811` companies in `company_financials` possess audited IFRS statements (`INCOME_STATEMENT`, `BALANCE_SHEET`, `CASH_FLOW`), predominantly KSE-100 firms (`2021-12-31` to `2026-06-30`). The remaining companies (e.g., `TELE`) explicitly return `NO_FINANCIAL_STATEMENTS` with `fundamental_score = None`.
2. **Stale & Incomplete Peer Filings**: Certain KSE-100 peers stop at `2024-06-30` (e.g., `POL`, `PPL`, `AIRLINK`, `TRG`), and specific filings are incomplete (e.g., `OGDC 2025-06-30` missing balance sheet and revenue; `OGDC 2026-06-30` missing `basic_eps` while having `net_income` and `ordinary_shares_number`).
3. **Unclassified Sector Metadata**: `711` of `811` stocks (`61` of `140` fundamental firms) carry `'OTHER / UNCLASSIFIED'` or `'OTHER / PSX HISTORICAL'` sectors, and several valid PSX sectors (`INSURANCE`, `TOBACCO`, `REFINERY`, etc.) have `< 2` comparable peers, limiting sector benchmarking on those symbols.
4. **Legacy Table Corruption (`ANNUAL` / `QUARTERLY` / `company_financials.unit`)**: Legacy `ANNUAL` and `QUARTERLY` rows contain repeated placeholder sentinels (`12121.0`, `435451.1`), future period dates (`2026-12-31`, `2027-09-30`), `publication_date < period_end_date`, and mislabeled units (`PKR_THOUSANDS` on full `1x` PKR IFRS amounts). Only audited IFRS annual tables are used by `FundamentalAnalysisEngine`.
5. **Corporate Payouts Archival & Face-Value Gaps**: `corporate_payouts` contains `1,381` junk `'type'` rows (excluded), mainly covers `FY 2025–2026` cash dividends (`289` of `334` valid dividend rows), and has `12` rows with `dividend_per_share` inconsistent with `payout_percentage * face_value / 100` (normalized by the engine).
6. **Missing Market Intraday / True OHLC Coverage on Some Sessions**: Approximately `19.4%` of raw `stock_prices` rows are flat EOD bars (`high == low`), and `13,424` weekend phantom rows exist in raw `stock_prices`. Flat bars are suppressed during candlestick pattern classification, and weekend rows are stripped via KSE-100 calendar inner joins.
7. **Absence of Quarterly IFRS Waterfall**: Reliable quarterly IFRS financial statements (clean `Q1/Q2/Q3` without `12121.0` sentinels) are unavailable in PostgreSQL, restricting Trailing-Twelve-Month (TTM) calculations to annual IFRS disclosures plus trailing announced payouts.

