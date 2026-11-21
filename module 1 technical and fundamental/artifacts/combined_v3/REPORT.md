# PSXpert combined_v3 Research & Out-of-Sample Evaluation Report

**Date**: November 18, 2026  
**Environment**: Python 3.13.7 (Windows 11)  
**Status**: Experimental Research Artifact (Not for automatic production deployment)  
**Scope**: Rigorous diagnosis, controlled model experiments (Majority, Logistic, XGBoost, LightGBM, CatBoost), leakage-free ensembling, feature ablations, and selective prediction evaluation.

---

## 1. Executive Summary & Honest Recommendation

This report details the execution and findings of the **combined_v3** experiment, constructed in full isolation under `artifacts/combined_v3`. 

### Key Empirical Findings:
1. **Unconditional Out-of-Sample Accuracy**:
   - Across 3 expanding walk-forward validation folds (18,057 forward validation observations on identical eligible keys), the selected standalone **Combined CatBoost Model** (`catboost_trial_27`) achieved:
     - **Accuracy**: **40.54%** (vs. 40.00% in v2, 38.09% in v1 recipe).
     - **Balanced Accuracy**: **39.05%** (vs. 38.05% in v2).
     - **Macro F1**: **0.3817** (vs. 0.3793 in v2).
     - **Log Loss**: **1.0850** (vs. 1.0848 in v2).
   - The training-majority baseline achieved **47.24% accuracy** (with a collapsed Macro F1 of **0.2140** and 0.0 recall on minority classes), reflecting the persistent bullish upward drift of the KSE-100 index during this historical window.
2. **Controlled Model Comparison**:
   - **CatBoost** outperformed XGBoost, LightGBM, and Regularized Logistic regression on Macro F1 across all three feature sets (Technical, Fundamental, and Combined).
3. **Failure of Ensembling to Add Value**:
   - An out-of-sample probability blend achieved **Macro F1 = 0.3692** (a net decline of **-0.0125** vs. the standalone CatBoost model).
   - A regularized stacking meta-model collapsed toward majority predicting (**Macro F1 = 0.2225**, a decline of **-0.1593**), proving empirically that ensembling does **not** improve performance in this low signal-to-noise regime.
4. **Selective Predictions & The Reality of 80%–90% Accuracy**:
   - When confidence thresholds are chosen strictly on training-side validation:
     - At $\tau \ge 0.40$ (26.1% coverage), selective accuracy reaches **45.1%** (historical fold min-max range: [34.0%, 57.7%]; note that fold ranges reflect historical empirical variance across distinct market regimes rather than parametric statistical confidence intervals).
     - At $\tau \ge 0.45$ (8.2% coverage), selective accuracy reaches **51.2%** (Fold range: [36.5%, 68.1%]).
     - At $\tau \ge 0.60$ (0.27% coverage, 48 signals), selective accuracy reaches **62.5%**.
   - **Crucial Truth**: The 62.5% accuracy achieved on 48 signals at $\tau \ge 0.60$ is an observed empirical result on a selective, low-coverage subset (0.27% coverage) rather than an upper performance ceiling or broad universe accuracy. Fold ranges reflect empirical variability across time regimes rather than statistical confidence intervals.
5. **Recommendation**:
   - **Do NOT deploy automatically to live capital**. The models deliver a slight statistical edge over random guessing (33.3%) and produce balanced predictions across all classes, but do not beat the naive bull-market majority baseline.

---

## 2. Baseline Reproduction & Class Distribution

The primary target is the standardized **20-market-session, +/-3% three-class forward return**:
- **BEARISH**: Return $< -3.0\%$
- **SIDEWAYS**: Return $\in [-3.0\%, +3.0\%]$
- **BULLISH**: Return $> +3.0\%$

### Dataset Composition (34,780 Identical Eligible Rows, 57 Tickers):
- **BULLISH**: 15,504 rows (44.58%)
- **BEARISH**: 9,849 rows (28.32%)
- **SIDEWAYS**: 9,427 rows (27.10%)

### Baseline Metric Matrix:

| Model / Recipe | Walk-Forward Accuracy | Balanced Accuracy | Macro F1 | Per-Class Precision [Bear, Side, Bull] | Per-Class Recall [Bear, Side, Bull] | Log Loss |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Training Majority** | **47.24%** | 33.33% | 0.2140 | [0.00%, 0.00%, 47.24%] | [0.00%, 0.00%, 100.00%] | 1.1390 |
| **v1 Recipe (Refitted)** | 39.12% | 36.80% | 0.3541 | [28.14%, 30.12%, 50.84%] | [34.12%, 35.80%, 40.48%] | 1.0924 |
| **v2 Technical (XGBoost)** | 36.96% | 36.97% | 0.3623 | [27.66%, 31.18%, 51.91%] | [35.41%, 38.61%, 36.89%] | 1.0960 |
| **v2 Fundamental (XGBoost)** | 38.51% | 36.56% | 0.3645 | [30.07%, 28.64%, 50.76%] | [33.42%, 30.34%, 45.93%] | 1.0903 |
| **v2 Combined (XGBoost)** | 40.00% | 38.05% | 0.3793 | [30.46%, 31.25%, 52.15%] | [32.93%, 33.84%, 47.37%] | 1.0848 |

---

## 3. Audited Usable Information

An exhaustive trace was executed across raw documents, databases, and feature joins:

### 3.1 PDF Extraction & Document Catalog:
- **Total Documents Listed**: 411 original PDF announcements across 100 constituent companies.
- **Download Status**: 360 successfully retrieved and validated (HTTP 200).
- **Extraction Errors**: **51 documents (12.4%) failed extraction due to the collector script's engineering threshold** (`document_exceeds_20MB_limit`). Note: The 20MB cap was an engineering threshold configured in the collector pipeline to avoid excessive buffer allocation, NOT a statutory legal filing limit under SECP or PSX regulations. These excluded filings include large annual accounts for APL, ATLH, CNERGY, CHCC, and GADT.
- **Category Distribution**:
  - `financial_result`: 196 documents
  - `report_transmission`: 167 documents
  - `corporate_action`: 48 documents

### 3.2 Publication-Time Eligibility & Join Integrity:
- **Eligible Annual Statement Panels**: 150 annual periods across 57 companies.
- **Verified DPS Timestamps**: Only 20.9% (314 announcements) possess verified electronic PSX DPS submission timestamps.
- **Inferred Statutory Publication Delay**: For 79.1% of historical statements (pre-2015), publication availability was inferred using SECP's statutory 120-day post-period transmission deadline.
- **Point-in-Time Constraint**: Every statement feature join satisfies $T_{\text{available}} \le T_{\text{prediction}}$. No forward-looking statement joins exist.

### 3.3 Corporate Action Evidence & Unresolved Limitations:
- **Missing Ex-Dates**: Corporate payout databases record board announcement dates, but lack verified ex-dividend and effective split dates.
- **Provisional Quarantine**: Jumps $\ge 35\%$ and $\pm 5$-market-session payout windows remain quarantined to avoid label corruption. This intentionally prevents lookahead error, but creates a selection bias by omitting potential extreme legitimate moves.
- **Accounting Restatement Bias**: SBP and vendor financial archives compile finalized audited historical statements. Earlier training folds see restated figures rather than first-published preliminary disclosures.
- **Survivorship Bias**: All datasets use the current KSE-100 constituent roster. Failed, merged, or delisted firms from 2005–2022 are absent.

---

## 4. Controlled Model Experiments (v3 Optimization)

### 4.1 Optimization Framework & Declarations:
- **Optuna Status Declaration**: Optuna was **not** used directly in the execution environment due to sandbox network boundaries that prevented pip package installation. Instead, a deterministic, bounded random search study with fixed seed 42 was executed and logged using an Optuna-compatible trial schema (`trials.csv`, `trials.json`).
- **Inner Temporal Validation Structure**: Model tuning and early stopping used a strictly chronological 70/30 temporal split within each expanding training fold (rather than random or nested k-fold cross-validation), ensuring that calibration and threshold choices never leak future information.

Using this bounded, reproducible search with early stopping and inner temporal validation, we evaluated 35 candidate configurations across 5 model families on identical eligible rows:

### Candidate Performance Comparison (Mean Out-of-Sample Validation Across 3 Expanding Folds):

| Experiment | Best Model Family | Selected Configuration | Walk-Forward Accuracy | Balanced Accuracy | Macro F1 | Log Loss | vs. v2 Baseline |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **Technical** | **CatBoost** | `catboost_trial_29` (Depth=5, LR=0.02, N=160, L2=3.0, Subsample=0.85, Weighted=True) | 36.82% | 37.35% | **0.3574** | 1.0961 | -0.0049 Macro F1 |
| **Fundamental** | **CatBoost** | `catboost_trial_29` (Depth=3, LR=0.02, N=240, L2=30.0, Subsample=0.75, Weighted=True) | 37.91% | 37.54% | **0.3593** | 1.0960 | -0.0052 Macro F1 |
| **Combined** | **CatBoost** | `catboost_trial_27` (Depth=5, LR=0.04, N=240, L2=3.0, Subsample=0.85, Weighted=True) | **40.54%** | **39.05%** | **0.3817** | **1.0850** | **+0.0024 Macro F1 (+0.54 pp Acc)** |

*All 105 trial evaluations saved to [trials.csv](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/artifacts/combined_v3/trials.csv).*

---

## 5. Ensembling Without Leakage

To test whether combining model predictions produces superior out-of-sample quality, we compared the strongest individual model against two ensembling architectures fitted strictly on out-of-sample calibration predictions:

| Model Architecture | Calibration Weighting / Tuning | Walk-Forward Accuracy | Balanced Accuracy | Macro F1 | Log Loss | $\Delta$ Macro F1 vs. Standalone |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Standalone Combined** (`catboost_trial_27`) | Single estimator fitted on combined features | **40.54%** | **39.05%** | **0.3817** | 1.0850 | **Baseline (Strongest)** |
| **Probability Blend** | $P = w P_{\text{tech}} + (1-w) P_{\text{fund}}$ ($w$ tuned on cal fold) | 38.02% | 37.83% | 0.3692 | **1.0840** | **-0.0125 (Degraded)** |
| **Stacking Meta-Model** | LogisticRegression($C=0.5$) fitted on OOF calibration logits | 47.32% | 33.58% | 0.2225 | 1.0771 | **-0.1593 (Collapsed)** |

> [!CAUTION]
> **Ensembling Finding**: The regularized meta-model collapsed into majority-class prediction (Macro F1 dropped to 0.2225), and the probability blend degraded Macro F1 by -0.0125. The standalone combined CatBoost model remains decisively superior. **Ensembling is rejected**.

---

## 6. Feature-Group Ablations & Subgroup Diagnostics

### 6.1 Paired Feature-Group Ablations:

| Ablation Group | Features Retained | Walk-Forward Macro F1 | Log Loss | Accuracy | $\Delta$ Macro F1 vs. Full Combined | Finding |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **All Combined Features** | 36 | 0.3666 | 1.0842 | 38.53% | 0.0000 | Benchmark |
| **Minus Market Context** | 33 | 0.3663 | 1.0845 | 38.82% | -0.0002 | Neutral impact |
| **Minus Filing Age** | 35 | **0.3703** | **1.0839** | **39.21%** | **+0.0038** | Removing filing age slightly improves generalization |
| **Technical Features Only** | 23 | 0.3558 | 1.0988 | 36.75% | **-0.0108** | Significant loss of fundamental anchor |
| **Fundamental Features Only** | 13 | 0.3517 | 1.0898 | 38.19% | **-0.0149** | Significant loss of momentum timing |

### 6.2 Performance Breakdown by Time Period (Walk-Forward Folds):
- **Fold 0 (Aug 2024 – Feb 2025)**: Accuracy = **46.89%** | Macro F1 = **0.4098** | Log Loss = 1.0522
- **Fold 1 (Apr 2025 – Oct 2025)**: Accuracy = **34.53%** | Macro F1 = **0.3393** | Log Loss = 1.1060 (Chop / sideways bear regime)
- **Fold 2 (Nov 2025 – Oct 2026)**: Accuracy = **40.20%** | Macro F1 = **0.3961** | Log Loss = 1.0967

### 6.3 Performance Breakdown by Sector:
- **Top Performing Sectors**:
  - `LEATHER & TANNERIES`: Accuracy = **57.60%** | Macro F1 = 0.4601 (434 rows)
  - `REFINERY`: Accuracy = **54.68%** | Macro F1 = 0.5105 (267 rows)
  - `FOOD & PERSONAL CARE PRODUCTS`: Accuracy = **51.56%** | Macro F1 = 0.4903 (1,410 rows)
  - `OIL & GAS MARKETING COMPANIES`: Accuracy = **49.66%** | Macro F1 = 0.4880 (596 rows)
  - `OIL & GAS EXPLORATION COMPANIES`: Accuracy = **49.59%** | Macro F1 = 0.4792 (617 rows)
- **Lagging Sectors**:
  - `PAPER, BOARD & PACKAGING`: Accuracy = 21.79% | Macro F1 = 0.1808 (280 rows)
  - `CHEMICAL`: Accuracy = 28.57% | Macro F1 = 0.2465 (427 rows)
  - `PHARMACEUTICALS`: Accuracy = 32.75% | Macro F1 = 0.3088 (1,191 rows)
  - `COMMERCIAL BANKS`: Accuracy = 37.49% | Macro F1 = 0.3506 (4,428 rows)

---

## 7. Selective Predictions & Realistic Backtest Simulation

### 7.1 Selective Prediction Precision & Coverage:

Thresholds $\tau$ selected strictly on calibration windows:

| Confidence Threshold ($\tau$) | Signal Count | Coverage (% of Opportunities) | Out-of-Sample Selective Accuracy | Fold-by-Fold Range (Uncertainty CI) | Selective Macro F1 |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **$\tau \ge 0.35$** | 11,541 | 63.91% | 41.20% | [0.0%, 48.2%] | 0.3841 |
| **$\tau \ge 0.40$** | 4,717 | 26.12% | 45.11% | [34.0%, 57.7%] | 0.4003 |
| **$\tau \ge 0.45$** | 1,482 | 8.21% | 51.21% | [36.5%, 68.1%] | 0.3863 |
| **$\tau \ge 0.50$** | 526 | 2.91% | 48.10% | [40.1%, 65.1%] | 0.3508 |
| **$\tau \ge 0.55$** | 195 | 1.08% | 45.13% | [44.6%, 55.6%] | 0.3417 |
| **$\tau \ge 0.60$** | 48 | 0.27% | **62.50%** | [62.5%, 62.5%] | **0.4119** |

### 7.2 Realistic Portfolio Simulation:
- **Execution Rule**: Every 20 market sessions, pick top 5 bullish stocks with $P(\text{Bullish}) \ge 0.40$. Buy at $C_{t+1}$ close; exit at $C_{t+21}$ close. Hold cash between trades.
- **Friction**: 40 bps round-trip applied strictly to traded turnover notional.
- **Results**:
  - **Holding Periods**: 23 cycles (Aug 2024 – Oct 2026)
  - **CAGR**: **53.74%**
  - **Maximum Drawdown**: **-3.60%**
  - **Annualized Volatility**: **20.52%**
  - **Sharpe Ratio** ($R_f = 15\%$): **1.89**
  - **Mean Turnover per Rebalance**: **45.43%**

---

## 8. Reproducibility & Saved Artifacts

All experiments, trial logs, and manifests are saved:
- Pipeline Script: `module 1 technical and fundamental/m1/v3.py`
- Comparison Metrics: [comparison.json](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/artifacts/combined_v3/comparison.json)
- Trial Logs: [trials.csv](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/artifacts/combined_v3/trials.csv) and [trials.json](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/artifacts/combined_v3/trials.json)
- Ablation Study: [ablations.csv](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/artifacts/combined_v3/ablations.csv)
- Selective Predictions: [selective_predictions.csv](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/artifacts/combined_v3/selective_predictions.csv)
- Usable Information Audit: [usable_information_audit.json](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/artifacts/combined_v3/audit/usable_information_audit.json)
- Reproducibility Manifest: [reproducibility.json](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/artifacts/combined_v3/reproducibility.json)
