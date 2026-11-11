# PSXpert Project Structure

PSXpert is organized around clear domain boundaries separating the web application entrypoint, shared path configuration, modular Python source packages, CLI scripts, automated tests, datasets, serialized ML artifacts, and evaluation reports.

---

## Directory Overview

```text
psxpert/
├── app.py                        # FastAPI ASGI entrypoint (lifespan ML preload + REST + static SPA)
├── .env.example                  # Sample PostgreSQL / SQLite & optional external data env variables
├── .gitignore
├── README.md                     # Project overview, setup, pipelines, API reference & quickstart
├── requirements.txt              # Core web, database, scraping, NLP, analytics & ML runtime deps
├── requirements-ml-train.txt     # Offline multi-candidate ML training & pytest dependencies
│
├── config/
│   ├── __init__.py
│   └── paths.py                  # Centralized PROJECT_ROOT, DATA_*, ARTIFACTS_*, REPORTS_*, STATIC_DIR
│
├── src/
│   ├── __init__.py
│   ├── analysis/                 # Quantitative indicators, candlestick patterns, HMM, GA, engines & cache
│   │   ├── candlestick_patterns.py
│   │   ├── common.py
│   │   ├── fundamental_engine.py
│   │   ├── genetic_algorithm.py
│   │   ├── persistence.py
│   │   ├── regime_hmm.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── technical_engine.py
│   │   ├── technical_indicators.py
│   │   └── walk_forward.py
│   │
│   ├── data_collection/          # Live & historical scrapers (Sarmaaya, PSX DPS, Dawn, Business Recorder)
│   │   ├── announcements_scraper.py
│   │   ├── fundamentals_scraper.py
│   │   ├── historical_news_scraper.py
│   │   ├── news_scraper.py
│   │   └── stock_scraper.py
│   │
│   ├── database/                 # SQLAlchemy models, PostgreSQL/SQLite connector, ETL cleaner & ingestor
│   │   ├── cleaner.py
│   │   ├── connection.py
│   │   ├── enrich_ohlc.py
│   │   ├── ingest.py
│   │   ├── merge_external_repo.py
│   │   ├── models.py
│   │   └── schema.sql
│   │
│   ├── ml/                       # Leakage-aware Technical & Fundamental ML training, SHA-256 serving & API
│   │   ├── fundamental_ml.py
│   │   ├── metrics.py
│   │   ├── models_router.py
│   │   ├── router.py
│   │   ├── service.py
│   │   └── technical_ml.py
│   │
│   ├── predictive_data/          # Chronological leakage-free daily/intraday parquet dataset builders
│   │   ├── audit.py
│   │   ├── daily_builder.py
│   │   ├── intraday_builder.py
│   │   ├── point_in_time.py
│   │   ├── preprocessing.py
│   │   ├── regime_causal.py
│   │   ├── reports.py
│   │   └── splits.py
│   │
│   ├── sentiment/                # Text cleaning, entity resolution, VADER/LM baseline & ProsusAI/finbert
│   │   ├── benchmark_evaluator.py
│   │   ├── cleaner.py
│   │   ├── entity_matcher.py
│   │   ├── finbert_analyzer.py
│   │   ├── impact_analyzer.py
│   │   ├── lexicon_baseline.py
│   │   ├── live_feed_ingest.py
│   │   └── pipeline.py
│   │
│   └── visualization/            # Static & interactive Plotly candlestick chart generators
│       └── chart_generator.py
│
├── scripts/
│   ├── data/                     # Scraping, ETL ingestion, sentiment, indicator & predictive builders
│   │   ├── build_predictive_datasets.py
│   │   ├── enrich_sectors.py
│   │   ├── generate_indicators_dataset.py
│   │   ├── ingest_all.py
│   │   ├── run_sentiment_pipeline.py
│   │   ├── scrape_announcements.py
│   │   ├── scrape_fundamentals.py
│   │   ├── scrape_historical_news.py
│   │   ├── scrape_news.py
│   │   └── scrape_stocks.py
│   │
│   ├── training/                 # Model training & readiness evaluation runner
│   │   └── train_ml_models.py
│   │
│   └── maintenance/              # DB setup, verification suites, CLI query & chart export helpers
│       ├── evaluate_sentiment.py
│       ├── generate_charts.py
│       ├── init_db.py
│       ├── query_db.py
│       ├── verify_data.py
│       ├── verify_db.py
│       ├── verify_indicators.py
│       └── verify_predictive_datasets.py
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   └── test_technical_indicators.py
│   ├── integration/
│   │   └── test_analysis_engines.py
│   └── model/
│       └── test_ml_models.py
│
├── data/
│   ├── raw/                      # 503 immutable scraped CSVs + per-company folders
│   ├── processed/                # Cleaned/typed CSVs ready for PostgreSQL bulk ingestion
│   ├── predictive/               # Chronologically split parquet datasets & manifests
│   └── psxpert.db                # Local SQLite fallback database
│
├── artifacts/
│   ├── technical/                # Production XGBClassifier & TrainOnlyPreprocessor .pkl + schema/metadata
│   └── fundamental/              # Blocker status metadata & 29-feature schema (no .pkl exported)
│
├── reports/
│   ├── analysis/                 # Analysis engine methodology & sample JSON outputs
│   ├── charts/                   # Generated candlestick HTML/PNG charts & gallery index
│   ├── data_audit/               # Dataset audit, cleanup audit, feature dictionary & split policy
│   └── model_evaluation/         # ML evaluation reports, retraining guide & feature importance outputs
│
├── static/                       # Institutional dashboard frontend (HTML / CSS / JS)
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
│
├── docs/
│   └── PROJECT_STRUCTURE.md
│
└── archive/                      # Superseded prototypes & v1 model bundle preserved outside active code
    ├── legacy_web_viewer.py
    └── v1_models/                # gitignored legacy v1.0 .joblib / evaluation outputs
```

---

## Key Architectural Design Decisions

1. **Root `app.py` without an `app/` Package Directory**: Keeping [`app.py`](../app.py) at the repository root avoids Python import shadowing that occurs if a folder named `app/` exists beside it (`uvicorn app:app` stays unambiguous). Shared filesystem constants reside in [`config/paths.py`](../config/paths.py).
2. **`src/ml/` Import Path Stability**: [`artifacts/technical/technical_preprocessor.pkl`](../artifacts/technical/technical_preprocessor.pkl) serializes `src.ml.technical_ml.TrainOnlyPreprocessor`. Preserving `src/ml/` keeps existing `.pkl` binaries 100% compatible without retraining.
3. **Strict Raw vs. Processed vs. Predictive Separation**: Immutable source CSVs live exclusively under `data/raw/`, normalized ETL outputs under `data/processed/`, and chronological feature/target Parquets under `data/predictive/`.
4. **Separated Active Artifacts vs. Legacy Archive**: Active deployed `.pkl` binaries and schemas live in `artifacts/`, while older v1.0 `.joblib` experiments and the prototype Flask script (`web_viewer.py`) are isolated under `archive/`.

