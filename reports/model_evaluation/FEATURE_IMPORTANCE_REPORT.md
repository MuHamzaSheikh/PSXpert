# Technical ML Model — Feature Importance & Explainability Report (`psxpert_tech_ml_v2.0`)

## 1. Input Feature Schema ([`technical_features.json`](../../artifacts/technical/technical_features.json))
The selected **XGBoost** classifier ingests **`74` strictly causal, stationary features** (`TECHNICAL_FEATURE_COLS`):
- **OHLCV & Returns (8)**: `ret_1d`, `ret_2d`, `ret_5d`, `ret_10d`, `ret_20d`, `log_ret_1d`, `overnight_gap_pct`, `intraday_ret_pct`
- **SMA & EMA Distances/Spreads (6)**: `dist_sma_20`, `dist_sma_50`, `dist_sma_200`, `dist_ema_20`, `ema_20_50_spread`, `ema_50_200_spread`
- **Oscillators & Trend Strength (13)**: `rsi_14`, `macd_diff_pct`, `bb_bandwidth`, `bb_percent_b`, `atr_pct`, `dmi_plus_14`, `dmi_minus_14`, `adx_14`, `dmi_diff`, `obv_zscore_20`, `stoch_k`, `stoch_d`, `stoch_k_minus_d`
- **Candlestick Anatomy & True-OHLC Patterns (13)**: `candle_body_pct`, `candle_range_pct`, `upper_shadow_ratio`, `lower_shadow_ratio`, `body_to_range_ratio`, `close_position_in_range`, `candlestick_pattern_signal_num`, `is_bullish_pattern`, `is_bearish_pattern`, `is_doji_true_ohlc`, `bullish_patterns_5d`, `bearish_patterns_5d`, `is_true_ohlc`
- **Volatility & Liquidity (14)**: `vol_5d`, `vol_20d`, `vol_60d`, `vol_ratio_5_20`, `parkinson_vol_20d`, `log_volume`, `log_turnover_pkr`, `volume_ratio_20d`, `amihud_illiquidity_20d`, `zero_volume_days_20d`, `hl_spread_pct`, `trailing_20d_adv_rank`, `listing_age_sessions`, `calendar_gap_days`
- **Causal HMM Regimes & Index/Breadth Context (20)**: `hmm_mkt_prob_bullish`, `hmm_mkt_prob_bearish`, `hmm_mkt_prob_sideways`, `hmm_mkt_regime_id`, `hmm_mkt_entropy`, `hmm_mkt_regime_duration`, KSE-100 returns/SMA/vol/RSI, relative strength (`5d`/`20d`), `60d` beta/correlation, and exchange breadth (`mkt_median_ret_1d`, `mkt_pct_above_sma50`, `mkt_adv_decline_ratio`).

---

## 2. Global Normalized Feature Importance (Top 15 — Selected Model: `XGBoost`)

Source: [`technical_feature_importance.csv`](./technical_feature_importance.csv) and [`technical_metadata.json`](../../artifacts/technical/technical_metadata.json).

| Rank (XGB) | Feature | Feature Group | XGBoost Gain Share | LightGBM Gain Share | Random Forest Gini Share |
| :---: | :--- | :--- | ---: | ---: | ---: |
| 1 | `hmm_mkt_regime_id` | HMM Market Regime | **0.050001** (`5.00%`) | 0.001408 (`0.14%`) | 0.003943 (`0.39%`) |
| 2 | `kse100_rsi_14` | Index Momentum | **0.036268** (`3.63%`) | 0.055371 (`5.54%`) | **0.057766** (`5.78%`) |
| 3 | `bb_percent_b` | Oscillators & Volatility | **0.030839** (`3.08%`) | 0.016423 (`1.64%`) | 0.022435 (`2.24%`) |
| 4 | `hmm_mkt_prob_bullish` | HMM Market Regime | **0.026725** (`2.67%`) | 0.029193 (`2.92%`) | 0.029819 (`2.98%`) |
| 5 | `kse100_vol_20d` | Index Volatility | **0.025034** (`2.50%`) | **0.059149** (`5.91%`) | 0.046517 (`4.65%`) |
| 6 | `mkt_median_ret_1d` | Market Breadth | **0.024945** (`2.49%`) | 0.039714 (`3.97%`) | 0.040633 (`4.06%`) |
| 7 | `hmm_mkt_prob_sideways` | HMM Market Regime | **0.024486** (`2.45%`) | 0.032981 (`3.30%`) | 0.031090 (`3.11%`) |
| 8 | `mkt_adv_decline_ratio` | Market Breadth | **0.022704** (`2.27%`) | 0.045959 (`4.60%`) | 0.044424 (`4.44%`) |
| 9 | `hmm_mkt_regime_duration` | HMM Market Regime | **0.022696** (`2.27%`) | 0.043446 (`4.34%`) | 0.032248 (`3.22%`) |
| 10 | `kse100_dist_sma50` | Index Trend | **0.022153** (`2.22%`) | 0.040529 (`4.05%`) | 0.044466 (`4.45%`) |
| 11 | `kse100_ret_5d` | Index Return | **0.022106** (`2.21%`) | **0.052306** (`5.23%`) | **0.048565** (`4.86%`) |
| 12 | `hmm_mkt_entropy` | HMM Market Regime | **0.021655** (`2.17%`) | 0.024094 (`2.41%`) | 0.031102 (`3.11%`) |
| 13 | `ret_10d` | Short-Horizon Return | **0.021608** (`2.16%`) | 0.012793 (`1.28%`) | 0.006539 (`0.65%`) |
| 14 | `mkt_pct_above_sma50` | Market Breadth | **0.021592** (`2.16%`) | **0.053038** (`5.30%`) | **0.051406** (`5.14%`) |
| 15 | `hmm_mkt_prob_bearish` | HMM Market Regime | **0.021334** (`2.13%`) | 0.020241 (`2.02%`) | 0.026837 (`2.68%`) |

Notice the smooth weight distribution (`~37.41%` across top 15 in XGBoost): forward 5-day volatility-adjusted market conditions rely broadly on **macro HMM regimes**, **KSE-100 momentum/volatility**, **market breadth**, **Bollinger %B**, and **short-horizon returns** rather than overfitting a single lagging moving average.

---

## 3. Local Inference Explainability (`TreeSHAP`)
On every live request (`POST /api/models/technical/predict` or `GET /api/analysis/ml/technical/{symbol}`), [`TechnicalMLPredictor._explain_prediction`](../../src/ml/technical_ml.py) extracts exact native **XGBoost TreeSHAP logits** via `get_booster().predict(xgb.DMatrix(x_mat), pred_contribs=True)` and returns the top 8 signed drivers contributing to or opposing the predicted class (`Bullish`, `Neutral`, or `Bearish`).
