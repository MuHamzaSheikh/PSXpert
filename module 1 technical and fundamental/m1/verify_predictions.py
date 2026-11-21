"""Audit script to verify prediction equivalence and trace trade discrepancies.

Compares row-by-row:
1. Predictions (fundamental scores and technical probabilities)
2. Shortlist membership (top 20% fundamental stocks)
3. Technical signals (P >= 0.50 threshold)
between selection_timing_v2 and selection_timing_v3.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
from xgboost import XGBClassifier, XGBRanker
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

from .decision_pipeline import DecisionConfig, build_targets, split_stage, feature_matrix, relevance
from .features import FUNDAMENTAL, TECHNICAL


def audit_prediction_equivalence():
    panel_path = Path("data/decision_panel_v2.csv")
    raw_prices_path = Path("data/raw_unadjusted_prices.csv")
    benchmark_path = Path("data/audited_benchmark.csv")

    panel = pd.read_csv(panel_path)
    raw_prices = pd.read_csv(raw_prices_path)
    bench = pd.read_csv(benchmark_path)
    config = DecisionConfig(
        fundamental_horizon=126,
        technical_horizon=10,
        cost_pct=0.50,
        entry_margin_pct=2.0,
        top_fraction=0.20,
        entry_threshold=0.55,
        seed=42,
    )
    data = build_targets(panel, raw_prices, bench, config)

    folds = [
        (5380, 5600, 5730),
        (5500, 5730, 5860),
        (5620, 5860, 6000),
    ]

    report = {}

    for fold_idx, (v_start, t_start, t_end) in enumerate(folds):
        fold_id = f"fold_{fold_idx + 1}"
        test_sessions = sorted(data[data.session.between(t_start, t_end - 1)]["session"].unique())
        test_slice = data[data.session.isin(test_sessions)].copy()

        # 1. Fundamental Model in v2 vs v3
        train_f, valid_f, test_f = split_stage(data, "fundamental", v_start, t_start, config)
        test_f = test_f[test_f.session.lt(t_end)].copy()

        # In fold 1, both v2 and v3 used momentum
        # In fold 2, both v2 and v3 used value_composite
        # In fold 3, v2 used ranker_xgb[0] (max_depth=2, lr=0.01, n=160), v3 used (max_depth=3, lr=0.03, n=140)
        if fold_id == "fold_1":
            fund_score_v2 = pd.to_numeric(test_slice.get("momentum_20_pct", pd.Series(0.0, index=test_slice.index)), errors="coerce").fillna(0.0).to_numpy()
            fund_score_v3 = fund_score_v2.copy()
        elif fold_id == "fold_2":
            pe_s = pd.to_numeric(test_slice.get("pe_ratio", pd.Series(np.nan, index=test_slice.index)), errors="coerce")
            pb_s = pd.to_numeric(test_slice.get("pb_ratio", pd.Series(np.nan, index=test_slice.index)), errors="coerce")
            inv_pe_s = np.nan_to_num(np.where(pe_s.gt(0), 1.0 / pe_s, -1.0), nan=-1.0)
            inv_pb_s = np.nan_to_num(np.where(pb_s.gt(0), 1.0 / pb_s, -1.0), nan=-1.0)
            fund_score_v2 = inv_pe_s + inv_pb_s
            fund_score_v3 = fund_score_v2.copy()
        else:
            # Fold 3
            ranker_v2 = XGBRanker(objective="rank:pairwise", tree_method="hist", random_state=42, n_jobs=2,
                                  min_child_weight=10, colsample_bytree=0.85,
                                  max_depth=2, learning_rate=0.01, n_estimators=160, reg_lambda=10.0, subsample=0.85)
            ranker_v2.fit(feature_matrix(train_f, FUNDAMENTAL), relevance(train_f), qid=train_f.session.to_numpy())
            fund_score_v2 = ranker_v2.predict(feature_matrix(test_slice, FUNDAMENTAL))

            ranker_v3 = XGBRanker(objective="rank:pairwise", tree_method="hist", random_state=42, n_jobs=2,
                                  min_child_weight=10, colsample_bytree=0.85,
                                  max_depth=3, learning_rate=0.03, n_estimators=140, reg_lambda=10.0, subsample=0.85)
            ranker_v3.fit(feature_matrix(train_f, FUNDAMENTAL), relevance(train_f), qid=train_f.session.to_numpy())
            fund_score_v3 = ranker_v3.predict(feature_matrix(test_slice, FUNDAMENTAL))

        # Check fundamental score identity
        fund_diff = np.abs(fund_score_v2 - fund_score_v3).max()

        # Shortlist comparison
        test_slice["fund_pctile_v2"] = test_slice.assign(score=fund_score_v2).groupby("session")["score"].rank(pct=True, method="average")
        test_slice["fund_pctile_v3"] = test_slice.assign(score=fund_score_v3).groupby("session")["score"].rank(pct=True, method="average")
        shortlist_v2 = test_slice["fund_pctile_v2"].gt(1.0 - config.top_fraction)
        shortlist_v3 = test_slice["fund_pctile_v3"].gt(1.0 - config.top_fraction)
        shortlist_mismatches = int((shortlist_v2 != shortlist_v3).sum())

        # 2. Technical Model in v2 vs v3
        train_t, valid_t, test_t = split_stage(data, "technical", v_start, t_start, config)
        test_t = test_t[test_t.session.lt(t_end)].copy()
        y_train_t = train_t.technical_target.gt(config.entry_margin_pct).astype(int)

        if fold_id == "fold_1":
            # Both v2 and v3 used sma_breakout
            dev = pd.to_numeric(test_slice.get("close_vs_sma_20_pct", pd.Series(0.0, index=test_slice.index)), errors="coerce").fillna(0.0)
            tech_prob_v2 = 1.0 / (1.0 + np.exp(-0.1 * dev.to_numpy()))
            tech_prob_v3 = tech_prob_v2.copy()
        elif fold_id == "fold_2":
            # v2 used max_depth=2, lr=0.01, n=160
            clf_v2 = XGBClassifier(objective="binary:logistic", eval_metric="logloss", tree_method="hist",
                                   random_state=42, n_jobs=2, min_child_weight=10, colsample_bytree=0.85,
                                   max_depth=2, learning_rate=0.01, n_estimators=160, reg_lambda=10.0, subsample=0.85)
            clf_v2.fit(feature_matrix(train_t, TECHNICAL), y_train_t)
            tech_prob_v2 = clf_v2.predict_proba(feature_matrix(test_slice, TECHNICAL))[:, 1]

            # v3 used max_depth=2, lr=0.05, n=100
            clf_v3 = XGBClassifier(objective="binary:logistic", eval_metric="logloss", tree_method="hist",
                                   random_state=42, n_jobs=2, min_child_weight=10, colsample_bytree=0.85,
                                   max_depth=2, learning_rate=0.05, n_estimators=100, reg_lambda=5.0, subsample=0.90)
            clf_v3.fit(feature_matrix(train_t, TECHNICAL), y_train_t)
            tech_prob_v3 = clf_v3.predict_proba(feature_matrix(test_slice, TECHNICAL))[:, 1]
        else:
            # Fold 3
            # v2 used max_depth=2, lr=0.01, n=160
            clf_v2 = XGBClassifier(objective="binary:logistic", eval_metric="logloss", tree_method="hist",
                                   random_state=42, n_jobs=2, min_child_weight=10, colsample_bytree=0.85,
                                   max_depth=2, learning_rate=0.01, n_estimators=160, reg_lambda=10.0, subsample=0.85)
            clf_v2.fit(feature_matrix(train_t, TECHNICAL), y_train_t)
            tech_prob_v2 = clf_v2.predict_proba(feature_matrix(test_slice, TECHNICAL))[:, 1]

            # v3 used max_depth=3, lr=0.03, n=140
            clf_v3 = XGBClassifier(objective="binary:logistic", eval_metric="logloss", tree_method="hist",
                                   random_state=42, n_jobs=2, min_child_weight=10, colsample_bytree=0.85,
                                   max_depth=3, learning_rate=0.03, n_estimators=140, reg_lambda=10.0, subsample=0.85)
            clf_v3.fit(feature_matrix(train_t, TECHNICAL), y_train_t)
            tech_prob_v3 = clf_v3.predict_proba(feature_matrix(test_slice, TECHNICAL))[:, 1]

        signals_v2 = tech_prob_v2 >= 0.50
        signals_v3 = tech_prob_v3 >= 0.50
        signal_mismatches = int((signals_v2 != signals_v3).sum())

        report[fold_id] = {
            "total_test_rows": len(test_slice),
            "fundamental_max_abs_diff": float(fund_diff),
            "shortlist_identical": bool(shortlist_mismatches == 0),
            "shortlist_mismatches_count": shortlist_mismatches,
            "technical_max_abs_diff": float(np.abs(tech_prob_v2 - tech_prob_v3).max()),
            "signals_v2_count": int(signals_v2.sum()),
            "signals_v3_count": int(signals_v3.sum()),
            "signals_identical": bool(signal_mismatches == 0),
            "signal_mismatches_count": signal_mismatches,
            "v2_max_tech_prob": float(tech_prob_v2.max()),
            "v3_max_tech_prob": float(tech_prob_v3.max()),
        }

    return report


if __name__ == "__main__":
    rep = audit_prediction_equivalence()
    print(json.dumps(rep, indent=2))
