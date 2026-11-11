# PSXpert Predictive Data Audit Report (Step 1)

## 1. Executive Audit Summary
- **Active Database**: `POSTGRESQL` (`localhost:5432/psxpert`)
- **Daily Universe & Range**: 811 companies in directory (100 flagged `is_kse100` snapshot); `2000-08-15` to `2026-10-13` (`2,096,135` raw `stock_prices` rows).
- **Cleaned Equity Panel Built**: **`2,024,340` rows** across **`726` equities** (`2002-01-01` to `2026-10-13`).
- **Intraday Availability**: **`0` historical sub-daily bars** exist in PostgreSQL, SQLite (`data/psxpert.db`), CSV archives, or tested API endpoints (`/timeseries/int/*` returned HTTP 404). Intraday forecasting horizons (`30m` / `60m`) cannot be populated with historical data until a live sub-daily bar collector runs over multiple months.

## 2. Database Table Inventory
| Table | Raw Row Count |
| :--- | ---: |
| `companies` | 811 |
| `company_financials` | 91,896 |
| `corporate_announcements` | 20,884 |
| `corporate_payouts` | 1,727 |
| `data_sources` | 5 |
| `market_indices` | 6,127 |
| `news_articles` | 249 |
| `news_entities` | 999 |
| `news_sentiment` | 617 |
| `stock_prices` | 2,096,135 |
| `technical_indicators` | 110,816 |

## 3. Critical Raw Data & Codebase Defects Found
1. **Forward-Filled Non-Trading Weekend/Holiday Rows in `stock_prices`**:
   - While `market_indices` (`KSE100`) contains `6,127` genuine Monday–Friday trading sessions (`weekend_rows = 0`), raw `stock_prices` contains **`13,424` Saturday/Sunday rows** and **`17,360` extra non-exchange-day rows** where Sarmaaya API (`source_id=2`) duplicated Friday's close and volume onto weekends/holidays (inflating 2024 KSE-100 dates from 246 to 347!).
   - *Fix applied*: Daily predictive panel inner-joins onto genuine `KSE100` trading sessions (`market_indices`).
2. **OHLC & Debt-Ticker Pollution in `stock_prices` / `companies`**:
   - Raw `stock_prices`: `1,330` non-positive `close <= 0`, `149` inverted `high < low`, `407,412` flat `high == low` bars, `264,587` envelope violations, `65,977` zero-volume rows.
   - `companies`: `63` fixed-income/PIB/Sukuk tickers (`^P[0-9]{2}`), `16` ETF/pref symbols, `711/811` lacking true sector metadata.
   - *Fix applied*: Excluded debt/ETF/pref tickers and `close <= 0`; clamped single-bar OHLC envelopes causally; gated candlestick & Parkinson volatility features strictly on `is_true_ohlc`.
3. **Unadjusted Corporate Splits & Source Glitches**:
   - Raw `stock_prices` lacks split adjustments across major sub-divisions/reverse-splits (`BML +1626.5%`, `SRVI -90.4%`, `MARI -88.2%`, `SYS -81.0%`, `LUCK -79.5%`, `UBL -50.1%`, `MTL -48.6%`, `BAFL -48.4%`). Early data also has source glitches (`UPFL` `1.00 <-> 1350`, `ATLH` `295 <-> 58.35`).
   - *Fix applied*: `point_in_time.adjust_splits_and_flag_glitches` separates persistent corporate-action steps from oscillating 1-bar glitches, produces split-continuous `adj_*` series, and masks glitch horizons (`target_valid_* = 0`).
4. **Synthetic OHLC & Zero Volume in `market_indices` (`KSE100`)**:
   - `enrich_ohlc.py` generated `KSE100` Open/High/Low synthetically from `close` and `point_change`, and `volume == 0` for `6,127/6,127` rows.
   - *Fix applied*: `daily_builder.py` and `CausalMarketRegimeHMM` use ONLY authentic `KSE100` `close` returns and volatility.
5. **Financial Statement Unit Mismatches, Sentinel `12121`, and Publication-Date Leakage**:

| Statement Type | Rows | Syms | Period Range | `pub == end` | `pub < end` | Future End (`>2026-10-13`) | `12121` Sentinel |
| :--- | ---: | ---: | :--- | ---: | ---: | ---: | ---: |
| `ANNUAL` | 10,758 | 96 | 2021-06-30 -> 2026-06-30 | 366 | 1,106 | 0 | 0 |
| `BALANCE_SHEET` | 32,202 | 140 | 2021-12-31 -> 2026-06-30 | 32,202 | 0 | 0 | 0 |
| `CASH_FLOW` | 20,091 | 140 | 2021-12-31 -> 2026-06-30 | 20,091 | 0 | 0 | 0 |
| `INCOME_STATEMENT` | 25,114 | 140 | 2021-12-31 -> 2026-06-30 | 25,114 | 0 | 0 | 0 |
| `QUARTERLY` | 3,731 | 100 | 2015-03-31 -> 2027-09-30 | 2,315 | 12 | 24 | 2,262 |

   - Audited IFRS tables (`INCOME_STATEMENT`, `BALANCE_SHEET`, `CASH_FLOW`) store full PKR (`1x`) but set **`100%` of `publication_date == period_end_date`**. Meanwhile `ANNUAL` suffered repeated dummy scrape values (`435451.1` / `168643.2`) and `QUARTERLY` suffered `2,262` sentinel `12121.0` rows plus future fiscal year bugs (`2027-09-30`). `kse100_financial_ratios.csv` lacks any date column (`fiscal_year` only) and embeds snapshot market prices.
   - *Fix applied*: Built point-in-time IFRS fundamental ratios exclusively from `INCOME_STATEMENT`, `BALANCE_SHEET`, and `CASH_FLOW`, recovering genuine filing dates from `corporate_announcements` (`Earnings Announcements`, empirical lag `p50=53d, p95=96d`) and applying a conservative **`+100 day` lag fallback** when unmatched. Valuation yields use split-invariant aggregate PKR items over daily `market_cap`.
6. **News Archive & Timestamp Limitations**:
   - Only `249` articles exist (`185` in 2026, `64` in 2002–2024). All `64` archive rows carry synthetic `YYYY-06-15 00:00` sampling dates, and `131` Oct 14–20 articles fall *after* the latest price session (`2026-10-13`).
   - *Fix applied*: Enforced `published_at <= 15:30 PKT` cutoff (post-close articles roll forward to next session; post-Oct-13 excluded) with explicit `has_*_news_7d` coverage masks.
7. **Existing Quantitative Modules Audit (`regime_hmm.py`, `walk_forward.py`, `candlestick_patterns.py`, `technical_indicators.py`)**:
   - `MarketRegimeHMM.predict_regimes()` uses `hmmlearn.predict_proba()` (**smoothed** posteriors over $X_{1:T}$) and `predict()` (Viterbi path) and truncates `history_sample` to `[-180:]`.
   - `WalkForwardEngine` indexes `history_sample[-180:]` (dropping >60% of 450+ train bars and shifting indices by 10 warmup NaNs).
   - `TechnicalIndicatorCalculator` calls `.bfill()` on line 63 and uses `min_periods=1`.
   - `CandlestickPatternDetector` marks `high == low` bars as `Doji`.
   - *Fix applied*: Existing backend/dashboard left intact; dedicated leak-free modules created in `src/predictive_data/` using causal log-space HMM forward filtering, strict `min_periods`, zero `.bfill()`, and true-OHLC pattern guards.
