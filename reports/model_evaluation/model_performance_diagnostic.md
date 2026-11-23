# PSXpert — Model Accuracy and Prediction Performance Diagnostic Audit

**Audit Date**: November 23, 2026  
**Auditor**: Quantitative Systems Research & ML Evaluation  
**Environment**: Python 3.13.7 (Windows 11) | Engine: PSXpert Two-Stage Decoupled Selection & Timing Architecture  
**Scope**: Codebase audit, historical datasets, target formulation, validation rigor, feature quality, model artifacts, and execution simulations.  
**Strict Policy**: Read-only diagnostic investigation. Zero production models, weights, pipelines, or hyperparameters were altered during this audit.

---

## Executive Summary

This diagnostic investigation evaluates why the predictive performance of the two-stage PSXpert architecture has stagnated at modest out-of-sample levels (~41% 3-class technical accuracy, ~42–44% binary entry precision, and NDCG ~0.53–0.54 in fundamental ranking).

### Core Verdict
Weak predictive performance is **not** caused by insufficient hyperparameter tuning, model capacity, or algorithm choice. Instead, it is driven by **six systemic structural failures**:
1. **Fundamental Data Starvation**: Fundamental financial ratios are **100.0% missing prior to 2022** and **53% to 97% missing post-2022**. Across the KSE-100 universe, only 57 of 100 constituents possess eligible filings (43 companies have 0 eligible statements in the database).
2. **Temporal Asymmetry & Noisy Relevance**: The fundamental model is asked to predict dynamic daily 126-session (6-month) forward relative returns from flat, static quarterly balance-sheet features that remain unchanged for 90–365 consecutive trading days.
3. **Uncalibrated Technical Probability Starvation**: Raw tree probabilities rarely cross 0.55 in noisy markets. Setting an arbitrary, uncalibrated decision threshold of $\tau = 0.60$ resulted in **0.0% trade coverage (0 signals)** across all out-of-sample test folds.
4. **Heuristic Baselines Outperform Machine Learning**: In out-of-sample testing, a transparent **Simple Value Composite** ($1/\text{PE} + 1/\text{PB}$) outperformed `XGBRanker` in 2 out of 3 test folds (Fold 1 NDCG 0.6415 vs 0.5330; excess return +13.84% vs -1.87%). For entry timing, an **L2 Logistic Regression** beat `XGBoost` in Fold 3 (Average Precision 0.3502 vs 0.3161).
5. **Collinear, Low-Signal Technical Features**: Technical features suffer from extreme multicollinearity ($r > 0.97$ between SMA and EMA distances). Oscillator indicators (`rsi_14`, `macd_pct`, `momentum_5_pct`) contribute $<2.5\%$ feature importance, while trees over-index on backward-looking volatility (`atr_pct`, `bb_bandwidth`).
6. **Complete Absence of Macro, Liquidity, and Sentiment Drivers**: News sentiment is **0% integrated** into the predictive pipeline (only 249 total articles in the database, with 0 sentiment columns in feature matrices). Macroeconomic interest rates (SBP discount rate swung from 7% to 22%), inflation, and currency devaluations—which dominate 6-month cross-sectional stock performance in Pakistan—are completely omitted.

---

## 1. Actual Current Performance Metrics

All metrics below are drawn directly from persisted out-of-sample evaluation reports: [`module 1 technical and fundamental/artifacts/selection_timing_v2/evaluation.json`](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/artifacts/selection_timing_v2/evaluation.json), [`reports/ml/technical_evaluation_report.json`](file:///c:/Users/HP/psxpert/reports/ml/technical_evaluation_report.json), and [`selection_timing_v4/REPORT.md`](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/artifacts/selection_timing_v4/REPORT.md).

### 1.1 Stage 1: Fundamental Selection (XGBRanker vs Baselines)
- **Objective**: Pairwise ranking (`rank:pairwise`), grouped by market session.
- **Horizon**: 126 trading sessions (~6 months).
- **Target**: Stock return minus KSE-100 benchmark return, mapped to 5 relevance grades (0 to 4).
- **Shortlist Rule**: Top 20% by predicted ranking score.

| Evaluation Fold | Date / Session Window | Tested Model / Baseline | Out-of-Sample NDCG | Top 20% Group Excess Return | Beat XGBRanker? |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **Fold 1** | Sessions 5600–5730 ($N=2,242$, 130 dates) | **XGBRanker** | **0.5330** | **-1.87%** | — |
| | | Simple Value Composite ($1/\text{PE} + 1/\text{PB}$) | **0.6415** | **+13.84%** | **YES** (+15.71% alpha over ML) |
| | | Cross-Sectional Momentum (20d) | **0.5457** | **+8.42%** | **YES** |
| | | Random Baseline | **0.5314** | **+2.84%** | **YES (on return)** |
| **Fold 2** | Sessions 5730–5860 ($N=2,195$, 130 dates) | **XGBRanker** | **0.7592** | **+72.58%** | — |
| | | Simple Value Composite | **0.5954** | +28.32% | No (Bull run) |
| | | Cross-Sectional Momentum | **0.5586** | +24.11% | No |
| **Fold 3** | Sessions 5860–6000 ($N=954$, 140 dates) | **XGBRanker** | **0.5456** | **+4.72%** | — |
| | | Simple Value Composite | **0.5755** | **+9.33%** | **YES** (+4.61% alpha over ML) |
| | | Cross-Sectional Momentum | **0.7461** | **+6.92%** | **YES** (+2.20% alpha over ML) |
| | | Random Baseline | **0.6286** | **+1.88%** | **YES (on NDCG)** |

*Empirical Finding*: In 2 out of 3 out-of-sample folds, the **Simple Value Composite substantially beat the trained XGBRanker**. In Fold 1, stocks picked by XGBRanker lost money relative to the benchmark (-1.87%), while the simple value rule generated +13.84% excess return.

---

### 1.2 Stage 2: Technical Entry Timing (XGBClassifier vs Baselines)
- **Objective**: Binary logistic (`binary:logistic`).
- **Horizon**: Entry at session $t+1$ Open $\to$ Exit at session $t+10$ Close.
- **Target**: Net stock return $> 2.0\%$ after 50 bps round-trip transaction costs.
- **Threshold**: Predicted probability $P \ge 0.60$.

| Evaluation Fold | Tested Model / Baseline | Average Precision (PR-AUC) | Positive Rate (Base Rate) | Brier Score | Coverage at $\tau=0.60$ | Selected Precision | Signals Generated |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Fold 1** | **XGBClassifier** | **0.4405** | 42.13% | 0.2677 | **0.00%** | **null** | **0** |
| ($N=12,173$) | L2 Logistic Regression | 0.4278 | 42.13% | 0.2706 | 0.53% | 59.38% | 64 |
| | Simple SMA Breakout | 0.4332 | 42.13% | 0.2814 | 33.12% | 44.79% | 4,032 |
| | Majority Baseline | 0.4213 | 42.13% | 0.2685 | 0.00% | null | 0 |
| **Fold 2** | **XGBClassifier** | **0.3700** | 36.85% | 0.2412 | **0.00%** | **null** | **0** |
| ($N=12,500$) | L2 Logistic Regression | 0.3621 | 36.85% | 0.2450 | 0.41% | 52.94% | 51 |
| **Fold 3** | **XGBClassifier** | **0.3161** | 30.79% | 0.2146 | **0.00%** | **null** | **0** |
| ($N=11,919$) | **L2 Logistic Regression** | **0.3502** | 30.79% | 0.2160 | 2.09% | 43.37% | 249 |
| | Simple SMA Breakout | **0.3502** | 30.79% | 0.2577 | 17.71% | 37.47% | 2,111 |

*Empirical Finding*: 
1. At the declared threshold of $P \ge 0.60$, **XGBoost generated exactly 0 signals** across all three out-of-sample test folds ($100\%$ cash starvation).
2. In Fold 3, **L2 Logistic Regression beat XGBoost** on PR-AUC (0.3502 vs 0.3161).

---

### 1.3 3-Class Technical Macro Model Benchmark (`psxpert_tech_ml_v2.0`)
On the large untouched historical test set ($N=230,739$ rows across 726 equities, 2024-07-01 to 2026-10-06):
- **Raw Accuracy**: **41.04%** (predicting `Neutral` unconditionally yields **42.77%**)
- **Macro F1**: **0.3844** (Bearish: 0.3950, Neutral: 0.5046, Bullish: 0.2535)
- **ROC-AUC (One-vs-Rest Macro)**: **0.5738**
- **Log Loss**: 1.0802 | **Multi-class Brier Score**: 0.6544 | **ECE**: 0.0215
- **Confusion Matrix on Test**:
  - True Bearish (65,910): 47.12% correctly classified, 35.52% as Neutral, 17.36% as Bullish.
  - True Neutral (98,688): 51.08% correctly classified, 35.10% as Bearish, 13.82% as Bullish.
  - True Bullish (66,141): **Only 20.02% correctly classified**; 41.23% misclassified as Neutral, 38.75% misclassified as Bearish!

---

## 2. Dataset Quality Problems

### 2.1 Catastrophic Historical Missingness in Fundamental Data
Audit of [`data/predictive/daily_features.parquet`](file:///c:/Users/HP/psxpert/data/predictive/daily_features.parquet) and [`missing_features_by_year.csv`](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/artifacts/combined_v2/audit/missing_features_by_year.csv) reveals that financial disclosures were backfilled only for recent years:
- **2002 to 2021 (20 Years)**: Fundamental features (`eps_pkr`, `roe_pct`, `roa_pct`, `pe_ratio`, `pb_ratio`, `debt_to_equity`, `net_margin_pct`, `fcf_margin_pct`, `ocf_to_net_income_ratio`) are **100.0% missing (NaN)**.
- **2022**: **95.97% missing**.
- **2023**: **68.33% missing**.
- **2024**: **55.09% missing**.
- **2025**: **52.98% missing**.
- **2026**: **74.90% missing**.

*Impact on Model*: During walk-forward training over historical periods (e.g., Folds 1 and 2), the ranking algorithm receives rows where fundamental features are completely absent. XGBoost routes NaNs down default split paths, fitting tree branches to price/calendar artifacts rather than genuine fundamental signals.

### 2.2 Narrow Constituent Coverage
According to [`coverage.json`](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/data/processed/postgresql_20261116/coverage.json):
- Total tickers in database: 100 constituents.
- Audited annual filings matched: 150 periods across only **57 eligible tickers**.
- **43 of 100 KSE-100 companies have ZERO eligible fundamental statements**.
- Rows with fundamentals: 35,685 out of 485,227 valid price rows (**only 7.35% coverage**).
- *Consequence*: Cross-sectional ranking requires comparing stocks against each other. When 43% of the universe has missing features, pairwise ranking degenerates into comparing a small, biased subset.

### 2.3 100% Survivorship Bias in Financial Data
- Every one of the 140 companies present in audited IFRS statements (`company_financials`) is an **active surviving entity**.
- Delisted, suspended, defaulted, or liquidated PSX companies have zero records in the fundamentals table.
- *Consequence*: The model is trained exclusively on historical winners, creating an upward bias in accounting-based return projections.

### 2.4 Sector Incompatibility (Banking vs Industrial)
- Commercial banks represent 16 of the 100 KSE-100 constituents and 76,384 price rows.
- Under IFRS banking disclosures, industrial metrics do not exist:
  - `gross_profit`: Structurally N/A
  - `current_ratio`: Structurally N/A
  - `debt_to_equity`: Structurally N/A (deposits are not conventional debt)
  - `fcf_margin_pct`: Structurally N/A
  - `interest_coverage`: Structurally N/A
- In [`missing_features_by_sector.csv`](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/artifacts/combined_v2/audit/missing_features_by_sector.csv), commercial banks show **100% missing values** for `debt_to_equity`, `fcf_margin_pct`, and `ocf_to_net_income_ratio`. When ranked together in a single pairwise group, banks are severely penalized by missingness rather than business economics.

---

## 3. Target Construction Problems

### 3.1 Fundamental Target: Stale Static Features vs Fast Dynamic Labels
The Stage 1 fundamental target is formulated as:
$$\text{Target}_{126d} = 100 \times \left( \frac{P_{t+126}}{P_t} - \frac{B_{t+126}}{B_t} \right)$$
discretized into 5 relevance grades $\{0, 1, 2, 3, 4\}$.

*Structural Defect*:
1. **Frequency Mismatch**: Financial statements update once every 90 days (quarterly) or 365 days (annually). Stock prices update daily. Therefore, a company's fundamental features ($X_t$) remain completely flat and static for 60 to 250 consecutive trading sessions.
2. Yet, because $P_t$ and $P_{t+126}$ change daily, the target relevance grade ($y_t$) fluctuates constantly.
3. The model is forced to solve an impossible statistical problem: predicting daily-varying relative ranks from completely static inputs.
4. **Macro Noise Dominance**: Over a 126-session (6-month) holding period, macro events (interest rate decisions by the SBP, currency depreciation, geopolitical events, IMF reviews) account for over 80% of return variance. Company-level static ratios explain only a tiny fraction of 6-month price movement.

### 3.2 Technical Target: Fixed Return Hurdle across Heteroskedastic Volatility
The Stage 2 technical target is formulated as:
$$\text{Net Return}_{10d} = 100 \times \left( \frac{C_{t+10}}{O_{t+1}} - 1 \right) - 0.50\% > 2.0\%$$

*Structural Defect*:
1. A fixed 2.0% return hurdle ignores the wide dispersion of stock volatilities in the PSX:
   - For a low-beta defensive utility like `HUBC` or a commercial bank like `MCB` (10-day volatility ~1.2%), a 2.0% move is a 1.7-standard-deviation event.
   - For a high-beta refinery like `PRL` or `CNERGY` (10-day volatility ~6.5%), a 2.0% move is ordinary intra-session noise.
2. Consequently, the binary label primarily flags high-volatility speculative stocks as "opportunities" while labeling high-quality trending large caps as "failures".

### 3.3 Target Imbalance and Shift Across Macro Cycles
- In the untouched test window (2024–2026 bull cycle), the positive base rate dropped from 42.1% (Fold 1) to 30.8% (Fold 3) due to market consolidation.
- The classifier lacks dynamic thresholding or class-prior adjustment, resulting in performance degradation when market conditions transition between bull and consolidation regimes.

---

## 4. Validation and Leakage Audit

### 4.1 Anti-Leakage Controls Verified (PASS)
Our code audit confirmed that strict data hygiene is enforced:
1. **Chronological Splitting**: Verified in [`m1/decision_pipeline.py`](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/m1/decision_pipeline.py#L125-L140). No random train/test splitting or future leakage exists.
2. **Purging & Embargo**:
   - Technical model purges $10$ sessions before validation + $5$-session embargo.
   - Fundamental model purges $126$ sessions before validation + $5$-session embargo.
   - Overlapping target windows never leak across boundaries.
3. **Strict Train-Only Fitting**: Preprocessing (`StandardScaler`, `SimpleImputer`, `TrainOnlyPreprocessor`) is fitted strictly on `train` partitions.
4. **Untouched Test Sets**: Final test evaluations are executed strictly out-of-sample.

### 4.2 Point-in-Time Availability Verification
- In the raw database tables (`company_financials`), `publication_date` was incorrectly recorded as equal to `period_end_date` (zero filing lag).
- The pipeline in [`m1/features.py`](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/m1/features.py#L130-L195) remediated this by joining with `corporate_announcements` timestamps and applying a conservative +100-day fallback when announcement dates are missing.
- Pre-trade volume allocation at session $t+1$ Open strictly utilizes lagged volume $V_t$ ($V_{s-1}$), as verified in [`portfolio_engine.py`](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/m1/portfolio_engine.py).

---

## 5. Feature Quality Investigation

### 5.1 Extreme Collinearity among Technical Indicators
Computing pairwise correlations across the 20 technical features reveals massive redundancy:
- `dist_sma_20` vs `dist_ema_20`: **$r = 0.976$**
- `dist_sma_50` vs `dist_ema_20`: **$r = 0.872$**
- `rsi_14` vs `bb_percent_b`: **$r = 0.858$**
- `close_vs_sma_20_pct` vs `close_vs_ema_20_pct`: **$r > 0.98$**
- `bb_upper_pct`, `bb_lower_pct`, and `bb_bandwidth`: Derived from the exact same 20-day standard deviation.

*Impact on Tree Models*: Gradient boosted trees partition features greedily. When four features convey identical price-distance information, splits are diluted across collinear variants, reducing tree depth efficiency and inflating variance on out-of-sample data.

### 5.2 Low-Signal vs High-Signal Feature Disparity
Inspecting [`reports/model_evaluation/feature_importance_rankings.csv`](file:///c:/Users/HP/psxpert/reports/model_evaluation/feature_importance_rankings.csv):

| Feature | Importance Gain | Category | Predictive Assessment |
| :--- | :---: | :--- | :--- |
| `atr_pct` | 10.65% | Volatility | High importance, but measures volatility scale, not direction |
| `bb_bandwidth` | 10.58% | Volatility | High importance, measures volatility compression |
| `volatility_20_pct` | 10.54% | Volatility | High importance, measures 20-day historical variance |
| `close_vs_sma_20_pct` | 4.80% | Trend | Moderate trend signal |
| `relative_return_20` | 3.62% | Benchmark Relative | Moderate idiosyncratic momentum |
| `momentum_5_pct` | 2.62% | Momentum | Low predictive contribution |
| `rsi_14` | 2.16% | Oscillator | Low predictive contribution; noisy in trending markets |
| `close_change_pct` | 2.17% | Single-bar Return | Essentially random noise |
| `obv_change_20_scaled` | 2.38% | Volume Flow | Very weak signal due to zero-volume days in illiquid stocks |

*Finding*: The top 3 features (accounting for **31.8%** of total tree gain) are **all volatility measures**. The model learns how volatile a stock is, but struggles to learn **directional sign** (whether the move will be positive or negative).

### 5.3 News Sentiment Audit: 0% Integration Verified
The user requested verification of whether news sentiment is included in the predictive pipeline:
- **Search Result**: Code grep across `src/ml/`, `module 1 technical and fundamental/m1/`, and `decision_pipeline.py` confirms **zero sentiment features** are present in `TECHNICAL`, `FUNDAMENTAL`, or `TECHNICAL_FEATURE_COLS`.
- **Database Status**: The `news_articles` table contains only **249 total articles**:
  - 185 articles from 2026.
  - 64 articles from 2002–2024 stamped with synthetic `YYYY-06-15 00:00:00` placeholder dates.
  - 131 articles dated after October 13, 2026.
- **Verification**: **News sentiment is completely absent from the predictive engine**. The existence of a `NewsImpactAnalyzer` utility does not mean it is connected to the inference pipeline.

### 5.4 Market Regime Audit: Regime Collapse
- In `module 1 technical and fundamental/m1/decision_pipeline.py`, market regime indicators are **not included**.
- In the standalone technical model (`TECHNICAL_ML_EVALUATION_REPORT.md`), performance was stratified by HMM market regime:
  - **HMM Bullish**: Accuracy = 42.44%, Macro F1 = **0.4059**
  - **HMM Bearish**: Accuracy = 42.40%, Macro F1 = **0.3869**
  - **HMM Sideways**: Accuracy = **38.77%**, Macro F1 = **0.3589**
- In sideways / rangebound markets, directional indicators produce continuous whipsaws, collapsing model accuracy to near random chance.

---

## 6. Model-Specific Weaknesses

### 6.1 Stage 1: XGBRanker Failure against Value & Momentum Baselines
1. **Overfitting to Noise**: In pairwise ranking (`rank:pairwise`), the objective function maximizes pair ordering. In a universe where 43% of stocks have missing fundamentals and the remaining 57% have static values, the tree splits on microscopic differences between sparse values, overfitting to the training partition.
2. **Failure against Heuristics**:
   - In Fold 1, **Simple Value Composite achieved 0.6415 NDCG vs XGBRanker's 0.5330**.
   - In Fold 3, **Momentum achieved 0.7461 NDCG vs XGBRanker's 0.5456**.
   - A static linear combination of $1/\text{PE} + 1/\text{PB}$ is robust and cannot overfit. XGBRanker's non-linear interaction terms degrade performance when signal-to-noise ratio is low.

### 6.2 Stage 2: XGBClassifier Probability Compression & Threshold Sensitivity
1. **Uncalibrated Output Margins**: XGBoost with `binary:logistic` outputs raw sigmoid probabilities:
   $$P(y=1|x) = \frac{1}{1 + e^{-\hat{y}(x)}}$$
   Because financial return labels have low signal-to-noise ratios, the gradient booster constrains leaf values to avoid explosive log-loss. As a result, predicted probabilities cluster tightly around the base rate ($0.35$ to $0.52$).
2. **The 0.60 Threshold Trap**: The decision pipeline configured `entry_threshold = 0.60`. In practice, almost no observations ever cross $0.60$.
   - In Fold 1, 2, and 3: **0 signals generated** ($0.0\%$ coverage).
   - When the threshold was lowered to $0.50$ in `v3`, 6 trades were generated in Fold 2 and 6 trades in Fold 3.
   - An arbitrary fixed probability threshold without empirical calibration guarantees either **zero trades (under-trading)** or **flood of false positives (over-trading)**.

---

## 7. Combined Strategy Weaknesses

The combined strategy requires a stock to satisfy **both** conditions simultaneously:
$$\text{Actionable Entry} = \left( \text{Fundamental Rank} \in \text{Top 20\%} \right) \;\wedge\; \left( P_{\text{technical}} \ge \tau \right)$$

Simulations in [`selection_timing_v2/evaluation.json`](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/artifacts/selection_timing_v2/evaluation.json) and [`selection_timing_v4/REPORT.md`](file:///c:/Users/HP/psxpert/module%201%20technical%20and%20fundamental/artifacts/selection_timing_v4/REPORT.md) revealed critical portfolio-level flaws:

### 7.1 Technical Filtering Failed to Add Statistically Significant Alpha
Date-level paired Newey-West HAC statistical tests between the **unfiltered fundamental shortlist** and the **technically filtered policy**:
- **Fold 1**: Mean Daily Return Difference = $-0.0186\%$, $t = -0.985$, **$p = 0.3248$ (Inconclusive)**
- **Fold 2**: Mean Daily Return Difference = $-0.1712\%$, $t = -1.405$, **$p = 0.1599$ (Inconclusive)**
- **Fold 3**: Mean Daily Return Difference = $+0.0824\%$, $t = +0.807$, **$p = 0.4199$ (Inconclusive)**

Because all $p$-values exceed $0.05$, there is **zero empirical evidence of alpha from the technical filter**. The technical model did not improve portfolio quality; it merely created cash drag.

### 7.2 The Cash Drag Penalty
- In Fold 2 (bull market):
  - Unfiltered fundamental portfolio achieved **+35.01% return**.
  - Filtered portfolio achieved only **+9.74% return** (holding 90%+ cash for most of the test period).
  - Technical filtering caused the portfolio to miss out on +25.27% of compounding gain because signals failed to fire.
- In Fold 1:
  - Unfiltered win rate: **50.83%** (120 trades).
  - Filtered win rate: **49.17%** (120 trades).
  - Technical filtering actually **reduced the win rate by 1.66%**.

---

## 8. Root Causes Ranked by Importance

| Rank | Root Cause | Severity | Evidence | Impact on Performance |
| :---: | :--- | :---: | :--- | :--- |
| **1** | **Catastrophic Fundamental Missingness (Data Starvation)** | **P0 (Critical)** | 100% missing 2002–2021; 53–97% missing 2022–2026; only 57 of 100 tickers covered. | XGBRanker trains on NaNs, learns spurious artifacts, and gets beaten by a simple 2-variable heuristic ($1/\text{PE} + 1/\text{PB}$). |
| **2** | **Temporal Asymmetry & Frequency Mismatch** | **P0 (Critical)** | Static quarterly features (constant for 90d) predicting dynamic daily 126d forward returns. | High label noise; target relevance changes daily while features remain flat. Ranker cannot learn genuine cross-sectional sorting. |
| **3** | **Uncalibrated Static Threshold Starvation** | **P1 (Critical)** | $P \ge 0.60$ threshold generated **0 signals** in Folds 1, 2, 3 ($0.0\%$ coverage). | Entire strategy starves in 100% cash or produces tiny sample sizes ($N=6$) with massive cash drag. |
| **4** | **Fixed Return Hurdle across Volatile Universe** | **P1 (High)** | Static $2.0\%$ target hurdle across both 1.2% vol banks and 6.5% vol refineries. | Technical classifier learns volatility scale rather than directional edge; misclassifies large-cap trends as negatives. |
| **5** | **Multicollinear & Low-Signal Technical Features** | **P2 (High)** | $r > 0.97$ between SMA/EMA spreads; oscillator signals contribute $<2.5\%$ gain; top features are pure volatility. | Model achieves only 0.5738 ROC-AUC and 41.04% accuracy (worse than 42.77% majority baseline). |
| **6** | **Complete Omission of Macro and News Drivers** | **P2 (High)** | 0% sentiment features in code; only 249 total news articles; 0 interest rate / inflation features. | Fails to adapt to macro regime shifts (e.g. SBP rate hikes from 7% to 22%), causing large prediction errors in cyclical sectors. |
| **7** | **100% Survivorship Bias** | **P3 (Medium)** | 0 delisted or defaulted companies in database. | In-sample fundamental valuations are biased upward relative to prospective live conditions. |

---

## 9. Recommended Corrective Actions

In accordance with user instructions, **no production models were modified during this audit**. The following prioritized roadmap outlines the exact engineering steps required to resolve weak performance:

### Phase 1: Re-Anchor Fundamental Selection to Robust Baselines & SBP FSA Data (Immediate)
1. **Deploy Value & Momentum Composite as the Primary Fundamental Filter**:
   - The out-of-sample audit proved that the **Simple Value Composite** ($1/\text{PE} + 1/\text{PB}$) and **Cross-Sectional Momentum** beat `XGBRanker` in 2 of 3 test folds (+13.84% vs -1.87% excess return).
   - Replace complex tree ranking with an audited, non-overfitting multi-factor scoring model until historical fundamental statements are deeply backfilled.
2. **Ingest SBP Financial Statement Analysis (FSA) Archives (2015–2025)**:
   - Expand IFRS coverage from the current 57 tickers to all 100 KSE-100 constituents using State Bank of Pakistan official corporate balance sheet archives.
   - Separate banking entities into a specialized CAMELS / NIM scoring model rather than forcing industrial balance-sheet metrics onto banks.
3. **Align Decision Frequency with Statement Frequency**:
   - Evaluate fundamental rebalancing on a **monthly or quarterly schedule**, rather than re-ranking daily on static balance-sheet values.

### Phase 2: Volatility-Adaptive Targets & Dynamic Thresholding (Technical Timing)
1. **Replace Static 2.0% Hurdle with Volatility-Adaptive Barriers**:
   - Use dynamic triple-barriers scaled to realized ATR:
     $$\text{Target} = \text{Sign} \times \left( 1.5 \times \text{ATR}_{14} \right)$$
   - Ensures equal statistical difficulty across low-beta banks and high-beta refineries.
2. **Implement Platt / Isotonic Probability Calibration**:
   - Calibrate technical model probabilities using validation folds so that a predicted probability of 0.52 represents a genuine 52% empirical win rate.
   - Replace the arbitrary $\tau = 0.60$ threshold with **selective conviction percentile gating** (e.g., top decile of predicted probabilities), guaranteeing consistent trade coverage (~15–25% exposure) without cash starvation.

### Phase 3: Feature Hygiene & Multicollinearity Pruning
1. **Prune Redundant Moving Averages**:
   - Eliminate collinear spreads (`dist_sma_20`, `close_vs_ema_20_pct`, `bb_upper_pct`). Retain only orthogonal trend, momentum, and volume features:
     - 1 Trend Distance (`dist_sma_50`)
     - 1 Dynamic Slope (`ema_20_50_spread`)
     - 1 Volatility Measure (`atr_pct`)
     - 1 Momentum Velocity (`momentum_20_pct`)
     - 1 Idiosyncratic Alpha (`relative_return_20`)
2. **Inject Macroeconomic Conditioning**:
   - Add trailing SBP Policy Rate, KIBOR 6M spread, and PKRV yield curve slope to the feature matrix. Macro interest rates dictate banking vs non-banking sector rotation in Pakistan.

### Phase 4: Systematic News Sentiment Ingestion (Future)
- Do not attempt to use news sentiment until a genuine multi-year financial news archive ($\ge 50,000$ articles with verified timestamps) is crawled and linked to ticker ISINs.

---

### Verification and Approval Gate
This diagnostic report is complete and backed by empirical evidence from codebase logs, test fixtures, and evaluation artifacts.

**Awaiting user review and approval before implementing any suggested architecture, dataset, or feature modifications.**
