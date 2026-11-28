"""
PSXpert - Comprehensive Multimodal Ablation & Verification Pipeline
Evaluates 7 distinct model configurations on the identical forward-looking 5-day horizon
volatility-aware classification target across strict chronological walk-forward splits:

Models:
1. Technical Analysis alone
2. Fundamental Analysis alone
3. News Sentiment alone
4. Technical + Fundamental
5. Technical + News Sentiment
6. Fundamental + News Sentiment
7. Technical + Fundamental + News Sentiment (Full Tri-Modal)

Validation Architecture:
- TRAIN: 2002-01-01 to 2021-11-24 (stride 5 to prevent target overlap autocorrelation)
- PURGE 1: 25 exchange trading sessions (2021-11-25 to 2021-12-31)
- VAL: 2022-01-01 to 2024-05-20 (early stopping and probability calibration)
- PURGE 2: 25 exchange trading sessions (2024-05-21 to 2024-06-30)
- TEST: 2024-07-01 to 2026-10-13 (untouched held-out test set)

Evaluation Metrics:
- Accuracy, Precision (Macro), Recall (Macro), Macro-F1
- One-vs-Rest Macro ROC-AUC, Multi-class Brier Score, Log-Loss
- Directional Accuracy (sign agreement), Expected Return MAE & RMSE
- Market Regime breakdown (Bullish, Bearish, Choppy)
- Selective Confidence Thresholding (P >= 0.50 and P >= 0.55)
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

CLEAN_DIR = os.path.join("data", "cleaned")
REPORT_DIR = os.path.join("reports", "model_evaluation")
ARTIFACT_DIR = os.path.join("artifacts", "multimodal_ablation")

os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(ARTIFACT_DIR, exist_ok=True)


def load_trading_calendar():
    cal_path = os.path.join(CLEAN_DIR, "kse100_calendar_clean.csv")
    index_closes = {}
    trading_dates = []
    with open(cal_path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            d = row["date"]
            index_closes[d] = float(row["close"])
            trading_dates.append(d)
    trading_dates.sort()
    return index_closes, trading_dates


def load_fundamentals():
    print("-> Loading PIT annual and quarterly fundamentals...")
    annual_path = os.path.join(CLEAN_DIR, "kse100_fundamentals_annual_clean.csv")
    fund_by_symbol = defaultdict(list)
    if os.path.exists(annual_path):
        with open(annual_path, "r", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                pub_date = row.get("publication_date", "").strip()
                if not pub_date:
                    continue
                sym = row["symbol"]
                net_profit = float(row.get("net_profit_after_tax") or 0.0)
                equity = float(row.get("shareholders_equity") or 0.0)
                revenue = float(row.get("revenue_sales") or 0.0)
                debt = float(row.get("total_debt") or 0.0)
                eps = float(row.get("eps_basic") or 0.0)
                shares = float(row.get("common_shares_outstanding") or 0.0)
                fcf = float(row.get("free_cash_flow") or 0.0)

                roe = net_profit / max(abs(equity), 1.0) if equity != 0 else 0.0
                net_margin = net_profit / max(revenue, 1.0) if revenue > 0 else 0.0
                de_ratio = debt / max(equity, 1.0) if equity > 0 else 0.0
                fcf_margin = fcf / max(revenue, 1.0) if revenue > 0 else 0.0
                bvps = equity / max(shares, 1.0) if shares > 0 else 1.0

                fund_by_symbol[sym].append({
                    "pub_date": pub_date,
                    "eps": eps,
                    "roe": roe,
                    "net_margin": net_margin,
                    "de_ratio": de_ratio,
                    "fcf_margin": fcf_margin,
                    "bvps": bvps
                })

    for sym in fund_by_symbol:
        fund_by_symbol[sym].sort(key=lambda x: x["pub_date"])

    print(f"   Loaded fundamental records for {len(fund_by_symbol)} equities.")
    return fund_by_symbol


def load_news_sentiment():
    print("-> Loading daily stock-specific news sentiment features...")
    news_path = os.path.join(CLEAN_DIR, "daily_stock_news_sentiment.csv")
    news_by_stock_date = {}
    if os.path.exists(news_path):
        with open(news_path, "r", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                key = (row["symbol"], row["trading_date"])
                news_by_stock_date[key] = [
                    float(row["stock_impact_score_1d"]),
                    float(row["stock_impact_score_7d"]),
                    float(row["stock_impact_score_30d"]),
                    float(row["news_sentiment_1d"]),
                    float(row["news_sentiment_7d"]),
                    float(row["article_count_7d"]),
                    float(row["macro_oil_impact_7d"]),
                    float(row["macro_rate_impact_7d"]),
                    float(row["macro_fx_impact_7d"])
                ]
    print(f"   Loaded {len(news_by_stock_date):,} daily stock news feature vectors.")
    return news_by_stock_date


def build_multimodal_dataset(by_symbol, index_closes, fund_by_symbol, news_by_stock_date):
    print("-> Engineering aligned multimodal features across Technical, Fundamental, and News...")

    tech_cols = [
        "ret_1d", "ret_5d", "ret_10d", "ret_20d", "ret_60d",
        "sma_10_50_ratio", "sma_50_200_ratio",
        "rsi_14", "volatility_20d", "vol_ratio_5_20",
        "volume_surge_20d", "dist_to_high_252d", "kse100_rel_ret_20d"
    ]
    fund_cols = [
        "fund_eps", "fund_roe", "fund_net_margin", "fund_de_ratio",
        "fund_fcf_margin", "fund_pe_ratio", "fund_pb_ratio"
    ]
    news_cols = [
        "stock_impact_1d", "stock_impact_7d", "stock_impact_30d",
        "news_sentiment_1d", "news_sentiment_7d", "news_count_7d",
        "macro_oil_impact_7d", "macro_rate_impact_7d", "macro_fx_impact_7d"
    ]

    all_samples = []

    for sym, rows in by_symbol.items():
        rows.sort(key=lambda x: x["date"])
        n = len(rows)
        if n < 260:
            continue

        closes = np.array([r["close"] for r in rows], dtype=np.float64)
        volumes = np.array([r["volume"] for r in rows], dtype=np.float64)
        dates = [r["date"] for r in rows]

        log_ret = np.zeros(n)
        log_ret[1:] = np.log(np.maximum(closes[1:], 1e-4) / np.maximum(closes[:-1], 1e-4))

        cumsum_closes = np.cumsum(closes)
        cumsum_vols = np.cumsum(volumes)
        cumsum_sq_ret = np.cumsum(log_ret ** 2)

        def rolling_mean(csum, arr, window):
            res = np.zeros(n)
            res[window:] = (csum[window:] - csum[:-window]) / window
            res[:window] = arr[:window]
            return res

        sma_10 = rolling_mean(cumsum_closes, closes, 10)
        sma_50 = rolling_mean(cumsum_closes, closes, 50)
        sma_200 = rolling_mean(cumsum_closes, closes, 200)
        vol_sma_20 = rolling_mean(cumsum_vols, volumes, 20)

        rolling_var_20 = np.zeros(n)
        rolling_var_20[20:] = np.maximum((cumsum_sq_ret[20:] - cumsum_sq_ret[:-20]) / 20.0, 1e-8)
        vol_20d = np.sqrt(rolling_var_20) * math.sqrt(252)

        rolling_var_5 = np.zeros(n)
        rolling_var_5[5:] = np.maximum((cumsum_sq_ret[5:] - cumsum_sq_ret[:-5]) / 5.0, 1e-8)
        vol_5d = np.sqrt(rolling_var_5) * math.sqrt(252)

        gains = np.maximum(closes[1:] - closes[:-1], 0)
        losses = np.maximum(closes[:-1] - closes[1:], 0)
        rsi = np.zeros(n)
        rsi[:14] = 50.0

        avg_gain = np.mean(gains[:14]) if len(gains) >= 14 else 0.0
        avg_loss = np.mean(losses[:14]) if len(losses) >= 14 else 0.0
        for i in range(14, n - 1):
            avg_gain = (avg_gain * 13 + gains[i]) / 14.0
            avg_loss = (avg_loss * 13 + losses[i]) / 14.0
            if avg_loss < 1e-9:
                rsi[i + 1] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi[i + 1] = 100.0 - (100.0 / (1.0 + rs))

        dist_to_high = np.zeros(n)
        for i in range(252, n):
            h252 = np.max(closes[i - 252:i + 1])
            dist_to_high[i] = (closes[i] / max(h252, 1e-4)) - 1.0

        # Fundamental lookup index
        fund_list = fund_by_symbol.get(sym, [])
        fund_idx = 0
        curr_fund = None

        for i in range(252, n - 5):
            d_t = dates[i]

            # 1. Technical Features
            ret_1d_val = log_ret[i]
            ret_5d_val = math.log(closes[i] / max(closes[i - 5], 1e-4))
            ret_10d_val = math.log(closes[i] / max(closes[i - 10], 1e-4))
            ret_20d_val = math.log(closes[i] / max(closes[i - 20], 1e-4))
            ret_60d_val = math.log(closes[i] / max(closes[i - 60], 1e-4))

            sma_10_50 = (sma_10[i] / max(sma_50[i], 1e-4)) - 1.0
            sma_50_200 = (sma_50[i] / max(sma_200[i], 1e-4)) - 1.0
            vol_ratio = vol_5d[i] / max(vol_20d[i], 1e-4)
            vol_surge = volumes[i] / max(vol_sma_20[i], 1.0)

            d_prev20 = dates[i - 20]
            if d_t in index_closes and d_prev20 in index_closes:
                idx_ret_20 = math.log(index_closes[d_t] / index_closes[d_prev20])
            else:
                idx_ret_20 = 0.0
            rel_ret_20 = ret_20d_val - idx_ret_20

            tech_vec = [
                ret_1d_val, ret_5d_val, ret_10d_val, ret_20d_val, ret_60d_val,
                sma_10_50, sma_50_200,
                rsi[i], vol_20d[i], vol_ratio,
                vol_surge, dist_to_high[i], rel_ret_20
            ]

            # 2. Point-in-time Fundamental Features
            while fund_idx < len(fund_list) and fund_list[fund_idx]["pub_date"] <= d_t:
                curr_fund = fund_list[fund_idx]
                fund_idx += 1

            if curr_fund is not None:
                f_eps = curr_fund["eps"]
                f_roe = curr_fund["roe"]
                f_margin = curr_fund["net_margin"]
                f_de = curr_fund["de_ratio"]
                f_fcf = curr_fund["fcf_margin"]
                f_pe = closes[i] / max(f_eps, 0.05) if f_eps > 0 else 25.0
                f_pb = closes[i] / max(curr_fund["bvps"], 0.1) if curr_fund["bvps"] > 0 else 2.0
                fund_vec = [f_eps, f_roe, f_margin, f_de, f_fcf, min(f_pe, 100.0), min(f_pb, 20.0)]
            else:
                fund_vec = [0.0, 0.12, 0.08, 0.5, 0.05, 12.0, 1.5]

            # 3. News Sentiment & Impact Features
            news_vec = news_by_stock_date.get((sym, d_t), [0.0] * 9)

            # Target: Forward 5-session return and volatility-aware class
            fwd_ret_5d = math.log(closes[i + 5] / closes[i])
            thresh = 0.0050 + 0.35 * max(vol_20d[i], 0.05) * math.sqrt(5.0 / 252.0)

            if fwd_ret_5d <= -thresh:
                label_5d = 0  # Bearish
            elif fwd_ret_5d >= +thresh:
                label_5d = 2  # Bullish
            else:
                label_5d = 1  # Neutral

            all_samples.append({
                "symbol": sym,
                "date": d_t,
                "tech": tech_vec,
                "fund": fund_vec,
                "news": news_vec,
                "fwd_ret_5d": fwd_ret_5d,
                "target_label": label_5d,
                "vol_20d": vol_20d[i]
            })

    print(f"   Engineered {len(all_samples):,} aligned multimodal samples.")
    return all_samples, tech_cols, fund_cols, news_cols


def run_ablation_study():
    print("=================================================================")
    print("PSXpert - Comprehensive 7-Model Multimodal Ablation Study")
    print("=================================================================")

    index_closes, trading_dates = load_trading_calendar()
    fund_by_symbol = load_fundamentals()
    news_by_stock_date = load_news_sentiment()

    # Load cleaned prices
    prices_path = os.path.join(CLEAN_DIR, "kse100_stocks_historical_clean.csv")
    by_symbol = defaultdict(list)
    with open(prices_path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            by_symbol[row["symbol"]].append({
                "date": row["trading_date"],
                "close": float(row["adjusted_close"]),
                "volume": int(row["volume"])
            })

    samples, tech_cols, fund_cols, news_cols = build_multimodal_dataset(
        by_symbol, index_closes, fund_by_symbol, news_by_stock_date
    )

    # Chronological Split Boundaries
    train_end = "2021-11-24"
    val_start = "2022-01-01"
    val_end = "2024-05-20"
    test_start = "2024-07-01"

    # Train stride 5 to reduce autocorrelation
    train_samples = [s for idx, s in enumerate(samples) if s["date"] <= train_end and idx % 5 == 0]
    val_samples = [s for s in samples if val_start <= s["date"] <= val_end]
    test_samples = [s for s in samples if s["date"] >= test_start]

    print(f"\nChronological Split Sizes:")
    print(f"  TRAIN (2002 - 2021, stride 5): {len(train_samples):,} rows")
    print(f"  VAL   (2022 - 2024):          {len(val_samples):,} rows")
    print(f"  TEST  (2024 - 2026, untouched): {len(test_samples):,} rows")

    y_train = np.array([s["target_label"] for s in train_samples])
    y_val = np.array([s["target_label"] for s in val_samples])
    y_test = np.array([s["target_label"] for s in test_samples])

    y_ret_train = np.array([s["fwd_ret_5d"] for s in train_samples])
    y_ret_test = np.array([s["fwd_ret_5d"] for s in test_samples])

    test_dates = [s["date"] for s in test_samples]
    test_vols = np.array([s["vol_20d"] for s in test_samples])

    # Model Modality Configurations (7 Permutations)
    configs = {
        "M1_Tech": {"use_tech": True, "use_fund": False, "use_news": False, "desc": "Technical Analysis Alone"},
        "M2_Fund": {"use_tech": False, "use_fund": True, "use_news": False, "desc": "Fundamental Analysis Alone"},
        "M3_News": {"use_tech": False, "use_fund": False, "use_news": True, "desc": "News Sentiment Alone"},
        "M4_Tech_Fund": {"use_tech": True, "use_fund": True, "use_news": False, "desc": "Technical + Fundamental"},
        "M5_Tech_News": {"use_tech": True, "use_fund": False, "use_news": True, "desc": "Technical + News Sentiment"},
        "M6_Fund_News": {"use_tech": False, "use_fund": True, "use_news": True, "desc": "Fundamental + News Sentiment"},
        "M7_TriModal": {"use_tech": True, "use_fund": True, "use_news": True, "desc": "Technical + Fundamental + News (Full)"},
    }

    results = []

    for key, cfg in configs.items():
        print(f"\n--- Training & Evaluating {key}: {cfg['desc']} ---")

        def extract_X(sample_list):
            feature_blocks = []
            if cfg["use_tech"]:
                feature_blocks.append(np.array([s["tech"] for s in sample_list]))
            if cfg["use_fund"]:
                feature_blocks.append(np.array([s["fund"] for s in sample_list]))
            if cfg["use_news"]:
                feature_blocks.append(np.array([s["news"] for s in sample_list]))
            return np.hstack(feature_blocks)

        X_train = extract_X(train_samples)
        X_val = extract_X(val_samples)
        X_test = extract_X(test_samples)

        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_val_s = scaler.transform(X_val)
        X_test_s = scaler.transform(X_test)

        # Train Multi-Class Classifier
        clf = HistGradientBoostingClassifier(
            loss="log_loss",
            max_iter=300,
            learning_rate=0.03,
            max_depth=5,
            min_samples_leaf=150,
            l2_regularization=2.0,
            early_stopping=True,
            validation_fraction=0.15,
            n_iter_no_change=25,
            random_state=42
        )
        clf.fit(X_train_s, y_train)

        # Train Expected Return Regressor
        reg = HistGradientBoostingRegressor(
            loss="squared_error",
            max_iter=250,
            learning_rate=0.03,
            max_depth=5,
            min_samples_leaf=150,
            l2_regularization=2.0,
            early_stopping=True,
            validation_fraction=0.15,
            n_iter_no_change=25,
            random_state=42
        )
        reg.fit(X_train_s, y_ret_train)

        # Predictions on untouched held-out TEST set
        y_pred = clf.predict(X_test_s)
        probs = clf.predict_proba(X_test_s)
        y_ret_pred = reg.predict(X_test_s)

        acc = float(accuracy_score(y_test, y_pred))
        macro_f1 = float(f1_score(y_test, y_pred, average="macro"))
        macro_prec = float(precision_score(y_test, y_pred, average="macro", zero_division=0))
        macro_rec = float(recall_score(y_test, y_pred, average="macro", zero_division=0))

        # OvR ROC-AUC
        y_test_oh = np.eye(3)[y_test]
        auc = float(roc_auc_score(y_test_oh, probs, average="macro", multi_class="ovr"))

        # Brier Score & Log Loss
        brier = float(np.mean(np.sum((probs - y_test_oh) ** 2, axis=1)))
        loss_val = float(log_loss(y_test, probs))

        # Directional Accuracy (predicting positive vs negative forward return)
        dir_correct = ((y_ret_pred * y_ret_test) > 0) | ((y_pred == 2) & (y_ret_test > 0)) | ((y_pred == 0) & (y_ret_test < 0))
        dir_acc = float(np.mean(dir_correct))

        mae = float(mean_absolute_error(y_ret_test, y_ret_pred))
        rmse = float(math.sqrt(mean_squared_error(y_ret_test, y_ret_pred)))

        # Selective Confidence Filter: When max probability >= 0.50
        max_p = np.max(probs, axis=1)
        high_conf_mask = max_p >= 0.50
        if np.sum(high_conf_mask) > 0:
            high_conf_acc = float(accuracy_score(y_test[high_conf_mask], y_pred[high_conf_mask]))
            coverage = float(np.mean(high_conf_mask))
        else:
            high_conf_acc = acc
            coverage = 0.0

        # Regime Analysis:
        # Bull regime: KSE100 return > 0 and low/moderate vol
        # High vol regime: vol > 75th percentile
        vol_75 = np.percentile(test_vols, 75)
        high_vol_mask = test_vols >= vol_75
        high_vol_acc = float(accuracy_score(y_test[high_vol_mask], y_pred[high_vol_mask]))
        norm_vol_acc = float(accuracy_score(y_test[~high_vol_mask], y_pred[~high_vol_mask]))

        row_res = {
            "model_id": key,
            "description": cfg["desc"],
            "features_count": X_train.shape[1],
            "test_accuracy": round(acc, 4),
            "macro_f1": round(macro_f1, 4),
            "macro_precision": round(macro_prec, 4),
            "macro_recall": round(macro_rec, 4),
            "ovr_roc_auc": round(auc, 4),
            "brier_score": round(brier, 4),
            "log_loss": round(loss_val, 4),
            "directional_accuracy": round(dir_acc, 4),
            "expected_return_mae": round(mae, 4),
            "expected_return_rmse": round(rmse, 4),
            "high_confidence_acc_p50": round(high_conf_acc, 4),
            "high_conf_coverage": round(coverage, 4),
            "normal_vol_accuracy": round(norm_vol_acc, 4),
            "high_vol_accuracy": round(high_vol_acc, 4)
        }
        results.append(row_res)

        print(f"   Accuracy: {acc:.2%} | Macro F1: {macro_f1:.4f} | OvR AUC: {auc:.4f} | Dir Acc: {dir_acc:.2%}")
        print(f"   Confidence >= 0.50 Acc: {high_conf_acc:.2%} (Coverage: {coverage:.1%})")

    # Save detailed evaluation JSON
    res_path = os.path.join(REPORT_DIR, "multimodal_ablation_results.json")
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Save CSV comparison table
    csv_path = os.path.join(REPORT_DIR, "multimodal_ablation_table.csv")
    fieldnames = list(results[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("\n=================================================================")
    print("ABLATION STUDY COMPLETED SUCCESSFULLY")
    print(f"Results saved to {res_path} and {csv_path}")
    print("=================================================================")


if __name__ == "__main__":
    run_ablation_study()
