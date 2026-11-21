"""Separate stock selection and entry timing research pipeline.

Inputs are explicitly audited point-in-time features and price series; see
DECISION_PIPELINE.md. Existing v1/v2/v3 models and APIs are not modified.
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

from .features import FUNDAMENTAL, TECHNICAL


@dataclass(frozen=True)
class DecisionConfig:
    fundamental_horizon: int = 126
    technical_horizon: int = 10
    embargo: int = 5
    cost_pct: float = 0.5
    entry_margin_pct: float = 2.0
    top_fraction: float = 0.2
    entry_threshold: float = 0.6
    max_filing_age_days: int = 550
    seed: int = 42

    def __post_init__(self):
        if not (self.fundamental_horizon > self.technical_horizon >= 1
                and self.embargo >= 0 and np.isfinite(self.cost_pct)
                and self.cost_pct >= 0 and np.isfinite(self.entry_margin_pct)
                and self.entry_margin_pct >= 0 and 0 < self.top_fraction <= 1
                and 0 < self.entry_threshold < 1 and self.max_filing_age_days > 0):
            raise ValueError("Invalid decision configuration")


def feature_matrix(frame: pd.DataFrame, names: list[str]) -> pd.DataFrame:
    return frame[names].apply(pd.to_numeric, errors="raise").replace(
        [np.inf, -np.inf], np.nan)


def validate_panel(panel: pd.DataFrame, config: DecisionConfig) -> pd.DataFrame:
    required = {"symbol", "session", "prediction_timestamp", "available_from_timestamp",
                *FUNDAMENTAL, *TECHNICAL}
    if missing := required - set(panel):
        raise ValueError(f"Missing panel fields: {sorted(missing)}")
    frame = panel.copy()
    if frame.duplicated(["symbol", "session"]).any():
        raise ValueError("Duplicate symbol/session features")
    if frame[["symbol", "session", "prediction_timestamp"]].isna().any().any():
        raise ValueError("Missing panel keys or prediction timestamp")
    if not pd.api.types.is_integer_dtype(frame.session):
        raise ValueError("session must be an integer global market-session ID")
    for name in ("prediction_timestamp", "available_from_timestamp"):
        for value in frame[name].dropna():
            if pd.Timestamp(value).tzinfo is None:
                raise ValueError(f"{name} must include a timezone")
        frame[name] = pd.to_datetime(frame[name], utc=True)
    has_financials = feature_matrix(frame, FUNDAMENTAL).notna().any(axis=1)
    age = (frame.prediction_timestamp - frame.available_from_timestamp).dt.total_seconds() / 86400
    if (has_financials & (age.isna() | age.lt(0))).any():
        raise ValueError("Fundamentals lack an eligible publication timestamp")
    frame["fundamental_eligible"] = has_financials & age.between(0, config.max_filing_age_days)
    frame["technical_eligible"] = feature_matrix(frame, TECHNICAL).notna().any(axis=1)
    return frame.sort_values(["session", "symbol"]).reset_index(drop=True)


def build_targets(panel: pd.DataFrame, prices: pd.DataFrame, benchmark: pd.DataFrame,
                  config: DecisionConfig = DecisionConfig()) -> pd.DataFrame:
    """Exact global-session joins: never shift over a suspended stock's missing bars.

    price_valid certifies upstream corporate-action/price audit. An invalid or
    missing bar anywhere in a target window excludes that label, not the stock
    from inference. Both horizons are newly constructed, never reused v2 labels.
    """
    frame = validate_panel(panel, config)
    prices = prices.copy()
    benchmark = benchmark.copy()
    if not {"symbol", "session", "adjusted_open", "adjusted_close", "price_valid"} <= set(prices):
        raise ValueError("Prices need symbol, session, adjusted_open, adjusted_close, price_valid")
    if not {"session", "adjusted_close", "price_valid"} <= set(benchmark):
        raise ValueError("Benchmark needs session, adjusted_close, price_valid")
    if prices.duplicated(["symbol", "session"]).any() or benchmark.session.duplicated().any():
        raise ValueError("Duplicate price keys")
    sessions = np.sort(benchmark.session.unique())
    if len(sessions) == 0 or not np.array_equal(sessions, np.arange(sessions[0], sessions[-1] + 1)):
        raise ValueError("Benchmark must supply a contiguous global market-session calendar")
    if not frame.session.isin(sessions).all() or not prices.session.isin(sessions).all():
        raise ValueError("Panel/prices use sessions outside the benchmark calendar")
    for source in (prices, benchmark):
        if not pd.api.types.is_integer_dtype(source.session) or source.session.isna().any():
            raise ValueError("Price session IDs must be integers")
        if source.price_valid.isna().any() or not source.price_valid.isin([True, False]).all():
            raise ValueError("price_valid must contain explicit booleans")
    prices = prices.set_index(["symbol", "session"])
    benchmark = benchmark.set_index("session").reindex(sessions)
    bclose = benchmark.adjusted_close
    bok = benchmark.price_valid.eq(True) & np.isfinite(bclose) & bclose.gt(0)
    parts = []
    for symbol, rows in frame.groupby("symbol", sort=False):
        if symbol not in prices.index.get_level_values(0):
            continue
        bars = prices.loc[symbol].reindex(sessions)
        good = bars.price_valid.eq(True)
        for col in ("adjusted_open", "adjusted_close"):
            good &= np.isfinite(bars[col]) & bars[col].gt(0)
        rows = rows.copy()
        for stage, horizon in (("fundamental", config.fundamental_horizon),
                               ("technical", config.technical_horizon)):
            valid = good.rolling(horizon + 1).sum().shift(-horizon).eq(horizon + 1)
            if stage == "fundamental":
                valid &= bok.rolling(horizon + 1).sum().shift(-horizon).eq(horizon + 1)
                target = 100 * (bars.adjusted_close.shift(-horizon) / bars.adjusted_close
                                - bclose.shift(-horizon) / bclose)
            else:
                target = 100 * (bars.adjusted_close.shift(-horizon)
                                / bars.adjusted_open.shift(-1) - 1) - config.cost_pct
            rows[f"{stage}_target"] = rows.session.map(target.where(valid))
            rows[f"{stage}_target_session"] = rows.session + horizon
        parts.append(rows)
    if not parts:
        raise ValueError("No panel symbols have prices")
    return pd.concat(parts, ignore_index=True).sort_values(["session", "symbol"])


def split_stage(data: pd.DataFrame, stage: str, validation_start: int,
                test_start: int, config: DecisionConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if validation_start >= test_start:
        raise ValueError("Validation must precede test")
    eligible = data[data[f"{stage}_eligible"] & data[f"{stage}_target"].notna()].copy()
    end = eligible[f"{stage}_target_session"]
    train = eligible[end.lt(validation_start - config.embargo)]
    valid = eligible[eligible.session.ge(validation_start) & end.lt(test_start - config.embargo)]
    test = eligible[eligible.session.ge(test_start)]
    if any(part.empty for part in (train, valid, test)):
        raise ValueError(f"Insufficient {stage} history after horizon purge and embargo")
    return train.copy(), valid.copy(), test.copy()


def relevance(frame: pd.DataFrame) -> np.ndarray:
    return np.minimum(4, np.floor(frame.groupby("session").fundamental_target.rank(
        pct=True, method="average").to_numpy() * 5)).astype(int)


def ranking_metrics(frame: pd.DataFrame, scores: np.ndarray, config: DecisionConfig) -> dict[str, Any]:
    data = frame.assign(score=scores, relevance=relevance(frame))
    ndcg, excess = [], []
    for _, group in data.groupby("session"):
        if len(group) < 2:
            continue
        k = max(1, int(np.ceil(len(group) * config.top_fraction)))
        ndcg.append(ndcg_score([group.relevance], [group.score], k=k))
        excess.append(group.nlargest(k, "score").fundamental_target.mean())
    if not ndcg:
        raise ValueError("Ranking requires at least two stocks per decision date")
    return {
        "ndcg": float(np.mean(ndcg)),
        "top_group_excess_return_pct": float(np.mean(excess)),
        "dates": len(ndcg),
        "rows": len(frame),
    }


def entry_metrics(frame: pd.DataFrame, probability: np.ndarray, config: DecisionConfig) -> dict[str, Any]:
    y = frame.technical_target.gt(config.entry_margin_pct).astype(int)
    if y.nunique() < 2:
        raise ValueError("Technical evaluation requires both entry outcome classes")
    selected = np.asarray(probability) >= config.entry_threshold
    brier = float(brier_score_loss(y, probability))
    return {
        "average_precision": float(average_precision_score(y, probability)),
        "log_loss": float(log_loss(y, probability, labels=[0, 1])),
        "brier_score": brier,
        "positive_rate": float(y.mean()),
        "coverage": float(selected.mean()),
        "entry_precision": float(y[selected].mean()) if selected.any() else None,
        "mean_selected_net_return_pct": float(frame.loc[selected, "technical_target"].mean())
        if selected.any() else None,
        "signals": int(selected.sum()),
        "rows": len(frame),
    }


# ==============================================================================
# BASELINES
# ==============================================================================

def compute_fundamental_baselines(train: pd.DataFrame, test: pd.DataFrame, config: DecisionConfig) -> dict[str, Any]:
    """Compute benchmark baselines for fundamental ranking:

    1. Uniform random / expected benchmark
    2. Cross-sectional price momentum (momentum_20_pct)
    3. Simple value composite (composite rank of PE and PB)
    """
    # 1. Random / expected
    random_metrics = ranking_metrics(test, np.zeros(len(test)), config)
    random_metrics["top_group_excess_return_pct"] = float(test.groupby("session").fundamental_target.mean().mean())

    # 2. Cross-sectional momentum (using momentum_20_pct)
    mom_col = "momentum_20_pct"
    if mom_col in test:
        mom_scores = test[mom_col].fillna(0).to_numpy()
        mom_metrics = ranking_metrics(test, mom_scores, config)
    else:
        mom_metrics = None

    # 3. Simple Value Composite (PE and PB)
    pe = pd.to_numeric(test.get("pe_ratio", pd.Series(np.nan, index=test.index)), errors="coerce")
    pb = pd.to_numeric(test.get("pb_ratio", pd.Series(np.nan, index=test.index)), errors="coerce")

    # Invert positive valuation ratios: cheaper stocks have higher 1/P
    inv_pe = np.where(pe.gt(0), 1.0 / pe, -1.0)
    inv_pb = np.where(pb.gt(0), 1.0 / pb, -1.0)
    inv_pe = np.nan_to_num(inv_pe, nan=-1.0)
    inv_pb = np.nan_to_num(inv_pb, nan=-1.0)
    val_scores = inv_pe + inv_pb
    value_metrics = ranking_metrics(test, val_scores, config)

    return {
        "random_baseline": random_metrics,
        "momentum_baseline": mom_metrics,
        "value_composite_baseline": value_metrics,
    }


def compute_technical_baselines(train: pd.DataFrame, test: pd.DataFrame, config: DecisionConfig) -> dict[str, Any]:
    """Compute benchmark baselines for technical entry classification:

    1. Majority class / base-rate prior probability
    2. Regularized Logistic Regression
    3. Moving-average breakout signal (close_vs_sma_20_pct)
    """
    y_train = train.technical_target.gt(config.entry_margin_pct).astype(int)
    base_rate = float(y_train.mean())

    # 1. Majority class / prior
    maj_probs = np.full(len(test), base_rate)
    majority_metrics = entry_metrics(test, maj_probs, config)

    # 2. Regularized Logistic Regression
    pipe = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=0.1, max_iter=2000, random_state=config.seed),
    )
    X_train = feature_matrix(train, TECHNICAL)
    X_test = feature_matrix(test, TECHNICAL)
    pipe.fit(X_train, y_train)
    lr_probs = pipe.predict_proba(X_test)[:, 1]
    logistic_metrics = entry_metrics(test, lr_probs, config)

    # 3. SMA breakout: close_vs_sma_20_pct converted to probability via logistic sigmoid
    sma_dev = pd.to_numeric(test.get("close_vs_sma_20_pct", pd.Series(0.0, index=test.index)), errors="coerce").fillna(0.0)
    # Simple calibrated sigmoid proxy: p = 1 / (1 + exp(-0.1 * sma_dev))
    sma_probs = 1.0 / (1.0 + np.exp(-0.1 * sma_dev.to_numpy()))
    sma_metrics = entry_metrics(test, sma_probs, config)

    return {
        "majority_class_baseline": majority_metrics,
        "logistic_regression_baseline": logistic_metrics,
        "sma_breakout_baseline": sma_metrics,
    }


# ==============================================================================
# BOUNDED SEARCH STUDY (OPTUNA-COMPATIBLE SCHEMA)
# ==============================================================================

def bounded_search_ranker(train: pd.DataFrame, valid: pd.DataFrame, config: DecisionConfig,
                          budget: int = 12) -> tuple[XGBRanker, dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Bounded, reproducible search study for XGBRanker."""
    rng = np.random.RandomState(config.seed)
    candidates_params = [
        {"max_depth": 2, "learning_rate": 0.03, "n_estimators": 120, "reg_lambda": 10.0, "subsample": 0.85, "colsample_bytree": 0.85},
        {"max_depth": 3, "learning_rate": 0.03, "n_estimators": 160, "reg_lambda": 10.0, "subsample": 0.85, "colsample_bytree": 0.85},
        {"max_depth": 4, "learning_rate": 0.02, "n_estimators": 120, "reg_lambda": 20.0, "subsample": 0.80, "colsample_bytree": 0.80},
        {"max_depth": 2, "learning_rate": 0.05, "n_estimators": 100, "reg_lambda": 5.0, "subsample": 0.90, "colsample_bytree": 0.90},
        {"max_depth": 3, "learning_rate": 0.05, "n_estimators": 140, "reg_lambda": 15.0, "subsample": 0.75, "colsample_bytree": 0.75},
        {"max_depth": 2, "learning_rate": 0.01, "n_estimators": 200, "reg_lambda": 10.0, "subsample": 0.85, "colsample_bytree": 0.85},
        {"max_depth": 3, "learning_rate": 0.01, "n_estimators": 240, "reg_lambda": 5.0, "subsample": 0.85, "colsample_bytree": 0.85},
        {"max_depth": 4, "learning_rate": 0.03, "n_estimators": 100, "reg_lambda": 10.0, "subsample": 0.70, "colsample_bytree": 0.70},
        {"max_depth": 2, "learning_rate": 0.08, "n_estimators": 80, "reg_lambda": 20.0, "subsample": 0.90, "colsample_bytree": 0.90},
        {"max_depth": 3, "learning_rate": 0.04, "n_estimators": 150, "reg_lambda": 8.0, "subsample": 0.80, "colsample_bytree": 0.80},
        {"max_depth": 2, "learning_rate": 0.02, "n_estimators": 160, "reg_lambda": 12.0, "subsample": 0.85, "colsample_bytree": 0.85},
        {"max_depth": 3, "learning_rate": 0.06, "n_estimators": 120, "reg_lambda": 10.0, "subsample": 0.85, "colsample_bytree": 0.85},
    ][:budget]

    X_train = feature_matrix(train, FUNDAMENTAL)
    y_train = relevance(train)
    qid_train = train.session.to_numpy()
    X_valid = feature_matrix(valid, FUNDAMENTAL)

    trials = []
    best_score = -np.inf
    best_model = None
    best_params = candidates_params[0]
    best_metrics = None

    for trial_idx, p in enumerate(candidates_params):
        model = XGBRanker(
            objective="rank:pairwise",
            tree_method="hist",
            random_state=config.seed + trial_idx,
            n_jobs=2,
            min_child_weight=10,
            **p,
        )
        model.fit(X_train, y_train, qid=qid_train)
        preds = model.predict(X_valid)
        metrics = ranking_metrics(valid, preds, config)
        score = metrics["ndcg"]

        trial_record = {
            "trial_id": trial_idx,
            "stage": "fundamental",
            "params": p,
            "validation_ndcg": float(score),
            "top_group_excess_return_pct": metrics["top_group_excess_return_pct"],
            "status": "COMPLETE",
        }
        trials.append(trial_record)

        if score > best_score:
            best_score = score
            best_model = model
            best_params = p
            best_metrics = metrics

    return best_model, best_params, best_metrics, trials


def bounded_search_classifier(train: pd.DataFrame, valid: pd.DataFrame, config: DecisionConfig,
                              budget: int = 12) -> tuple[XGBClassifier, dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Bounded, reproducible search study for XGBClassifier."""
    candidates_params = [
        {"max_depth": 2, "learning_rate": 0.03, "n_estimators": 120, "reg_lambda": 10.0, "subsample": 0.85, "colsample_bytree": 0.85},
        {"max_depth": 3, "learning_rate": 0.03, "n_estimators": 160, "reg_lambda": 10.0, "subsample": 0.85, "colsample_bytree": 0.85},
        {"max_depth": 4, "learning_rate": 0.02, "n_estimators": 120, "reg_lambda": 20.0, "subsample": 0.80, "colsample_bytree": 0.80},
        {"max_depth": 2, "learning_rate": 0.05, "n_estimators": 100, "reg_lambda": 5.0, "subsample": 0.90, "colsample_bytree": 0.90},
        {"max_depth": 3, "learning_rate": 0.05, "n_estimators": 140, "reg_lambda": 15.0, "subsample": 0.75, "colsample_bytree": 0.75},
        {"max_depth": 2, "learning_rate": 0.01, "n_estimators": 200, "reg_lambda": 10.0, "subsample": 0.85, "colsample_bytree": 0.85},
        {"max_depth": 3, "learning_rate": 0.01, "n_estimators": 240, "reg_lambda": 5.0, "subsample": 0.85, "colsample_bytree": 0.85},
        {"max_depth": 4, "learning_rate": 0.03, "n_estimators": 100, "reg_lambda": 10.0, "subsample": 0.70, "colsample_bytree": 0.70},
        {"max_depth": 2, "learning_rate": 0.08, "n_estimators": 80, "reg_lambda": 20.0, "subsample": 0.90, "colsample_bytree": 0.90},
        {"max_depth": 3, "learning_rate": 0.04, "n_estimators": 150, "reg_lambda": 8.0, "subsample": 0.80, "colsample_bytree": 0.80},
        {"max_depth": 2, "learning_rate": 0.02, "n_estimators": 160, "reg_lambda": 12.0, "subsample": 0.85, "colsample_bytree": 0.85},
        {"max_depth": 3, "learning_rate": 0.06, "n_estimators": 120, "reg_lambda": 10.0, "subsample": 0.85, "colsample_bytree": 0.85},
    ][:budget]

    X_train = feature_matrix(train, TECHNICAL)
    y_train = train.technical_target.gt(config.entry_margin_pct).astype(int)
    X_valid = feature_matrix(valid, TECHNICAL)

    trials = []
    best_score = -np.inf
    best_model = None
    best_params = candidates_params[0]
    best_metrics = None

    for trial_idx, p in enumerate(candidates_params):
        model = XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
            random_state=config.seed + trial_idx,
            n_jobs=2,
            min_child_weight=10,
            **p,
        )
        model.fit(X_train, y_train)
        probs = model.predict_proba(X_valid)[:, 1]
        metrics = entry_metrics(valid, probs, config)
        score = metrics["average_precision"]

        trial_record = {
            "trial_id": trial_idx,
            "stage": "technical",
            "params": p,
            "validation_average_precision": float(score),
            "validation_log_loss": metrics["log_loss"],
            "validation_signals": metrics["signals"],
            "status": "COMPLETE",
        }
        trials.append(trial_record)

        if score > best_score:
            best_score = score
            best_model = model
            best_params = p
            best_metrics = metrics

    return best_model, best_params, best_metrics, trials


# ==============================================================================
# PIPELINE TRAINING & INFERENCE
# ==============================================================================

def train_pipeline(data: pd.DataFrame, validation_start: int, test_start: int,
                   config: DecisionConfig = DecisionConfig(), trees: int = 160) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bounded validation selection, followed by one test evaluation; no test refit."""
    data = data.sort_values(["session", "symbol"]).reset_index(drop=True)
    models, report = {}, {
        "config": asdict(config),
        "validation_start": validation_start,
        "test_start": test_start,
        "fresh_holdout_verified": False,
        "note": "Historical research assessment; not a live trading guarantee.",
    }
    for stage, names in (("fundamental", FUNDAMENTAL), ("technical", TECHNICAL)):
        train, valid, test = split_stage(data, stage, validation_start, test_start, config)
        if stage == "fundamental":
            counts = train.groupby("session").symbol.transform("size")
            train = train[counts.ge(2)].copy()
            if train.empty:
                raise ValueError("Fundamental training requires cross-sectional groups")
        else:
            if train.technical_target.gt(config.entry_margin_pct).nunique() < 2:
                raise ValueError("Technical training requires both entry outcome classes")
        if feature_matrix(train, names).notna().sum().eq(0).all():
            raise ValueError(f"No usable {stage} training features")
        candidates = []
        for depth in (2, 3):
            params = dict(n_estimators=trees, max_depth=depth, learning_rate=0.03,
                          min_child_weight=10, reg_lambda=10, subsample=0.85,
                          colsample_bytree=0.85, n_jobs=2, random_state=config.seed,
                          tree_method="hist")
            if stage == "fundamental":
                model = XGBRanker(objective="rank:pairwise", **params)
                model.fit(feature_matrix(train, names), relevance(train),
                          qid=train.session.to_numpy())
                metrics = ranking_metrics(valid, model.predict(feature_matrix(valid, names)), config)
                score = metrics["ndcg"]
            else:
                model = XGBClassifier(objective="binary:logistic", eval_metric="logloss", **params)
                model.fit(feature_matrix(train, names),
                          train.technical_target.gt(config.entry_margin_pct).astype(int))
                metrics = entry_metrics(valid, model.predict_proba(feature_matrix(valid, names))[:, 1], config)
                score = metrics["average_precision"]
            candidates.append((score, model, metrics, depth))
        _, winner, validation, depth = max(candidates, key=lambda item: item[0])
        models[stage] = winner
        if stage == "fundamental":
            test_metrics = ranking_metrics(test, winner.predict(feature_matrix(test, names)), config)
            baseline = ranking_metrics(test, np.zeros(len(test)), config)
            baseline["top_group_excess_return_pct"] = float(test.groupby("session").fundamental_target.mean().mean())
        else:
            test_metrics = entry_metrics(test, winner.predict_proba(feature_matrix(test, names))[:, 1], config)
            base = train.technical_target.gt(config.entry_margin_pct).mean()
            baseline = entry_metrics(test, np.full(len(test), base), config)
        report[stage] = {
            "features": names,
            "selected_depth": depth,
            "validation": validation,
            "test": test_metrics,
            "baseline_test": baseline,
            "train_rows": len(train),
            "trials": [{"depth": item[3], "validation": item[2]} for item in candidates],
        }
    return {
        "models": models,
        "config": config,
        "feature_schema": {"fundamental": list(FUNDAMENTAL), "technical": list(TECHNICAL)},
        "trained_through_session": max(validation_start, test_start),
    }, report


def predict_decisions(bundle: dict[str, Any], panel: pd.DataFrame) -> pd.DataFrame:
    config = bundle["config"]
    frame = validate_panel(panel, config)
    if frame.session.min() < bundle["trained_through_session"]:
        raise ValueError("Inference predates model selection; use chronological out-of-sample predictions")
    out = frame[["symbol", "session", "prediction_timestamp"]].copy()
    out["fundamental_score"] = np.nan
    out["fundamental_percentile"] = np.nan
    out["entry_probability_raw"] = np.nan
    for stage, names in (("fundamental", FUNDAMENTAL), ("technical", TECHNICAL)):
        mask = frame[f"{stage}_eligible"]
        if not mask.any():
            continue
        x = feature_matrix(frame.loc[mask], names)
        model = bundle["models"][stage]
        if stage == "fundamental":
            out.loc[mask, "fundamental_score"] = model.predict(x)
        else:
            out.loc[mask, "entry_probability_raw"] = model.predict_proba(x)[:, 1]
    groups = out.groupby("session").fundamental_score
    out["fundamental_percentile"] = groups.rank(pct=True, method="average").where(groups.transform("count").ge(2))
    shortlisted = out.fundamental_percentile.gt(1 - config.top_fraction)
    available = out.fundamental_percentile.notna() & out.entry_probability_raw.notna()
    out["decision"] = np.select(
        [~available, ~shortlisted, out.entry_probability_raw.ge(config.entry_threshold)],
        ["INSUFFICIENT_DATA", "NOT_SHORTLISTED", "ENTRY_CANDIDATE"], default="WAIT")
    return out


# ==============================================================================
# EXPANDING WALK-FORWARD EVALUATION & JOINT POLICY SIMULATION
# ==============================================================================

def simulate_joint_policy(bundle: dict[str, Any], test_data: pd.DataFrame, config: DecisionConfig) -> dict[str, Any]:
    """Chronologically evaluate joint decision policy on out-of-sample observations:

    Compare:
    1. ENTRY_CANDIDATE: Fundamental shortlist + Technical timing filter (P >= entry_threshold)
    2. NAIVE_SHORTLIST: Buying all top 20% fundamental stocks without technical filter
    3. WAIT: Shortlisted stocks with weak technical timing (P < entry_threshold)
    4. NOT_SHORTLISTED: Non-shortlisted universe stocks
    """
    decisions = predict_decisions(bundle, test_data)
    merged = decisions.merge(
        test_data[["symbol", "session", "technical_target", "fundamental_target"]],
        on=["symbol", "session"],
        how="inner",
    )

    results = {
        "total_test_rows": len(merged),
        "decision_counts": merged["decision"].value_counts().to_dict(),
        "groups": {},
    }

    # Groups
    entry_cand = merged[merged["decision"] == "ENTRY_CANDIDATE"]
    wait_cand = merged[merged["decision"] == "WAIT"]
    not_short = merged[merged["decision"] == "NOT_SHORTLISTED"]
    naive_short = merged[merged["decision"].isin(["ENTRY_CANDIDATE", "WAIT"])]

    for name, subset in (("entry_candidate", entry_cand),
                         ("naive_fundamental_shortlist", naive_short),
                         ("wait_shortlisted", wait_cand),
                         ("not_shortlisted", not_short)):
        n = len(subset)
        if n == 0:
            results["groups"][name] = {"count": 0}
            continue
        net_returns = subset["technical_target"].dropna()
        results["groups"][name] = {
            "count": n,
            "mean_net_return_10session_pct": float(net_returns.mean()) if len(net_returns) else None,
            "median_net_return_10session_pct": float(net_returns.median()) if len(net_returns) else None,
            "win_rate_pct": float((net_returns > 0).mean() * 100) if len(net_returns) else None,
            "large_gain_rate_pct": float((net_returns > config.entry_margin_pct).mean() * 100) if len(net_returns) else None,
            "std_net_return_pct": float(net_returns.std()) if len(net_returns) > 1 else 0.0,
        }

    # Hypothesis test: Does technical filter improve over naive fundamental shortlist?
    if len(entry_cand["technical_target"].dropna()) >= 10 and len(naive_short["technical_target"].dropna()) >= 10:
        ret_entry = entry_cand["technical_target"].dropna().to_numpy()
        ret_naive = naive_short["technical_target"].dropna().to_numpy()
        t_stat, p_val = stats.ttest_ind(ret_entry, ret_naive, equal_var=False)
        results["hypothesis_test"] = {
            "comparison": "ENTRY_CANDIDATE vs NAIVE_FUNDAMENTAL_SHORTLIST",
            "delta_mean_net_return_pct": float(np.mean(ret_entry) - np.mean(ret_naive)),
            "t_statistic": float(t_stat),
            "p_value": float(p_val),
            "significant_at_5pct": bool(p_val < 0.05),
        }
    else:
        results["hypothesis_test"] = None

    return results


def evaluate_expanding_folds(data: pd.DataFrame, config: DecisionConfig = DecisionConfig(),
                             folds: list[tuple[int, int, int]] | None = None) -> dict[str, Any]:
    """Execute rigorous chronological expanding walk-forward outer evaluation."""
    if folds is None:
        folds = [
            (5380, 5600, 5730),
            (5500, 5730, 5860),
            (5620, 5860, 6000),
        ]

    fold_reports = []
    all_trials_fundamental = []
    all_trials_technical = []
    latest_bundle = None

    for fold_idx, (v_start, t_start, t_end) in enumerate(folds):
        fold_id = f"fold_{fold_idx + 1}"
        fold_res = {
            "fold_id": fold_id,
            "validation_start": v_start,
            "test_start": t_start,
            "test_end": t_end,
        }

        # 1. Fundamental stage
        train_f, valid_f, test_f = split_stage(data, "fundamental", v_start, t_start, config)
        test_f = test_f[test_f.session.lt(t_end)].copy()

        ranker, best_rank_params, val_rank_metrics, f_trials = bounded_search_ranker(
            train_f, valid_f, config, budget=12)
        for t in f_trials:
            t["fold"] = fold_id
        all_trials_fundamental.extend(f_trials)

        test_rank_metrics = ranking_metrics(test_f, ranker.predict(feature_matrix(test_f, FUNDAMENTAL)), config)
        f_baselines = compute_fundamental_baselines(train_f, test_f, config)

        fold_res["fundamental"] = {
            "train_rows": len(train_f),
            "valid_rows": len(valid_f),
            "test_rows": len(test_f),
            "selected_params": best_rank_params,
            "validation_ndcg": val_rank_metrics["ndcg"],
            "test_ndcg": test_rank_metrics["ndcg"],
            "test_excess_return_pct": test_rank_metrics["top_group_excess_return_pct"],
            "baselines": f_baselines,
        }

        # 2. Technical stage
        train_t, valid_t, test_t = split_stage(data, "technical", v_start, t_start, config)
        test_t = test_t[test_t.session.lt(t_end)].copy()

        clf, best_clf_params, val_clf_metrics, t_trials = bounded_search_classifier(
            train_t, valid_t, config, budget=12)
        for t in t_trials:
            t["fold"] = fold_id
        all_trials_technical.extend(t_trials)

        probs_test = clf.predict_proba(feature_matrix(test_t, TECHNICAL))[:, 1]
        test_clf_metrics = entry_metrics(test_t, probs_test, config)
        t_baselines = compute_technical_baselines(train_t, test_t, config)

        fold_res["technical"] = {
            "train_rows": len(train_t),
            "valid_rows": len(valid_t),
            "test_rows": len(test_t),
            "selected_params": best_clf_params,
            "validation_ap": val_clf_metrics["average_precision"],
            "test_ap": test_clf_metrics["average_precision"],
            "test_log_loss": test_clf_metrics["log_loss"],
            "test_signals": test_clf_metrics["signals"],
            "test_entry_precision": test_clf_metrics["entry_precision"],
            "test_mean_selected_net_return_pct": test_clf_metrics["mean_selected_net_return_pct"],
            "baselines": t_baselines,
        }

        # 3. Joint Policy Simulation
        bundle = {
            "models": {"fundamental": ranker, "technical": clf},
            "config": config,
            "feature_schema": {"fundamental": list(FUNDAMENTAL), "technical": list(TECHNICAL)},
            "trained_through_session": t_start,
        }
        latest_bundle = bundle

        test_data_slice = data[data.session.between(t_start, t_end - 1)].copy()
        sim_res = simulate_joint_policy(bundle, test_data_slice, config)
        fold_res["joint_policy"] = sim_res
        fold_reports.append(fold_res)

    # Compute summary across folds
    f_ndcg_list = [f["fundamental"]["test_ndcg"] for f in fold_reports]
    f_excess_list = [f["fundamental"]["test_excess_return_pct"] for f in fold_reports]
    t_ap_list = [f["technical"]["test_ap"] for f in fold_reports]
    t_prec_list = [f["technical"]["test_entry_precision"] for f in fold_reports if f["technical"]["test_entry_precision"] is not None]

    summary = {
        "status": "COMPLETED",
        "num_folds": len(fold_reports),
        "optuna_status": "Declared: Optuna unavailable in sandbox environment; reproducible BoundedSearchStudy used (seed 42, 12 bounded trials per stage per fold).",
        "mean_fundamental_test_ndcg": float(np.mean(f_ndcg_list)),
        "mean_fundamental_test_excess_return_pct": float(np.mean(f_excess_list)),
        "mean_technical_test_ap": float(np.mean(t_ap_list)),
        "mean_technical_entry_precision": float(np.mean(t_prec_list)) if t_prec_list else None,
        "fold_reports": fold_reports,
    }

    return {
        "summary": summary,
        "latest_bundle": latest_bundle,
        "trials_fundamental": all_trials_fundamental,
        "trials_technical": all_trials_technical,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--prices", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--validation-start", type=int, default=5620)
    parser.add_argument("--test-start", type=int, default=5860)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expanding-folds", action="store_true", help="Run full expanding chronological walk-forward assessment")
    args = parser.parse_args()

    if args.output.exists():
        # Allow running in existing directory if empty, otherwise raise
        if any(args.output.iterdir()):
            raise FileExistsError(f"Output directory {args.output} is not empty")
    else:
        args.output.mkdir(parents=True, exist_ok=True)

    config = DecisionConfig()
    data = build_targets(pd.read_csv(args.panel), pd.read_csv(args.prices),
                         pd.read_csv(args.benchmark), config)

    if args.expanding_folds:
        expanding_results = evaluate_expanding_folds(data, config)
        bundle = expanding_results["latest_bundle"]
        report = expanding_results["summary"]

        joblib.dump(bundle, args.output / "decision_models.joblib")
        (args.output / "evaluation.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")

        # Save trials
        pd.DataFrame(expanding_results["trials_fundamental"]).to_csv(args.output / "trials_fundamental.csv", index=False)
        (args.output / "trials_fundamental.json").write_text(json.dumps(expanding_results["trials_fundamental"], indent=2), encoding="utf-8")

        pd.DataFrame(expanding_results["trials_technical"]).to_csv(args.output / "trials_technical.csv", index=False)
        (args.output / "trials_technical.json").write_text(json.dumps(expanding_results["trials_technical"], indent=2), encoding="utf-8")

        # Save baseline comparison
        baselines_data = {
            fold["fold_id"]: {
                "fundamental_baselines": fold["fundamental"]["baselines"],
                "technical_baselines": fold["technical"]["baselines"],
            }
            for fold in report["fold_reports"]
        }
        (args.output / "baseline_comparison.json").write_text(json.dumps(baselines_data, indent=2), encoding="utf-8")

        # Save joint policy simulation
        joint_sim_data = {
            fold["fold_id"]: fold["joint_policy"]
            for fold in report["fold_reports"]
        }
        (args.output / "joint_policy_simulation.json").write_text(json.dumps(joint_sim_data, indent=2), encoding="utf-8")
        print(f"Expanding evaluation complete. Saved artifacts to {args.output}")
    else:
        bundle, report = train_pipeline(data, args.validation_start, args.test_start, config)
        joblib.dump(bundle, args.output / "decision_models.joblib")
        (args.output / "evaluation.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        print(f"Pipeline training complete. Saved artifacts to {args.output}")


if __name__ == "__main__":
    main()
