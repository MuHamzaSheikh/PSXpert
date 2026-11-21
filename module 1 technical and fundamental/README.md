# PSXpert Module 1

Standalone research and inference for a pooled, two-estimator XGBoost forecast of PSX equity direction and percentage price return over 20 trading sessions. The module reads the existing project database and imports the existing analysis engines. Run commands from this folder.

## Install and run

```powershell
Set-Location -LiteralPath 'C:\Users\HP\psxpert\module 1 technical and fundamental'
python -B -m venv .venv
$env:PYTHONDONTWRITEBYTECODE = '1'
.\.venv\Scripts\python.exe -B -m pip install --no-cache-dir -r requirements.txt
$modulePython = '.\.venv\Scripts\python.exe'

& $modulePython -B -m m1 inspect
& $modulePython -B -m m1 build --version research_v1 --as-of '2026-11-16T14:00:00+05:00'
& $modulePython -B -m m1 train --version combined_v2 --as-of '2026-11-16T14:00:00+05:00'
& $modulePython -B -m pytest -q -p no:cacheprovider --basetemp .qa
```

`build` writes `data/processed/<version>/combined.csv.gz` and `coverage.json` from the common experimental cohort. With zero eligible rows it records the coverage, writes a header-only dataset, and exits with status 1. `train` rebuilds from the database with the supplied cutoff and runs all three experiments. Pass `--bearish` and `--bullish` to set the boundaries. Use a fresh version such as `combined_v2` to reproduce the included `combined_v1` run without replacing it. Use matching cutoffs and thresholds when building and training. Use a new version for each build or model export.

```powershell
Get-Content -LiteralPath 'artifacts/combined_v1/comparison.json'
Get-Content -LiteralPath 'artifacts/combined_v1/combined/evaluation.json'
Get-ChildItem -LiteralPath 'artifacts/plots/combined_v1/combined'
& $modulePython -B -m m1 scores OGDC --as-of '2026-11-16T14:00:00+05:00'
& $modulePython -B -m m1 predict OGDC --version combined_v1 --as-of '2026-11-16T14:00:00+05:00'
& $modulePython -B -m m1 explain OGDC --version combined_v1 --as-of '2026-11-16T14:00:00+05:00'
$env:MODULE1_MODEL_VERSION = 'combined_v1'
& $modulePython -B -m uvicorn api.app:app --host 127.0.0.1 --port 8001
```

`train` generates the versioned model pair, training metadata, evaluation JSON, held-out prediction CSV, predicted-versus-actual plot and global TreeSHAP plots for each feature group. `predict` returns per-class and expected-return TreeSHAP contributions for a single ticker. `explain` archives the same result under `artifacts/plots/<version>/local/`. `scores` prepares the existing independent scores offline for the latest completed ticker snapshot or a supplied `--as-of` cutoff. This keeps the legacy analytical HMM fit outside API requests. A missing or inapplicable score is returned as null. Score files are keyed by ticker and trading date. A forecast requires a successfully trained artifact and a signal date after its last training or calibration label. The included OGDC score and explanation files already cover the documented cutoff. Use a different eligible ticker or date to create additional score and explanation files.

The [real-data audit and held-out results](reports/real_data_20261116.md) describe the included run.

## Data access and pyPSX

The connector reads the existing environment and project `.env`. It opens PostgreSQL with a read-only, repeatable-read transaction. A refused connection falls back to an existing SQLite snapshot with `mode=ro`, `immutable=1` and `query_only=ON`. The snapshot must have no pending WAL or rollback journal and should be kept stable while reading. The optional `MODULE1_DATABASE_URL` can pin a specific read-only deployment or SQLite snapshot. An explicit PostgreSQL override reports connection failures directly. The pipeline does not run ingestion or migrations.

The module reads `stock_prices`, `market_indices` (KSE-100 session dates), `companies`, `company_financials`, `corporate_announcements`, `corporate_payouts` and `data_sources`. It computes technical features through the existing mathematical calculator from cutoff-eligible daily candles. The existing profitability, financial-health, growth and cash-flow methods supply the corresponding fundamental ratios. Sector membership controls applicable ratios. Ticker and sector are retained as metadata; the model inputs are numeric ratios and indicators.

The official SDK distribution and import are both named `pypsx`. Install the credentials-enabled SDK when running the optional OHLCV gap and overlap audit. It uses `get_ohlcv` for raw daily bars with split adjustment explicitly disabled. [PyPI package](https://pypi.org/project/pypsx/) · [SDK history documentation](https://docs.pypsx.com/pypsx-history-archive/)

```powershell
& $modulePython -B -m pip install --no-cache-dir pypsx==2.8.3
# Supply PYPSX_API_KEY_ID and PYPSX_API_SECRET_KEY through the environment.
& $modulePython -B -m m1 check-pypsx OGDC --start 2026-09-01 --end 2026-10-13 --version ogdc_check_v1
```

The audit records normalized keys, duplicates, field-level conflicts and pyPSX-only keys. It compares price fields within PKR 0.005 and volume exactly. Database bars have absolute priority, with raw SDK responses and conflicts saved under `data/pypsx/<version>/`. The pipeline uses a single price basis and leaves unmatched gaps empty. An optional `MODULE1_CHECK_PYPSX=1` in the API or `--check-pypsx` on the prediction command checks overlaps and reports coverage. Forecasts retain provenance for the price and financial records they used.

## Signal time and financial eligibility

- The conservative end-of-day signal is at 23:59:59 in Asia/Karachi. Historical requests before that time use earlier completed snapshots. A signal uses the price and filing information eligible on that daily snapshot. The requested timestamp and actual signal timestamp are both returned.
- Eligible periods use the repository's IFRS income, balance sheet and cash-flow inputs and an exact fiscal period match to a PSX annual-report transmission. For date-only releases, features are eligible from the start of the following Pakistan calendar day. The exact timestamp is recorded as null in this case. If the financial table supplies a consistent timezone-aware release for all the selected metrics, it may be used as the availability timestamp.
- Unmatched reports, ambiguous dates, conflicting metric versions, incomplete core statements and known placeholder values are excluded. Period-end dates and assumed reporting lags cannot supply availability. Growth compares previously disclosed annual periods only. Filings expire 550 calendar days after period end. The snapshot lacks an original-vintage/restatement archive, so report availability can be checked more precisely than the vintage of each accounting value.
- The database roster is the stored KSE-100 universe. A historical membership history is unavailable, so selection and survivorship bias remain possible.
- A label uses the observed positive closing price exactly 20 subsequent KSE-100 sessions later. A missing ticker close on the target date leaves the label empty. Returns are price returns in percentages. Values greater than +3 are bullish and values less than −3 are bearish, with both boundary values sideways by default.
- Prices use the database's unadjusted close. Corporate payout records provide announcement dates, with incomplete effective-date and adjustment coverage. Labels intersecting a known split or bonus announcement buffer of five calendar days on either side are excluded, as are windows crossing observed absolute one-bar moves of at least 35%. These filters are imperfect. The independent analytical scores can apply their own legacy price-cleaning rules and are excluded from the feature schema.

## Walk-forward evaluation and portfolio simulation

Three expanding chronological folds share the same common cohort, market-session boundaries and labels across experiments. The last 20% of eligible session dates form the final test. The cutoff for each earlier partition's labels leaves a five-session embargo before the following period. Models use fixed seeded XGBoost parameters with native missing values. The terminal validation window can supply a multinomial probability calibrator when it has at least 20 observations per class. The classification report shows raw and calibrated log loss and classwise calibration. Alternative symmetric 2% and 5% thresholds are measured on terminal validation only. Validation macro F1 and RMSE rank the comparisons independently. The final test is scored after all settings are fixed.

TreeSHAP explains raw multiclass margins and the regression prediction in percentage points. The global plots show mean absolute contributions by feature. Per-prediction output includes technical and fundamental group sums, class-specific contributions, and the return decomposition. Contributions describe the fitted model.

The separate portfolio simulator ranks up to five bullish positive-return forecasts every 20 sessions, buys equal cash weights at the next close, and exits at the close 20 sessions after entry. It marks positions daily and assumes 15 bps commission plus 10 bps slippage per side. Returns, Sharpe, drawdown and turnover require a verified corporate-action-adjusted execution series. The current database path reports the financial backtest as unavailable.

## API integration

The standalone endpoint is `GET /api/module1/predict/{ticker}`. Pass an ISO 8601 `as_of_timestamp` with an explicit offset. Input validation returns 422, unknown tickers return 404, and unavailable source data or artifacts return 503. URL-encode a positive offset when sending a query string. For example:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8001/api/module1/predict/OGDC?as_of_timestamp=2026-11-16T14%3A00%3A00%2B05%3A00'
```

For later integration, the main backend can keep the service separate and proxy the prefix. To mount the router in-process, add this directory to the backend's Python import path and import `router` from `api.app`, then call the backend's `app.include_router(router)`. Set `MODULE1_MODEL_VERSION` to the published artifact and configure the same read-only source. If the backend already has a top-level `api` package, use the standalone service path to avoid import conflicts.
