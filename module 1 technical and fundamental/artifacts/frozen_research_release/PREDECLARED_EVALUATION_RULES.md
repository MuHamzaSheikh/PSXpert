# Predeclared Forward Paper Evaluation Rules

This document specifies the frozen, tamper-proof protocol for evaluating the **PSXpert Fundamental Selection & Technical Timing Architecture** during forward paper evaluation. To preserve genuine scientific integrity and prevent lookahead, selective reporting, or p-hacking, all evaluation criteria, statistical benchmarks, review cadences, and risk limits are predeclared before collecting forward outcomes.

---

## 1. Tracked Policies & Baselines

All policies operate under identical universe, capital ($10,000,000 PKR initial per policy), and execution rules (T+1 open entry, T+10 close exit, 0.50% round-trip friction, 10% maximum single position limit):

1. **Policy A (Fundamental Selection Only)**:
   - Stock Selection: Top 20% fundamental rank by XGBoost Ranker (Shortlist).
   - Technical Timing: Disabled (all shortlisted stocks generate buy signals).
   - Allocation: Slot-budgeted up to 10 positions simultaneously.

2. **Policy B (Fundamental Selection + Technical Timing Gate)**:
   - Stock Selection: Identical Top 20% fundamental shortlist as Policy A.
   - Technical Timing: Frozen XGBoost Classifier probability gate $P(\text{Up}_{20} \mid \text{Shortlist}) \ge 0.50$.
   - Allocation: Enters only when technical signal fires; otherwise capital remains in cash.

3. **Value Composite Baseline**:
   - Stock Selection: Top quintile composite ranking across $E/P$, $B/P$, and $S/P$.
   - Technical Timing: Identical frozen technical classifier gate ($P \ge 0.50$).

4. **Momentum Baseline**:
   - Stock Selection: Top quintile 126-session price momentum.
   - Technical Timing: Identical frozen technical classifier gate ($P \ge 0.50$).

---

## 2. Predeclared Evaluation Horizons & Maturity Rules

1. **Technical Timing Horizon**:
   - **Maturity Duration**: Exactly **10 trading sessions** ($T + 10$).
   - **Label Maturity Condition**: An entry signal emitted at session $t$ close evaluates against the price return from session $t+1$ Open to session $t+10$ Close.
   - **Strict Logging Rule**: Forward outcomes are recorded in `matured_technical_outcomes.csv` only when session clock advances to $\ge t + 10$. Historical predictions are NEVER modified or updated prior to maturity.

2. **Fundamental Selection Horizon**:
   - **Maturity Duration**: Exactly **126 trading sessions** (~6 calendar months).
   - **Label Maturity Condition**: Evaluates benchmark-relative excess return over KSE-100 index from session $t$ close to $t+126$ close.
   - **Strict Logging Rule**: Forward outcomes are recorded in `matured_fundamental_outcomes.csv` only when session clock advances to $\ge t + 126$.

---

## 3. Formal Review Cadence & Minimum Observation Thresholds

Premature evaluation on small sample sizes ($N < 60$) produces unreliable statistical estimates dominated by idiosyncrasy.

| Evaluation Tier | Formal Review Frequency | Minimum Sample Size ($N_{\min}$) | Statistical Standard |
| :--- | :--- | :--- | :--- |
| **Technical Timing Review** | Quarterly (every 63 trading sessions) | $N \ge 60$ matured signals | Paired return difference with Newey-West HAC standard errors (lag 10) |
| **Fundamental Selection Review**| Annual (every 252 trading sessions) | $N \ge 252$ sessions | NDCG@20% and top-quintile forward excess return |
| **Interim Health Checks** | Monthly (every 21 trading sessions) | Descriptive only | Ledger integrity, position cash reconciliation, stale-quote audit |

---

## 4. Performance Metrics & Statistical Inference

### Primary Metrics
1. **Technical Timing Primary**:
   $$\Delta \bar{r} = \frac{1}{N} \sum_{i=1}^N (r_{B, i} - r_{A, i})$$
   Evaluated with **Newey-West Heteroskedasticity and Autocorrelation Consistent (HAC) standard errors with lag 10** to account for overlapping 10-session holding periods. Two-tailed significance threshold: $p < 0.05$.
2. **Fundamental Selection Primary**:
   Normalized Discounted Cumulative Gain (**NDCG@20%**) against realized 126-session forward excess returns.

### Secondary Metrics
- **Brier Score & Precision-Recall AUC (PR-AUC)** against the realized empirical base rate.
- **Trade Win Rate** ($\% \text{ trades with net return} > 0$).
- **Portfolio Sharpe Ratio** and **Annualized Volatility**.
- **Spearman Rank Correlation** across all shortlisted vs excluded stocks.

---

## 5. Risk Limits & Circuit Breakers

1. **Portfolio Drawdown Limit**:
   - Maximum Drawdown Threshold: **25.0%**.
   - Action on Breach: Immediately halt new entries for all policies. Existing positions run to scheduled $t+10$ exit. Formal model audit initiated.
2. **Single-Position Concentration Limit**:
   - Maximum capital allocation per position: **10.0%** of total portfolio equity.
3. **Leverage Limit**:
   - Strict cash account policy: Maximum leverage = **1.0x** (no margin borrowing, opening purchases capped by prior-day closing settled cash $C_{s-1}$).
4. **Stale Price Quarantine**:
   - If an asset is suspended or untraded for $> 5$ consecutive sessions at scheduled exit, it is placed in delayed exit quarantine; valuation uses last known trade price but flags uncertainty in daily state reports.

---

## 6. Prohibited Practices

To maintain audit-grade scientific integrity:
1. **No Retrospective Overwriting**: Earlier fundamental predictions must NEVER be retroactively overwritten when historical financial statements are restated or revised.
2. **No Early Maturity Evaluation**: Outcomes must never be computed or claimed before the full 10- or 126-session holding window has closed.
3. **No Unaudited Metric Claims**: Arbitrary accuracy targets (such as 80–90%) are mathematically unachievable and prohibited for noisy financial asset prediction.
4. **No Alpha Leakage Across Folds**: No model hyperparameter tuning or retraining is allowed during the paper evaluation phase. Models remain frozen as hashed in `release_manifest.json`.
