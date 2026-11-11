# Unresolved ML & Data Infrastructure Problems

This document catalogs verified structural data gaps and modeling constraints observed across `psxpert` that limit further supervised ML development — particularly for the blocked Fundamental ML model and future intraday / sentiment-driven forecasting phases.

---

## 1. Fundamental ML Blocking Limitations (Critical)

1. **Zero Independent Ground-Truth Credit / Distress Labels (`external_credit_rating_labels = 0`)**:
   - No historical `PACRA` or `VIS` entity credit ratings, loan default filings, or PSX Defaulter Segment historical placement logs exist in the database.
   - Without exogenous external credit/distress targets, supervised training must either clone existing accounting rules (circular tautology) or predict next-year accounting transitions (`t -> t+1`).

2. **Shallow IFRS Historical Depth (`573` Disclosures Across `140` Companies)**:
   - Valid `INCOME_STATEMENT`, `BALANCE_SHEET`, and `CASH_FLOW` tables span only `2021-12-31` to `2026-06-30`.
   - Enforcing strict point-in-time (`<= 2024-05-20`) separation yields only **`142` non-overlapping in-train `(t -> t+1)` transitions** (effectively one fiscal cycle) and only **`24` strict `FUND_TEST` transitions** (with minimum class count **`5`**).
   - Empirical stress testing proved `CatBoost` (`0.4442`), `LightGBM` (`0.4408`), and `XGBoost` (`0.4185`) all fall below a 3-metric heuristic rule baseline (`0.4778` Macro-F1) and collapse on the `Moderate` class.

3. **100% Survivorship Bias in Company Financials (`inactive_delisted_firms = 0`)**:
   - Every one of the `140` companies present in audited IFRS tables remains currently active; bankrupt, suspended, or delisted PSX companies have zero historical IFRS disclosures in `company_financials`.

4. **Contaminated Legacy `ANNUAL` & `QUARTERLY` Financial Tables**:
   - All `INCOME_STATEMENT` (`25,114`), `BALANCE_SHEET` (`32,202`), and `CASH_FLOW` (`20,091`) rows store `100%` `publication_date == period_end_date` in raw DB (requiring PIT lag reconstruction from `corporate_announcements` + `+100d` fallback).
   - `QUARTERLY` (`3,731` rows) contains **`2,262` sentinel `12121.0` rows** and **`24` future `period_end_date` entries up to `2027-09-30`**; `ANNUAL` (`10,758` rows) contains repeated dummy scrape placeholders (`435451.1` / `168643.2`).

5. **Banking & Sector Sparsity**:
   - `12 / 140` audited companies are commercial banks (`gross_profit`, `current_ratio`, `interest_coverage` are structurally N/A under bank IFRS formats), driving `27.9%` missing `current_ratio` and `27.1%` missing `interest_coverage` across the `573` disclosures.
   - `61 / 140` (`43.6%`) IFRS issuers (and `711 / 811` total `companies`) lack PSX sector classification tags, causing **`66.5%` missingness in `sector_roe_diff`** and other sector-relative features.
   - Raw `corporate_payouts` retains `1,381` upstream `'type'` placeholder rows (filtered out in pipelines).

---

## 2. Market Microstructure & Technical ML Data Limitations

1. **Zero Historical Intraday Bars (`0` Sub-Daily Observations)**:
   - PostgreSQL, SQLite, CSV archives, and inspected endpoints hold `0` historical intraday bars (`/timeseries/int/*` returned HTTP 404). No historical sub-daily technical ML or `30m`/`60m` ML models can be trained until an intraday ingestion collector runs across several months.

2. **Flat EOD Bars & Illiquidity in `stock_prices`**:
   - Raw `stock_prices` (`2,096,135` rows) contains **`407,412` flat `high == low` bars**, **`264,587` OHLC envelope violations**, **`65,977` zero-volume rows**, **`149` inverted `high < low` rows**, **`1,330` `close <= 0` rows**, and **`30,784` non-exchange weekend/holiday forward-fills** (`13,424` Sat/Sun + `17,360` non-exchange days).
   - Downstream candlestick and Parkinson features must remain strictly gated by `is_true_ohlc`, and active session gates (`is_zero_volume == 0`) remain mandatory for valid predictions/evaluation.

3. **Synthetic OHLC & Missing Volume in `KSE100` (`market_indices`)**:
   - `KSE100` has `volume == 0` for all `6,127` sessions and synthetically enriched `open`/`high`/`low` from `close` and `point_change`. Index features in `TechnicalMLPredictor` and `CausalMarketRegimeHMM` are therefore restricted to close-derived returns, volatility, moving averages, and Wilder RSI.

4. **Thin Historical FinBERT News Archive (`249` Articles)**:
   - Only `249` rows exist in `news_articles` (`185` in 2026; `64` in 2002–2024 all stamped with synthetic `YYYY-06-15 00:00` dates; `131` dated after `2026-10-13`). Sentiment features are therefore omitted from Technical ML until a genuine archival news ingestion pipeline is populated.

5. **Minor Class-Balance Sensitivity Across Macro Cycles**:
   - In `psxpert_tech_ml_v1.0`, the untouched `TEST` bull-market regime (`2024-07-01` – `2026-10-13`) shifted `Bearish` share down from `29.55%` (`VAL`) to `11.90%` (`TEST`), yielding lower `Bearish` F1 (`0.7130` TEST vs `0.8352` VAL) relative to `Bullish` (`0.8542`) and `Neutral` (`0.8689`), though zero `Bearish <-> Bullish` cross-errors occurred.

---

## 3. Recommended Remediation Order Before Next Modeling Phases
1. Ingest multi-year `PACRA`/`VIS` credit ratings + PSX Defaulter Segment & delisting histories.
2. Backfill clean `2015–2021` audited annual/quarterly IFRS filings (replacing sentinel/dummy scrapes) and map true PSX sectors for the `711` unclassified tickers.
3. Deploy scheduled intraday bar collection and genuine timestamped corporate/market news ingestion before attempting intraday or multimodal ML forecasting.

