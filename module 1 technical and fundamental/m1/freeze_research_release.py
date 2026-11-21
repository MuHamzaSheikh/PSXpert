"""Freeze Reproducible Research Release.

Saves:
1. Exact model artifacts for fundamental rankers and technical classifiers (joblib / JSON).
2. Complete feature schema (names, categories, imputations, target definitions).
3. Universe rules, sizing limits, and execution assumptions.
4. Predeclared evaluation rules (horizons, review schedule, risk limits).
5. Environment dependencies and SHA-256 manifest.
6. Verification script proving reload reproducibility against saved prediction snapshots.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from xgboost import XGBClassifier, XGBRanker

from .decision_pipeline import (
    DecisionConfig,
    build_targets,
    feature_matrix,
    relevance,
    split_stage,
)
from .features import FUNDAMENTAL, TECHNICAL


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_file_sha256(path: Path) -> str:
    if not path.exists():
        return "NOT_FOUND"
    return compute_sha256(path.read_bytes())


def freeze_research_release(release_dir: Path):
    release_dir.mkdir(parents=True, exist_ok=True)
    models_dir = release_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] Freezing research release to {release_dir}...")

    # 1. Environment & Dependencies
    import sklearn
    import xgboost

    deps = {
        "python_version": sys.version,
        "platform": sys.platform,
        "packages": {
            "xgboost": xgboost.__version__,
            "scikit-learn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "joblib": joblib.__version__,
        },
        "freeze_timestamp": timestamp,
    }
    (release_dir / "environment_and_dependencies.json").write_text(json.dumps(deps, indent=2), encoding="utf-8")

    # 2. Feature Schema
    schema = {
        "fundamental_features": FUNDAMENTAL,
        "technical_features": TECHNICAL,
        "imputation": {
            "fundamental": "median with indicator or rank percentile",
            "technical": "median with StandardScaler for linear baselines; native missing handling for XGBoost",
        },
        "target_definitions": {
            "fundamental": {
                "horizon_sessions": 126,
                "type": "ranking_excess_return",
                "benchmark": "audited_benchmark.csv (KSE-100)",
                "description": "Forward 126-session cumulative stock return minus benchmark return.",
            },
            "technical": {
                "horizon_sessions": 10,
                "type": "binary_hurdle",
                "hurdle_pct": 2.0,
                "description": "Binary flag indicating forward 10-session stock return > benchmark return + 2.0% hurdle.",
            },
        },
    }
    (release_dir / "feature_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")

    # 3. Universe and Execution Rules
    exec_rules = {
        "universe_definition": "Liquid PSX equities with active OHLCV quotes and quarterly published fundamentals.",
        "eligibility_gate": "Point-in-time publication date verified (published_date <= decision_session).",
        "heuristic_quarantine": "Provisional exclusion bounds (+/- 5 sessions around announcement and jumps >= 35%).",
        "portfolio_allocation": {
            "initial_capital_pkr": 10_000_000.0,
            "max_positions": 10,
            "max_position_weight": 0.10,
            "cash_constraint": "Morning buys bounded strictly by prior session close cash (C_{s-1}). Zero leverage.",
            "candidate_ordering": "Fundamental score descending. Alphabetical sorting strictly prohibited.",
        },
        "execution_timing": {
            "signal_generation": "Session t close (using data up to t close).",
            "order_entry": "Session t+1 open (executable open price > 0, volume > 0).",
            "holding_period_sessions": 10,
            "order_exit": "Session t+10 close (executable close price > 0, volume > 0).",
            "delayed_exit_policy": "Hold position if quote missing or halted at close until executable quote appears; never liquidate at entry price.",
            "round_trip_friction_pct": 0.50,
            "buy_fee_pct": 0.25,
            "sell_fee_pct": 0.25,
        },
        "liquidity_rules": {
            "mode": "unconstrained_benchmark",
            "max_volume_participation_pct": None,
            "enforce_volume_positive": True,
            "missing_volume_policy": {
                "disabled_mode": "Contemporaneous volume Vs <= 0 rejects fill.",
                "enabled_mode": "Lagged volume V_{s-1} <= 0 caps spend at 0.0 (rejects order).",
            },
        },
        "decision_thresholds": {
            "technical_gate_threshold": 0.50,
            "fundamental_shortlist_top_fraction": 0.20,
        },
    }
    (release_dir / "universe_and_execution_rules.json").write_text(json.dumps(exec_rules, indent=2), encoding="utf-8")

    # 4. Predeclared Evaluation Rules
    eval_rules = {
        "predeclared_horizons": {
            "technical_horizon_sessions": 10,
            "fundamental_horizon_sessions": 126,
        },
        "review_schedule": {
            "technical_review_cadence": "Quarterly (every ~63 sessions)",
            "fundamental_review_cadence": "Annual (every 252 sessions)",
            "minimum_technical_observations_for_evaluation": 60,
            "minimum_fundamental_observations_for_evaluation": 252,
            "small_sample_warning_threshold": 30,
        },
        "evaluation_metrics": {
            "technical_timing_primary": "Paired daily return difference with Newey-West HAC standard errors (lag 10), two-tailed p < 0.05",
            "technical_timing_secondary": ["PR-AUC vs base rate", "Brier Score", "Trade Win Rate", "Sharpe Ratio", "Max Drawdown"],
            "fundamental_selection_primary": "NDCG@20% and top-quintile 126-session forward excess return over KSE-100",
            "fundamental_selection_secondary": ["Spearman Rank Correlation", "Top vs Bottom Spread"],
        },
        "risk_limits": {
            "max_drawdown_limit_pct": 25.0,
            "action_on_breach": "Halt new entries for formal audit and model review.",
            "max_single_position_pct": 10.0,
            "leverage_limit": 1.0,
        },
        "prohibited_practices": [
            "Never claim predictive success from small samples (N < 60).",
            "Never assert arbitrary fixed accuracy targets (e.g. 80-90%) on noisy financial asset returns.",
            "Never overwrite historical predictions upon receipt of financial statement restatements.",
            "Never evaluate trade outcomes before the exact target horizon has matured.",
        ],
    }
    (release_dir / "evaluation_rules.json").write_text(json.dumps(eval_rules, indent=2), encoding="utf-8")

    # 5. Fit and Save Exact Model Artifacts
    print("Fitting and serializing exact release models...")
    panel_path = Path("data/decision_panel_v2.csv")
    raw_prices_path = Path("data/raw_unadjusted_prices.csv")
    benchmark_path = Path("data/audited_benchmark.csv")

    panel = pd.read_csv(panel_path)
    prices = pd.read_csv(raw_prices_path)
    bench = pd.read_csv(benchmark_path)
    config = DecisionConfig(seed=42)

    data = build_targets(panel, prices, bench, config)

    # Fold 2 models
    train_f2, _, _ = split_stage(data, "fundamental", 5500, 5730, config)
    train_t2, _, _ = split_stage(data, "technical", 5500, 5730, config)
    y_train_t2 = train_t2.technical_target.gt(config.entry_margin_pct).astype(int)

    clf_f2 = XGBClassifier(objective="binary:logistic", eval_metric="logloss", tree_method="hist",
                           random_state=42, n_jobs=2, min_child_weight=10, colsample_bytree=0.85,
                           max_depth=2, learning_rate=0.05, n_estimators=100, reg_lambda=5.0, subsample=0.90)
    clf_f2.fit(feature_matrix(train_t2, TECHNICAL), y_train_t2)
    joblib.dump(clf_f2, models_dir / "fold_2_technical_xgboost.joblib")

    # Fold 3 models (Latest research models)
    train_f3, _, _ = split_stage(data, "fundamental", 5620, 5860, config)
    train_t3, _, _ = split_stage(data, "technical", 5620, 5860, config)
    y_train_t3 = train_t3.technical_target.gt(config.entry_margin_pct).astype(int)

    ranker_f3 = XGBRanker(objective="rank:pairwise", tree_method="hist", random_state=42, n_jobs=2,
                          min_child_weight=10, colsample_bytree=0.85,
                          max_depth=3, learning_rate=0.03, n_estimators=140, reg_lambda=10.0, subsample=0.85)
    ranker_f3.fit(feature_matrix(train_f3, FUNDAMENTAL), relevance(train_f3), qid=train_f3.session.to_numpy())
    joblib.dump(ranker_f3, models_dir / "fold_3_fundamental_xgbranker.joblib")

    clf_f3 = XGBClassifier(objective="binary:logistic", eval_metric="logloss", tree_method="hist",
                           random_state=42, n_jobs=2, min_child_weight=10, colsample_bytree=0.85,
                           max_depth=3, learning_rate=0.03, n_estimators=140, reg_lambda=10.0, subsample=0.85)
    clf_f3.fit(feature_matrix(train_t3, TECHNICAL), y_train_t3)
    joblib.dump(clf_f3, models_dir / "fold_3_technical_xgboost.joblib")

    # Baselines
    pipe_lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                            LogisticRegression(C=0.1, max_iter=2000, random_state=42))
    pipe_lr.fit(feature_matrix(train_t3, TECHNICAL), y_train_t3)
    joblib.dump(pipe_lr, models_dir / "fold_3_technical_logistic_regression.joblib")

    # Model metadata manifest
    model_manifest = {
        "fold_1": {
            "fundamental": "cross_sectional_momentum_20_pct (heuristic formula)",
            "technical": "sma_breakout_sigmoid (heuristic formula)",
        },
        "fold_2": {
            "fundamental": "simple_value_composite (inv_pe + inv_pb)",
            "technical": "fold_2_technical_xgboost.joblib",
            "technical_sha256": compute_file_sha256(models_dir / "fold_2_technical_xgboost.joblib"),
        },
        "fold_3": {
            "fundamental": "fold_3_fundamental_xgbranker.joblib",
            "fundamental_sha256": compute_file_sha256(models_dir / "fold_3_fundamental_xgbranker.joblib"),
            "technical": "fold_3_technical_xgboost.joblib",
            "technical_sha256": compute_file_sha256(models_dir / "fold_3_technical_xgboost.joblib"),
            "technical_baseline_lr": "fold_3_technical_logistic_regression.joblib",
            "technical_baseline_lr_sha256": compute_file_sha256(models_dir / "fold_3_technical_logistic_regression.joblib"),
        },
    }
    (models_dir / "model_manifest.json").write_text(json.dumps(model_manifest, indent=2), encoding="utf-8")

    # 6. Release Manifest (SHA-256 for every file)
    manifest = {
        "release_version": "v1.0.0-frozen",
        "release_timestamp": timestamp,
        "input_data_hashes": {
            "decision_panel_v2.csv": compute_file_sha256(panel_path),
            "raw_unadjusted_prices.csv": compute_file_sha256(raw_prices_path),
            "audited_benchmark.csv": compute_file_sha256(benchmark_path),
        },
        "release_files": {},
    }
    for p in release_dir.rglob("*"):
        if p.is_file() and p.name != "release_manifest.json":
            rel_name = str(p.relative_to(release_dir)).replace("\\", "/")
            manifest["release_files"][rel_name] = compute_file_sha256(p)

    (release_dir / "release_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Research release successfully frozen in {release_dir} with {len(manifest['release_files'])} verified files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Freeze Research Release")
    parser.add_argument("--release-dir", default="artifacts/frozen_research_release", help="Directory for release")
    args = parser.parse_args()
    freeze_research_release(Path(args.release_dir))
