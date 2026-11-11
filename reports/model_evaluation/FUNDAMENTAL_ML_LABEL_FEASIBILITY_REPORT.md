# Fundamental Analysis ML Model — Label Feasibility & Diagnostic Audit Report (`psxpert_fund_ml_audit_v2.0`)

## 1. Executive Decision
- **Module Version**: `psxpert_fund_ml_audit_v2.0`
- **Training & Export Status**: **`BLOCKED_INSUFFICIENT_RELIABLE_LABELS`**
- **Exported Artifacts (`artifacts/fundamental/`)**:
  - [`fundamental_metadata.json`](../../artifacts/fundamental/fundamental_metadata.json) (`21,899` bytes — documents `model_exported: false`, blocking reasons, diagnostic metrics, and proposed target spec)
  - [`fundamental_features.json`](../../artifacts/fundamental/fundamental_features.json) (`1,775` bytes — 29-feature schema & observed missingness)
  - **`fundamental_model.pkl`**: **Intentionally NOT generated** (per strict prompt rule: *"Do not save an untrained model and call it trained... If a valid model cannot be trained because of missing labels or unreliable data, report the issue instead of producing a misleading `.pkl` file."*).

Production fundamental scoring remains backed by [`FundamentalAnalysisEngine`](../../src/analysis/fundamental_engine.py), while `POST /api/models/fundamental/predict` safely returns `HTTP 503` and `GET /api/models/status` reports exact readiness blockers.

---

## 2. Point-in-Time IFRS Disclosure Audit

[`build_fundamental_disclosures_dataset`](../../src/ml/fundamental_ml.py) constructed [`fundamental_disclosures_features.parquet`](./fundamental_disclosures_features.parquet) (`573` rows × `57` columns, `29` core `FUND_FEATURE_COLS`) across `INCOME_STATEMENT`, `BALANCE_SHEET`, and `CASH_FLOW`, using authentic filing dates from `corporate_announcements` + `+100d` fallback.

| Audit Metric | Observed Count / Pct | Impact on Supervised Training |
|---|---:|---|
| Unique PIT IFRS disclosures (`symbol, period_end_date`) | **573** | Shallow fiscal span (`2021-12-31` – `2026-06-30`) |
| Audited IFRS issuers | **140** | Covers `< 20%` of `726` equities |
| Commercial Banks (`is_bank == 1`) | **12** | Bank reporting omits `gross_profit`, `current_ratio`, `interest_coverage` |
| Unclassified-sector IFRS issuers | **61 / 140** (`43.6%`) | Drives `66.5%` missing `sector_roe_diff`, `68.6%` missing `sector_pe_diff` |
| Inactive / delisted / defaulted IFRS issuers | **`0 / 140`** | **`100%` survivorship bias** |
| External PACRA / VIS credit rating labels | **`0`** | No independent historical ground truth |
| Missing `current_ratio` / `interest_coverage` | `27.9%` / `27.1%` | Structural banking & disclosure omissions |

---

## 3. Non-Circular Inter-Temporal Diagnostic Benchmark (`t -> t+1`)

Aligned with `chronological_splits.json` (`FUND_TRAIN <= 2024-05-20`, `FUND_VAL 2024-07-01..2025-05-20`, `FUND_TEST >= 2025-07-01`), transition sample counts are severely underpowered:
- Strictly in `FUND_TRAIN` (`t, t+1 <= 2024-05-20`): **`142`** (`Weak=60, Moderate=46, Strong=36` — essentially 1 fiscal cycle `FY22->FY23`)
- Cross `FUND_TRAIN -> FUND_VAL`: **`137`** (`Weak=48, Moderate=51, Strong=38`)
- Cross `FUND_VAL -> FUND_TEST` (diagnostic stress test): **`89`** (`Weak=30, Moderate=28, Strong=31`)
- Strictly inside `FUND_TEST`: **`24`** (`Weak=5, Moderate=9, Strong=10`)

### Unseen `Val -> Test` Diagnostic Benchmark (`n = 89`, Not Deployed)

| Candidate / Baseline | Accuracy | Macro F1 | OvR AUC | Key Failure Mode |
|---|---:|---:|---:|---|
| **Simple 3-Metric Rule Baseline** | `0.4944` | **`0.4778`** | — | Outperforms every GBDT (`Moderate` F1 `0.2857`) |
| `CatBoost` Diagnostic | `0.5393` | `0.4442` | `0.6505` | **Collapsed `Moderate` F1 to `0.0000` (`0/28` recall)** |
| `LightGBM` Diagnostic | `0.4944` | `0.4408` | `0.6671` | `ECE = 0.2956`, Macro-F1 below heuristic rule |
| `XGBoost` Diagnostic | `0.4944` | `0.4185` | `0.6715` | `Moderate` F1 collapsed to `0.0588` (`ECE = 0.1683`) |
| `Majority` (`Weak`) | `0.3371` | `0.1681` | — | Single-class collapse |

---

## 4. Approval Prerequisites & Proposed Target (`PROPOSED_FUNDAMENTAL_TARGET_SPEC`)
- **Proposed Target**: `next_12m_fundamental_health_and_distress_outcome` (`Strong`, `Moderate`, `Weak`) anchored on external credit stability/downgrades (`PACRA/VIS`), PSX Defaulter Counter placements, uninterrupted dividends, operating cash flow, and solvency coverage (`Interest Coverage < 1.25x`).
- **Required Before Training Can Be Approved**:
  1. Historical `PACRA`/`VIS` credit rating panel & PSX Defaulter Segment / delisting logs (`0` rows today).
  2. Non-survivor historical IFRS statements (eliminate `100%` survivorship bias).
  3. `>= 8–10` years of audited annual + clean quarterly disclosures across `>= 300+` companies (`>= 1,500` non-overlapping train transitions before `VAL`/`TEST`).
  4. Sector classification backfill for the `61` unclassified IFRS issuers (`711` total) + pre-2025 `corporate_payouts` cleanup.
