"""
PSXpert - Binary Directional Trend Model (Bullish vs Bearish)
Evaluates directional trend prediction accuracy on cleaned PSX data.
"""

import csv
import math
import os
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, confusion_matrix, precision_score, recall_score
from sklearn.preprocessing import StandardScaler

CLEAN_DIR = os.path.join("data", "cleaned")

def run_binary_test():
    prices_path = os.path.join(CLEAN_DIR, "kse100_stocks_historical_clean.csv")
    cal_path = os.path.join(CLEAN_DIR, "kse100_calendar_clean.csv")
    
    index_closes = {}
    with open(cal_path, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            index_closes[row['date']] = float(row['close'])
            
    by_symbol = {}
    with open(prices_path, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            by_symbol.setdefault(row['symbol'], []).append({
                'date': row['trading_date'],
                'close': float(row['adjusted_close']),
                'volume': int(row['volume']),
                'is_active': int(row['is_active_trade'])
            })
            
    samples = []
    for sym, rows in by_symbol.items():
        rows.sort(key=lambda x: x['date'])
        n = len(rows)
        if n < 260:
            continue
            
        closes = np.array([r['close'] for r in rows], dtype=np.float64)
        volumes = np.array([r['volume'] for r in rows], dtype=np.float64)
        dates = [r['date'] for r in rows]
        
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
        
        rolling_var_20 = np.maximum((cumsum_sq_ret[20:] - cumsum_sq_ret[:-20]) / 20.0, 1e-8)
        vol_20d = np.zeros(n)
        vol_20d[20:] = np.sqrt(rolling_var_20) * math.sqrt(252)
        
        # Wilder RSI
        gains = np.maximum(closes[1:] - closes[:-1], 0)
        losses = np.maximum(closes[:-1] - closes[1:], 0)
        rsi = np.zeros(n)
        rsi[:14] = 50.0
        avg_gain = np.mean(gains[:14]) if len(gains) >= 14 else 0.0
        avg_loss = np.mean(losses[:14]) if len(losses) >= 14 else 0.0
        for i in range(14, n - 1):
            avg_gain = (avg_gain * 13 + gains[i]) / 14.0
            avg_loss = (avg_loss * 13 + losses[i]) / 14.0
            rs = avg_gain / max(avg_loss, 1e-9)
            rsi[i + 1] = 100.0 - (100.0 / (1.0 + rs))
            
        for i in range(252, n - 10):
            d_t = dates[i]
            # 10-session trend
            fwd_ret_10d = math.log(closes[i+10] / closes[i])
            thresh = 0.010 # 1.0% hurdle
            
            # Binary classification on directional trend (filter out minor chop < 1%)
            if abs(fwd_ret_10d) < thresh:
                continue
            label = 1 if fwd_ret_10d > 0 else 0
            
            ret_5d = math.log(closes[i] / max(closes[i-5], 1e-4))
            ret_20d = math.log(closes[i] / max(closes[i-20], 1e-4))
            ret_60d = math.log(closes[i] / max(closes[i-60], 1e-4))
            sma_10_50 = (sma_10[i] / max(sma_50[i], 1e-4)) - 1.0
            sma_50_200 = (sma_50[i] / max(sma_200[i], 1e-4)) - 1.0
            vol_surge = volumes[i] / max(vol_sma_20[i], 1.0)
            
            d_prev20 = dates[i-20]
            idx_ret_20 = math.log(index_closes[d_t] / index_closes[d_prev20]) if (d_t in index_closes and d_prev20 in index_closes) else 0.0
            rel_ret_20 = ret_20d - idx_ret_20
            
            feat_vec = [
                log_ret[i], ret_5d, ret_20d, ret_60d,
                sma_10_50, sma_50_200, rsi[i], vol_20d[i], vol_surge, rel_ret_20
            ]
            samples.append({
                'date': d_t,
                'features': feat_vec,
                'label': label
            })
            
    samples.sort(key=lambda x: x['date'])
    
    train_x, train_y = [], []
    val_x, val_y = [], []
    test_x, test_y = [], []
    
    stride = 0
    for s in samples:
        d = s['date']
        f = s['features']
        y = s['label']
        if d <= '2021-11-24':
            stride += 1
            if stride % 5 == 0:
                train_x.append(f)
                train_y.append(y)
        elif '2022-01-01' <= d <= '2024-05-20':
            val_x.append(f)
            val_y.append(y)
        elif '2024-07-01' <= d <= '2026-10-13':
            test_x.append(f)
            test_y.append(y)
            
    X_train = np.array(train_x, dtype=np.float32)
    y_train = np.array(train_y, dtype=np.int32)
    X_val = np.array(val_x, dtype=np.float32)
    y_val = np.array(val_y, dtype=np.int32)
    X_test = np.array(test_x, dtype=np.float32)
    y_test = np.array(test_y, dtype=np.int32)
    
    hgb = HistGradientBoostingClassifier(
        max_iter=250, learning_rate=0.03, max_depth=5,
        min_samples_leaf=80, l2_regularization=5.0,
        early_stopping=True, n_iter_no_change=20, random_state=42
    )
    hgb.fit(X_train, y_train)
    
    test_probs = hgb.predict_proba(X_test)[:, 1]
    test_preds = (test_probs >= 0.50).astype(int)
    
    raw_acc = accuracy_score(y_test, test_preds) * 100.0
    auc = roc_auc_score(y_test, test_probs)
    
    print(f"Binary Trend Directional Classifier (10-Day Horizon):")
    print(f"  Total Held-out Test Signals: {len(y_test)}")
    print(f"  Raw Accuracy (Threshold 0.50): {raw_acc:.2f}% | ROC-AUC: {auc:.4f}")
    
    print("\nSelective High-Conviction Accuracy Scaling:")
    for conf in [0.55, 0.60, 0.65, 0.70]:
        mask = (test_probs >= conf) | (test_probs <= (1.0 - conf))
        cov = np.sum(mask) / len(y_test) * 100.0
        acc = accuracy_score(y_test[mask], test_preds[mask]) * 100.0
        print(f"  Confidence >= {conf:.2f} ({1.0-conf:.2f}): Coverage = {cov:>5.1f}% ({np.sum(mask):>5} trades) -> ACCURACY = {acc:.2f}%")

if __name__ == "__main__":
    run_binary_test()
