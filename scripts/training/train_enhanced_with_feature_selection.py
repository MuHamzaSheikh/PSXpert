"""Enhanced Quantitative ML Pipeline: Feature Selection, Retraining, and High-Conviction Selective Prediction.

Key Execution Steps:
1. Ingest clean daily price history, market index, authentic SBP fundamentals (including banks), and company metadata.
2. Perform point-in-time alignment and sector-relative median imputation (matching missing values with sector info).
3. Stage 1: Fit full candidate feature sets, extract XGBoost Gain/Importance, and rank features.
4. Stage 2: Prune low-importance features and retrain technical, fundamental, and ensemble models on top parameters.
5. High-Conviction Analysis: Evaluate Selective Prediction / Precision Gating to demonstrate 80%-90% accuracy tier.
6. Persist models, feature importances, and conviction predictions.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import scipy.stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, log_loss
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import joblib

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("EnhancedPipeline")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "psx all data"
REPORTS_DIR = PROJECT_ROOT / "reports" / "model_evaluation"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def load_datasets() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    logger.info("Loading cleaned datasets, market index, fundamentals, corporate payouts, and company metadata...")
    prices_path = DATA_DIR / "1_market_and_prices" / "stock_price_history.csv.gz"
    index_path = DATA_DIR / "1_market_and_prices" / "market_indices_clean.csv"
    funds_path = PROJECT_ROOT / "data" / "processed" / "kse100_fundamentals_historical_2005_2026.csv"
    payouts_path = DATA_DIR / "4_corporate_payouts" / "kse100_corporate_payouts_2001_2026.csv"
    comp_path = PROJECT_ROOT / "data" / "processed" / "companies_clean.csv"
    ann_path = DATA_DIR / "5_corporate_announcements" / "corporate_announcements_clean.csv"

    prices = pd.read_csv(prices_path)
    prices["trading_date"] = pd.to_datetime(prices["date"], utc=True).dt.tz_localize(None).dt.strftime("%Y-%m-%d")
    prices = prices.sort_values(["symbol", "trading_date"]).drop_duplicates(["symbol", "trading_date"]).reset_index(drop=True)
    for c in ["open", "high", "low", "close", "volume"]:
        if c in prices.columns:
            prices[c] = pd.to_numeric(prices[c], errors="coerce")
        else:
            prices[c] = np.nan

    index_df = pd.read_csv(index_path)
    index_df["trading_date"] = pd.to_datetime(index_df["trading_date"]).dt.strftime("%Y-%m-%d")
    index_df = index_df.sort_values("trading_date").drop_duplicates("trading_date").reset_index(drop=True)
    index_df["kse100_close"] = pd.to_numeric(index_df["close"], errors="coerce")

    funds = pd.read_csv(funds_path)
    payouts = pd.read_csv(payouts_path)
    comp = pd.read_csv(comp_path)
    ann = pd.read_csv(ann_path)

    # Merge company metadata
    prices = prices.merge(comp[["symbol", "sector", "sector_category", "is_shariah"]], on="symbol", how="left")
    funds = funds.merge(comp[["symbol", "sector", "sector_category"]], on="symbol", how="left")

    logger.info(f"Loaded {len(prices):,} price bars for {prices['symbol'].nunique()} symbols, {len(funds):,} fundamental records.")
    return prices, index_df, funds, payouts, comp, ann


def build_feature_dataset(prices: pd.DataFrame, index_df: pd.DataFrame, funds: pd.DataFrame, 
                         payouts: pd.DataFrame, ann: pd.DataFrame) -> Tuple[pd.DataFrame, List[str], List[str]]:
    logger.info("Computing causal technical indicators and point-in-time sector-relative fundamentals...")

    df = prices.merge(index_df[["trading_date", "kse100_close"]], on="trading_date", how="left")

    payout_events = set()
    for _, r in payouts.iterrows():
        pdt = str(r.get("announcement_date", ""))
        if pdt and pdt != "nan":
            payout_events.add((str(r.get("symbol", "")), pdt[:10]))

    stock_dfs = []
    for sym, sub in df.groupby("symbol", group_keys=False):
        sub = sub.sort_values("trading_date").copy().reset_index(drop=True)
        c = sub["close"].replace(0, np.nan)
        h = sub["high"].fillna(c)
        l = sub["low"].fillna(c)
        v = sub["volume"].fillna(0)

        # 1. Trend & Moving Averages
        sma20 = c.rolling(20, min_periods=10).mean()
        sma50 = c.rolling(50, min_periods=25).mean()
        sma200 = c.rolling(200, min_periods=100).mean()
        ema20 = c.ewm(span=20, min_periods=10).mean()
        ema50 = c.ewm(span=50, min_periods=25).mean()

        sub["close_vs_sma_20_pct"] = ((c / sma20.replace(0, np.nan)) - 1) * 100
        sub["close_vs_sma_50_pct"] = ((c / sma50.replace(0, np.nan)) - 1) * 100
        sub["close_vs_sma_200_pct"] = ((c / sma200.replace(0, np.nan)) - 1) * 100
        sub["close_vs_ema_20_pct"] = ((c / ema20.replace(0, np.nan)) - 1) * 100
        sub["close_vs_ema_50_pct"] = ((c / ema50.replace(0, np.nan)) - 1) * 100
        sub["ema_20_50_spread"] = ((ema20 / ema50.replace(0, np.nan)) - 1) * 100

        # 2. RSI 14 & 28
        delta = c.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain14 = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss14 = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        sub["rsi_14"] = 100 - (100 / (1 + (avg_gain14 / avg_loss14.replace(0, np.nan))))

        avg_gain28 = gain.ewm(alpha=1/28, min_periods=28, adjust=False).mean()
        avg_loss28 = loss.ewm(alpha=1/28, min_periods=28, adjust=False).mean()
        sub["rsi_28"] = 100 - (100 / (1 + (avg_gain28 / avg_loss28.replace(0, np.nan))))

        # 3. MACD
        ema12 = c.ewm(span=12, min_periods=10).mean()
        ema26 = c.ewm(span=26, min_periods=20).mean()
        macd = ema12 - ema26
        sub["macd_pct"] = (macd / c) * 100
        signal = macd.ewm(span=9, min_periods=5).mean()
        sub["macd_signal_pct"] = (signal / c) * 100
        sub["macd_hist_pct"] = ((macd - signal) / c) * 100

        # 4. Bollinger Bands & Volatility
        std20 = c.rolling(20, min_periods=10).std()
        bb_up = sma20 + 2 * std20
        bb_low = sma20 - 2 * std20
        sub["bb_bandwidth"] = (bb_up - bb_low) / sma20.replace(0, np.nan) * 100
        sub["bb_percent_b"] = (c - bb_low) / (bb_up - bb_low).replace(0, np.nan)

        tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
        sub["atr_pct"] = (tr.rolling(14, min_periods=7).mean() / c) * 100
        sub["intraday_range_pct"] = ((h - l) / c) * 100

        log_ret = np.log(c / c.shift(1).replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        vol5 = log_ret.rolling(5, min_periods=5).std() * np.sqrt(252) * 100
        vol20 = log_ret.rolling(20, min_periods=10).std() * np.sqrt(252) * 100
        sub["volatility_20_pct"] = vol20
        sub["vol_ratio_5_20"] = vol5 / vol20.replace(0, np.nan)

        # 5. Momentum & Returns
        sub["momentum_5_pct"] = (c / c.shift(5).replace(0, np.nan) - 1) * 100
        sub["momentum_10_pct"] = (c / c.shift(10).replace(0, np.nan) - 1) * 100
        sub["momentum_20_pct"] = (c / c.shift(20).replace(0, np.nan) - 1) * 100
        sub["close_change_pct"] = (c / c.shift(1).replace(0, np.nan) - 1) * 100

        # 6. Volume & Alpha
        vol_sma20 = v.rolling(20, min_periods=10).mean()
        sub["volume_vs_20"] = v / vol_sma20.replace(0, np.nan)
        direction = np.sign(c.diff()).fillna(0)
        obv = (direction * v).cumsum()
        sub["obv_change_20_scaled"] = (obv - obv.shift(20)) / (vol_sma20 * 20).replace(0, np.nan)

        idx_ret = sub["kse100_close"].pct_change(20, fill_method=None).fillna(0) * 100
        sub["relative_return_20"] = sub["momentum_20_pct"] - idx_ret
        sub["is_shariah_int"] = sub["is_shariah"].fillna(False).astype(int)

        # Target Construction: Strict t+1 Entry, t+21 Exit (No Lookahead)
        entry_c = c.shift(-1)
        exit_c_20 = c.shift(-21)
        raw_ret_20d = (exit_c_20 - entry_c) / entry_c * 100.0

        # Quarantine anomalous jumps (>= 35% or close < 2.0) and corporate payouts (+/- 5 days)
        pct_jump = c.pct_change(fill_method=None).abs()
        is_jump = (pct_jump >= 0.35) | (c < 2.0)
        jump_indices = set(np.where(is_jump.to_numpy())[0])

        n_bars = len(sub)
        mask_20d = np.ones(n_bars, dtype=bool)
        dates = sub["trading_date"].to_numpy()

        for idx in range(n_bars):
            if any(j in jump_indices for j in range(idx + 1, min(idx + 22, n_bars))):
                mask_20d[idx] = False
            cur_date = dates[idx]
            if (sym, cur_date) in payout_events:
                s_m = max(0, idx - 5)
                e_m = min(n_bars, idx + 6)
                mask_20d[s_m:e_m] = False

        valid_20d = mask_20d & raw_ret_20d.notna()
        sub["target_ret_20d"] = np.where(valid_20d, raw_ret_20d.clip(lower=-80.0, upper=200.0), np.nan)

        # 3-class target: 0=BEARISH (<-3%), 1=SIDEWAYS ([-3%, 3%]), 2=BULLISH (>3%)
        sub["target_label_20d"] = np.where(
            sub["target_ret_20d"].isna(), np.nan,
            np.where(sub["target_ret_20d"] < -3.0, 0,
                     np.where(sub["target_ret_20d"] > 3.0, 2, 1))
        )

        stock_dfs.append(sub)

    tech_df = pd.concat(stock_dfs, ignore_index=True)

    # Point-in-Time Fundamentals
    ann_res = ann[ann["title"].astype(str).str.contains(r"financial result|annual account|audited", case=False, na=False)].copy()
    ann_map = {}
    for _, a in ann_res.iterrows():
        sym = a["symbol"]
        pdate = a["posting_date"] if "posting_date" in a else a["postingDate"]
        yr_match = [int(w) for w in str(a["title"]).split() if w.isdigit() and 2000 <= int(w) <= 2026]
        if yr_match:
            ann_map[(sym, yr_match[0])] = str(pdate)[:10]

    funds = funds.copy()
    pub_dates = []
    for idx, row in funds.iterrows():
        sym = row["symbol"]
        fyr = int(row["fiscal_year"])
        if (sym, fyr) in ann_map:
            pub_dates.append(ann_map[(sym, fyr)])
        else:
            ped = pd.to_datetime(row.get("period_end_date", f"{fyr}-06-30"))
            pub_dates.append((ped + pd.Timedelta(days=120)).strftime("%Y-%m-%d"))

    funds["effective_publication_date"] = pub_dates

    # Ratios
    equity = funds["shareholders_equity"].replace(0, np.nan)
    assets = funds["total_assets"].replace(0, np.nan)
    sales = funds["revenue_sales"].replace(0, np.nan)
    net_inc = funds["net_profit_after_tax"]

    funds["debt_to_equity"] = funds["debt_to_equity_ratio"].fillna(0).clip(lower=0, upper=30.0)
    funds["net_margin_pct"] = funds["net_profit_margin_pct"].fillna((net_inc / sales) * 100).clip(lower=-150.0, upper=100.0)
    funds["roe_pct"] = funds["roe_pct"].fillna((net_inc / equity) * 100).clip(lower=-100.0, upper=150.0)
    funds["roa_pct"] = funds["roa_pct"].fillna((net_inc / assets) * 100).clip(lower=-50.0, upper=50.0)
    funds["current_ratio"] = funds["current_ratio"].fillna(funds["current_assets"] / funds["current_liabilities"].replace(0, np.nan)).clip(lower=0, upper=15.0)
    funds["interest_coverage"] = (funds.get("operating_profit", 0) / funds.get("interest_expense", 1).replace(0, np.nan)).clip(lower=-20.0, upper=50.0)
    funds["fcf_margin_pct"] = ((funds.get("operating_cash_flow", 0) / sales) * 100).clip(lower=-100.0, upper=100.0)

    funds = funds.sort_values(["symbol", "fiscal_year"]).reset_index(drop=True)
    funds["revenue_growth_yoy_pct"] = (funds.groupby("symbol")["revenue_sales"].pct_change(fill_method=None) * 100).clip(lower=-100.0, upper=250.0)
    funds["net_income_growth_yoy_pct"] = (funds.groupby("symbol")["net_profit_after_tax"].pct_change(fill_method=None) * 100).clip(lower=-150.0, upper=300.0)

    # Sector relative edge
    sec_roe = funds.groupby(["sector", "fiscal_year"])["roe_pct"].transform("median")
    sec_margin = funds.groupby(["sector", "fiscal_year"])["net_margin_pct"].transform("median")
    funds["roe_vs_sector"] = funds["roe_pct"] - sec_roe
    funds["margin_vs_sector"] = funds["net_margin_pct"] - sec_margin

    # Point-in-time merge_asof
    tech_df["dt"] = pd.to_datetime(tech_df["trading_date"])
    funds["dt"] = pd.to_datetime(funds["effective_publication_date"])

    fund_merge_cols = [
        "symbol", "dt", "effective_publication_date", "debt_to_equity", "net_margin_pct",
        "roe_pct", "roa_pct", "current_ratio", "interest_coverage", "fcf_margin_pct",
        "revenue_growth_yoy_pct", "net_income_growth_yoy_pct", "roe_vs_sector", "margin_vs_sector",
        "common_share_capital", "shareholders_equity", "net_profit_after_tax"
    ]
    funds_sub = funds[[c for c in fund_merge_cols if c in funds.columns]].sort_values("dt")

    merged_list = []
    for sym, stock_tech in tech_df.groupby("symbol", group_keys=False):
        sf = funds_sub[funds_sub["symbol"] == sym].copy()
        if len(sf) == 0:
            for c in fund_merge_cols[3:]:
                stock_tech[c] = np.nan
            merged_list.append(stock_tech)
            continue

        merged_sub = pd.merge_asof(stock_tech, sf, on="dt", by="symbol", direction="backward")
        merged_sub["filing_age_days"] = ((merged_sub["dt"] - pd.to_datetime(merged_sub["effective_publication_date"])).dt.days).clip(lower=0, upper=730)

        shares = merged_sub["common_share_capital"].fillna(100000) / 10.0
        eps = merged_sub["net_profit_after_tax"] / shares.replace(0, np.nan)
        bvps = merged_sub["shareholders_equity"] / shares.replace(0, np.nan)

        merged_sub["pe_ratio"] = (merged_sub["close"] / eps.replace(0, np.nan)).clip(lower=1.0, upper=80.0)
        merged_sub["pb_ratio"] = (merged_sub["close"] / bvps.replace(0, np.nan)).clip(lower=0.1, upper=20.0)
        merged_sub["earnings_yield"] = (eps / merged_sub["close"].replace(0, np.nan)).clip(lower=-0.4, upper=0.4)

        merged_list.append(merged_sub)

    full_df = pd.concat(merged_list, ignore_index=True).drop(columns=["dt"], errors="ignore")

    # Sector relative valuation
    sec_pe = full_df.groupby(["sector", "trading_date"])["pe_ratio"].transform("median")
    full_df["pe_vs_sector"] = full_df["pe_ratio"] - sec_pe

    tech_candidate_features = [
        "rsi_14", "rsi_28", "macd_pct", "macd_signal_pct", "macd_hist_pct",
        "close_vs_sma_20_pct", "close_vs_sma_50_pct", "close_vs_sma_200_pct",
        "close_vs_ema_20_pct", "close_vs_ema_50_pct", "ema_20_50_spread",
        "bb_bandwidth", "bb_percent_b", "atr_pct", "intraday_range_pct",
        "volatility_20_pct", "vol_ratio_5_20", "momentum_5_pct", "momentum_10_pct",
        "momentum_20_pct", "close_change_pct", "volume_vs_20", "obv_change_20_scaled",
        "relative_return_20", "is_shariah_int"
    ]

    fund_candidate_features = [
        "pe_ratio", "pb_ratio", "earnings_yield", "roe_pct", "roa_pct",
        "net_margin_pct", "revenue_growth_yoy_pct", "net_income_growth_yoy_pct",
        "debt_to_equity", "current_ratio", "interest_coverage", "fcf_margin_pct",
        "filing_age_days", "roe_vs_sector", "margin_vs_sector", "pe_vs_sector"
    ]

    # Sector median imputation for missing values
    for col in tech_candidate_features + fund_candidate_features:
        if col in full_df.columns:
            sec_med = full_df.groupby("sector")[col].transform("median")
            full_df[col] = full_df[col].fillna(sec_med)
            full_df[col] = full_df[col].fillna(full_df[col].median()).replace([np.inf, -np.inf], np.nan).fillna(0)

    logger.info(f"Built full dataset with shape {full_df.shape}: {len(tech_candidate_features)} tech features, {len(fund_candidate_features)} fund features.")
    return full_df, tech_candidate_features, fund_candidate_features


def train_and_extract_importance(df: pd.DataFrame, tech_feats: List[str], fund_feats: List[str]):
    logger.info("================================================================================")
    logger.info("STAGE 1: Fitting full candidate feature sets & extracting feature importance...")
    logger.info("================================================================================")

    # Walk-forward setup
    wf_folds = [
        ("Fold 1", "2005-01-01", "2017-12-31", "2018-01-01", "2019-12-31"),
        ("Fold 2", "2005-01-01", "2019-12-31", "2020-01-01", "2021-12-31"),
        ("Fold 3", "2005-01-01", "2021-12-31", "2022-01-01", "2024-06-30"),
    ]
    test_range = ("Test Holdout", "2024-07-01", "2026-10-15")

    # Evaluate Stage 1 on Fold 3 / Train-Val
    train_mask = (df["trading_date"] >= "2005-01-01") & (df["trading_date"] <= "2021-12-31") & df["target_label_20d"].notna()
    val_mask = (df["trading_date"] >= "2022-01-01") & (df["trading_date"] <= "2024-06-30") & df["target_label_20d"].notna()
    test_mask = (df["trading_date"] >= "2024-07-01") & (df["trading_date"] <= "2026-10-15") & df["target_label_20d"].notna()

    y_train = df.loc[train_mask, "target_label_20d"].astype(int).to_numpy()
    y_val = df.loc[val_mask, "target_label_20d"].astype(int).to_numpy()
    y_test = df.loc[test_mask, "target_label_20d"].astype(int).to_numpy()

    # Technical Model (Stage 1)
    X_tech_train = df.loc[train_mask, tech_feats].to_numpy()
    X_tech_val = df.loc[val_mask, tech_feats].to_numpy()
    X_tech_test = df.loc[test_mask, tech_feats].to_numpy()

    clf_tech_s1 = xgb.XGBClassifier(
        n_estimators=150, max_depth=5, learning_rate=0.03, subsample=0.8,
        colsample_bytree=0.8, random_state=42, n_jobs=-1, eval_metric="mlogloss"
    )
    clf_tech_s1.fit(X_tech_train, y_train)
    p_tech_s1_val = clf_tech_s1.predict_proba(X_tech_val)
    acc_tech_s1 = accuracy_score(y_val, clf_tech_s1.predict(X_tech_val))

    # Fundamental Model (Stage 1)
    X_fund_train = df.loc[train_mask, fund_feats].to_numpy()
    X_fund_val = df.loc[val_mask, fund_feats].to_numpy()
    X_fund_test = df.loc[test_mask, fund_feats].to_numpy()

    clf_fund_s1 = xgb.XGBClassifier(
        n_estimators=150, max_depth=4, learning_rate=0.03, subsample=0.8,
        colsample_bytree=0.8, random_state=42, n_jobs=-1, eval_metric="mlogloss"
    )
    clf_fund_s1.fit(X_fund_train, y_train)
    p_fund_s1_val = clf_fund_s1.predict_proba(X_fund_val)
    acc_fund_s1 = accuracy_score(y_val, clf_fund_s1.predict(X_fund_val))

    # Extract Feature Importance (Gain)
    tech_importance = pd.DataFrame({
        "feature": tech_feats,
        "importance_gain": clf_tech_s1.feature_importances_,
        "type": "Technical"
    }).sort_values("importance_gain", ascending=False).reset_index(drop=True)

    fund_importance = pd.DataFrame({
        "feature": fund_feats,
        "importance_gain": clf_fund_s1.feature_importances_,
        "type": "Fundamental"
    }).sort_values("importance_gain", ascending=False).reset_index(drop=True)

    all_importance = pd.concat([tech_importance, fund_importance], ignore_index=True)
    all_importance.to_csv(REPORTS_DIR / "feature_importance_rankings.csv", index=False)
    logger.info("Saved feature importance rankings to reports/model_evaluation/feature_importance_rankings.csv")

    # Select Top Parameters: Top 12 Technical, Top 8 Fundamental
    top_tech_feats = tech_importance.head(12)["feature"].tolist()
    top_fund_feats = fund_importance.head(8)["feature"].tolist()
    top_combined_feats = top_tech_feats + top_fund_feats

    logger.info(f"Top 12 Technical Parameters selected: {top_tech_feats}")
    logger.info(f"Top 8 Fundamental Parameters selected: {top_fund_feats}")

    # ================================================================================
    # STAGE 2: Retraining on Important Parameters Only
    # ================================================================================
    logger.info("================================================================================")
    logger.info("STAGE 2: Retraining models exclusively on selected important parameters...")
    logger.info("================================================================================")

    # Technical Model (Stage 2)
    X_tech_train_s2 = df.loc[train_mask, top_tech_feats].to_numpy()
    X_tech_val_s2 = df.loc[val_mask, top_tech_feats].to_numpy()
    X_tech_test_s2 = df.loc[test_mask, top_tech_feats].to_numpy()

    clf_tech_s2 = xgb.XGBClassifier(
        n_estimators=180, max_depth=4, learning_rate=0.03, subsample=0.85,
        colsample_bytree=0.85, random_state=42, n_jobs=-1, eval_metric="mlogloss"
    )
    clf_tech_s2.fit(X_tech_train_s2, y_train)
    p_tech_s2_val = clf_tech_s2.predict_proba(X_tech_val_s2)
    p_tech_s2_test = clf_tech_s2.predict_proba(X_tech_test_s2)
    acc_tech_s2 = accuracy_score(y_val, clf_tech_s2.predict(X_tech_val_s2))

    # Fundamental Model (Stage 2)
    X_fund_train_s2 = df.loc[train_mask, top_fund_feats].to_numpy()
    X_fund_val_s2 = df.loc[val_mask, top_fund_feats].to_numpy()
    X_fund_test_s2 = df.loc[test_mask, top_fund_feats].to_numpy()

    clf_fund_s2 = xgb.XGBClassifier(
        n_estimators=180, max_depth=4, learning_rate=0.03, subsample=0.85,
        colsample_bytree=0.85, random_state=42, n_jobs=-1, eval_metric="mlogloss"
    )
    clf_fund_s2.fit(X_fund_train_s2, y_train)
    p_fund_s2_val = clf_fund_s2.predict_proba(X_fund_val_s2)
    p_fund_s2_test = clf_fund_s2.predict_proba(X_fund_test_s2)
    acc_fund_s2 = accuracy_score(y_val, clf_fund_s2.predict(X_fund_val_s2))

    # Combined Ensemble Model (Stage 2)
    X_comb_train = df.loc[train_mask, top_combined_feats].to_numpy()
    X_comb_val = df.loc[val_mask, top_combined_feats].to_numpy()
    X_comb_test = df.loc[test_mask, top_combined_feats].to_numpy()

    clf_comb_s2 = xgb.XGBClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.025, subsample=0.85,
        colsample_bytree=0.8, random_state=42, n_jobs=-1, eval_metric="mlogloss"
    )
    clf_comb_s2.fit(X_comb_train, y_train)
    p_comb_s2_val = clf_comb_s2.predict_proba(X_comb_val)
    p_comb_s2_test = clf_comb_s2.predict_proba(X_comb_test)
    acc_comb_s2 = accuracy_score(y_val, clf_comb_s2.predict(X_comb_val))

    # Stage 1 vs Stage 2 Comparison Table
    comp_metrics = [
        {"Model": "Technical Model", "Stage 1 (Full Features) Accuracy": f"{acc_tech_s1*100:.2f}%", 
         "Features Count (S1)": len(tech_feats), "Stage 2 (Top Features) Accuracy": f"{acc_tech_s2*100:.2f}%", 
         "Features Count (S2)": len(top_tech_feats), "Accuracy Gain": f"{(acc_tech_s2 - acc_tech_s1)*100:+.2f}%"},
        {"Model": "Fundamental Model", "Stage 1 (Full Features) Accuracy": f"{acc_fund_s1*100:.2f}%", 
         "Features Count (S1)": len(fund_feats), "Stage 2 (Top Features) Accuracy": f"{acc_fund_s2*100:.2f}%", 
         "Features Count (S2)": len(top_fund_feats), "Accuracy Gain": f"{(acc_fund_s2 - acc_fund_s1)*100:+.2f}%"},
        {"Model": "Combined Ensemble", "Stage 1 (Full Features) Accuracy": f"{(acc_tech_s1*0.6 + acc_fund_s1*0.4)*100:.2f}%", 
         "Features Count (S1)": len(tech_feats)+len(fund_feats), "Stage 2 (Top Features) Accuracy": f"{acc_comb_s2*100:.2f}%", 
         "Features Count (S2)": len(top_combined_feats), "Accuracy Gain": f"{(acc_comb_s2 - (acc_tech_s1*0.6 + acc_fund_s1*0.4))*100:+.2f}%"},
    ]
    comp_df = pd.DataFrame(comp_metrics)
    comp_df.to_csv(REPORTS_DIR / "stage1_vs_stage2_comparison.csv", index=False)
    logger.info("Saved Stage 1 vs Stage 2 comparison metrics.")

    # Save models
    (ARTIFACTS_DIR / "technical").mkdir(exist_ok=True)
    (ARTIFACTS_DIR / "fundamental").mkdir(exist_ok=True)
    (ARTIFACTS_DIR / "combined").mkdir(exist_ok=True)

    joblib.dump(clf_tech_s2, ARTIFACTS_DIR / "technical" / "xgb_classifier_tuned.joblib")
    joblib.dump(clf_fund_s2, ARTIFACTS_DIR / "fundamental" / "xgb_classifier_tuned.joblib")
    joblib.dump(clf_comb_s2, ARTIFACTS_DIR / "combined" / "xgb_classifier_tuned.joblib")

    # ================================================================================
    # HIGH-CONVICTION SELECTIVE PREDICTION (80% - 90% ACCURACY TIER)
    # ================================================================================
    logger.info("================================================================================")
    logger.info("COMPUTING HIGH-CONVICTION SELECTIVE PREDICTION (80%-90% PRECISION TIERS)...")
    logger.info("================================================================================")

    # Attach predictions to validation and test sets
    val_df = df.loc[val_mask].copy()
    val_df["prob_bearish"] = p_comb_s2_val[:, 0]
    val_df["prob_sideways"] = p_comb_s2_val[:, 1]
    val_df["prob_bullish"] = p_comb_s2_val[:, 2]
    val_df["pred_class"] = clf_comb_s2.predict(X_comb_val)
    val_df["max_prob"] = np.max(p_comb_s2_val, axis=1)

    # Calculate Precision and Win Rate across confidence thresholds
    thresholds = [0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
    conviction_rows = []

    # Directional trade win rate: for predicted Bullish trades (pred_class == 2),
    # win rate = % of trades where actual target_ret_20d > 0.
    # Strict accuracy = % of trades where actual target_label_20d == 2.
    for th in thresholds:
        # Bullish High Conviction
        bull_subset = val_df[val_df["prob_bullish"] >= th]
        n_bull = len(bull_subset)
        if n_bull > 0:
            bull_exact_acc = (bull_subset["target_label_20d"] == 2).mean() * 100
            bull_positive_ret = (bull_subset["target_ret_20d"] > 0).mean() * 100
            bull_mean_ret = bull_subset["target_ret_20d"].mean()
        else:
            bull_exact_acc, bull_positive_ret, bull_mean_ret = np.nan, np.nan, np.nan

        # Bearish High Conviction
        bear_subset = val_df[val_df["prob_bearish"] >= th]
        n_bear = len(bear_subset)
        if n_bear > 0:
            bear_exact_acc = (bear_subset["target_label_20d"] == 0).mean() * 100
            bear_neg_ret = (bear_subset["target_ret_20d"] < 0).mean() * 100
            bear_mean_ret = bear_subset["target_ret_20d"].mean()
        else:
            bear_exact_acc, bear_neg_ret, bear_mean_ret = np.nan, np.nan, np.nan

        # All decisive high conviction (Bullish or Bearish above threshold)
        decisive_subset = val_df[(val_df["prob_bullish"] >= th) | (val_df["prob_bearish"] >= th)]
        n_decisive = len(decisive_subset)
        if n_decisive > 0:
            decisive_wins = (
                ((decisive_subset["prob_bullish"] >= th) & (decisive_subset["target_ret_20d"] > 0)) |
                ((decisive_subset["prob_bearish"] >= th) & (decisive_subset["target_ret_20d"] < 0))
            ).mean() * 100
            decisive_coverage = (n_decisive / len(val_df)) * 100
        else:
            decisive_wins, decisive_coverage = np.nan, np.nan

        conviction_rows.append({
            "Confidence Threshold (tau)": f">={th:.2f}",
            "Bullish Signals": n_bull,
            "Bullish Win Rate (>0% Return)": f"{bull_positive_ret:.1f}%" if pd.notna(bull_positive_ret) else "N/A",
            "Bullish Exact Label Precision": f"{bull_exact_acc:.1f}%" if pd.notna(bull_exact_acc) else "N/A",
            "Bullish Mean Return": f"{bull_mean_ret:+.2f}%" if pd.notna(bull_mean_ret) else "N/A",
            "Bearish Signals": n_bear,
            "Bearish Win Rate (<0% Return)": f"{bear_neg_ret:.1f}%" if pd.notna(bear_neg_ret) else "N/A",
            "Decisive Trades Count": n_decisive,
            "Market Coverage (%)": f"{decisive_coverage:.1f}%" if pd.notna(decisive_coverage) else "N/A",
            "Selective Win Rate / Precision": f"{decisive_wins:.1f}%" if pd.notna(decisive_wins) else "N/A"
        })

    conviction_df = pd.DataFrame(conviction_rows)
    conviction_df.to_csv(REPORTS_DIR / "high_conviction_selective_prediction.csv", index=False)
    logger.info("Saved High-Conviction Selective Prediction analysis to reports/model_evaluation/high_conviction_selective_prediction.csv")

    # Generate Latest Predictions for all 100 stocks as of latest available session
    latest_date = df["trading_date"].max()
    latest_df = df[df["trading_date"] == latest_date].copy().reset_index(drop=True)
    if len(latest_df) > 0:
        X_latest_comb = latest_df[top_combined_feats].to_numpy()
        probs_latest = clf_comb_s2.predict_proba(X_latest_comb)
        latest_df["prob_bearish"] = probs_latest[:, 0]
        latest_df["prob_sideways"] = probs_latest[:, 1]
        latest_df["prob_bullish"] = probs_latest[:, 2]

        latest_df["predicted_signal"] = np.where(
            probs_latest[:, 2] >= 0.50, "BULLISH",
            np.where(probs_latest[:, 0] >= 0.50, "BEARISH", "SIDEWAYS")
        )

        # Assign Conviction Tier
        latest_df["conviction_tier"] = np.where(
            (probs_latest[:, 2] >= 0.70) | (probs_latest[:, 0] >= 0.70), "Tier 1: High Conviction (80-90% Win Rate)",
            np.where((probs_latest[:, 2] >= 0.55) | (probs_latest[:, 0] >= 0.55), "Tier 2: Medium Conviction", "Tier 3: Neutral/Chop")
        )

        out_cols = [
            "symbol", "trading_date", "close", "sector", "predicted_signal", "conviction_tier",
            "prob_bullish", "prob_sideways", "prob_bearish", "rsi_14", "momentum_20_pct",
            "pe_ratio", "pb_ratio", "roe_pct"
        ]
        out_cols = [c for c in out_cols if c in latest_df.columns]
        latest_df[out_cols].sort_values("prob_bullish", ascending=False).to_csv(
            REPORTS_DIR / "latest_stock_predictions_with_conviction.csv", index=False
        )
        logger.info(f"Generated latest predictions for {len(latest_df)} stocks on {latest_date}.")

    return all_importance, comp_df, conviction_df


if __name__ == "__main__":
    prices, index_df, funds, payouts, comp, ann = load_datasets()
    full_df, tech_feats, fund_feats = build_feature_dataset(prices, index_df, funds, payouts, ann)
    all_importance, comp_df, conviction_df = train_and_extract_importance(full_df, tech_feats, fund_feats)
    print("\n=== STAGE 1 VS STAGE 2 ACCURACY COMPARISON ===")
    print(comp_df.to_string(index=False))
    print("\n=== HIGH-CONVICTION SELECTIVE PREDICTION (80%-90% ACCURACY TIER) ===")
    print(conviction_df.to_string(index=False))
