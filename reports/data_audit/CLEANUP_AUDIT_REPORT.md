# PSXpert — Phase 1 Codebase Audit & Cleanup Plan

**Branch**: `cleanup/restructure-project` (branched cleanly from `main` at `f14e889`)  
**Audit Date**: `2026-11-11`  
**Constraint**: Preserve all core application behavior, API endpoints, database state, raw datasets, and trained `.pkl` artifacts without altering business logic or ML results.

---

## 1. Pre-Cleanup Findings Summary

### 1.1 Duplicate Files & Redundant Data
1. **503 Duplicated Raw CSV Files (`data/` vs `data/raw/`)**:
   - All `12` root raw CSVs and `491` per-ticker CSVs (`stocks_historical/`, `announcements_company/`, `fundamentals_company/`) were tracked at `data/` top level while `.gitignore`'d `data/raw/` stored an exact duplicate copy of `502` files (`~65 MB`) plus `1` stale un-enriched copy of `data/raw/kse100_stocks_historical_2002_2026.csv` (`27.76 MB`, old `9/9/2026` dates vs. tracked `29.96 MB` `2026-10-13` ISO version).
   - **Action**: Consolidate all canonical raw files cleanly inside `data/raw/`, keeping the newer `2026-10-13` copy of `kse100_stocks_historical_2002_2026.csv`, unignoring `data/raw/`, and eliminating the duplicate copies.
2. **Duplicate Parquet Dataset (`models/fundamental/` vs `reports/ml/`)**:
   - `models/fundamental/fundamental_disclosures_features.parquet` (`186.9 KB`) has an identical SHA-256 hash to `reports/ml/fundamental_disclosures_features.parquet`.
   - **Action**: Delete the duplicate `.parquet` inside `models/fundamental/` and archive superseded `v1.0` `models/` files cleanly under `archive/v1_models/`.

### 1.2 Hardcoded Developer Paths & Credential Hygiene
1. [`src/database/enrich_ohlc.py`](file:///c:/Users/HP/psxpert/src/database/enrich_ohlc.py): hardcoded `C:/Users/HP/.gemini/.../scratch/PSX-Data` (L26) and fallback DB password literal (L37). **Action**: Parameterize via CLI/env var (`PSX_EXTERNAL_DATA_DIR`) and read DB connection exclusively via centralized `connection.py` / env vars without hardcoded password strings.
2. [`src/database/merge_external_repo.py`](file:///c:/Users/HP/psxpert/src/database/merge_external_repo.py): hardcoded `C:\Users\HP\.gemini\...\scratch\PSX-Data` (L355). **Action**: Parameterize via env/CLI argument cleanly.
3. [`verify_predictive_datasets.py`](file:///c:/Users/HP/psxpert/verify_predictive_datasets.py): hardcoded `C:\Users\HP\.gemini\...\scratch\prep_check` (L203). **Action**: Replace with `tempfile.TemporaryDirectory()`.
4. [`README.md`](file:///c:/Users/HP/psxpert/README.md): contains `file:///c:/Users/HP/psxpert/...` local absolute links. **Action**: Rewrite using relative repository paths.

### 1.3 Loose Root Scripts, Loose Source Scrapers, Temporary & Legacy Files
- **18 operational `.py` scripts** scattered at project root (`main.py`, `scrape_*.py`, `init_db.py`, `ingest_all.py`, `enrich_sectors.py`, `query_db.py`, `verify_*.py`, `generate_*.py`, `run_sentiment_pipeline.py`, `evaluate_sentiment.py`, `build_predictive_datasets.py`, `train_ml_models.py`, `web_viewer.py`). **Action**: Organize into `scripts/{data,training,maintenance}/` and archive `web_viewer.py` -> `archive/legacy_web_viewer.py`.
- **5 loose scraper modules** in `src/` (`scraper.py`, `news_scraper.py`, `historical_news_scraper.py`, `fundamentals_scraper.py`, `announcements_scraper.py`). **Action**: Move into `src/data_collection/`.
- **Temporary scratch artifacts**: `catboost_info/` (`4` CatBoost telemetry files, `45.8 KB`) and `scratch/compare_data.py` (`1.9 KB` one-off dev script referencing personal `.gemini` directory). **Action**: Delete `catboost_info/` and `scratch/`.
- **Local Windows PostgreSQL installers (`.exe`) & reset scripts (`reset_password.ps1`, `reset_postgres.bat`, `.env`)**: Untracked, `.gitignore`'d local machine files (`~483 MB` installers + DB password script). **Action**: Leave user's `.env`, `.exe`, and local reset utilities untouched on disk (never commit or delete user environment files).

### 1.4 Dependency Audit ([`requirements.txt`](file:///c:/Users/HP/psxpert/requirements.txt))
- **Unused runtime package**: `tqdm>=4.65.0` (`0` imports anywhere in codebase) -> remove.
- **`flask`**: used only by legacy `web_viewer.py` (`ARCHIVE`) -> do not include in active requirements.
- **Missing active app/pipeline packages**: `fastapi`, `uvicorn`, `pydantic`, `numpy`, `scipy`, `hmmlearn`, `transformers`, `torch`, `curl_cffi`, `plotly`, `matplotlib`, `mplfinance` are imported by `app.py`, sentiment, analysis, visualization, and scrapers -> ensure active dependencies are cleanly documented without altering pinned `.pkl`-compatible ML runtime versions (`joblib>=1.5.2,<2.0.0`, `scikit-learn>=1.7.2,<2.0.0`, `xgboost>=3.4.1,<4.0.0`).

### 1.5 `.pkl` Pickle Compatibility Critical Finding
- [`artifacts/technical/technical_preprocessor.pkl`](file:///c:/Users/HP/psxpert/artifacts/technical/technical_preprocessor.pkl) serializes `src.ml.technical_ml.TrainOnlyPreprocessor`. Moving `src/ml/` away from `src.ml.technical_ml` without re-export shims would break artifact loading without retraining.
- **Adaptation**: Keep [`app.py`](file:///c:/Users/HP/psxpert/app.py) at root (preventing `app/` package shadowing of `app.py`), retain [`src/ml/`](file:///c:/Users/HP/psxpert/src/ml/technical_ml.py) cleanly as the ML module path for binary `.pkl` compatibility, add [`config/paths.py`](file:///c:/Users/HP/psxpert/config/paths.py), and group all scripts, data, reports, docs, and tests cleanly around domain responsibilities.

---

## 2. Classification Matrix (A: Keep | B: Organize | C: Archive | D: Delete)

| Category | Items | Destination / Action |
|---|---|---|
| **A. KEEP** | `app.py`, `static/*`, `artifacts/{technical,fundamental}/*`, `src/{analysis,database,ml,predictive_data,sentiment,visualization}/*`, `data/{processed,predictive}/*`, `.env`, `.env.example`, `.gitignore` | Keep functional modules & binaries intact; update paths via `config/paths.py` |
| **B. ORGANIZE** | `src/*.py` scrapers -> `src/data_collection/`; root scripts -> `scripts/{data,training,maintenance}/`; raw CSVs `data/*` -> `data/raw/`; `reports/` -> `reports/{data_audit,analysis,model_evaluation,charts}/`; `tests/` -> `tests/{unit,integration,model}/` + `conftest.py`; new `config/` & `docs/` | Structured modular layout with updated imports & paths |
| **C. ARCHIVE** | `web_viewer.py` -> `archive/legacy_web_viewer.py`; `models/` (`v1.0` `.joblib` & reports) -> `archive/v1_models/`; `reports/model_verification_report.md` -> `reports/model_evaluation/v1_model_verification_report.md` | Preserved for historical traceability, cleanly separated from production |
| **D. DELETE** | `catboost_info/`, `scratch/compare_data.py` & `scratch/`, duplicate `502+1` CSV mirror copies inside `data/raw/` (replacing with canonical copies), duplicate `models/fundamental/fundamental_disclosures_features.parquet`, compiled `__pycache__/` / `*.pyc` | Verified temporary caches, one-off scratch debug scripts, and redundant exact duplicates |

