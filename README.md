# PSXpert — Pakistan Stock Exchange Quantitative Intelligence & Analysis Platform

PSXpert is an end-to-end quantitative equity research, PostgreSQL ETL, NLP sentiment, technical/fundamental analysis, and machine-learning platform built for the **Pakistan Stock Exchange (PSX / KSE-100)**.

> Detailed directory map and architecture conventions: see [`docs/PROJECT_STRUCTURE.md`](./docs/PROJECT_STRUCTURE.md).

---

## Core Modules & Capabilities

- **Multi-Source PSX Data Collection (`src/data_collection/`)**: Historical daily OHLCV prices & KSE-100 index (`2002–2026`), company profiles & sectors, annual/quarterly financial statements, corporate announcements/payouts, and Pakistani business news (Dawn & Business Recorder).
- **Relational Data Engineering (`src/database/`)**: PostgreSQL 18 primary store with automatic SQLite (`data/psxpert.db`) fallback, composite unique keys (`(symbol, trading_date)`), publication-date tracking (`publication_date >= period_end_date`), and idempotent upsert pipelines.
- **Financial News Sentiment (`src/sentiment/`)**: Text deduplication, ticker/sector entity resolution, Pakistani finance lexicon baseline (`vaderSentiment`), and `ProsusAI/finbert` transformer scoring.
- **Quantitative Analysis & Regimes (`src/analysis/`)**:
  - 8 zero-lookahead technical indicators (`TechnicalIndicatorCalculator`) and 20+ candlestick patterns (`CandlestickPatternDetector`).
  - Causal Markov-switching regime estimation (`MarketRegimeHMM` / `CausalMarketRegimeHMM`), walk-forward validation, and genetic parameter optimization.
  - Explainable rule/pillar **Technical**, **Fundamental**, and **Combined** analysis engines with PostgreSQL result caching (`analysis_results`).
- **Leakage-Aware Predictive Datasets (`src/predictive_data/`)**: Daily & intraday Parquet feature/target stores with strict chronological `TRAIN` / `VAL` / `TEST` and embargoed purge splits (`build_manifest.json`, `chronological_splits.json`).
- **Machine Learning Training & Inference (`src/ml/`)**:
  - **Technical ML Model (`artifacts/technical/`)**: Chronologically validated `XGBClassifier` + `TrainOnlyPreprocessor` persisted as `.pkl` artifacts with SHA-256 verification and native TreeSHAP explanations (`POST /api/models/technical/predict`).
  - **Fundamental ML Audit (`artifacts/fundamental/`)**: Point-in-time IFRS feature builder & honest readiness gate (`BLOCKED_INSUFFICIENT_RELIABLE_LABELS` — safely blocks exporting a fabricated model and returns HTTP `503` on prediction requests until authentic ground-truth labels exist).
- **FastAPI Backend & Interactive Terminal (`app.py`, `static/`)**: Startup-preloaded ML artifacts (`lifespan`), market overview, candlestick charting, technical/fundamental analysis views, and REST APIs.

---

## Repository Layout Summary

| Directory | Purpose |
|---|---|
| [`app.py`](./app.py) | FastAPI ASGI application entrypoint & router mounting |
| [`config/`](./config/paths.py) | Centralized filesystem path constants (`PROJECT_ROOT`, `DATA_*`, `ARTIFACTS_*`, `REPORTS_*`, `STATIC_DIR`) |
| [`src/`](./src/) | Domain packages: `analysis`, `data_collection`, `database`, `ml`, `predictive_data`, `sentiment`, `visualization` |
| [`scripts/`](./scripts/) | CLI pipelines organized into `scripts/data/`, `scripts/training/`, and `scripts/maintenance/` |
| [`tests/`](./tests/) | Automated `pytest` suites under `unit/`, `integration/`, and `model/` |
| [`data/`](./data/) | `raw/` (503 immutable CSVs), `processed/` (9 ETL CSVs), `predictive/` (Parquet stores & splits), `psxpert.db` |
| [`artifacts/`](./artifacts/) | Serialized production `.pkl` models, preprocessors, feature schemas, and metadata JSONs |
| [`reports/`](./reports/) | Structured reports organized into `data_audit/`, `analysis/`, `model_evaluation/`, and `charts/` |
| [`static/`](./static/) | Dashboard frontend (`index.html`, `css/style.css`, `js/app.js`) |
| [`docs/`](./docs/PROJECT_STRUCTURE.md) | Architecture and project organization documentation |
| [`archive/`](./archive/) | Legacy Flask viewer prototype and archived `v1_models/` experiments |

---

## Setup & Installation

### 1. Environment Configuration
Copy `.env.example` to `.env` and configure your PostgreSQL credentials (or keep the embedded SQLite URL):

```powershell
Copy-Item .env.example .env
```

Optional environment variable `PSX_EXTERNAL_DATA_DIR` can be set in `.env` when running [`src/database/enrich_ohlc.py`](./src/database/enrich_ohlc.py) or [`src/database/merge_external_repo.py`](./src/database/merge_external_repo.py).

### 2. Install Dependencies

Runtime web API, scraping, DB, analytics, and deployed ML inference:
```bash
pip install -r requirements.txt
```

Full offline multi-candidate ML training (`LightGBM`, `CatBoost`) and automated test suite (`pytest`, `httpx`):
```bash
pip install -r requirements-ml-train.txt
```

---

## Pipeline Commands

Run all commands from the repository root (`psxpert/`):

### Data Scraping (`scripts/data/`)
```bash
python scripts/data/scrape_stocks.py --help
python scripts/data/scrape_news.py --help
python scripts/data/scrape_historical_news.py --help
python scripts/data/scrape_fundamentals.py --help
python scripts/data/scrape_announcements.py --help
python scripts/data/enrich_sectors.py
```

### Database Initialization, ETL & Verification (`scripts/maintenance/`, `scripts/data/`)
```bash
python scripts/maintenance/init_db.py
python scripts/data/ingest_all.py
python scripts/maintenance/verify_data.py
python scripts/maintenance/verify_db.py
python scripts/maintenance/query_db.py tables
```

### Sentiment, Technical Indicators & Charts
```bash
python scripts/maintenance/evaluate_sentiment.py
python scripts/data/run_sentiment_pipeline.py
python scripts/maintenance/verify_indicators.py
python scripts/data/generate_indicators_dataset.py
python scripts/maintenance/generate_charts.py
```

### Predictive Datasets & Machine Learning
```bash
# Build chronologically split feature/target Parquets & reports
python scripts/data/build_predictive_datasets.py

# Run 12-check zero-leakage verification suite
python scripts/maintenance/verify_predictive_datasets.py

# Train & compare Technical ML candidates (LightGBM / XGBoost / Random Forest) + Fundamental readiness audit
python scripts/training/train_ml_models.py
```

See [`reports/model_evaluation/ML_RETRAINING_AND_ARTIFACTS_GUIDE.md`](./reports/model_evaluation/ML_RETRAINING_AND_ARTIFACTS_GUIDE.md) for artifact schemas, SHA-256 checks, and standalone `.pkl` loading examples.

---

## Running the Web Server & Tests

### Launch FastAPI Dashboard
```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```
Open `http://127.0.0.1:8000/` in your browser (Swagger docs at `http://127.0.0.1:8000/docs`).

### Core API Endpoints
- `GET /` — Interactive PSXpert dashboard (`static/index.html`)
- `GET /api/market-summary` — KSE-100 index snapshot, breadth & sentiment summary
- `GET /api/stocks` | `GET /api/sectors` — Listed companies and sector breakdowns
- `GET /api/ohlcv/{symbol}` | `GET /api/indicators/{symbol}` | `GET /api/patterns/{symbol}` — Market data, indicators & candlestick patterns
- `GET /api/sentiment/latest` | `POST /api/news/refresh` — FinBERT news sentiment feed
- `GET /api/quantitative/hmm` | `GET /api/quantitative/ga/optimize` — Market regime & genetic parameter endpoints
- `GET /api/analysis/technical/{symbol}` | `GET /api/analysis/fundamental/{symbol}` | `GET /api/analysis/combined/{symbol}` | `GET /api/analysis/{symbol}` — Cached quantitative analysis engines
- `GET /api/models/status` — ML artifact readiness, SHA-256/load state & blocker diagnostics
- `POST /api/models/technical/predict` — Real-time Technical ML inference + TreeSHAP attribution
- `POST /api/models/fundamental/predict` — Returns HTTP `503` blocker while Fundamental ML labels are unverified
- `GET /api/analysis/ml/models/status` | `/technical/{symbol}` | `/fundamental/{symbol}` | `/combined/{symbol}` — Compatibility ML analysis endpoints

### Automated Test Suite
```bash
python -m pytest tests -v
```
- [`tests/unit/test_technical_indicators.py`](./tests/unit/test_technical_indicators.py) — Path configuration, first-principles indicator math, zero-lookahead invariance, candlestick detection
- [`tests/integration/test_analysis_engines.py`](./tests/integration/test_analysis_engines.py) — Rule-based Technical/Fundamental/Combined engines, PostgreSQL caching & API endpoints
- [`tests/model/test_ml_models.py`](./tests/model/test_ml_models.py) — Leakage checks, `.pkl` SHA-256 verification, chronological model selection, FastAPI startup preloading & HTTP `200`/`503` prediction endpoints

---

## Disclaimer

All quantitative indicators, pattern detections, analysis engine scores, and ML probabilities are **analytical diagnostic outputs only** and do not constitute investment or financial advice.
