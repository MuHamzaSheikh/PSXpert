# Technical Analysis ML Model — Evaluation Report (`psxpert_tech_ml_v2.0`)

## 1. Executive Summary
- **Model Identifier**: `psxpert_tech_ml_v2.0`
- **Selected Algorithm**: **`XGBoost`** (`XGBClassifier`), objectively selected strictly on chronological **Validation (`VAL`) Macro-F1 (`0.3987`)** ahead of initial primary candidate `LightGBM` (`0.3949`) and `Random Forest` (`0.3837`).
- **Trained At (UTC)**: `2026-11-11T16:12:54.200905+00:00`
- **Exported Artifacts (`artifacts/technical/`)**:
  - [`technical_model.pkl`](file:///c:/Users/HP/psxpert/artifacts/technical/technical_model.pkl) (`1,308,782` bytes)
  - [`technical_preprocessor.pkl`](file:///c:/Users/HP/psxpert/artifacts/technical/technical_preprocessor.pkl) (`2,326` bytes)
  - [`technical_features.json`](file:///c:/Users/HP/psxpert/artifacts/technical/technical_features.json) (`74` features)
  - [`technical_metadata.json`](file:///c:/Users/HP/psxpert/artifacts/technical/technical_metadata.json)
- **Untouched Test Performance (`n = 230,739`, `2024-07-01` – `2026-10-06`)**:
  - **Accuracy**: `0.4104` vs. Rule Engine Baseline `0.3081`, Simple MA+RSI Baseline `0.3541`, Majority (`Neutral`) `0.4277`
  - **Macro-F1**: **`0.3844`** vs. LightGBM `0.3833`, Random Forest `0.3644`, Simple MA+RSI `0.3199`, Rule Engine `0.3050`, Majority `0.1997`
  - **One-vs-Rest Macro ROC-AUC**: **`0.5738`**
  - **Multi-class Brier Score**: `0.6544` | **Log-Loss**: `1.0802` | **ECE (10-bin)**: `0.0215`

> [!NOTE]
> **Scope Boundary**: This single-modality Technical classifier predicts `5d` volatility-aware technical condition (`Bullish` / `Neutral` / `Bearish`) from `74` technical/OHLCV/HMM/liquidity features only (`is_expected_return_regression = false`). It does **not** include fundamentals, FinBERT sentiment, or expected-return regression (reserved for the final forecasting phase).

---

## 2. Target Labeling & Anti-Leakage Architecture

### 2.1 Documented Volatility-Aware Forward Target (`target_label_5d`)
Instead of cloning [`TechnicalAnalysisEngine`](file:///c:/Users/HP/psxpert/src/analysis/technical_engine.py) scores, targets come strictly from [`data/predictive/daily_targets.parquet`](file:///c:/Users/HP/psxpert/data/predictive/daily_targets.parquet), defined using causal 20-day volatility (`vol_20d[t]`) plus a `50 bps` PSX round-trip transaction-cost threshold:
$$\text{threshold}_{5d,t} = 0.0050 + 0.35 \cdot \max(\text{vol}_{20d,t},\; 0.005) \cdot \sqrt{5}$$

| Class Index | Label | Rule in `daily_targets.parquet` | Active Validity Gates |
| :---: | :--- | :--- | :--- |
| `0` | **`Bearish`** | `target_ret_5d <= -threshold_5d` (`DOWN`) | `target_valid_5d == 1` & `is_zero_volume == 0` |
| `1` | **`Neutral`** | `\|target_ret_5d\| < threshold_5d` (`NEUTRAL`) | `target_valid_5d == 1` & `is_zero_volume == 0` |
| `2` | **`Bullish`** | `target_ret_5d >= +threshold_5d` (`UP`) | `target_valid_5d == 1` & `is_zero_volume == 0` |

### 2.2 Chronological Splits, Non-Overlapping Stride & Imbalance Weighting (`726` Equities)

| Split | Date Window | Trading Rule | Valid Rows | `Bearish` | `Neutral` | `Bullish` |
|---|---|---|---|---:|---:|---:|
| **`TRAIN`** | `2002-01-22` – `2021-11-24` | `cal_idx % 5 == 0` (0 overlapping `5d` targets) | `235,849` | `68,721` (`29.14%`) | `94,895` (`40.24%`) | `72,233` (`30.63%`) |
| `PURGE_TV` | `2021-11-29` – `2021-12-31` | `25`-session exclusion buffer (`5x` horizon) | — | — | — | — |
| **`VAL`** | `2022-01-03` – `2024-05-20` | Early stopping, selection & calibration audit | `165,656` | `49,563` (`29.92%`) | `69,133` (`41.73%`) | `46,960` (`28.35%`) |
| `PURGE_VT` | `2024-05-21` – `2024-06-28` | `25`-session exclusion buffer | — | — | — | — |
| **`TEST`** | `2024-07-01` – `2026-10-06` | **Untouched** final evaluation set | `230,739` | `65,910` (`28.56%`) | `98,688` (`42.77%`) | `66,141` (`28.66%`) |

- **Preprocessing ([`TrainOnlyPreprocessor`](file:///c:/Users/HP/psxpert/src/ml/technical_ml.py))**: `[0.5%, 99.5%]` winsorization bounds (discrete flags `unique <= 12` preserved unclipped) and medians fitted **strictly on `TRAIN`**; `impute_missing=False` preserves native `NaN`s for `XGBoost`.
- **Class Imbalance Mitigation**: Mild inverse class-frequency weighting (`exponent = 0.7`, computed solely on `TRAIN`) prevents collapse onto the `40–43%` `Neutral` majority class without distorting log-odds.

---

## 3. Selected Model & Candidate Benchmark Comparisons

### 3.1 Selected Hyperparameters (`XGBoost`, `best_iteration = 598`)
`objective="multi:softprob"`, `num_class=3`, `eval_metric="mlogloss"`, `n_estimators=600`, `learning_rate=0.025`, `max_depth=5`, `min_child_weight=250`, `subsample=0.8`, `colsample_bytree=0.7`, `reg_alpha=2.0`, `reg_lambda=10.0`, `tree_method="hist"`, `early_stopping_rounds=35`, `random_state=42`.

### 3.2 Chronological Validation (`VAL`, `n = 165,656`)

| Model / Baseline | Accuracy | Macro Prec | Macro Rec | Macro F1 | Weighted F1 | OvR AUC | Brier | Log-Loss | ECE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **`XGBoost` (Selected)** | `0.4157` | **`0.4047`** | **`0.4022`** | **`0.3987`** | **`0.4111`** | **`0.5828`** | **`0.6508`** | **`1.0742`** | **`0.0166`** |
| `LightGBM` (Primary Init) | `0.4126` | `0.4027` | `0.3991` | `0.3949` | `0.4076` | `0.5794` | `0.6526` | `1.0766` | `0.0179` |
| `Random Forest` | `0.3997` | `0.3917` | `0.3853` | `0.3837` | `0.3924` | `0.5619` | `0.6577` | `1.0861` | `0.0350` |
| Simple MA + RSI Rule | `0.3428` | `0.3326` | `0.3284` | `0.3254` | — | — | — | — | — |
| Rule Engine Approximation | `0.3033` | `0.3343` | `0.3244` | `0.2987` | — | — | — | — | — |
| Majority (`Neutral`) | **`0.4173`** | `0.1391` | `0.3333` | `0.1963` | — | — | — | — | — |

### 3.3 Untouched Final Test (`TEST`, `n = 230,739`)

| Model / Baseline | Accuracy | Macro Prec | Macro Rec | Macro F1 | Weighted F1 | OvR AUC | Brier | Log-Loss | ECE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **`XGBoost` (Selected)** | `0.4104` | **`0.3947`** | **`0.3941`** | **`0.3844`** | **`0.4013`** | **`0.5738`** | `0.6544` | `1.0802` | `0.0215` |
| `LightGBM` | `0.4093` | `0.3927` | `0.3923` | `0.3833` | `0.4000` | `0.5725` | **`0.6543`** | **`1.0799`** | **`0.0182`** |
| `Random Forest` | `0.4035` | `0.3764` | `0.3731` | `0.3644` | `0.3886` | `0.5534` | `0.6562` | `1.0837` | `0.0186` |
| Simple MA + RSI Rule | `0.3541` | `0.3256` | `0.3310` | `0.3199` | — | — | — | — | — |
| Rule Engine Approximation | `0.3081` | `0.3393` | `0.3285` | `0.3050` | — | — | — | — | — |
| Majority (`Neutral`) | **`0.4277`** | `0.1426` | `0.3333` | `0.1997` | — | — | — | — | — |

---

## 4. Confusion Matrices & Per-Class Performance (`XGBoost`)

### Untouched `TEST` (`n = 230,739`)
| True \ Predicted | `Bearish` | `Neutral` | `Bullish` | Support | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`Bearish`** | **31,056** (`47.12%`) | 23,412 (`35.52%`) | 11,442 (`17.36%`) | 65,910 | `0.3401` | `0.4712` | `0.3950` |
| **`Neutral`** | 34,639 (`35.10%`) | **50,407** (`51.08%`) | 13,642 (`13.82%`) | 98,688 | `0.4986` | `0.5108` | `0.5046` |
| **`Bullish`** | 25,629 (`38.75%`) | 27,271 (`41.23%`) | **13,241** (`20.02%`) | 66,141 | `0.3455` | `0.2002` | `0.2535` |

### `VAL` (`n = 165,656`)
| True \ Predicted | `Bearish` | `Neutral` | `Bullish` | Support | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`Bearish`** | **22,334** (`45.06%`) | 18,492 (`37.31%`) | 8,737 (`17.63%`) | 49,563 | `0.3624` | `0.4506` | `0.4017` |
| **`Neutral`** | 22,549 (`32.62%`) | **34,390** (`49.74%`) | 12,194 (`17.64%`) | 69,133 | `0.4846` | `0.4974` | `0.4910` |
| **`Bullish`** | 16,745 (`35.66%`) | 18,079 (`38.50%`) | **12,136** (`25.84%`) | 46,960 | `0.3670` | `0.2584` | `0.3033` |

---

## 5. Probability Calibration & Regime-Stratified Analysis

### 5.1 Calibration Audit (`VAL` & Untouched `TEST`)
- On `VAL`, raw `XGBoost` achieved **`ECE = 0.0166` (`log_loss = 1.0742`, `f1_macro = 0.3987`)**. 5-fold Platt calibration reduced `ECE` (`0.0036`) and `log_loss` (`1.0609`), **but lowered `VAL` Macro-F1 to `0.3475`** (re-anchoring decisions toward `Neutral`), violating the `-0.015` Macro-F1 retention guard; raw probabilities were therefore retained (`applied: false`).
- Untouched `TEST` reliability bins (`ECE = 0.0215`):
  - `[0.3, 0.4]` (`79,691` rows): confidence `0.3757`, accuracy `0.3732`
  - `[0.4, 0.5]` (`120,934` rows): confidence `0.4398`, accuracy `0.4223`
  - `[0.5, 0.6]` (`26,439` rows): confidence `0.5369`, accuracy `0.4526`
  - `[0.6, 0.7]` (`3,500` rows): confidence `0.6295`, accuracy `0.5134`
  - `[0.7, 0.8]` (`170` rows): confidence `0.7307`, accuracy `0.7529`
  - `[0.8, 0.9]` (`5` rows): confidence `0.8157`, accuracy `0.2000`

### 5.2 Market-Regime & Liquidity Slices (`TEST`, `XGBoost`)

| Slice (`TEST`) | Samples | Accuracy | Macro F1 | OvR AUC | ECE |
|---|---:|---:|---:|---:|---:|
| **HMM `BEARISH`** | `66,281` | `0.4240` | `0.3869` | `0.5834` | `0.0228` |
| **HMM `BULLISH`** | `77,337` | `0.4244` | **`0.4059`** | **`0.5955`** | **`0.0103`** |
| **HMM `SIDEWAYS`** | `87,121` | `0.3877` | `0.3589` | `0.5463` | `0.0439` |
| **`liquid_top100`** | `55,945` | `0.3944` | `0.3703` | `0.5522` | — |
