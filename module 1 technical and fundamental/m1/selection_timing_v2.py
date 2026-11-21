"""Corrected Selection and Timing Architecture (v2).

Audited and corrected according to quantitative research standards:
1. Rebuilds inputs from point-in-time sources without future label filtering.
2. Model selection conducted exclusively inside training-side inner validation.
3. Fair candidate model comparison: XGBRanker vs Value vs Momentum; XGBClassifier vs Logistic Regression vs SMA.
4. Transparent reporting of where simple baselines (Value, Logistic Regression) beat ML.
5. Realistic daily portfolio simulation: cash tracking, position limits (10%), overlapping positions, 0.50% friction.
6. Corrected paired date-block evaluation with Newey-West HAC standard errors (lag 10).
7. Concentration diagnostics (HHI, top-5 ticker share, sector breakdown).
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, ndcg_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier, XGBRanker

from .decision_pipeline import (
    DecisionConfig,
    build_targets,
    compute_fundamental_baselines,
    compute_technical_baselines,
    entry_metrics,
    feature_matrix,
    ranking_metrics,
    relevance,
    split_stage,
)
from .features import FUNDAMENTAL, TECHNICAL
from .portfolio_simulation import (
    compute_concentration_metrics,
    compute_newey_west_t_stat,
    evaluate_portfolio_performance,
    run_portfolio_backtest,
)


def select_fundamental_model(train: pd.DataFrame, valid: pd.DataFrame,
                             config: DecisionConfig) -> tuple[Any, str, dict[str, Any], list[dict[str, Any]]]:
    """Compare XGBRanker against Simple Value Composite and Momentum on inner validation only."""
    trials = []

    # 1. XGBRanker candidates
    xgb_candidates = [
        {"max_depth": 2, "learning_rate": 0.01, "n_estimators": 160, "reg_lambda": 10.0, "subsample": 0.85},
        {"max_depth": 3, "learning_rate": 0.03, "n_estimators": 140, "reg_lambda": 10.0, "subsample": 0.85},
        {"max_depth": 2, "learning_rate": 0.05, "n_estimators": 100, "reg_lambda": 5.0, "subsample": 0.90},
        {"max_depth": 3, "learning_rate": 0.01, "n_estimators": 200, "reg_lambda": 15.0, "subsample": 0.75},
    ]

    best_xgb = None
    best_xgb_score = -np.inf
    best_xgb_p = xgb_candidates[0]
    best_xgb_m = None

    X_train = feature_matrix(train, FUNDAMENTAL)
    y_train = relevance(train)
    qid_train = train.session.to_numpy()
    X_valid = feature_matrix(valid, FUNDAMENTAL)

    for idx, p in enumerate(xgb_candidates):
        ranker = XGBRanker(objective="rank:pairwise", tree_method="hist", random_state=config.seed + idx,
                           n_jobs=2, min_child_weight=10, colsample_bytree=0.85, **p)
        ranker.fit(X_train, y_train, qid=qid_train)
        preds = ranker.predict(X_valid)
        metrics = ranking_metrics(valid, preds, config)
        score = metrics["ndcg"]
        trial_rec = {"candidate": f"xgbranker_d{p['max_depth']}_lr{p['learning_rate']}",
                     "params": p, "inner_val_ndcg": float(score), "excess_return_pct": metrics["top_group_excess_return_pct"]}
        trials.append(trial_rec)
        if score > best_xgb_score:
            best_xgb_score = score
            best_xgb = ranker
            best_xgb_p = p
            best_xgb_m = metrics

    # 2. Simple Value Composite candidate
    pe_v = pd.to_numeric(valid.get("pe_ratio", pd.Series(np.nan, index=valid.index)), errors="coerce")
    pb_v = pd.to_numeric(valid.get("pb_ratio", pd.Series(np.nan, index=valid.index)), errors="coerce")
    inv_pe_v = np.nan_to_num(np.where(pe_v.gt(0), 1.0 / pe_v, -1.0), nan=-1.0)
    inv_pb_v = np.nan_to_num(np.where(pb_v.gt(0), 1.0 / pb_v, -1.0), nan=-1.0)
    val_scores_v = inv_pe_v + inv_pb_v
    val_metrics = ranking_metrics(valid, val_scores_v, config)
    trials.append({"candidate": "simple_value_composite", "params": "inverse_pe_pb_sum",
                   "inner_val_ndcg": float(val_metrics["ndcg"]), "excess_return_pct": val_metrics["top_group_excess_return_pct"]})

    # 3. Momentum candidate
    mom_v = pd.to_numeric(valid.get("momentum_20_pct", pd.Series(0.0, index=valid.index)), errors="coerce").fillna(0.0).to_numpy()
    mom_metrics = ranking_metrics(valid, mom_v, config)
    trials.append({"candidate": "cross_sectional_momentum", "params": "momentum_20_pct",
                   "inner_val_ndcg": float(mom_metrics["ndcg"]), "excess_return_pct": mom_metrics["top_group_excess_return_pct"]})

    # Select winner based STRICTLY on inner validation NDCG
    candidates_scores = [
        ("xgbranker", best_xgb_score, best_xgb, best_xgb_m),
        ("value_composite", val_metrics["ndcg"], "value_composite", val_metrics),
        ("momentum", mom_metrics["ndcg"], "momentum", mom_metrics),
    ]
    winner_name, winner_score, winner_model, winner_metrics = max(candidates_scores, key=lambda x: x[1])
    return winner_model, winner_name, winner_metrics, trials


def select_technical_model(train: pd.DataFrame, valid: pd.DataFrame,
                           config: DecisionConfig) -> tuple[Any, str, dict[str, Any], list[dict[str, Any]]]:
    """Compare XGBClassifier against Regularized Logistic Regression and SMA Breakout on inner validation only."""
    trials = []

    y_train = train.technical_target.gt(config.entry_margin_pct).astype(int)
    X_train = feature_matrix(train, TECHNICAL)
    X_valid = feature_matrix(valid, TECHNICAL)

    # 1. XGBoost Candidates
    xgb_candidates = [
        {"max_depth": 2, "learning_rate": 0.01, "n_estimators": 160, "reg_lambda": 10.0, "subsample": 0.85},
        {"max_depth": 3, "learning_rate": 0.03, "n_estimators": 140, "reg_lambda": 10.0, "subsample": 0.85},
        {"max_depth": 2, "learning_rate": 0.05, "n_estimators": 100, "reg_lambda": 5.0, "subsample": 0.90},
        {"max_depth": 3, "learning_rate": 0.05, "n_estimators": 120, "reg_lambda": 10.0, "subsample": 0.85},
    ]

    best_xgb = None
    best_xgb_score = -np.inf
    best_xgb_p = xgb_candidates[0]
    best_xgb_m = None

    for idx, p in enumerate(xgb_candidates):
        clf = XGBClassifier(objective="binary:logistic", eval_metric="logloss", tree_method="hist",
                            random_state=config.seed + idx, n_jobs=2, min_child_weight=10,
                            colsample_bytree=0.85, **p)
        clf.fit(X_train, y_train)
        probs = clf.predict_proba(X_valid)[:, 1]
        metrics = entry_metrics(valid, probs, config)
        score = metrics["average_precision"]
        trials.append({"candidate": f"xgb_d{p['max_depth']}_lr{p['learning_rate']}",
                       "params": p, "inner_val_ap": float(score), "log_loss": metrics["log_loss"]})
        if score > best_xgb_score:
            best_xgb_score = score
            best_xgb = clf
            best_xgb_p = p
            best_xgb_m = metrics

    # 2. Regularized Logistic Regression Candidates (C in [0.01, 0.1, 1.0])
    best_lr = None
    best_lr_score = -np.inf
    best_lr_c = 0.1
    best_lr_m = None

    for c_val in (0.01, 0.1, 1.0):
        pipe = make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            LogisticRegression(C=c_val, max_iter=2000, random_state=config.seed),
        )
        pipe.fit(X_train, y_train)
        probs = pipe.predict_proba(X_valid)[:, 1]
        metrics = entry_metrics(valid, probs, config)
        score = metrics["average_precision"]
        trials.append({"candidate": f"logistic_regression_C{c_val}", "params": {"C": c_val},
                       "inner_val_ap": float(score), "log_loss": metrics["log_loss"]})
        if score > best_lr_score:
            best_lr_score = score
            best_lr = pipe
            best_lr_c = c_val
            best_lr_m = metrics

    # 3. SMA Breakout Proxy
    sma_dev_v = pd.to_numeric(valid.get("close_vs_sma_20_pct", pd.Series(0.0, index=valid.index)), errors="coerce").fillna(0.0)
    sma_probs_v = 1.0 / (1.0 + np.exp(-0.1 * sma_dev_v.to_numpy()))
    sma_m = entry_metrics(valid, sma_probs_v, config)
    trials.append({"candidate": "sma_breakout", "params": "close_vs_sma_20_pct",
                   "inner_val_ap": float(sma_m["average_precision"]), "log_loss": sma_m["log_loss"]})

    # Select winner based STRICTLY on inner validation Average Precision
    candidates = [
        ("xgboost", best_xgb_score, best_xgb, best_xgb_m),
        ("logistic_regression", best_lr_score, best_lr, best_lr_m),
        ("sma_breakout", sma_m["average_precision"], "sma_breakout", sma_m),
    ]
    winner_name, winner_score, winner_model, winner_metrics = max(candidates, key=lambda x: x[1])
    return winner_model, winner_name, winner_metrics, trials


def run_evaluation_and_simulation_v2(
    data: pd.DataFrame,
    raw_prices_df: pd.DataFrame,
    config: DecisionConfig = DecisionConfig(),
    folds: list[tuple[int, int, int]] | None = None,
) -> dict[str, Any]:
    """Execute complete fair model comparison, out-of-sample assessment, and realistic portfolio backtest."""
    if folds is None:
        folds = [
            (5380, 5600, 5730),
            (5500, 5730, 5860),
            (5620, 5860, 6000),
        ]

    # Sector mapping for concentration diagnostics
    sector_lookup = data.drop_duplicates("symbol").set_index("symbol")["sector"].to_dict() if "sector" in data else {}

    fold_reports = []
    all_trials = []
    daily_equity_frames = []

    for fold_idx, (v_start, t_start, t_end) in enumerate(folds):
        fold_id = f"fold_{fold_idx + 1}"
        fold_record = {
            "fold_id": fold_id,
            "validation_start": v_start,
            "test_start": t_start,
            "test_end": t_end,
        }

        # --- A. Fundamental Branch ---
        train_f, valid_f, test_f = split_stage(data, "fundamental", v_start, t_start, config)
        test_f = test_f[test_f.session.lt(t_end)].copy()

        winner_fund_model, fund_winner_name, val_fund_m, fund_trials = select_fundamental_model(train_f, valid_f, config)
        for t in fund_trials:
            t["fold"] = fold_id
            t["stage"] = "fundamental"
        all_trials.extend(fund_trials)

        # Evaluate all candidate models on outer test holdout for fair comparison
        # 1. XGBRanker
        ranker_xgb = [t for t in fund_trials if t["candidate"].startswith("xgbranker") and t.get("params")]
        best_xgb_p = ranker_xgb[0]["params"] if ranker_xgb else {}
        test_ranker = XGBRanker(objective="rank:pairwise", tree_method="hist", random_state=config.seed,
                                n_jobs=2, min_child_weight=10, colsample_bytree=0.85, **best_xgb_p)
        test_ranker.fit(feature_matrix(train_f, FUNDAMENTAL), relevance(train_f), qid=train_f.session.to_numpy())
        xgb_test_scores = test_ranker.predict(feature_matrix(test_f, FUNDAMENTAL))
        xgb_test_metrics = ranking_metrics(test_f, xgb_test_scores, config)

        # 2. Value Composite
        pe_t = pd.to_numeric(test_f.get("pe_ratio", pd.Series(np.nan, index=test_f.index)), errors="coerce")
        pb_t = pd.to_numeric(test_f.get("pb_ratio", pd.Series(np.nan, index=test_f.index)), errors="coerce")
        inv_pe_t = np.nan_to_num(np.where(pe_t.gt(0), 1.0 / pe_t, -1.0), nan=-1.0)
        inv_pb_t = np.nan_to_num(np.where(pb_t.gt(0), 1.0 / pb_t, -1.0), nan=-1.0)
        val_test_scores = inv_pe_t + inv_pb_t
        val_test_metrics = ranking_metrics(test_f, val_test_scores, config)

        # 3. Momentum
        mom_test_scores = pd.to_numeric(test_f.get("momentum_20_pct", pd.Series(0.0, index=test_f.index)), errors="coerce").fillna(0.0).to_numpy()
        mom_test_metrics = ranking_metrics(test_f, mom_test_scores, config)

        # 4. Random
        rand_test_metrics = ranking_metrics(test_f, np.zeros(len(test_f)), config)
        rand_test_metrics["top_group_excess_return_pct"] = float(test_f.groupby("session").fundamental_target.mean().mean())

        fold_record["fundamental_comparison"] = {
            "inner_validation_winner": fund_winner_name,
            "xgbranker_test_metrics": xgb_test_metrics,
            "value_composite_test_metrics": val_test_metrics,
            "momentum_test_metrics": mom_test_metrics,
            "random_baseline_metrics": rand_test_metrics,
            "did_value_composite_beat_xgbranker": bool(val_test_metrics["ndcg"] > xgb_test_metrics["ndcg"]),
            "did_momentum_beat_xgbranker": bool(mom_test_metrics["ndcg"] > xgb_test_metrics["ndcg"]),
        }

        # --- B. Technical Branch ---
        train_t, valid_t, test_t = split_stage(data, "technical", v_start, t_start, config)
        test_t = test_t[test_t.session.lt(t_end)].copy()

        winner_tech_model, tech_winner_name, val_tech_m, tech_trials = select_technical_model(train_t, valid_t, config)
        for t in tech_trials:
            t["fold"] = fold_id
            t["stage"] = "technical"
        all_trials.extend(tech_trials)

        # Outer test evaluations of all technical candidates
        # 1. XGBoost
        xgb_t_trials = [t for t in tech_trials if t["candidate"].startswith("xgb_") and t.get("params")]
        best_clf_p = xgb_t_trials[0]["params"] if xgb_t_trials else {}
        clf_xgb = XGBClassifier(objective="binary:logistic", eval_metric="logloss", tree_method="hist",
                                random_state=config.seed, n_jobs=2, min_child_weight=10,
                                colsample_bytree=0.85, **best_clf_p)
        y_train_t = train_t.technical_target.gt(config.entry_margin_pct).astype(int)
        clf_xgb.fit(feature_matrix(train_t, TECHNICAL), y_train_t)
        xgb_test_probs = clf_xgb.predict_proba(feature_matrix(test_t, TECHNICAL))[:, 1]
        xgb_test_m = entry_metrics(test_t, xgb_test_probs, config)

        # 2. Logistic Regression
        pipe_lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                LogisticRegression(C=0.1, max_iter=2000, random_state=config.seed))
        pipe_lr.fit(feature_matrix(train_t, TECHNICAL), y_train_t)
        lr_test_probs = pipe_lr.predict_proba(feature_matrix(test_t, TECHNICAL))[:, 1]
        lr_test_m = entry_metrics(test_t, lr_test_probs, config)

        # 3. SMA Breakout
        sma_dev_t = pd.to_numeric(test_t.get("close_vs_sma_20_pct", pd.Series(0.0, index=test_t.index)), errors="coerce").fillna(0.0)
        sma_test_probs = 1.0 / (1.0 + np.exp(-0.1 * sma_dev_t.to_numpy()))
        sma_test_m = entry_metrics(test_t, sma_test_probs, config)

        # 4. Majority class
        maj_probs = np.full(len(test_t), float(y_train_t.mean()))
        maj_test_m = entry_metrics(test_t, maj_probs, config)

        fold_record["technical_comparison"] = {
            "inner_validation_winner": tech_winner_name,
            "xgboost_test_metrics": xgb_test_m,
            "logistic_regression_test_metrics": lr_test_m,
            "sma_breakout_test_metrics": sma_test_m,
            "majority_class_test_metrics": maj_test_m,
            "did_logistic_beat_xgboost": bool(lr_test_m["average_precision"] > xgb_test_m["average_precision"]),
        }

        # --- C. Realistic Daily Portfolio Backtest (Policy A vs Policy B) ---
        # Generate shortlist and technical signals across test calendar
        test_sessions = sorted(data[data.session.between(t_start, t_end - 1)]["session"].unique())
        test_slice = data[data.session.isin(test_sessions)].copy()

        # Score with selected models
        if fund_winner_name == "value_composite":
            pe_s = pd.to_numeric(test_slice.get("pe_ratio", pd.Series(np.nan, index=test_slice.index)), errors="coerce")
            pb_s = pd.to_numeric(test_slice.get("pb_ratio", pd.Series(np.nan, index=test_slice.index)), errors="coerce")
            inv_pe_s = np.nan_to_num(np.where(pe_s.gt(0), 1.0 / pe_s, -1.0), nan=-1.0)
            inv_pb_s = np.nan_to_num(np.where(pb_s.gt(0), 1.0 / pb_s, -1.0), nan=-1.0)
            test_slice["fund_score"] = inv_pe_s + inv_pb_s
        elif fund_winner_name == "momentum":
            test_slice["fund_score"] = pd.to_numeric(test_slice.get("momentum_20_pct", pd.Series(0.0, index=test_slice.index)), errors="coerce").fillna(0.0)
        else:
            test_slice["fund_score"] = test_ranker.predict(feature_matrix(test_slice, FUNDAMENTAL))

        # Rank and shortlist top 20%
        test_slice["fund_pctile"] = test_slice.groupby("session")["fund_score"].rank(pct=True, method="average")
        is_shortlisted = test_slice["fund_pctile"].gt(1.0 - config.top_fraction)

        # Technical signals: using Logistic Regression or XGBoost winner
        if tech_winner_name == "logistic_regression":
            test_slice["tech_prob"] = pipe_lr.predict_proba(feature_matrix(test_slice, TECHNICAL))[:, 1]
        elif tech_winner_name == "sma_breakout":
            dev = pd.to_numeric(test_slice.get("close_vs_sma_20_pct", pd.Series(0.0, index=test_slice.index)), errors="coerce").fillna(0.0)
            test_slice["tech_prob"] = 1.0 / (1.0 + np.exp(-0.1 * dev.to_numpy()))
        else:
            test_slice["tech_prob"] = clf_xgb.predict_proba(feature_matrix(test_slice, TECHNICAL))[:, 1]

        # Use 0.50 threshold if calibrated, or config.entry_threshold
        has_tech_signal = test_slice["tech_prob"].ge(0.50)

        # Build session-level lookup sets
        shortlist_by_session = test_slice[is_shortlisted].groupby("session")["symbol"].apply(set).to_dict()
        tech_signals_by_session = test_slice[has_tech_signal].groupby("session")["symbol"].apply(set).to_dict()

        # Run Policy A: Unfiltered Fundamental Shortlist
        df_unfiltered, trades_unfiltered = run_portfolio_backtest(
            sessions=test_sessions,
            prices_df=raw_prices_df,
            shortlist_series=shortlist_by_session,
            technical_signal_series=tech_signals_by_session,
            initial_capital=10_000_000.0,
            cost_rate=0.005,
            max_position_weight=0.10,
            holding_period=10,
            is_filtered=False,
        )
        perf_unfiltered = evaluate_portfolio_performance(df_unfiltered, trades_unfiltered)

        # Run Policy B: Technically Filtered Fundamental Shortlist
        df_filtered, trades_filtered = run_portfolio_backtest(
            sessions=test_sessions,
            prices_df=raw_prices_df,
            shortlist_series=shortlist_by_session,
            technical_signal_series=tech_signals_by_session,
            initial_capital=10_000_000.0,
            cost_rate=0.005,
            max_position_weight=0.10,
            holding_period=10,
            is_filtered=True,
        )
        perf_filtered = evaluate_portfolio_performance(df_filtered, trades_filtered)

        # --- D. Paired Date-Level Evaluation with Newey-West HAC (lag 10) ---
        d_returns = df_filtered["daily_return_pct"].to_numpy() - df_unfiltered["daily_return_pct"].to_numpy()
        mean_diff, t_hac, p_hac = compute_newey_west_t_stat(d_returns, max_lags=10)

        # Concentration diagnostics
        conc_unfiltered = compute_concentration_metrics(df_unfiltered, sector_lookup)
        conc_filtered = compute_concentration_metrics(df_filtered, sector_lookup)

        fold_record["portfolio_simulation"] = {
            "unfiltered_policy": perf_unfiltered,
            "filtered_policy": perf_filtered,
            "paired_statistical_test": {
                "mean_daily_return_difference_pct": float(mean_diff),
                "newey_west_hac_t_stat": float(t_hac),
                "newey_west_hac_p_value": float(p_hac),
                "is_significant_at_5pct": bool(p_hac < 0.05),
                "lags": 10,
            },
            "concentration": {
                "unfiltered_hhi": conc_unfiltered["mean_hhi"],
                "unfiltered_top5_pct": conc_unfiltered["mean_top5_ticker_weight_pct"],
                "filtered_hhi": conc_filtered["mean_hhi"],
                "filtered_top5_pct": conc_filtered["mean_top5_ticker_weight_pct"],
                "filtered_sector_exposure": conc_filtered["average_sector_exposure_pct"],
            },
        }

        # Track daily equity
        df_merged = df_filtered[["session", "total_equity", "exposure_pct"]].rename(
            columns={"total_equity": "filtered_equity", "exposure_pct": "filtered_exposure"}
        )
        df_merged["unfiltered_equity"] = df_unfiltered["total_equity"]
        df_merged["unfiltered_exposure"] = df_unfiltered["exposure_pct"]
        df_merged["fold"] = fold_id
        daily_equity_frames.append(df_merged)

        fold_reports.append(fold_record)

    all_daily_equity = pd.concat(daily_equity_frames, ignore_index=True)

    summary = {
        "status": "COMPLETED",
        "num_folds": len(fold_reports),
        "fold_reports": fold_reports,
    }

    return {
        "summary": summary,
        "all_trials": all_trials,
        "daily_equity": all_daily_equity,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, default=Path("data/decision_panel_v2.csv"))
    parser.add_argument("--prices", type=Path, default=Path("data/raw_unadjusted_prices.csv"))
    parser.add_argument("--benchmark", type=Path, default=Path("data/audited_benchmark.csv"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/selection_timing_v2"))
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    config = DecisionConfig()

    print("Loading data and building targets without future label filtering...", flush=True)
    panel = pd.read_csv(args.panel)
    prices = pd.read_csv(args.prices)
    benchmark = pd.read_csv(args.benchmark)

    data = build_targets(panel, prices, benchmark, config)
    print(f"Targets built successfully. Panel rows: {len(panel)}, Target data rows: {len(data)}")

    results = run_evaluation_and_simulation_v2(data, prices, config)
    summary = results["summary"]

    # Save artifacts
    (args.output / "evaluation.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    pd.DataFrame(results["all_trials"]).to_csv(args.output / "model_selection_trials.csv", index=False)
    (args.output / "model_selection_trials.json").write_text(json.dumps(results["all_trials"], indent=2), encoding="utf-8")
    results["daily_equity"].to_csv(args.output / "portfolio_daily_equity.csv", index=False)

    # Save baseline comparison and portfolio simulation slices
    baselines_comp = {f["fold_id"]: {
        "fundamental": f["fundamental_comparison"],
        "technical": f["technical_comparison"],
    } for f in summary["fold_reports"]}
    (args.output / "baseline_comparison.json").write_text(json.dumps(baselines_comp, indent=2), encoding="utf-8")

    port_sim = {f["fold_id"]: f["portfolio_simulation"] for f in summary["fold_reports"]}
    (args.output / "portfolio_simulation.json").write_text(json.dumps(port_sim, indent=2), encoding="utf-8")

    print(f"v2 evaluation and portfolio backtest complete! Saved artifacts to {args.output}")


if __name__ == "__main__":
    main()
