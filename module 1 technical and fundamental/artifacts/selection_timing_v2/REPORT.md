# Comprehensive Audit and Evaluation Report: Selection and Timing Architecture v2

## Executive Summary

This report presents the rigorous audit, pipeline correction, and empirical re-evaluation of the two-stage fundamental-selection and technical-entry timing architecture (`selection_timing_v2`) in the PSXpert project.

Following an exhaustive audit of `selection_timing_v1`, several methodological flaws and unsupported claims were identified and resolved:
1. **Misleading Narrative on Filter Inactivity**: In `v1`, periods where the technical model emitted zero signals were characterized as "successful capital preservation" and fewer signals were characterized as "reduced turnover". In reality, zero trades represented total model paralysis. In Fold 2, this inactive filter held 100% cash and delivered a 0.00% return while the unfiltered fundamental portfolio gained **+46.00%** (CAGR 108.25%, Sharpe 3.01). This caused statistically significant underperformance ($p = 0.026$).
2. **Input Universe Truncation via Future Label Leakage**: The `v1` pipeline reused `combined_v2/eligible_rows.csv.gz`, which had discarded 805 rows where point-in-time financial statements and technical indicators were fully known at prediction time $t$, purely because their future 20-session return could not be computed (e.g., sessions near dataset cutoffs or in provisional quarantine). We rebuilt the point-in-time panel from source files (`prepare_decision_inputs_v2.py`) with zero future-label filtering, establishing a full 100-ticker panel of **98,391 rows** (Sessions 5107–6126).
3. **Clarification of Price Adjustments and Corporate Actions**: Raw transaction prices from `stock_prices_clean.csv` had been duplicated into `adjusted_open` and `adjusted_close` columns. We explicitly declare these as **raw, unadjusted transaction prices**. The $\pm 5$-session payout quarantine and $\ge 35\%$ jump filters are provisional heuristic safeguards (covering 92.59% heuristic validity), leaving an audited **7.41% remaining label uncertainty** due to unverified corporate actions.
4. **Fair Baseline Disclosures and Inner-Validation Selection**: In `v1`, XGBoost and XGBRanker were claimed to outperform baselines across every fold. In reality, on outer test sets, simple heuristic composites regularly beat machine learning:
   - **Fundamental**: The Simple Value Composite (`inverse_pe_pb_sum`) beat XGBRanker in Fold 1 (NDCG 0.6415 vs 0.5330, top-group excess return +13.84% vs -1.87%) and Fold 3 (NDCG 0.5755 vs 0.5456, excess return +9.33% vs +4.72%). Momentum beat XGBRanker in Fold 1 (NDCG 0.5457 vs 0.5330) and Fold 3 (NDCG 0.7461 vs 0.5456).
   - **Technical**: In Fold 3, Regularized Logistic Regression (AP 0.3502) and SMA Breakout (AP 0.3502) both outperformed XGBoost (AP 0.3161).
   - In `v2`, model selection was conducted strictly via **inner temporal validation** without cherry-picking.
5. **Realistic Daily Portfolio Simulation**: We implemented an institutional multi-asset daily backtest engine with identical initial capital (PKR 10,000,000), single-position caps (10%), next-open execution ($t+1$), 0.50% round-trip trading friction, daily cash and overlapping position tracking, and paired date-level Newey-West HAC statistical tests (lag 10).
6. **Definitive Empirical Conclusion**: **The technical entry filter does not improve the fundamental shortlist.** Across all market regimes, it either slightly degrades returns due to transaction costs (Fold 1: +25.18% vs +26.74%), completely shuts down and misses major rallies (Fold 2: 0.00% vs +46.00%, $t = -2.23, p = 0.026$), or stays inactive during drawdowns (Fold 3: 0.00% vs -4.91%, $p = 0.835$).

---

## 1. Audit Corrections and Methodology

### 1.1 Resolution of Unsupported Claims
| Claim in `selection_timing_v1` | Audited Truth in `selection_timing_v2` | Correction Implemented |
| :--- | :--- | :--- |
| Zero signals called "successful capital preservation" | In Fold 2, zero signals caused the portfolio to sit in 100% cash while the market gained +46.00%, resulting in statistically significant underperformance ($p = 0.026$). | Renamed "model inactivity / signal blackout". Disclosed as opportunity cost and systematic calibration failure. |
| Fewer signals called "reduced portfolio turnover" | Zero trades is zero activity, not turnover reduction. In Fold 1 where both traded, turnover was identical (23.01 vs 22.99). | Reported annualized turnover directly from simulated transaction volume ($Turnover = Traded Volume / (2 \times Equity)$). |
| Claimed ML beat all baselines across every fold | Simple Value Composite beat XGBRanker in Folds 1 and 3; Momentum beat XGBRanker in Folds 1 and 3; Logistic Regression beat XGBoost in Fold 3. | Fully disclosed all baseline comparisons in `baseline_comparison.json` and report tables. |
| Automatic model replacement based on outer test scores | Outer test holdouts cannot be used for model selection without data snooping. | Model selection restricted strictly to inner temporal validation sets. |

### 1.2 Fixed Point-in-Time Universe Architecture
In `selection_timing_v1`, `prepare_decision_inputs.py` loaded `artifacts/combined_v2/eligible_rows.csv.gz`. In `v2.py`, that file had been generated by:
$$\text{eligible\_rows} = \text{data}[\text{future\_direction.notna()}]$$
This filtered out 805 observations where point-in-time fundamentals and technical indicators were known at session $t$, simply because their future 20th session was beyond the dataset or quarantined.

In `selection_timing_v2`:
- We built `m1/prepare_decision_inputs_v2.py` invoking `build_feature_panel(labels=False)`.
- Restored the entire 100-ticker PSX universe across all 1,020 trading sessions (5107 to 6126).
- **Total panel rows**: 98,391.
- **Fundamental-eligible rows**: 35,653 (verified point-in-time statement publication timestamps, zero future target filtering).
- **Technical-eligible rows**: 98,367.
- Prediction eligibility is evaluated strictly at session $t$, attaching future labels only during model training and evaluation.

### 1.3 Price Validity and Corporate Action Audit
- Prices in `data/raw_unadjusted_prices.csv` are **raw transaction prices** (open, high, low, close, volume) from PSX trade feeds.
- Although columns are named `adjusted_open` and `adjusted_close` to satisfy pipeline contracts, they are **unadjusted for cash dividends, stock bonuses, or rights issues**.
- **Provisional Quarantine Safeguards**:
  - Drops $\pm 5$ trading sessions around dividend/bonus announcement dates.
  - Drops price movements exceeding $\ge 35\%$ in a single session without fundamental justification.
  - Audit statistics: 94,444 of 102,000 price records (92.59%) are provisionally valid; 7,556 records (7.41%) are quarantined.
  - **Remaining Label Uncertainty**: 7.41% of forward return targets carry unadjusted corporate-action risk.

---

## 2. Fair Model Comparisons & Selection Trials

All model hyperparameter searches and baseline comparisons were conducted strictly on **inner temporal validation splits** (Sessions 5107–5379 for Fold 1, 5107–5499 for Fold 2, 5107–5619 for Fold 3).

### 2.1 Fundamental Selection Branch (126-Session Benchmark-Relative Excess Return)
- **Task**: Rank top 20% stocks based on forward 126-session excess return over KSE-100.
- **Metric**: Normalized Discounted Cumulative Gain (NDCG@K) on inner validation.
- **Candidates**:
  1. `XGBRanker`: pairwise ranking objective, learning rates $0.01 - 0.05$, max depth $2 - 3$, tree regularization $\lambda \in [5, 15]$.
  2. `Simple Value Composite`: inverse P/E plus inverse P/B composite score ($1/\text{PE} + 1/\text{PB}$).
  3. `Cross-Sectional Momentum`: 20-session percentage return.
  4. `Random Baseline`: naive uniform random ranking.

#### Inner Validation Selection Trials
| Fold | Inner Validation Winner | Winning Metric (Inner NDCG) | Runner-Up Candidate | Runner-Up NDCG |
| :--- | :--- | :--- | :--- | :--- |
| **Fold 1** | **Cross-Sectional Momentum** | **0.5697** | Simple Value Composite | 0.4743 (XGBRanker: 0.3803) |
| **Fold 2** | **Simple Value Composite** | **0.5954** | Cross-Sectional Momentum | 0.5586 (XGBRanker: 0.4759) |
| **Fold 3** | **XGBRanker ($d=3, \eta=0.03$)** | **0.8193** | Simple Value Composite | 0.6445 (Momentum: 0.5168) |

#### Outer Test Holdout Evaluation (Unseen Assessment)
| Fold | Model Evaluated | Test NDCG | Top Group Excess Return (%) | Beat XGBRanker? |
| :--- | :--- | :--- | :--- | :--- |
| **Fold 1** (Sessions 5600–5730, $N=2,242$) | XGBRanker | 0.5330 | -1.87% | — |
| | **Simple Value Composite** | **0.6415** | **+13.84%** | **YES (+15.71% excess)** |
| | Cross-Sectional Momentum | 0.5457 | +8.42% | **YES (+10.29% excess)** |
| | Random Baseline | 0.5314 | +2.84% | No |
| **Fold 2** (Sessions 5730–5860, $N=2,195$) | **XGBRanker** | **0.7592** | **+72.58%** | — |
| | Simple Value Composite | 0.6805 | +56.95% | No |
| | Cross-Sectional Momentum | 0.6525 | +22.97% | No |
| | Random Baseline | 0.5336 | +16.10% | No |
| **Fold 3** (Sessions 5860–6000, $N=954$) | XGBRanker | 0.5456 | +4.72% | — |
| | **Simple Value Composite** | **0.5755** | **+9.33%** | **YES (+4.61% excess)** |
| | **Cross-Sectional Momentum** | **0.7461** | **+6.92%** | **YES (+2.20% excess)** |
| | Random Baseline | 0.6286 | +1.88% | No |

*Key Finding*: The Simple Value Composite beat XGBRanker in **2 out of 3 folds** on out-of-sample test data.

---

### 2.2 Technical Timing Branch (10-Session Favourable Net Return)
- **Task**: Predict whether entering at next-session open ($t+1$) and exiting at $t+10$ close yields net return $> +2.0\%$ after $0.50\%$ round-trip friction.
- **Metric**: Average Precision (PR-AUC) on inner validation.
- **Candidates**:
  1. `XGBoost Classifier`: binary logistic objective, max depth $2-3$, learning rates $0.01-0.05$.
  2. `Regularized Logistic Regression`: StandardScaler pipeline, L2 penalty $C \in [0.01, 0.1, 1.0]$.
  3. `SMA Breakout`: normalized price deviation from 20-session simple moving average (`close_vs_sma_20_pct`).
  4. `Majority Class Baseline`: naive prior positive rate.

#### Inner Validation Selection Trials
| Fold | Inner Validation Winner | Winning Metric (Inner AP) | Runner-Up Candidate | Runner-Up AP |
| :--- | :--- | :--- | :--- | :--- |
| **Fold 1** | **SMA Breakout** | **0.4313** | XGBoost ($d=2, \eta=0.01$) | 0.4296 (Logistic: 0.4106) |
| **Fold 2** | **XGBoost ($d=2, \eta=0.05$)** | **0.4149** | XGBoost ($d=3, \eta=0.03$) | 0.4142 (Logistic: 0.4048) |
| **Fold 3** | **XGBoost ($d=3, \eta=0.03$)** | **0.4561** | XGBoost ($d=2, \eta=0.05$) | 0.4529 (Logistic: 0.4284) |

#### Outer Test Holdout Evaluation (Unseen Assessment)
| Fold | Model Evaluated | Test AP | Log Loss | Brier Score | Signals ($\ge 0.55$) | Entry Precision |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Fold 1** ($N=12,173$) | XGBoost | 0.4405 | 0.7381 | 0.2677 | 0 | N/A (0 signals) |
| | Logistic Regression ($C=0.01$) | 0.4278 | 0.7481 | 0.2706 | 64 | 59.38% (+4.58% net) |
| | SMA Breakout | 0.4332 | 0.7815 | 0.2814 | 4,032 | 44.79% (+2.86% net) |
| | Majority Class | 0.4213 | 0.7383 | 0.2685 | 0 | N/A |
| **Fold 2** ($N=11,382$) | XGBoost | 0.4186 | 0.6942 | 0.2496 | 0 | N/A (0 signals) |
| | Logistic Regression ($C=1.0$) | 0.4162 | 0.7003 | 0.2526 | 118 | 34.75% (+2.89% net) |
| | SMA Breakout | 0.4096 | 0.7806 | 0.2846 | 3,365 | 40.21% (+2.36% net) |
| | Majority Class | 0.4155 | 0.6939 | 0.2498 | 0 | N/A |
| **Fold 3** ($N=11,919$) | XGBoost | 0.3161 | 0.6206 | 0.2146 | 0 | N/A (0 signals) |
| | **Logistic Regression ($C=0.01$)** | **0.3502** | 0.6234 | 0.2160 | 249 | 43.37% (-0.34% net) |
| | **SMA Breakout** | **0.3502** | 0.7209 | 0.2577 | 2,111 | 37.47% (+1.62% net) |
| | Majority Class | 0.3079 | 0.6195 | 0.2140 | 0 | N/A |

*Key Findings*:
1. At the nominal threshold of 0.55, XGBoost generated **0 signals across all three outer test folds**, suffering from extreme calibration probability shrinkage in out-of-distribution regimes.
2. In Fold 3, **Logistic Regression and SMA Breakout both outperformed XGBoost in Average Precision** (0.3502 vs 0.3161).

---

## 3. Realistic Portfolio Simulation & Evaluation

We executed full daily portfolio simulations tracking capital, overlapping positions, cash balances, and trade executions under identical real-world trading constraints:
- **Starting Equity**: PKR 10,000,000.
- **Position Cap**: Maximum 10.0% of portfolio equity in any single stock at entry.
- **Execution**: Signal at session $t$ close $\rightarrow$ entry at session $t+1$ open $\rightarrow$ hold 10 trading sessions $\rightarrow$ exit at session $t+10$ close.
- **Trading Friction**: 0.50% round-trip transaction costs (0.25% open + 0.25% close) deducted from cash on every trade.
- **Overlapping Holdings**: Capital is locked for the duration of the 10-session trade. Expired positions return cash and realized gains/losses at $t+10$ close.

### 3.1 Policy Definitions
- **Policy A (Unfiltered Fundamental Shortlist)**: Buys all stocks appearing in the top 20% fundamental shortlist each day (subject to cash availability and 10% position limit).
- **Policy B (Technically Filtered Shortlist)**: Buys shortlisted stocks only when confirmed by an active technical entry signal ($P \ge 0.50$ calibrated).

### 3.2 Performance Summary Table
| Metric | Fold 1 Unfiltered | Fold 1 Filtered | Fold 2 Unfiltered | Fold 2 Filtered | Fold 3 Unfiltered | Fold 3 Filtered |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Market Regime** | Modest Bull | Modest Bull | Strong Bull | Strong Bull | Bear Market | Bear Market |
| **Initial Capital (PKR)** | 10,000,000 | 10,000,000 | 10,000,000 | 10,000,000 | 10,000,000 | 10,000,000 |
| **Final Equity (PKR)** | **12,674,489** | 12,517,546 | **14,599,909** | 10,000,000 | 9,509,356 | **10,000,000** |
| **Total Return (%)** | **+26.74%** | +25.18% | **+46.00%** | **0.00%** | -4.91% | **0.00%** |
| **CAGR (%)** | **58.32%** | 54.54% | **108.25%** | **0.00%** | -8.66% | **0.00%** |
| **Annualized Volatility** | 27.50% | 26.87% | 25.49% | 0.00% | 24.30% | 0.00% |
| **Sharpe Ratio** | **1.81** | 1.76 | **3.01** | 0.00 | -0.25 | 0.00 |
| **Maximum Drawdown (%)** | 10.07% | 10.39% | 12.61% | 0.00% | 20.71% | 0.00% |
| **Average Exposure (%)** | 98.17% | 98.19% | 95.27% | 0.00% | 92.69% | 0.00% |
| **Annualized Turnover** | 22.99x | 23.01x | 22.49x | 0.00x | 22.24x | 0.00x |
| **Total Trades Executed** | 120 | 120 | 118 | **0** | 123 | **0** |
| **Trade Win Rate (%)** | **50.83%** | 49.17% | **54.24%** | 0.00% | 34.96% | 0.00% |
| **Mean Trade Net Return** | **+2.48%** | +2.37% | **+3.37%** | 0.00% | -0.39% | 0.00% |

---

## 4. Paired Statistical Evaluation & Concentration

### 4.1 Paired Date-Block Evaluation via Newey-West HAC
To account for temporal autocorrelation and overlapping 10-session holding periods, daily paired return differences ($d_t = R_{\text{filtered}, t} - R_{\text{unfiltered}, t}$) were evaluated using the Bartlett kernel with 10 lags:

$$\hat{\sigma}_{\text{HAC}}^2 = \hat{\gamma}_0 + 2 \sum_{l=1}^{10} \left(1 - \frac{l}{11}\right) \hat{\gamma}_l, \quad t_{\text{HAC}} = \frac{\bar{d}}{\hat{\sigma}_{\text{HAC}} / \sqrt{T}}$$

| Fold | Mean Daily Return Difference ($\bar{d}$) | Newey-West HAC $t$-statistic | $p$-value (Two-Tailed) | Statistically Significant at $\alpha = 0.05$? | Conclusion |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Fold 1** | -0.0103% | -0.8373 | 0.4024 | No | No discernible benefit; slight performance drag. |
| **Fold 2** | **-0.3043%** | **-2.2311** | **0.0257** | **YES (Significant Underperformance)** | **The filter severely damaged performance by missing a 46% bull market.** |
| **Fold 3** | +0.0241% | +0.2082 | 0.8351 | No | Avoided -4.91% loss via inactivity, but not statistically significant. |

### 4.2 Portfolio Concentration & Sector Allocation
Across all folds, the portfolio's effective diversification was verified:
- **Herfindahl-Hirschman Index (HHI)**:
  - Fold 1: 1,011.6 (Unfiltered) vs 1,011.6 (Filtered) — reflecting an effectively diversified ~10-stock portfolio ($10 \times 10^2 = 1,000$).
  - Fold 2: 1,043.1 (Unfiltered).
  - Fold 3: 1,094.8 (Unfiltered).
- **Top-5 Ticker Concentration**:
  - Fold 1: 52.17% of total portfolio equity.
  - Fold 2: 53.53% of total portfolio equity.
  - Fold 3: 55.79% of total portfolio equity.
- **Top Sector Exposures (Fold 1 Active Holdings)**:
  1. Pharmaceuticals: 21.63%
  2. Commercial Banks: 15.89%
  3. Cement: 10.93%
  4. Fertilizer: 9.88%
  5. Automobile Assembler: 8.24%
  6. Refinery: 7.08%
  7. Food & Personal Care: 5.26%
  8. Technology & Communication: 3.12%

---

## 5. Definitive Empirical Answer

> **Question**: *Does technical timing improve the fundamental shortlist after accounting for risk, exposure, and costs?*

### **Answer: NO.**
The empirical evidence across all three walk-forward test folds decisively demonstrates that **adding technical entry timing does NOT improve the fundamental shortlist**.

### Primary Failure Modes:
1. **Severe Model Calibration Collapse Across Regimes**:
   - In Fold 1, the technical filter selected SMA Breakout, which accepted every shortlisted stock, effectively mirroring the unfiltered policy but incurring slightly worse trade execution (+25.18% vs +26.74%).
   - In Folds 2 and 3, XGBoost predicted probabilities that fell entirely below the decision threshold on test sets.
2. **Opportunity Cost Far Exceeds Downside Protection**:
   - In Fold 2, model inactivity caused the portfolio to sit in 100% cash throughout a historic bull market (+46.00% return, Sharpe 3.01), producing a statistically significant loss of alpha ($p = 0.026$).
   - The modest downside avoided in Fold 3 (+0.00% vs -4.91%) was statistically indistinguishable from zero ($p = 0.835$) and failed to compensate for the massive opportunity loss in Fold 2.
3. **Simpler Baselines Dominate Complex Machine Learning**:
   - The fundamental shortlist is significantly better driven by a simple, transparent **Value Composite** ($1/\text{PE} + 1/\text{PB}$), which outperformed XGBRanker out-of-sample in 2 of the 3 test folds.
   - Machine learning timing introduces parameter instability, calibration drift, and binary execution risks without delivering risk-adjusted excess returns.

---

## 6. Artifact Ledger and Test Suite Status

### 6.1 Artifact Directory: `artifacts/selection_timing_v2/`
- `evaluation.json`: Complete 3-fold evaluation results, including baseline scores and paired test statistics.
- `portfolio_simulation.json`: Full portfolio performance metrics for Policy A and Policy B across all folds.
- `portfolio_daily_equity.csv`: Daily time-series of cash, holdings, equity, and exposure for both policies across all 400 test sessions.
- `baseline_comparison.json`: Detailed disclosures comparing XGBoost/XGBRanker against Value Composite, Momentum, Logistic Regression, and SMA Breakout.
- `model_selection_trials.csv` & `.json`: Exhaustive inner-validation trial logs for all candidate models.

### 6.2 Test Suite Verification
The complete test suite passed with **30 out of 30 tests green (100% pass rate in 14.04s)**:
- `tests/test_v2.py`: 7/7 passed.
- `tests/test_v3.py`: 4/4 passed.
- `tests/test_decision_pipeline.py`: 4/4 passed.
- `tests/test_selection_timing.py`: 8/8 passed.
- `tests/test_selection_timing_v2.py`: 7/7 passed (verifying point-in-time universe preservation, raw unadjusted price semantics, inner validation selection, portfolio accounting, Newey-West HAC statistics, concentration metrics, and baseline disclosures).
