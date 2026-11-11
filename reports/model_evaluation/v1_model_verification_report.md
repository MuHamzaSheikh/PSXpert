# PSXpert — ML Model Training, Artifact & Deployment Verification Report

**Verification Timestamp**: `2026-11-11T20:26+05:00`  
**Verification Mode**: Read-only inspection, isolated temp-directory failure testing, direct serialized bundle execution on real historical observations, and live FastAPI HTTP endpoint verification (no models retrained, no artifacts modified, no code altered).

---

## Executive Summary & Final Status Assignment

| Verification | Technical Model | Fundamental Model |
|---|---|---|
| Training script exists | **Yes** ([`train_ml_models.py`](file:///c:/Users/HP/psxpert/train_ml_models.py) -> [`src/ml/technical_ml.py`](file:///c:/Users/HP/psxpert/src/ml/technical_ml.py)) | **Partial (Audit/Diagnostic Only)** ([`train_ml_models.py`](file:///c:/Users/HP/psxpert/train_ml_models.py) -> [`src/ml/fundamental_ml.py`](file:///c:/Users/HP/psxpert/src/ml/fundamental_ml.py)) |
| Training completed | **Yes** (`2026-11-11T14:53:09Z`; LightGBM, XGBoost, RF trained; LightGBM selected) | **Blocked by Label Gate** (`BLOCKED_INSUFFICIENT_RELIABLE_LABELS`; only a discarded 142-row diagnostic benchmark ran) |
| Model artifact exists | **Yes** ([`technical_model_bundle.joblib`](file:///c:/Users/HP/psxpert/models/technical/technical_model_bundle.joblib), `4,445,257` bytes) | **No** (Zero `.joblib`/`.cbm`/`.pkl`/`.ubj` weights saved; only parquet dataset + readiness JSON + scratch `catboost_info/` logs) |
| Artifact loads | **Yes** (`joblib.load` loads `LGBMClassifier`, `TrainOnlyPreprocessor`, 74-feature schema) | **No** (No model weights exist to load; `FundamentalMLAdvisor` loads JSON readiness report only) |
| Evaluation completed | **Yes** ([`evaluation_report.json`](file:///c:/Users/HP/psxpert/models/technical/evaluation_report.json)) | **Yes (Feasibility & Diagnostic Benchmark)** ([`fundamental_ml_readiness_report.json`](file:///c:/Users/HP/psxpert/models/fundamental/fundamental_ml_readiness_report.json)) |
| Test results available | **Yes** (Untouched `TEST` `n = 240,386`: Acc `0.8469`, Macro-F1 `0.8120`, OvR AUC `0.9550`) | **Yes (Diagnostic Proof of Failure)** (`89` `Val->Test` transitions: GBDTs scored `0.4185–0.4442` F1M < Rule `0.4778`; strict `TEST` only `24` rows) |
| Prediction function exists | **Yes** ([`TechnicalMLPredictor.predict_for_symbol`](file:///c:/Users/HP/psxpert/src/ml/technical_ml.py#L644-L729)) | **Blocker Wrapper Only** ([`FundamentalMLAdvisor.assess_symbol`](file:///c:/Users/HP/psxpert/src/ml/fundamental_ml.py#L483-L540) returns `predicted_health_category=None`) |
| API endpoint deployed | **Yes** (`GET /api/analysis/ml/technical/{symbol}`, `/ml/combined/{symbol}`, `/ml/models/status` live on port `8000`) | **Blocker Status Only** (`GET /api/analysis/ml/fundamental/{symbol}` returns rule outputs + blocked ML status) |
| Real inference tested | **Yes** (Direct bundle on `TEST` parquet + live HTTP on `OGDC`, `MEBL`, `LUCK`, `SYS` matched to 4 decimals) | **Verified Honest Non-Inference** (`MEBL` live check returns `model_available=false`, `predicted_health_category=None`, `13/16` completeness) |
| **Assigned Status** | **`DEPLOYED AND VERIFIED`** | **`IMPLEMENTED BUT NOT TRAINED`** |

### Status Classification Distinction
- **`NOT IMPLEMENTED`**: Neither pipeline code, features, nor target logic exist. *(Neither model falls here.)*
- **`IMPLEMENTED BUT NOT TRAINED`**: Data preparation, feature engineering, feasibility checks, and model scaffolding exist in code, but a deployable target model has **not** been trained because prerequisite data/label criteria failed (**Fundamental ML** falls here: formal supervised training was intentionally halted at the label-quality gate, with only a discarded `142`-row diagnostic benchmark executed to prove un-trainability and zero saved weights).
- **`TRAINED BUT NOT SAVED`**: Training completed in memory but no weights were persisted on disk. *(Applies only to the discarded non-production Fundamental diagnostic experiment, not to any deployable model.)*
- **`TRAINED AND SAVED`**: Weights persisted to disk and validated, but no prediction service or API exposes them. *(Exceeded by Technical ML.)*
- **`TRAINED BUT NOT DEPLOYED`**: Artifact saved and callable locally, not mounted in FastAPI routes. *(Exceeded by Technical ML.)*
- **`DEPLOYED AND VERIFIED`**: Serialized model artifact exists on disk, loads cleanly into FastAPI prediction services, is served over live HTTP endpoints, and matches offline `TEST` evaluation parity on genuine historical observations (**Technical ML** backend; note frontend UI & startup hardening items in Section 7).

---

## 1. Model Training Verification

### 1.1 Training Scripts & Execution Logs
- **Entrypoint Script**: [`train_ml_models.py`](file:///c:/Users/HP/psxpert/train_ml_models.py) (`2,661` bytes, modified `2026-11-11 19:45:00`) orchestrates both pipelines against live PostgreSQL (`is_postgres=True`):
  1. [`train_and_evaluate_technical_models`](file:///c:/Users/HP/psxpert/src/ml/technical_ml.py#L336-L588)
  2. [`run_fundamental_ml_audit`](file:///c:/Users/HP/psxpert/src/ml/fundamental_ml.py#L354-L459)
- **Training Logs**:
  - `train_ml_models.py` logs via Python's console logger (`logging.basicConfig`), so no `.log` file is written inside the repository tree.
  - The full runtime log from the training execution is preserved externally in task log `task-4079.log` (`4,942` bytes, `2026-11-11 19:44:50` – `19:53:29` PKT, exit code `0`).
  - Transient CatBoost fit logs exist in [`catboost_info/`](file:///c:/Users/HP/psxpert/catboost_info/catboost_training.json) (`catboost_training.json`, `learn_error.tsv`, `time_left.tsv` at `19:53:28`) from the diagnostic-only benchmark.

### 1.2 Technical Model Training Confirmation
- **Actual ML Training Confirmed**: Genuine gradient-boosted and tree ensemble training ran over real PSX daily panel data (**not** rule engine formulas):
  - **Dataset**: [`data/predictive/daily_features.parquet`](file:///c:/Users/HP/psxpert/data/predictive/daily_features.parquet) (`681,302,651` bytes, `2,024,340` rows across `726` historical PSX symbols including inactive/delisted tickers).
  - **Target Labels ([`compute_causal_technical_labels`](file:///c:/Users/HP/psxpert/src/ml/technical_ml.py#L148-L192))**: Strictly future-independent `<= t` structural classes (`Bearish=0`, `Neutral=1`, `Bullish=2`) built from trailing `ir_126d`, `ker_90d`, and `pos_252d`. None of those three label variables nor any `target_*`, `fin_*`, or raw price level columns appear in the `74` input features ([`TECHNICAL_FEATURE_COLS`](file:///c:/Users/HP/psxpert/src/ml/technical_ml.py#L47-L128)).
  - **Methodology**:
    - `TRAIN` (`2002-01-01` – `2021-11-26`): weekly-strided (`cal_idx % 5 == 0`, `277,591` valid samples) to reduce daily label autocorrelation.
    - `PURGE_TRAIN_VAL`: `25` trading sessions (`2021-11-29` – `2021-12-31`).
    - `VAL` (`2022-01-03` – `2024-05-20`, `198,627` valid samples): early stopping, model selection by Macro-F1, and Platt calibration audit (`calibration_applied: false`).
    - `PURGE_VAL_TEST`: `25` trading sessions (`2024-05-21` – `2024-06-28`).
    - `TEST` (`2024-07-01` – `2026-10-13`, `240,386` valid samples): untouched until final evaluation.
    - [`TrainOnlyPreprocessor`](file:///c:/Users/HP/psxpert/src/ml/technical_ml.py#L244-L288): `0.5% / 99.5%` quantile clipping (preserving binary flags with `unique <= 12`) and medians fit strictly on `TRAIN`.
  - **Verified Hyperparameters**:
    - **LightGBM (Selected)**: `objective="multiclass"`, `num_class=3`, `n_estimators=450` (actual `best_iteration_=449`), `learning_rate=0.05`, `num_leaves=63`, `max_depth=8`, `min_child_samples=80`, `subsample=0.8`, `subsample_freq=1`, `colsample_bytree=0.8`, `reg_alpha=0.5`, `reg_lambda=1.0`, `early_stopping(35)`.
    - **XGBoost (Benchmark 1)**: `objective="multi:softprob"`, `num_class=3`, `n_estimators=450`, `learning_rate=0.05`, `max_depth=6`, `min_child_weight=50`, `subsample=0.8`, `colsample_bytree=0.8`, `reg_alpha=0.5`, `reg_lambda=1.0`, `tree_method="hist"`, `early_stopping_rounds=35`.
    - **Random Forest (Benchmark 2)**: `n_estimators=160`, `max_depth=16`, `min_samples_leaf=40`, `max_features="sqrt"`.

### 1.3 Fundamental Model Training Verification
- **Feature Engineering Executed**: [`build_fundamental_disclosures_dataset`](file:///c:/Users/HP/psxpert/src/ml/fundamental_ml.py#L89-L351) produced [`models/fundamental/fundamental_disclosures_features.parquet`](file:///c:/Users/HP/psxpert/models/fundamental/fundamental_disclosures_features.parquet) (`573` unique point-in-time IFRS disclosures across `140` companies, `57` total columns including `29` [`FUND_FEATURE_COLS`](file:///c:/Users/HP/psxpert/src/ml/fundamental_ml.py#L30-L60)).
- **Production Training Intentionally Halted**: No production model was trained because:
  - `external_credit_rating_labels = 0` (no PACRA/VIS historical ratings).
  - `inactive_delisted_firms = 0` (`100%` survivorship bias across `140` IFRS issuers).
  - Constructing labels from year-`t` ratios would tautologically clone [`FundamentalAnalysisEngine`](file:///c:/Users/HP/psxpert/src/analysis/fundamental_engine.py).
  - Inter-temporal `(t -> t+1)` transitions totaled only `142` in `FUND_TRAIN`, `137` in `Train->Val`, `89` in `Val->Test`, and `24` in strict `FUND_TEST` (`min_class = 5`).
- **Diagnostic-Only Benchmark Run (Discarded)**: `CatBoostClassifier` (`iterations=250, depth=4, lr=0.04, l2_leaf_reg=6.0`), `LGBMClassifier` (`n_estimators=150, num_leaves=15, lr=0.04`), and `XGBClassifier` (`n_estimators=150, max_depth=3, lr=0.04`) were transiently fit on the `142` transitions and evaluated on `89` `Val->Test` transitions solely to prove feasibility failure; **no weights were saved**.

---

## 2. Model Artifact Verification

Recursive search across the workspace for `.joblib`, `.pkl`, `.cbm`, `.txt`, `.json`, `.ubj` (plus `.csv`/`.parquet` under `models/`) identified the following files (excluding library configs like `requirements.txt` and predictive datasets):

| Exact Path | Kind / Framework | Size (Bytes) | Last Modified (PKT) | Loads? | Schema & Metadata |
|---|---|---:|---|---|---|---|
| [`models/technical/technical_model_bundle.joblib`](file:///c:/Users/HP/psxpert/models/technical/technical_model_bundle.joblib) | Trained Technical Model Bundle (`joblib`, `LightGBM LGBMClassifier 4.7.0`) | `4,445,257` | `2026-11-11 19:53:10` | **Yes** | Embedded `feature_cols` (`74` exact match to `TECHNICAL_FEATURE_COLS`), `TrainOnlyPreprocessor`, `label_names`, `label_spec` |
| [`models/technical/model_metadata.json`](file:///c:/Users/HP/psxpert/models/technical/model_metadata.json) | Technical Model Metadata JSON | `5,396` | `2026-11-11 19:53:10` | **Yes** | `psxpert_tech_ml_v1.0`, splits, class counts, calibration audit, top 15 features |
| [`models/technical/evaluation_report.json`](file:///c:/Users/HP/psxpert/models/technical/evaluation_report.json) | Technical Evaluation Report JSON | `53,755` | `2026-11-11 19:53:10` | **Yes** | Full VAL & TEST metrics, confusion matrices, calibration bins, regime & liquid subsets |
| [`models/technical/feature_importance.csv`](file:///c:/Users/HP/psxpert/models/technical/feature_importance.csv) | Feature Importance CSV (`74` features) | `3,241` | `2026-11-11 19:53:09` | **Yes** | Normalized LightGBM gain, XGBoost gain, Random Forest Gini shares |
| [`models/fundamental/fundamental_ml_readiness_report.json`](file:///c:/Users/HP/psxpert/models/fundamental/fundamental_ml_readiness_report.json) | Fundamental Feasibility Audit JSON (NOT model weights) | `19,039` | `2026-11-11 19:53:29` | **Yes** | `BLOCKED_INSUFFICIENT_RELIABLE_LABELS`, missingness audit, diagnostic metrics, target proposal |
| [`models/fundamental/fundamental_disclosures_features.parquet`](file:///c:/Users/HP/psxpert/models/fundamental/fundamental_disclosures_features.parquet) | Fundamental Feature Dataset (`573 × 57`) | `191,373` | `2026-11-11 19:53:27` | **Yes** | 29 `FUND_FEATURE_COLS` + split/outcome audit columns (no model weights) |
| [`catboost_info/catboost_training.json`](file:///c:/Users/HP/psxpert/catboost_info/catboost_training.json) (+ `.tsv`) | CatBoost Scratch Telemetry Log (`250` iters) | `24,759` | `2026-11-11 19:53:28` | N/A | Training loss log only from discarded `catboost_diag` run; **no `.cbm` weights exist** |

**Direct Bundle Load Inspection Output**:
```text
Bundle keys: ['model_version', 'selected_model_name', 'input_kind', 'model', 'calibrator', 'preprocessor', 'feature_cols', 'label_names', 'label_spec', 'trained_at']
Estimator: LGBMClassifier | classes_: [0, 1, 2] | n_features_in_: 74 | best_iteration_: 449
calibrator: None | feature_cols count: 74 | matches TECHNICAL_FEATURE_COLS: True
```

---

## 3. Model Evaluation Verification

### 3.1 Technical Analysis ML Model

#### Split Sizes & Class Distributions
- **`TRAIN` (weekly strided)**: `277,591` (`Bearish`: `59,209` / `21.33%`, `Neutral`: `153,941` / `55.46%`, `Bullish`: `64,441` / `23.21%`)
- **`VAL` (`2022-01-03` – `2024-05-20`)**: `198,627` (`Bearish`: `58,702` / `29.55%`, `Neutral`: `108,082` / `54.41%`, `Bullish`: `31,843` / `16.03%`)
- **`TEST` (`2024-07-01` – `2026-10-13`, untouched)**: `240,386` (`Bearish`: `28,609` / `11.90%`, `Neutral`: `140,696` / `58.53%`, `Bullish`: `71,081` / `29.57%`)

#### Validation vs. Untouched Test Comparison

| Split | Model / Baseline | Accuracy | Macro Prec | Macro Rec | Macro F1 | OvR AUC | Brier | Log-Loss | ECE |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **VAL** | **LightGBM (Selected)** | **0.8557** | **0.8534** | **0.8510** | **0.8522** | **0.9631** | **0.2021** | **0.3209** | **0.0066** |
| **VAL** | XGBoost | 0.8551 | 0.8531 | 0.8496 | 0.8513 | **0.9631** | 0.2027 | 0.3227 | 0.0134 |
| **VAL** | Random Forest | 0.8374 | 0.8465 | 0.8159 | 0.8296 | 0.9546 | 0.2369 | 0.3936 | 0.0705 |
| **VAL** | Simple MA+RSI Baseline | 0.6617 | 0.6548 | 0.6944 | 0.6661 | — | — | — | — |
| **VAL** | Rule Engine Baseline | 0.4091 | 0.4486 | 0.5265 | 0.4075 | — | — | — | — |
| **VAL** | Majority Baseline (`Neutral`) | 0.5441 | 0.1814 | 0.3333 | 0.2349 | — | — | — | — |
| **TEST** | **LightGBM (Selected)** | **0.8469** | 0.8201 | **0.8060** | **0.8120** | **0.9550** | **0.2162** | **0.3453** | 0.0155 |
| **TEST** | XGBoost | 0.8462 | **0.8206** | 0.8028 | 0.8105 | 0.9545 | 0.2167 | 0.3459 | **0.0091** |
| **TEST** | Random Forest | 0.8328 | **0.8206** | 0.7576 | 0.7823 | 0.9465 | 0.2428 | 0.4043 | 0.0603 |
| **TEST** | Simple MA+RSI Baseline | 0.6554 | 0.6146 | 0.6684 | 0.6330 | — | — | — | — |
| **TEST** | Rule Engine Baseline | 0.3996 | 0.4422 | 0.5278 | 0.3922 | — | — | — | — |
| **TEST** | Majority Baseline (`Neutral`) | 0.5853 | 0.1951 | 0.3333 | 0.2461 | — | — | — | — |

#### Untouched `TEST` Confusion Matrix & Per-Class Metrics (LightGBM, `n = 240,386`)

| True \ Pred | `Bearish` | `Neutral` | `Bullish` | Support | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`Bearish`** | **19,279** | 9,330 | **0** | 28,609 | 0.7569 | 0.6739 | 0.7130 |
| **`Neutral`** | 6,192 | **121,944** | 12,560 | 140,696 | 0.8711 | 0.8667 | 0.8689 |
| **`Bullish`** | **0** | 8,721 | **62,360** | 71,081 | 0.8324 | 0.8773 | 0.8542 |

#### Market-Regime & Liquidity Verification (`TEST`, LightGBM)
- **HMM `BEARISH`** (`n = 67,758`): Acc `0.8549`, Macro-F1 `0.8390`, OvR AUC `0.9603`, ECE `0.0108`
- **HMM `BULLISH`** (`n = 81,136`): Acc `0.8505`, Macro-F1 `0.7964`, OvR AUC `0.9563`, ECE `0.0082`
- **HMM `SIDEWAYS`** (`n = 91,492`): Acc `0.8378`, Macro-F1 `0.7869`, OvR AUC `0.9494`, ECE `0.0256`
- **`liquid_top100`** (`n = 55,924`): Acc `0.8475`, Macro-F1 `0.8072`, OvR AUC `0.9587`, ECE `0.0247`

#### Probability Calibration Verification
- Tested 5-fold stratified Platt/logistic calibration on `VAL` log-odds (`raw_log_loss = 0.3209` vs `cv_cal_log_loss = 0.3206`; `raw_ece = 0.0066` vs `cv_cal_ece = 0.0041`). Improvement (`0.0003`) fell below the `0.002` activation threshold, so raw well-calibrated probabilities were kept (`calibrator = None`, `TEST ECE = 0.0155`).

#### Leakage & Validation Audit (Technical)
- **Confirmed Clean**: `TEST` (`2024-07-01` – `2026-10-13`) was separated by a 25-day purge and never used for training, `TrainOnlyPreprocessor`, early stopping, candidate selection, or calibration tuning. Pytest verified bit-for-bit identical causal labels before/after future row truncation (`test_causal_technical_labels_zero_future_leakage`).
- **Observed Weaknesses**:
  1. `early_stopping(35)` on `VAL` reached `best_iteration_ = 449` out of `450` (did not stop early cleanly — indicates slightly higher `n_estimators` could still improve fit on `VAL`).
  2. Macro-cycle class shift between `VAL` (`29.55%` Bearish) and `TEST` (`11.90%` Bearish) lowered `Bearish` recall/F1 on `TEST` (`0.6739` / `0.7130`).
  3. Technical target measures **trailing structural regime (`<= t`)**, not forward future returns.

### 3.2 Fundamental Analysis ML Model (Diagnostic Audit Only)
- Evaluated on `89` `Val->Test` transitions (`Weak=30`, `Moderate=28`, `Strong=31`):
  - **`catboost_diag`**: Acc `0.5393`, Macro-F1 `0.4442`, OvR AUC `0.6505`, Brier `0.6179`, ECE `0.1556` (CM rows `[25,1,4], [9,0,19], [4,4,23]` -> **`Moderate` F1 = `0.0000`**).
  - **`lightgbm_diag`**: Acc `0.4944`, Macro-F1 `0.4408`, OvR AUC `0.6671`, Brier `0.7095`, ECE `0.2956` (`Moderate` F1 = `0.0976`).
  - **`xgboost_diag`**: Acc `0.4944`, Macro-F1 `0.4185`, OvR AUC `0.6715`, Brier `0.6240`, ECE `0.1683` (`Moderate` F1 = `0.0588`).
  - **`simple_rule_baseline`**: Acc `0.4944`, Macro-F1 **`0.4778`** (beats every ML candidate).
  - **`majority_baseline`**: Acc `0.3371`, Macro-F1 `0.1681`.
- **Leakage & Validation Verdict**: Zero leakage in the diagnostic split policy, and the test mathematically exposed severe small-sample underpowering (`142` train rows) + `100%` survivorship bias — confirming the block on deployment.

---

## 4. Model Loading & Deployment Verification

### 4.1 FastAPI Registration & Artifact Usage
- [`app.py`](file:///c:/Users/HP/psxpert/app.py#L580-L583) includes [`src/ml/router.py`](file:///c:/Users/HP/psxpert/src/ml/router.py) (`prefix="/api/analysis/ml"`), registering:
  - `/api/analysis/ml/models/status`
  - `/api/analysis/ml/technical/{symbol}`
  - `/api/analysis/ml/fundamental/{symbol}`
  - `/api/analysis/ml/combined/{symbol}`
- Confirmed via direct comparison (Section 5) that live API requests load and execute [`models/technical/technical_model_bundle.joblib`](file:///c:/Users/HP/psxpert/models/technical/technical_model_bundle.joblib) via [`TechnicalMLPredictor`](file:///c:/Users/HP/psxpert/src/ml/technical_ml.py#L591-L782) and leave legacy rule-engine endpoints (`/api/analysis/*`) untouched.

### 4.2 Startup Behavior vs. Lazy Initialization Finding
- **Application Startup**: `app.py` executes cleanly with **no errors**, **but** does **not** define a `lifespan` or `@app.on_event("startup")` hook for ML models.
- **Lazy Loading Verified**: At FastAPI module import/startup before requests arrive, `src.ml.router._ml_service` is `None` and `TechnicalMLPredictor._bundle` is `None`. `joblib.load(...)` executes **on the first incoming HTTP ML request**, meaning corrupt or missing bundle errors would surface at request time rather than failing fast at boot.

### 4.3 Missing & Corrupted Artifact Safe-Handling Verification
Tested in isolated temporary directories via FastAPI `TestClient`:
- **Missing Technical `.joblib` + Missing Fundamental JSON**:
  - `GET /api/analysis/ml/models/status` -> **`HTTP 200`**: `{"technical_ml_model": {"status": "NOT_TRAINED", "model_available": false}, "fundamental_ml_model": {"training_status": "BLOCKED_INSUFFICIENT_RELIABLE_LABELS", "model_deployed": false, ...}}`.
  - `GET /api/analysis/ml/technical/OGDC` -> **`HTTP 503`** (`FileNotFoundError` caught cleanly by `_run_safe`).
- **Corrupted `.joblib` (`b"NOT_A_VALID_JOBLIB_ARTIFACT"`) + Corrupted `.json` (`"{bad_json"`)**:
  - FastAPI worker does **not** crash, but `_run_safe` returns a generic **`HTTP 500`** (`{"detail": "ML analysis error: 79"}`) instead of a structured `503` degraded status, and there is no SHA-256 checksum verification before unpickling.

### 4.4 Frontend Dashboard Notice
- Inspected [`static/js/app.js`](file:///c:/Users/HP/psxpert/static/js/app.js#L1627-L1634): the existing dashboard UI calls `/api/analysis/*` (rule engines only) and has **not yet** been wired to display `/api/analysis/ml/*`.

---

## 5. Real Historical Feature Inference Tests

All tests executed on genuine PSX historical observations as of **`2026-10-13`** (untouched `TEST` / `FUND_TEST` period; zero synthetic or random inputs). Notice that on `2026-10-13` EOD quotes carry `is_true_ohlc = 0` (`high == low`), so the pipeline masks the 9 intraday candle/range features (`overnight_gap_pct`, `intraday_ret_pct`, `candle_body_pct`, `candle_range_pct`, `upper_shadow_ratio`, `lower_shadow_ratio`, `body_to_range_ratio`, `close_position_in_range`, `hl_spread_pct`) as `NaN` (`65/74` finite features), and LightGBM handles them identically in both offline parquet and live database inference.

### 5.1 Technical ML Parity: Direct `.joblib` Bundle (`TEST` Parquet) vs. Live HTTP API (`127.0.0.1:8000`)

| Symbol (`2026-10-13`) | Valid Inputs | Parquet Direct `.joblib` Prediction & Probs | Live FastAPI HTTP Prediction & Probs | Version / Future Flag | Top-3 Live TreeSHAP Drivers | Valid? |
|---|---|---|---|---|---|---|
| **`OGDC`** | `65 / 74` (`9` flat-OHLC masked) | **`Neutral`** (`Bear:0.0477, Neut:0.9521, Bull:0.0002`) | `HTTP 200` -> **`Neutral`** (`0.0477, 0.9521, 0.0002`) | `psxpert_tech_ml_v1.0` / `false` | `dist_sma_200` (`+1.5223`), `vol_60d` (`-0.512`), `atr_pct` (`-0.2139`) | **Yes (Exact 4-dp match)** |
| **`MEBL`** | `65 / 74` | **`Bullish`** (`Bear:0.0004, Neut:0.4345, Bull:0.5651`) | `HTTP 200` -> **`Bullish`** (`0.0004, 0.4345, 0.5651`) | `psxpert_tech_ml_v1.0` / `false` | `dist_sma_200` (`+2.709`), `ema_50_200_spread` (`+0.7988`), `dist_sma_50` (`+0.6871`) | **Yes (Exact 4-dp match)** |
| **`LUCK`** | `65 / 74` | **`Bearish`** (`Bear:0.6960, Neut:0.3039, Bull:0.0001`) | `HTTP 200` -> **`Bearish`** (`0.6960, 0.3039, 0.0001`) | `psxpert_tech_ml_v1.0` / `false` | `dist_sma_200` (`+2.7953`), `ema_20_50_spread` (`+0.5069`), `dist_sma_50` (`-0.4723`) | **Yes (Exact 4-dp match)** |
| **`SYS`** | `65 / 74` | **`Bearish`** (`Bear:0.9589, Neut:0.0411, Bull:0.0000`) | `HTTP 200` -> **`Bearish`** (`0.9589, 0.0411, 0.0000`) | `psxpert_tech_ml_v1.0` / `false` | `dist_sma_200` (`+3.723`), `ema_20_50_spread` (`+0.9317`), `ema_50_200_spread` (`+0.4894`) | **Yes (Exact 4-dp match)** |

### 5.2 Fundamental Feature & Live Endpoint Verification
- Real `FUND_TEST` IFRS disclosures verified in [`fundamental_disclosures_features.parquet`](file:///c:/Users/HP/psxpert/models/fundamental/fundamental_disclosures_features.parquet):
  - `OGDC` (`period=2026-06-30`, `pub=2026-09-04`): `22/29` non-NaN (`roe=0.1595`, `pe_pit=5.8175`)
  - `MEBL` (`period=2025-12-31`, `pub=2026-02-09`): `25/29` non-NaN (`roe=0.3176`, `pe_pit=9.7446`)
  - `LUCK` (`period=2026-06-30`, `pub=2026-08-10`): `29/29` non-NaN (`roe=0.2078`, `pe_pit=7.4796`)
- Live HTTP test `GET /api/analysis/ml/fundamental/MEBL?as_of_date=2026-10-13` -> `HTTP 200`:
  - `ml_based_fundamental_assessment.status = "BLOCKED_INSUFFICIENT_RELIABLE_LABELS"`, `model_available = false`, `predicted_health_category = None`, `probabilities = None`, `feature_completeness = "13/16"`, while preserving `rule_based_fundamental_assessment` (`CONSTRUCTIVE`, `69.9`).

---

## 6. What Is Missing Before Both Models Are Production-Ready

### 6.1 Missing Before **Fundamental ML Model** Can Be Trained & Deployed
1. **Exogenous Ground-Truth Health/Distress Labels**: Ingest historical `PACRA` / `VIS` entity credit ratings and PSX Defaulter Segment / delisting date logs (`0` rows exist today).
2. **Eliminate Survivorship Bias**: Historical IFRS financial statements for **inactive, suspended, and delisted PSX firms** must be ingested (`0 / 140` non-survivor firms exist today).
3. **Sufficient Multi-Cycle Sample Depth**: Expand audited annual & clean quarterly IFRS coverage from `~3–4` years (`573` rows -> `142` in-train transitions) to **`>= 8–10` years across `>= 300` companies (`>= 1,500` non-overlapping training transitions)**.
4. **Metadata & Feature Remediation**: Assign authentic PSX sectors to the `61` unclassified IFRS issuers (`711/811` unclassified total), clean sentinel `12121.0` / dummy rows in `QUARTERLY`/`ANNUAL`, and backfill `corporate_payouts` dividends.
5. **Re-Train & Beat Baselines**: Only deploy CatBoost/LightGBM once non-circular out-of-sample `FUND_TEST` Macro-F1 and probability calibration decisively beat the heuristic baseline without collapsing the `Moderate` class.

### 6.2 Missing Before **Technical ML Model** Is Enterprise Production-Grade
1. **Eager Startup Preloading & Healthcheck**: Wire a FastAPI `lifespan` startup loader in [`app.py`](file:///c:/Users/HP/psxpert/app.py) so [`TechnicalMLPredictor`](file:///c:/Users/HP/psxpert/src/ml/technical_ml.py#L591-L643) loads and validates the `.joblib` bundle at boot rather than lazily on the first HTTP request.
2. **Artifact Integrity & Corrupt-File Resilience**: Store and verify a SHA-256 checksum inside `model_metadata.json`, wrap `joblib.load` and `json.loads` corruption exceptions in [`FundamentalMLAdvisor`](file:///c:/Users/HP/psxpert/src/ml/fundamental_ml.py#L469-L481) / [`_run_safe`](file:///c:/Users/HP/psxpert/src/ml/router.py#L23-L33) to return explicit `HTTP 503` degraded status instead of generic `HTTP 500`, and persist structured training logs inside the project.
3. **Scheduled Drift & Retraining Pipeline + UI Integration**: Add automated periodic model retraining/regime-drift monitoring (`PSI`/calibration drift across bull/bear shifts where `Bearish` recall dipped to `0.6739`), clean [`catboost_info/`](file:///c:/Users/HP/psxpert/catboost_info/catboost_training.json) scratch output or suppress it with `allow_writing_files=False`, and surface `/api/analysis/ml/*` outputs inside [`static/js/app.js`](file:///c:/Users/HP/psxpert/static/js/app.js) if user-facing ML display is desired.
4. **Separate Phase Separation Note**: Neither model currently predicts **future returns (`t+1d`, `5d`, `20d`)** — a dedicated supervised return/direction forecasting pipeline remains the next separate phase.

