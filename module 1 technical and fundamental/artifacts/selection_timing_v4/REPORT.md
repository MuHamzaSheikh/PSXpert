# Controlled Three-Way Verification & Audit Report
## Selection & Timing Architecture v4: Controlled Isolation of Simulator vs. Prediction Effects

**Experiment**: `artifacts/selection_timing_v4`  
**Run Timestamp**: `2026-11-18T17:20:49.518679+00:00` (UTC) / `22:20:49+05:00` (PKT)  
**Environment**: Python 3.13.7 (Windows 11)  
**Status**: Completed Quantitative Controlled Evaluation  
**Scope**: Verification of prediction equivalence, controlled execution isolation (A vs. B), controlled prediction isolation (B vs. C), exact cash-flow accounting reconciliation, and provenance tracking.

---

## Executive Summary

To definitively eliminate ambiguity between simulator modifications and model hyperparameter shifts, this audit executed a **controlled three-way evaluation**:
1. **Run A**: Original predictions (`v2`) evaluated through the Original simulator (`portfolio_simulation.py`).
2. **Run B**: The **exact same** original predictions (`v2`) evaluated through the Corrected institutional simulator (`portfolio_engine.py`).
3. **Run C**: Revised predictions (`v3`, inner-validation winners) evaluated through the Corrected institutional simulator (`portfolio_engine.py`).

### Key Controlled Isolation Insights:
- **A vs. B (Pure Execution Isolation)**:
  - Input predictions are **100% row-by-row identical** (`diff = 0.0`).
  - In Fold 1 (unfiltered), return increases from +26.74% to +67.04% purely due to eliminating alphabetical ticker sorting (ordering candidates by fundamental rank descending) and enforcing morning cash bounds.
  - In Folds 2 and 3 (filtered), both Run A and Run B generate **0 trades and 0.00% return**. This proves that the original predictions generate zero technical signals regardless of simulator execution rules.
- **B vs. C (Pure Model/Prediction Isolation)**:
  - Simulator execution rules and parameters are **100% identical**.
  - In Fold 2 (filtered), return changes from 0.00% (0 trades) to +9.74% (6 trades).
  - In Fold 3 (filtered), return changes from 0.00% (0 trades) to -1.82% (6 trades).
  - This proves that the 6 trades in Folds 2 and 3 were **100% caused by model/prediction changes** (`clf_xgb` fitted with inner-winner learning rates rather than trial 0 `lr=0.01`), and must not be described as a simulator-only comparison.

---

## 1. Quantitative Verification & Completion Table

| Dimension | Specification / Check | Empirical Evidence | Status |
| :--- | :--- | :--- | :---: |
| **Prediction Equivalence** | Fold 1 Equivalence | 12,910 rows compared. Fundamental max diff = 0.0; Technical max diff = 0.0; Shortlist mismatches = 0; Signal mismatches = 0. | **PASS** |
| | Fold 2 Equivalence | 12,978 rows compared. Fundamental max diff = 0.0; Shortlist mismatches = 0; Technical max diff = 0.1729; Signal mismatches = 108. | **FAIL (Diagnosed)** |
| | Fold 3 Equivalence | 13,994 rows compared. Fundamental max diff = 0.4168; Shortlist mismatches = 1,210; Technical max diff = 0.1784; Signal mismatches = 300. | **FAIL (Diagnosed)** |
| **Execution Isolation (A vs. B)** | Simulator impact on identical original predictions | Fold 1 unfiltered return shifts from +26.74% to +67.04% due to fundamental slot ranking and morning cash integrity. Folds 2 & 3 filtered remain at 0 trades in both. | **PASS** |
| **Model Isolation (B vs. C)** | Model impact on identical corrected simulator | Folds 2 & 3 filtered generate 6 trades each in Run C (absent in Run B) strictly due to inner-winner hyperparameter assignment. | **PASS** |
| **Liquidity Configuration** | Mode actually used: Unconstrained benchmark | `max_volume_participation_pct = None`. Pre-trade spend allocated by portfolio bounds. Execution requires contemporaneous volume $V_s > 0$. | **PASS** |
| | Defined missing volume handling | Disabled mode: $V_s \le 0$ or NaN rejects order.<br>Enabled mode: $V_{s-1} \le 0$ or NaN sets max spend to 0.0 (rejects order). | **PASS** |
| **Accounting Reconciliation** | $C_0 + \text{Realized P&L} + \text{Unrealized P&L} = \text{Terminal Equity}$ | Reconciled across all folds in Run B and Run C to the exact cent ($0.00$ discrepancy; max residual $< 10^{-8}$ PKR). Run A failed reconciliation due to lack of ledger and fabricated prices. | **PASS** |
| **Artifact Provenance** | Immutable snapshots & hashes recorded | Input data hashes, code hashes, config hash (`eefd5856`), and snapshot hashes stored in `metadata.json`. Original predictions labeled `reconstructed: true`. | **PASS** |
| **Reporting Discipline** | Inconclusive paired test results | All Newey-West HAC tests show $p > 0.05$ across all folds in Run B and Run C. 6-trade results disclosed as small sample ($N=6$). | **PASS** |

---

## 2. Prediction Snapshots & Provenance Audit

Two immutable, compressed prediction snapshots were generated and saved with full provenance:
1. `predictions_original_reconstructed.csv.gz` (SHA-256: `de43a62a98663d98fa0d82105bc25bfbacdf20c37414e425edb383923d915c6c`, 39,882 rows). Clearly labeled as **deterministically reconstructed** using original `v2` parameters.
2. `predictions_revised.csv.gz` (SHA-256: `1aa13d96861103da6ec31e44cda035ec0629e4900d2daead96d1881ad21a22a4`, 39,882 rows). Generated using `v3` inner-validation winner parameters.

Each row contains:
`version`, `fold`, `session`, `symbol`, `fundamental_model`, `fundamental_score`, `shortlist_membership`, `technical_model`, `technical_score`, `threshold` (0.50), and `entry_signal` (0 or 1).

### Provenance Hashes:
- **Input Data Hashes (SHA-256)**:
  - `data/decision_panel_v2.csv`: `d9120f2b4903c9a176dd7a9f49e6df5a7ed5b8f37f301dcc60a6aa608b308765`
  - `data/raw_unadjusted_prices.csv`: `ebb855d75150a18aab6c9060c3dd8d5fb753d91f80ab2d391134081cca510650`
  - `data/audited_benchmark.csv`: `0b83109f84a2c4ce2667adb953462c665e640d886b399337d313844b952f32a2`
- **Code Hashes (SHA-256)**:
  - `m1/portfolio_simulation.py`: `ba42992ef1602c23efb7d7595640bd4fe3cdce51e11063f90c6c6bffaa847ba2`
  - `m1/portfolio_engine.py`: `427d47c93314e42ce84dc780ef1ddf3cac0cfced7e75d852eabca979cd1e6de0`
  - `m1/decision_pipeline.py`: `20f4191457f876e7904b3f51333845721f0a0a550012926e8cb4f6e28db7eed5`
  - `m1/controlled_evaluation_v4.py`: `d9cad4ac6410ec022f36c182c61dc0e25e6457d0d2b449814d95215cd7a6f112`
- **Configuration Hash (SHA-256)**:
  - `DecisionConfig(seed=42, fund_h=126, tech_h=10, cost=0.50%, margin=2.0%, top=0.20)`: `eefd5856815b9516aa163c1fe75c807120573a94bd01be0935e076acfce9e2d8`

---

## 3. Controlled Comparison Matrix (Runs A, B, and C)

The table below contrasts the three runs across all three folds:

| Fold & Policy | Metric | Run A (Orig Preds + Orig Sim) | Run B (Orig Preds + Corr Sim) | Run C (Rev Preds + Corr Sim) | Isolation: A vs. B (Execution) | Isolation: B vs. C (Model) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Fold 1 Unfiltered** | Total Return (%) | +26.74% | **+67.04%** | **+67.04%** | **+40.30%** (Score Rank & Cash Bounds) | **0.00%** (Identical Preds) |
| | CAGR (%) | 58.32% | **170.34%** | **170.34%** | +112.02% | 0.00% |
| | Sharpe Ratio | 1.81 | **3.93** | **3.93** | +2.12 | 0.00 |
| | Max Drawdown (%) | 10.07% | **9.78%** | **9.78%** | -0.29% | 0.00% |
| | Completed Trades | 120 | **118 (+10 open)** | **118 (+10 open)** | -2 trades (+10 open) | 0 trades |
| **Fold 1 Filtered** | Total Return (%) | +25.18% | **+63.13%** | **+63.13%** | **+37.95%** (Score Rank & Cash Bounds) | **0.00%** (Identical Preds) |
| | Sharpe Ratio | 1.76 | **3.80** | **3.80** | +2.04 | 0.00 |
| | Completed Trades | 120 | **119 (+10 open)** | **119 (+10 open)** | -1 trade (+10 open) | 0 trades |
| | Paired Test ($p$-value) | $p = 0.402$ | **$p = 0.325$** | **$p = 0.325$** | Inconclusive | Inconclusive |
| **Fold 2 Unfiltered** | Total Return (%) | +46.00% | **+35.01%** | **+35.01%** | **-10.99%** (Execution & Cash Bounds) | **0.00%** (Identical Preds) |
| | Sharpe Ratio | 3.01 | **2.38** | **2.38** | -0.63 | 0.00 |
| **Fold 2 Filtered** | Total Return (%) | 0.00% | **0.00%** | **+9.74%** | **0.00%** (0 Trades in Both) | **+9.74%** (Inner Winner `lr=0.05`) |
| | Completed Trades | 0 | **0** | **6 (+1 open)** | **0 trades** | **+6 trades** (Different Prediction) |
| | Trade Win Rate (%) | N/A | **N/A** | **83.33%** | N/A | Small Sample ($N=6$) |
| | Paired Test ($p$-value) | $p = 0.026$ | **N/A (No Trades)** | **$p = 0.160$** | Simulator Inactive | Inconclusive |
| **Fold 3 Unfiltered** | Total Return (%) | -4.91% | **-12.02%** | **-14.09%** | **-7.11%** (Execution & Delayed Exit) | **-2.07%** (Ranker Winner) |
| | Sharpe Ratio | -0.25 | **-0.78** | **-0.93** | -0.53 | -0.15 |
| **Fold 3 Filtered** | Total Return (%) | 0.00% | **0.00%** | **-1.82%** | **0.00%** (0 Trades in Both) | **-1.82%** (Inner Winner `lr=0.03`) |
| | Completed Trades | 0 | **0** | **6 (+0 open)** | **0 trades** | **+6 trades** (Different Prediction) |
| | Trade Win Rate (%) | N/A | **N/A** | **33.33%** | N/A | Small Sample ($N=6$) |
| | Paired Test ($p$-value) | $p = 0.835$ | **N/A (No Trades)** | **$p = 0.420$** | Simulator Inactive | Inconclusive |

---

## 4. Liquidity Behavior & Missing-Volume Configuration

The backtests explicitly configured and operated under the following liquidity rules:
- **Mode Used in Backtest**: `max_volume_participation_pct = None` (Unconstrained participation benchmark).
- **Contemporaneous Trading Feasibility**: `enforce_volume_positive = True`.

### Missing-Volume Behavior Documented for Both Modes:
1. **Disabled Participation Mode (`max_volume_participation_pct = None`, setting used)**:
   - Opening orders are budgeted by portfolio risk limits ($C \times w_{\max}$) without pre-trade volume participation caps.
   - Fill execution strictly requires contemporaneous day $s$ volume $V_s > 0$. If $V_s \le 0$ or NaN, the stock was halted or suspended; opening purchases are rejected.
   - At session close, scheduled exits require observable $P_{\text{close}} > 0$ and $V_s > 0$. If volume is 0 or NaN, the position is held over under the Delayed-Exit Policy (never liquidated at entry price).
2. **Enabled Participation Mode (`max_volume_participation_pct` set, e.g. 5.0%)**:
   - Pre-trade order spend at open is additionally capped by lagged volume:
     $$\text{Max Liquidity Spend} = V_{s-1} \times \left(\frac{\text{Participation Pct}}{100}\right) \times P_{\text{open}}$$
   - If lagged volume $V_{s-1}$ is missing (NaN) or non-positive ($\le 0$), pre-trade liquidity cannot be verified, so order spend is safely set to $0.0$ (order rejected).
   - Contemporaneous fill check still requires $V_s > 0$.

---

## 5. Exact Cash-Flow Accounting Reconciliation

For every fold and policy in Run B and Run C, terminal balance sheet equity reconciles to the exact cent:
$$\text{Terminal Equity} = \text{Initial Capital} + \sum \text{Realized Net P&L} + \sum \text{Unrealized Net P&L}$$

| Run & Fold | Policy | Initial Capital | Terminal Cash | Terminal Holdings | Terminal Equity | Realized Net P&L | Unrealized Net P&L | Discrepancy | Reconciled? |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Run B - Fold 1** | Unfiltered | 10,000,000 | 0.00 | 16,703,606.49 | 16,703,606.49 | +6,822,685.19 | -119,078.70 | **$0.00$** | **EXACT** |
| **Run B - Fold 1** | Filtered | 10,000,000 | 0.00 | 16,313,280.24 | 16,313,280.24 | +6,429,576.33 | -116,296.09 | **$0.00$** | **EXACT** |
| **Run B - Fold 2** | Unfiltered | 10,000,000 | 0.00 | 13,500,839.26 | 13,500,839.26 | +3,522,381.51 | -21,542.25 | **$0.00$** | **EXACT** |
| **Run B - Fold 2** | Filtered | 10,000,000 | 10,000,000.00 | 0.00 | 10,000,000.00 | 0.00 | 0.00 | **$0.00$** | **EXACT** |
| **Run B - Fold 3** | Unfiltered | 10,000,000 | 1,946.88 | 8,795,787.08 | 8,797,733.97 | -1,325,556.42 | +123,290.38 | **$0.00$** | **EXACT** |
| **Run B - Fold 3** | Filtered | 10,000,000 | 10,000,000.00 | 0.00 | 10,000,000.00 | 0.00 | 0.00 | **$0.00$** | **EXACT** |
| **Run C - Fold 1** | Unfiltered | 10,000,000 | 0.00 | 16,703,606.49 | 16,703,606.49 | +6,822,685.19 | -119,078.70 | **$0.00$** | **EXACT** |
| **Run C - Fold 1** | Filtered | 10,000,000 | 0.00 | 16,313,280.24 | 16,313,280.24 | +6,429,576.33 | -116,296.09 | **$0.00$** | **EXACT** |
| **Run C - Fold 2** | Unfiltered | 10,000,000 | 0.00 | 13,500,839.26 | 13,500,839.26 | +3,522,381.51 | -21,542.25 | **$0.00$** | **EXACT** |
| **Run C - Fold 2** | Filtered | 10,000,000 | 9,933,707.95 | 1,040,134.79 | 10,973,842.74 | +800,008.20 | +173,834.54 | **$0.00$** | **EXACT** |
| **Run C - Fold 3** | Unfiltered | 10,000,000 | 1,677.30 | 8,589,709.54 | 8,591,386.84 | -1,452,187.97 | +43,574.81 | **$0.00$** | **EXACT** |
| **Run C - Fold 3** | Filtered | 10,000,000 | 9,818,146.58 | 0.00 | 9,818,146.58 | -181,853.42 | 0.00 | **$0.00$** | **EXACT** |

*Note: In Run A, exact cash reconciliation failed ($2.67M discrepancy in Fold 1, $4.60M in Fold 2) because the legacy simulator did not maintain an order ledger, tracked returns heuristically, and fabricated liquidation prices on suspensions.*

---

## 6. Synthesis of Empirical Conclusions

1. **Prediction Equivalence Confirmed as PASS for Fold 1, FAIL for Folds 2–3**:
   - Fold 1 predictions are 100.0% equivalent.
   - Folds 2 and 3 failed prediction equivalence due to hyperparameter assignment (trial 0 vs. inner winner). Changed-model results are strictly identified as **Model Changes (Run C vs. Run B)**, never as a simulator-only comparison.
2. **Simulator Fixes (Run A vs. Run B)**:
   - Eliminating alphabetical ordering and enforcing morning cash integrity significantly altered returns on identical predictions (increasing Fold 1 unfiltered from +26.74% to +67.04%, while reducing Fold 2 from +46.00% to +35.01%).
   - When predictions had 0 signals (Folds 2 & 3 filtered), both simulators generated 0 trades.
3. **Model Effects (Run B vs. Run C)**:
   - The appearance of 6 trades in Fold 2 and 6 trades in Fold 3 is 100% attributable to using inner-validation winner learning rates (`lr=0.05` and `0.03`) instead of trial 0 (`lr=0.01`).
4. **Statistical Significance**:
   - Technical filtering does **not** generate statistically significant outperformance over the unfiltered fundamental shortlist in any fold ($p = 0.325$ in Fold 1, $p = 0.160$ in Fold 2, $p = 0.420$ in Fold 3). All paired tests remain statistically inconclusive.
5. **Sample Size Caveat**:
   - Filtered trades in Folds 2 and 3 constitute a very small sample ($N=6$). No general conclusions regarding model-family superiority can be drawn.
