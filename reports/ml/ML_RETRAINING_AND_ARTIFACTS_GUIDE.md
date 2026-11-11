# PSXpert — ML Retraining, Artifact Export & Verification Guide

## 1. Directory & Artifact Layout

```text
artifacts/
    technical/
        technical_model.pkl         # Fitted winning classifier (XGBClassifier, psxpert_tech_ml_v2.0)
        technical_preprocessor.pkl  # Fitted TrainOnlyPreprocessor (quantile winsorizer, impute_missing=False)
        technical_features.json     # Ordered 74-feature schema, class IDs, missingness policy
        technical_metadata.json     # Metrics, hyperparams, SHA-256 checksums, versions, splits
    fundamental/
        fundamental_metadata.json   # Honest blocker status (BLOCKED_INSUFFICIENT_RELIABLE_LABELS), audit counts, proposed target
        fundamental_features.json   # Ordered 29-feature schema & observed missingness percentages
        # NOTE: No fundamental_model.pkl is exported until independent ground-truth labels are approved & ingested.
```

Full diagnostic JSON and feature importances are written to:
- [`reports/ml/technical_evaluation_report.json`](file:///c:/Users/HP/psxpert/reports/ml/technical_evaluation_report.json)
- [`reports/ml/technical_feature_importance.csv`](file:///c:/Users/HP/psxpert/reports/ml/technical_feature_importance.csv)
- [`reports/ml/fundamental_ml_readiness_report.json`](file:///c:/Users/HP/psxpert/reports/ml/fundamental_ml_readiness_report.json)
- [`reports/ml/fundamental_disclosures_features.parquet`](file:///c:/Users/HP/psxpert/reports/ml/fundamental_disclosures_features.parquet)

---

## 2. Retraining Instructions

### Prerequisites
- PostgreSQL running (`localhost:5432/psxpert`).
- Predictive feature/target datasets built in `data/predictive/` (`daily_features.parquet`, `daily_targets.parquet`).
- Runtime inference dependencies are pinned in [`requirements.txt`](file:///c:/Users/HP/psxpert/requirements.txt) (`joblib`, `scikit-learn`, `xgboost` — strictly matching the selected `XGBClassifier` artifact).
- Multi-candidate offline retraining (`LightGBM`, `CatBoost` benchmarks) uses [`requirements-ml-train.txt`](file:///c:/Users/HP/psxpert/requirements-ml-train.txt):
  ```powershell
  pip install -r requirements-ml-train.txt
  ```

### Execute Retraining & Export
```powershell
python train_ml_models.py
```
This script:
1. Loads non-overlapping 5-day strided `TRAIN` (`2002-01-22` – `2021-11-24`), purged `VAL` (`2022-01-03` – `2024-05-20`), and untouched `TEST` (`2024-07-01` – `2026-10-06`).
2. Trains `LightGBM`, `XGBoost`, and `Random Forest` strictly on `TRAIN`, selects the winner strictly by `VAL` Macro-F1, audits 5-fold `VAL` probability calibration, evaluates untouched `TEST`, and exports `artifacts/technical/*.pkl` & `.json` with SHA-256 digests.
3. Builds point-in-time IFRS disclosures and runs the Fundamental label feasibility check (`artifacts/fundamental/fundamental_metadata.json`). **It will intentionally block exporting `fundamental_model.pkl` until valid historical ground-truth labels exist.**

---

## 3. Standalone `.pkl` Loading & Inference in a Fresh Python Process

```python
import json
from pathlib import Path
import joblib
import pandas as pd

preproc = joblib.load("artifacts/technical/technical_preprocessor.pkl")
model = joblib.load("artifacts/technical/technical_model.pkl")
schema = json.loads(Path("artifacts/technical/technical_features.json").read_text())

row_df = pd.read_parquet("data/predictive/daily_features.parquet", columns=schema["feature_cols"]).tail(1)
X = preproc.transform(row_df[schema["feature_cols"]])
probs = model.predict_proba(X)[0]
pred_class = schema["classes"][str(int(probs.argmax()))]
print(pred_class, probs)
```

---

## 4. FastAPI Startup Loading & Endpoints

[`app.py`](file:///c:/Users/HP/psxpert/app.py) loads [`TechnicalMLPredictor`](file:///c:/Users/HP/psxpert/src/ml/technical_ml.py) and [`FundamentalMLAdvisor`](file:///c:/Users/HP/psxpert/src/ml/fundamental_ml.py) **once during FastAPI startup (`lifespan`)** with SHA-256 checksum verification, reusing the in-memory bundle across every HTTP call without reloading `.pkl` files per request:

- **`GET /api/models/status`** — reports `artifact_exists`, `loaded_successfully`, `model_type`, `version`, `training_date`, `ready_for_inference`, and blocking reasons/errors.
- **`POST /api/models/technical/predict`** — accepts JSON `{ "symbol": "OGDC", "as_of_date": "2026-10-13" }` OR `{ "features": { ...74 values... } }`.
- **`POST /api/models/fundamental/predict`** — safely returns `HTTP 503` while Fundamental ML remains `BLOCKED_INSUFFICIENT_RELIABLE_LABELS` (or runs `.pkl` inference once approved labels enable training).

Run automated tests after any change:
```powershell
python -m pytest tests/test_ml_models.py tests/test_analysis_engines.py -v
```

