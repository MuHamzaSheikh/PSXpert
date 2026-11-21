"""Rerun of Selection and Timing Architecture (v3) with Institutional Chronological Simulator.

Preserves selection_timing_v2 completely and writes all results to artifacts/selection_timing_v3.
Isolates simulator corrections using the exact frozen models and policies without retuning.

Features:
1. Strict chronological execution: next-open entry, morning cash bounds, no afternoon funding of morning buys.
2. Removal of fabricated execution prices: suspended stocks held until quote resumes; stale valuations tracked.
3. Exact target alignment: signal at t, entry at t+1 open, exit at t+10 close.
4. Fundamental rank preservation: scarce slots allocated by fundamental score descending, never alphabetically.
5. Order-level accounting ledger: all buys, sells, fees, and boundary turnover tracked.
6. Causal execution: retrospective quarantine does not block live trades; liquidity constraints declared.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
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
from .portfolio_engine import (
    compute_newey_west_t_stat,
    evaluate_chronological_performance,
    run_chronological_portfolio_backtest,
)


def run_evaluation_and_simulation_v3(
    data: pd.DataFrame,
    prices_with_volume: pd.DataFrame,
    config: DecisionConfig = DecisionConfig(),
    folds: list[tuple[int, int, int]] | None = None,
) -> dict[str, Any]:
    """Execute v3 evaluation isolating chronological simulator corrections on frozen models."""
    if folds is None:
        folds = [
            (5380, 5600, 5730),
            (5500, 5730, 5860),
            (5620, 5860, 6000),
        ]

    sector_lookup = data.drop_duplicates("symbol").set_index("symbol")["sector"].to_dict() if "sector" in data else {}

    fold_reports = []
    all_daily_equity = []
    unresolved_all = {}
    order_ledgers_all = {}

    for fold_idx, (v_start, t_start, t_end) in enumerate(folds):
        fold_id = f"fold_{fold_idx + 1}"
        fold_record = {
            "fold_id": fold_id,
            "validation_start": v_start,
            "test_start": t_start,
            "test_end": t_end,
        }

        # --- A. Fundamental Branch (Frozen Model Selection) ---
        train_f, valid_f, test_f = split_stage(data, "fundamental", v_start, t_start, config)
        test_f = test_f[test_f.session.lt(t_end)].copy()

        # Frozen winner assignment matching v2 inner validation:
        # Fold 1: momentum
        # Fold 2: value_composite
        # Fold 3: xgbranker (d=3, lr=0.03, n=140, reg_lambda=10.0, subsample=0.85)
        if fold_id == "fold_1":
            fund_winner_name = "momentum"
        elif fold_id == "fold_2":
            fund_winner_name = "value_composite"
        else:
            fund_winner_name = "xgbranker"

        # Fit XGBRanker for outer comparison and Fold 3
        ranker_params = {"max_depth": 3, "learning_rate": 0.03, "n_estimators": 140, "reg_lambda": 10.0, "subsample": 0.85}
        test_ranker = XGBRanker(objective="rank:pairwise", tree_method="hist", random_state=config.seed,
                                n_jobs=2, min_child_weight=10, colsample_bytree=0.85, **ranker_params)
        test_ranker.fit(feature_matrix(train_f, FUNDAMENTAL), relevance(train_f), qid=train_f.session.to_numpy())
        xgb_test_scores = test_ranker.predict(feature_matrix(test_f, FUNDAMENTAL))
        xgb_test_metrics = ranking_metrics(test_f, xgb_test_scores, config)

        # Baseline: Value Composite
        pe_t = pd.to_numeric(test_f.get("pe_ratio", pd.Series(np.nan, index=test_f.index)), errors="coerce")
        pb_t = pd.to_numeric(test_f.get("pb_ratio", pd.Series(np.nan, index=test_f.index)), errors="coerce")
        inv_pe_t = np.nan_to_num(np.where(pe_t.gt(0), 1.0 / pe_t, -1.0), nan=-1.0)
        inv_pb_t = np.nan_to_num(np.where(pb_t.gt(0), 1.0 / pb_t, -1.0), nan=-1.0)
        val_test_scores = inv_pe_t + inv_pb_t
        val_test_metrics = ranking_metrics(test_f, val_test_scores, config)

        # Baseline: Momentum
        mom_test_scores = pd.to_numeric(test_f.get("momentum_20_pct", pd.Series(0.0, index=test_f.index)), errors="coerce").fillna(0.0).to_numpy()
        mom_test_metrics = ranking_metrics(test_f, mom_test_scores, config)

        # Baseline: Random
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

        # --- B. Technical Branch (Frozen Model Selection) ---
        train_t, valid_t, test_t = split_stage(data, "technical", v_start, t_start, config)
        test_t = test_t[test_t.session.lt(t_end)].copy()

        # Frozen winner assignment matching v2 inner validation:
        # Fold 1: sma_breakout
        # Fold 2: xgboost (d=2, lr=0.05, n=100, reg_lambda=5.0, subsample=0.90)
        # Fold 3: xgboost (d=3, lr=0.03, n=140, reg_lambda=10.0, subsample=0.85)
        if fold_id == "fold_1":
            tech_winner_name = "sma_breakout"
            xgb_p = {"max_depth": 2, "learning_rate": 0.01, "n_estimators": 160, "reg_lambda": 10.0, "subsample": 0.85}
        elif fold_id == "fold_2":
            tech_winner_name = "xgboost"
            xgb_p = {"max_depth": 2, "learning_rate": 0.05, "n_estimators": 100, "reg_lambda": 5.0, "subsample": 0.90}
        else:
            tech_winner_name = "xgboost"
            xgb_p = {"max_depth": 3, "learning_rate": 0.03, "n_estimators": 140, "reg_lambda": 10.0, "subsample": 0.85}

        # Target for technical training
        y_train_t = train_t.technical_target.gt(config.entry_margin_pct).astype(int)

        # Fit XGBoost Classifier
        clf_xgb = XGBClassifier(objective="binary:logistic", eval_metric="logloss", tree_method="hist",
                                random_state=config.seed, n_jobs=2, min_child_weight=10, colsample_bytree=0.85, **xgb_p)
        clf_xgb.fit(feature_matrix(train_t, TECHNICAL), y_train_t)
        xgb_test_probs = clf_xgb.predict_proba(feature_matrix(test_t, TECHNICAL))[:, 1]
        xgb_tech_metrics = entry_metrics(test_t, xgb_test_probs, config)

        # Baseline: Logistic Regression
        from sklearn.impute import SimpleImputer
        lr_c = 0.01 if fold_id in ["fold_1", "fold_3"] else 1.0
        pipe_lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                LogisticRegression(C=lr_c, max_iter=2000, random_state=config.seed))
        pipe_lr.fit(feature_matrix(train_t, TECHNICAL), y_train_t)
        lr_test_probs = pipe_lr.predict_proba(feature_matrix(test_t, TECHNICAL))[:, 1]
        lr_tech_metrics = entry_metrics(test_t, lr_test_probs, config)

        # Baseline: SMA Breakout
        sma_dev_test = pd.to_numeric(test_t.get("close_vs_sma_20_pct", pd.Series(0.0, index=test_t.index)), errors="coerce").fillna(0.0)
        sma_test_probs = 1.0 / (1.0 + np.exp(-0.1 * sma_dev_test.to_numpy()))
        sma_tech_metrics = entry_metrics(test_t, sma_test_probs, config)

        # Baseline: Majority Class
        majority_prior = float(y_train_t.mean())
        maj_probs = np.full(len(test_t), majority_prior)
        maj_tech_metrics = entry_metrics(test_t, maj_probs, config)

        fold_record["technical_comparison"] = {
            "inner_validation_winner": tech_winner_name,
            "xgboost_test_metrics": xgb_tech_metrics,
            "logistic_regression_test_metrics": lr_tech_metrics,
            "sma_breakout_test_metrics": sma_tech_metrics,
            "majority_class_test_metrics": maj_tech_metrics,
            "did_logistic_beat_xgboost": bool(lr_tech_metrics["average_precision"] > xgb_tech_metrics["average_precision"]),
        }

        # --- C. Multi-Asset Portfolio Simulation with Chronological Engine ---
        test_sessions = sorted(data[data.session.between(t_start, t_end - 1)]["session"].unique())
        test_slice = data[data.session.isin(test_sessions)].copy()

        # Score fundamental model
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

        # Technical probabilities
        if tech_winner_name == "logistic_regression":
            test_slice["tech_prob"] = pipe_lr.predict_proba(feature_matrix(test_slice, TECHNICAL))[:, 1]
        elif tech_winner_name == "sma_breakout":
            dev = pd.to_numeric(test_slice.get("close_vs_sma_20_pct", pd.Series(0.0, index=test_slice.index)), errors="coerce").fillna(0.0)
            test_slice["tech_prob"] = 1.0 / (1.0 + np.exp(-0.1 * dev.to_numpy()))
        else:
            test_slice["tech_prob"] = clf_xgb.predict_proba(feature_matrix(test_slice, TECHNICAL))[:, 1]

        has_tech_signal = test_slice["tech_prob"].ge(0.50)

        # Build candidate shortlists with fundamental ranking PRESERVED:
        # For each session, list of (symbol, fund_score) sorted by fund_score descending
        candidate_shortlists: dict[int, list[tuple[str, float]]] = {}
        for s, group in test_slice[is_shortlisted].groupby("session"):
            sorted_g = group.sort_values("fund_score", ascending=False)
            candidate_shortlists[s] = list(zip(sorted_g["symbol"], sorted_g["fund_score"]))

        # Build technical signal lookup
        technical_signals: dict[int, set[str]] = (
            test_slice[has_tech_signal].groupby("session")["symbol"].apply(set).to_dict()
        )

        # Run Policy A: Unfiltered Shortlist
        res_unfiltered = run_chronological_portfolio_backtest(
            sessions=test_sessions,
            prices_df=prices_with_volume,
            candidate_shortlists=candidate_shortlists,
            technical_signals=technical_signals,
            initial_capital=10_000_000.0,
            cost_rate=0.005,
            max_position_weight=0.10,
            holding_period=10,
            is_filtered=False,
            max_volume_participation_pct=None,  # Declared unconstrained benchmark liquidity
            enforce_volume_positive=True,
        )

        # Run Policy B: Technically Filtered Shortlist
        res_filtered = run_chronological_portfolio_backtest(
            sessions=test_sessions,
            prices_df=prices_with_volume,
            candidate_shortlists=candidate_shortlists,
            technical_signals=technical_signals,
            initial_capital=10_000_000.0,
            cost_rate=0.005,
            max_position_weight=0.10,
            holding_period=10,
            is_filtered=True,
            max_volume_participation_pct=None,
            enforce_volume_positive=True,
        )

        perf_unfiltered = res_unfiltered["performance_metrics"]
        perf_filtered = res_filtered["performance_metrics"]

        # Paired Date-Block Evaluation via Newey-West HAC (lag 10)
        daily_u = res_unfiltered["daily_equity"]["daily_return_pct"].to_numpy()
        daily_f = res_filtered["daily_equity"]["daily_return_pct"].to_numpy()
        diffs = daily_f - daily_u
        mean_d, t_stat, p_val = compute_newey_west_t_stat(diffs, max_lags=10)

        paired_test = {
            "mean_daily_return_difference_pct": float(mean_d),
            "newey_west_hac_t_stat": float(t_stat),
            "newey_west_hac_p_value": float(p_val),
            "is_significant_at_5pct": bool(p_val < 0.05),
            "lags": 10,
        }

        # Concentration metrics
        # Compute HHI from daily positions
        hhis_u, hhis_f = [], []
        top5_u, top5_f = [], []
        sector_exp = {}

        for row in res_unfiltered["daily_equity"].itertuples():
            pos_v = row.position_values
            if row.holdings_value > 0 and pos_v:
                w = np.array([v / row.holdings_value for v in pos_v.values()])
                hhis_u.append(float(np.sum(w ** 2) * 10_000))
                top5_u.append(float(np.sum(sorted(w, reverse=True)[:5]) * 100.0))

        for row in res_filtered["daily_equity"].itertuples():
            pos_v = row.position_values
            if row.holdings_value > 0 and pos_v:
                w = np.array([v / row.holdings_value for v in pos_v.values()])
                hhis_f.append(float(np.sum(w ** 2) * 10_000))
                top5_f.append(float(np.sum(sorted(w, reverse=True)[:5]) * 100.0))
                for sym, val in pos_v.items():
                    sec = sector_lookup.get(sym, "OTHER")
                    sector_exp[sec] = sector_exp.get(sec, 0.0) + (val / row.total_equity)

        n_days = max(1, len(res_filtered["daily_equity"]))
        avg_sector_exposure = {sec: float((v / n_days) * 100.0) for sec, v in sector_exp.items()}

        concentration = {
            "unfiltered_hhi": float(np.mean(hhis_u)) if hhis_u else 0.0,
            "unfiltered_top5_pct": float(np.mean(top5_u)) if top5_u else 0.0,
            "filtered_hhi": float(np.mean(hhis_f)) if hhis_f else 0.0,
            "filtered_top5_pct": float(np.mean(top5_f)) if top5_f else 0.0,
            "filtered_sector_exposure": dict(sorted(avg_sector_exposure.items(), key=lambda x: x[1], reverse=True)),
        }

        fold_record["portfolio_simulation"] = {
            "unfiltered_policy": perf_unfiltered,
            "filtered_policy": perf_filtered,
            "paired_statistical_test": paired_test,
            "concentration": concentration,
        }
        fold_reports.append(fold_record)

        # Store daily equity time-series
        eq_u = res_unfiltered["daily_equity"].rename(columns=lambda c: f"unfiltered_{c}")
        eq_f = res_filtered["daily_equity"].rename(columns=lambda c: f"filtered_{c}")
        merged_eq = pd.concat([eq_u, eq_f], axis=1)
        merged_eq["fold"] = fold_id
        merged_eq["session"] = res_unfiltered["daily_equity"]["session"]
        all_daily_equity.append(merged_eq)

        # Store order ledgers
        order_ledgers_all[f"{fold_id}_unfiltered"] = res_unfiltered["order_ledger"]
        order_ledgers_all[f"{fold_id}_filtered"] = res_filtered["order_ledger"]

        # Store unresolved positions
        unresolved_all[fold_id] = {
            "unfiltered": res_unfiltered["unresolved_positions"],
            "filtered": res_filtered["unresolved_positions"],
        }

    df_all_equity = pd.concat(all_daily_equity, ignore_index=True)

    baseline_comparison = {f["fold_id"]: {
        "fundamental": f["fundamental_comparison"],
        "technical": f["technical_comparison"],
    } for f in fold_reports}

    portfolio_sim_results = {f["fold_id"]: f["portfolio_simulation"] for f in fold_reports}

    return {
        "fold_reports": fold_reports,
        "daily_equity": df_all_equity,
        "portfolio_simulation": portfolio_sim_results,
        "baseline_comparison": baseline_comparison,
        "order_ledgers": order_ledgers_all,
        "unresolved_positions": unresolved_all,
    }


def main():
    parser = argparse.ArgumentParser(description="Run Selection & Timing Architecture v3")
    parser.add_argument("--out-dir", default="artifacts/selection_timing_v3", help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading point-in-time panel and market data...")
    panel_path = Path("data/decision_panel_v2.csv")
    raw_prices_path = Path("data/raw_unadjusted_prices.csv")
    benchmark_path = Path("data/audited_benchmark.csv")

    panel = pd.read_csv(panel_path)
    raw_prices = pd.read_csv(raw_prices_path)
    bench = pd.read_csv(benchmark_path)

    # Merge volume into raw_prices for the simulator
    prices_with_vol = pd.merge(
        raw_prices,
        panel[["symbol", "session", "volume"]],
        on=["symbol", "session"],
        how="left",
    )
    prices_with_vol["open"] = prices_with_vol["adjusted_open"]
    prices_with_vol["close"] = prices_with_vol["adjusted_close"]

    config = DecisionConfig(
        fundamental_horizon=126,
        technical_horizon=10,
        cost_pct=0.50,
        entry_margin_pct=2.0,
        top_fraction=0.20,
        entry_threshold=0.55,
        seed=42,
    )

    print("Building target labels for model fitting...")
    data = build_targets(panel, raw_prices, bench, config)
    print(f"Targets built successfully. Panel rows: {len(data)}")

    print("Running v3 evaluation and institutional chronological simulation...")
    res = run_evaluation_and_simulation_v3(
        data=data,
        prices_with_volume=prices_with_vol,
        config=config,
    )

    # Save artifacts
    print(f"Saving artifacts to {out_dir}...")
    def json_default(obj):
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(out_dir / "evaluation.json", "w") as f:
        json.dump({"status": "COMPLETED", "num_folds": len(res["fold_reports"]), "fold_reports": res["fold_reports"]}, f, indent=2, default=json_default)

    with open(out_dir / "portfolio_simulation.json", "w") as f:
        json.dump(res["portfolio_simulation"], f, indent=2, default=json_default)

    with open(out_dir / "baseline_comparison.json", "w") as f:
        json.dump(res["baseline_comparison"], f, indent=2, default=json_default)

    with open(out_dir / "unresolved_positions.json", "w") as f:
        json.dump(res["unresolved_positions"], f, indent=2, default=json_default)

    res["daily_equity"].to_csv(out_dir / "portfolio_daily_equity.csv", index=False)

    for ledger_name, df_ledger in res["order_ledgers"].items():
        df_ledger.to_csv(out_dir / f"order_ledger_{ledger_name}.csv", index=False)

    print("v3 evaluation and portfolio simulation complete!")


if __name__ == "__main__":
    main()
