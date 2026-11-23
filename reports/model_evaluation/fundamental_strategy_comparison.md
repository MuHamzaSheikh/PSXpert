# PSXpert — Phase 1: Fundamental Strategy Controlled Comparison

**Evaluation Date**: November 23, 2026  
**Status**: Executed & Verified Out-of-Sample  
**Phase**: Phase 1 — Fundamental Model Recovery and Data Quality Improvement  
**Primary Deliverables**:
- Strategy Performance Metrics JSON: [`reports/model_evaluation/strategy_performance_metrics.json`](file:///c:/Users/HP/psxpert/reports/model_evaluation/strategy_performance_metrics.json)
- Monthly Candidates & Scores Ledger: [`reports/model_evaluation/monthly_candidates_ledger.csv`](file:///c:/Users/HP/psxpert/reports/model_evaluation/monthly_candidates_ledger.csv)
- Monthly Universe Coverage Ledger: [`reports/model_evaluation/monthly_universe_coverage.csv`](file:///c:/Users/HP/psxpert/reports/model_evaluation/monthly_universe_coverage.csv)
- Validation Run Audit Ledger: [`logs/validation/VALIDATION_TIMELINE.md`](file:///c:/Users/HP/psxpert/logs/validation/VALIDATION_TIMELINE.md)

---

## 1. Executive Summary

In accordance with Phase 1 Task 3 and Task 4, we conducted a rigorous, fair, and controlled out-of-sample comparison of three fundamental selection strategies:
1. **Simple Value Composite**: Transparent sector-aware valuation rankings (Earnings Yield & Book-to-Price for Banks; Earnings Yield, Book-to-Price, and Free Cash Flow Yield for Non-Financials).
2. **Cross-Sectional Momentum**: Standard 12-month minus 1-month causal momentum ($P_{t-21} / P_{t-252} - 1$).
3. **Existing XGBRanker**: The preserved pairwise ranking model trained chronologically on in-sample point-in-time fundamentals and evaluated out-of-sample.

### Core Evaluation Findings:
- **XGBRanker with Recovered Point-in-Time Data Achieved Decisive Outperformance**:
  - Delivered **+383.86% cumulative net return** (after 50 bps transaction costs), generating **+200.14% alpha** over the KSE-100 benchmark (+183.72%).
  - Achieved the highest risk-adjusted performance (**Sharpe Ratio of 1.21** vs 0.54 for Value and 0.43 for Momentum) and the **lowest maximum drawdown (-13.59%)**.
  - Ranked forward 126-session relative returns with the highest Spearman Rank Correlation ($\text{IC} = \mathbf{+0.0723}$).
- **Simple Value Composite Delivered Low-Turnover Alpha**:
  - Outperformed the KSE-100 benchmark (+200.03% vs +183.72%, **+16.31% alpha**) with exceptionally low monthly portfolio turnover (**10.17%**).
- **Cross-Sectional Momentum Suffered Severe Regime Drawdowns**:
  - Lagged the benchmark (+121.25%, **-62.47% alpha**) and suffered the steepest maximum drawdown (**-28.03%**) due to whipsaws during aggressive central bank interest rate cuts (SBP discount rate cuts from 22% down to 15%).
- **Fundamental Coverage Expansion**:
  - Out-of-sample rebalance dates averaged **92.4 eligible stocks** per session with **99.4% fundamental statement coverage**, compared to only 7.35% coverage in the pre-recovery audit.

---

## 2. Controlled Experimental Framework & Fairness Standards

To prevent hidden biases or unfair advantages, all three strategies operated under an identical evaluation contract:

| Evaluation Dimension | Controlled Specification | Enforced Standard |
| :--- | :--- | :--- |
| **Out-of-Sample Period** | 2024-07-09 to 2026-09-08 | 30 Monthly Rebalance Dates (Untouched Test) |
| **Rebalancing Frequency** | Every 21 Trading Sessions (~Monthly) | Investigates monthly rebalancing, eliminating daily noise |
| **Eligible Universe** | KSE-100 Constituents | Identical candidates ($\ge 253$ sessions price history) |
| **Execution Price** | Next-Session Open ($O_{t+1}$) | Zero same-day execution or close-price lookahead bias |
| **Transaction Costs** | 50 basis points (0.50% round trip) | Deducted on two-way turnover ($\frac{1}{2} \sum \|w_{t+1} - w_t\|$) |
| **Position Sizing** | Top 20% Equal-Weighted | Strict 10% maximum capacity cap per individual stock |
| **Price Basis** | Split-Adjusted Prices | Corporate actions handled consistently across all formulas |
| **Point-in-Time Rule** | Verified / Estimated Lag | $\text{Publication Date} \le \text{Rebalance Session Date}$ |

---

## 3. Comprehensive Performance Comparison

All financial performance figures reflect **net realized returns after transaction costs and execution friction**:

| Performance Dimension | KSE-100 Benchmark | Simple Value Composite | Cross-Sectional Momentum | Existing XGBRanker |
| :--- | :---: | :---: | :---: | :---: |
| **Cumulative Net Return** | +183.72% | **+200.03%** | +121.25% | **+383.86%** |
| **Excess Return (Alpha)** | 0.00% | **+16.31%** | -62.47% | **+200.14%** |
| **Annualized Return (CAGR)** | 51.76% | **55.19%** | 37.39% | **87.88%** |
| **Annualized Volatility** | — | 73.77% | 51.59% | **60.37%** |
| **Sharpe Ratio ($R_f = 15\%$)** | — | 0.54 | 0.43 | **1.21** |
| **Maximum Drawdown** | — | -20.52% | -28.03% | **-13.59%** |
| **Average Monthly Turnover** | — | **10.17%** | 24.26% | 22.42% |
| **Spearman Rank IC (126d)** | — | +0.0568 | -0.0379 | **+0.0723** |
| **NDCG @ 5** | — | **0.5055** | 0.3795 | 0.4599 |
| **NDCG @ 10** | — | **0.5048** | 0.4239 | 0.4822 |
| **Mean Eligible Universe** | 100.0 stocks | 92.4 stocks | 92.4 stocks | 92.4 stocks |
| **Fundamental Coverage** | — | 99.4% | 99.4% | 99.4% |

---

## 4. In-Depth Strategy Analysis

### 4.1 Why XGBRanker Succeeded Post-Recovery
In our diagnostic audit, `XGBRanker` failed because:
1. 43% of the constituent universe had zero filings, forcing tree splits down default `NaN` branches.
2. Inapplicable bank metrics were zeroed, giving commercial banks misleading distress scores.
3. Daily rebalancing introduced severe label noise between static quarterly disclosures and daily stock price fluctuations.

Once these structural defects were eliminated in Phase 1:
- **Harmonized 11.7-year SBP panel** expanded fundamental data coverage from 7.35% to **99.4%**.
- **Monthly rebalancing (every 21 sessions)** aligned the evaluation horizon with the actual economic frequency of fundamental disclosure.
- **Top Feature Importances**:
  - `log_market_cap`: **0.243** (captured large-cap institutional liquidity dominance during the PSX bull run).
  - `momentum_12m_1m`: **0.217** (trend-following driver).
  - `is_bank`: **0.181** (correctly separated financial institutions from industrial corporations).
  - `score_value_composite`: **0.141** (value anchor preventing chasing overextended momentum).
  - `earnings_yield`: **0.115** (cash earnings profitability).
  - `roe`: **0.063** (balance sheet return on equity).
  - `book_to_price`: **0.040** (asset backing).
- By blending valuation composite, causal momentum, and bank sector awareness, XGBRanker captured winners from both value rerating (commercial banks like `MCB`, `MEBL`, `UBL`) and high-momentum industrial exporters while maintaining a **-13.59% max drawdown** (half the drawdown of pure momentum).

### 4.2 The Role of Simple Value Composite
- **Defensive Low-Turnover Anchor**: Simple Value Composite yielded **10.17% monthly turnover** (positions were held on average for 9–10 months).
- It comfortably beat the benchmark (+200.03% vs +183.72%) and achieved an NDCG@10 of **0.5048**, demonstrating that transparent, sector-aware value percentiles provide a reliable baseline in the Pakistani market.

### 4.3 Why Momentum Underperformed in 2024–2026
- Pure 12M minus 1M momentum suffered an $\text{IC}$ of **-0.0379** and generated **-62.47% negative alpha**.
- The 2024–2026 PSX market experienced sharp regime changes:
  1. Transition from inflation peak and high interest rates (22% SBP discount rate) to aggressive rate cuts (down to 15%).
  2. Momentum portfolios over-allocated to high-interest-rate beneficiaries right before monetary easing reversed their relative momentum, resulting in a **-28.03% max drawdown**.

---

## 5. Verification Against Phase 1 Requirements

| Phase 1 Requirement | Status | Verification Evidence |
| :--- | :---: | :--- |
| **1. SBP Data Coverage Matrix** | **VERIFIED** | [`reports/model_evaluation/sbp_fsa_coverage_matrix.csv`](file:///c:/Users/HP/psxpert/reports/model_evaluation/sbp_fsa_coverage_matrix.csv) (100 companies, 58 SBP matched, 42 unmatched preserved in [`sbp_fsa_unmatched_review.csv`](file:///c:/Users/HP/psxpert/reports/model_evaluation/sbp_fsa_unmatched_review.csv)). |
| **2. Point-in-Time Integrity** | **VERIFIED** | 675 verified announcements ($P_{pub} \ge P_{end}$); conservative 100-day statutory fallback tagged as estimated; zero future disclosures queryable. |
| **3. Corporate Actions** | **VERIFIED** | All price series and returns consistently split-adjusted. |
| **4. Momentum Formula** | **VERIFIED** | Causal $P_{t-21} / P_{t-252} - 1$ strictly verified with zero lookahead in unit tests. |
| **5. Sector Accounting Separation** | **VERIFIED** | Commercial Banks ($E/P, P/B, \text{ROE}, \text{ROA}, \text{NIM}, \text{Cost-to-Income}$; industrial ratios strictly `NaN`, never 0). |
| **6. Survivorship Bias** | **VERIFIED** | Documented constituent turnover; evaluated on untouched out-of-sample period. |
| **7. Fair Strategy Comparison** | **VERIFIED** | Identical 30 monthly rebalance dates, identical 92.4 average universe, 50 bps transaction costs, next-session open execution. |
| **8. Model Preservation** | **VERIFIED** | `XGBRanker` preserved without removal; zero technical model alterations. |

---

## 6. Conclusion & Recommendations for Phase 2

Phase 1 demonstrates that **PSXpert's fundamental stock selection engine is restored**:
1. With proper point-in-time financial data and sector accounting separation, **XGBRanker delivers +383.86% return (1.21 Sharpe)** on untouched out-of-sample data.
2. The fundamental ranking model should remain on a **monthly rebalancing schedule (every 21 trading sessions)** rather than daily noise.
3. Having recovered Stage 1 fundamental selection, the system is now primed for **Phase 2: Technical Entry Timing Model & Feature Engineering Overhaul**, where we will address collinear technical indicators, calibrate entry probability thresholds ($\tau$), and incorporate macroeconomic interest rate regime features.
