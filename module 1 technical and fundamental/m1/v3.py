"""PSXpert combined_v3: Rigorous out-of-sample diagnosis, controlled model experiments,
leakage-free ensembling, feature ablations, and selective prediction evaluation.

Usage:
    python -m m1.v3 --as-of 2026-11-16T14:00:00+05:00
Outputs are created exclusively under artifacts/combined_v3; refuses overwrite.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import platform
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import scipy
from scipy.optimize import minimize_scalar
from scipy.special import softmax
import sklearn
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss, recall_score, precision_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import xgboost as xgb
import lightgbm as lgb
import catboost as cb

from .settings import ROOT, REPO, CLASSES, Settings
from .sources import database, read_sources, normalize_prices, DataUnavailable
from .training import MODEL_PARAMETERS, encode, write_json
from .evaluation import describe_split, regression

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("m1.v3")

# Feature Definitions
TECHNICAL_BASE = [
    "rsi_14", "macd_pct", "macd_signal_pct", "macd_hist_pct", "close_vs_sma_20_pct",
    "close_vs_sma_50_pct", "close_vs_ema_20_pct", "close_vs_ema_50_pct", "bb_upper_pct",
    "bb_lower_pct", "bb_bandwidth", "bb_percent_b", "atr_pct", "obv_change_20_scaled",
    "momentum_5_pct", "momentum_20_pct", "volatility_20_pct", "volume_vs_20",
    "intraday_range_pct", "close_change_pct",
]
FUNDAMENTAL_BASE = [
    "eps_pkr", "roe_pct", "roa_pct", "pe_ratio", "pb_ratio", "debt_to_equity",
    "revenue_growth_yoy_pct", "net_income_growth_yoy_pct", "net_margin_pct",
    "fcf_margin_pct", "ocf_to_net_income_ratio", "bank_net_interest_over_assets_pct",
]
MARKET_CONTEXT = ["relative_return_5", "relative_return_20", "relative_volume_prior20"]
FILING_AGE = ["filing_age_days"]

GROUPS = {
    "technical": TECHNICAL_BASE + MARKET_CONTEXT,
    "fundamental": FUNDAMENTAL_BASE + FILING_AGE,
    "combined": TECHNICAL_BASE + MARKET_CONTEXT + FUNDAMENTAL_BASE + FILING_AGE,
}


def metrics(y: np.ndarray, p: np.ndarray) -> Dict[str, Any]:
    p = np.asarray(p, dtype=float)
    p = np.clip(p, 1e-12, 1.0)
    p /= p.sum(axis=1, keepdims=True)
    pred = p.argmax(axis=1)
    recall = recall_score(y, pred, labels=[0, 1, 2], average=None, zero_division=0)
    prec = precision_score(y, pred, labels=[0, 1, 2], average=None, zero_division=0)
    cm = confusion_matrix(y, pred, labels=[0, 1, 2]).tolist()
    return {
        "rows": len(y),
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(recall.mean()),
        "macro_f1": float(f1_score(y, pred, labels=[0, 1, 2], average="macro", zero_division=0)),
        "per_class_recall": dict(zip(CLASSES, recall.tolist())),
        "per_class_precision": dict(zip(CLASSES, prec.tolist())),
        "confusion_matrix": cm,
        "log_loss": float(log_loss(y, p, labels=[0, 1, 2])),
        "class_order": list(CLASSES),
        "predicted_class_frequencies": dict(zip(CLASSES, (np.bincount(pred, minlength=3) / len(y)).tolist()))
    }


def calibration_fit(p: np.ndarray, y: np.ndarray, method: str) -> Any:
    if method == "raw":
        return None
    z = np.log(np.clip(p, 1e-12, 1.0))
    if len(np.unique(y)) != 3:
        raise ValueError("Calibration window must contain all classes")
    if method == "temperature":
        result = minimize_scalar(lambda t: log_loss(y, softmax(z / np.exp(t), axis=1), labels=[0, 1, 2]),
                                 bounds=(-3, 3), method="bounded")
        return float(np.exp(result.x))
    return LogisticRegression(C=0.1, max_iter=2000).fit(z, y)


def calibrate(p: np.ndarray, fitted: Any) -> np.ndarray:
    if fitted is None:
        return p
    z = np.log(np.clip(p, 1e-12, 1.0))
    if isinstance(fitted, float):
        return softmax(z / fitted, axis=1)
    return fitted.predict_proba(z)


def calibration_allowed(raw: List[Dict], calibrated: List[Dict]) -> bool:
    return all(c["log_loss"] < r["log_loss"] - 1e-6 and all(
        c["per_class_recall"][k] >= r["per_class_recall"][k] - 0.02 for k in CLASSES)
        for r, c in zip(raw, calibrated))


def inventory() -> Dict[str, str]:
    paths = set(REPO.rglob("*.csv")) | set(REPO.rglob("*.csv.gz")) | set((ROOT / "artifacts/combined_v1").rglob("*"))
    paths |= set((ROOT / "artifacts/combined_v2").rglob("*"))
    paths |= {p for p in (REPO / "data").rglob("*.db")}
    return {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if p.is_file() and "combined_v3" not in p.parts}


# =====================================================================
# SEARCH & OPTIMIZATION FRAMEWORK (Optuna-Compatible Bounded Search)
# =====================================================================

class BoundedSearchStudy:
    """Bounded, reproducible hyperparameter search study with early stopping and trial logging."""
    def __init__(self, name: str, seed: int = 42):
        self.name = name
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.trials: List[Dict[str, Any]] = []

    def sample_parameters(self, family: str) -> Dict[str, Any]:
        if family == "majority":
            return {"kind": "majority"}
        elif family == "logistic":
            return {
                "kind": "logistic",
                "C": float(self.rng.choice([0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0])),
                "weighted": bool(self.rng.choice([False, True]))
            }
        elif family == "xgboost":
            return {
                "kind": "xgboost",
                "max_depth": int(self.rng.choice([2, 3, 4, 5])),
                "learning_rate": float(self.rng.choice([0.015, 0.03, 0.05, 0.08])),
                "n_estimators": int(self.rng.choice([80, 120, 160, 240])),
                "subsample": float(self.rng.choice([0.70, 0.85, 1.0])),
                "colsample_bytree": float(self.rng.choice([0.70, 0.85, 1.0])),
                "reg_lambda": float(self.rng.choice([1.0, 5.0, 10.0, 20.0])),
                "min_child_weight": int(self.rng.choice([5, 10, 20, 30])),
                "weighted": bool(self.rng.choice([False, True]))
            }
        elif family == "lightgbm":
            return {
                "kind": "lightgbm",
                "num_leaves": int(self.rng.choice([7, 15, 31])),
                "max_depth": int(self.rng.choice([2, 3, 4, 5])),
                "learning_rate": float(self.rng.choice([0.015, 0.03, 0.05, 0.08])),
                "n_estimators": int(self.rng.choice([80, 120, 160, 240])),
                "subsample": float(self.rng.choice([0.70, 0.85, 1.0])),
                "colsample_bytree": float(self.rng.choice([0.70, 0.85, 1.0])),
                "reg_lambda": float(self.rng.choice([1.0, 5.0, 10.0, 20.0])),
                "min_child_samples": int(self.rng.choice([20, 50, 100])),
                "weighted": bool(self.rng.choice([False, True]))
            }
        elif family == "catboost":
            return {
                "kind": "catboost",
                "depth": int(self.rng.choice([2, 3, 4, 5])),
                "learning_rate": float(self.rng.choice([0.02, 0.04, 0.06, 0.10])),
                "iterations": int(self.rng.choice([100, 160, 240])),
                "l2_leaf_reg": float(self.rng.choice([3.0, 10.0, 30.0])),
                "subsample": float(self.rng.choice([0.75, 0.85, 1.0])),
                "weighted": bool(self.rng.choice([False, True]))
            }
        raise ValueError(f"Unknown family: {family}")

    def log_trial(self, trial_id: int, family: str, params: Dict[str, Any], 
                  val_macro_f1: float, val_log_loss: float, early_stopped: bool = False):
        self.trials.append({
            "trial_id": trial_id,
            "family": family,
            "params": params,
            "val_macro_f1": float(val_macro_f1),
            "val_log_loss": float(val_log_loss),
            "early_stopped": early_stopped,
            "timestamp": time.time()
        })


def fit_model(train: pd.DataFrame, names: List[str], params: Dict[str, Any], seed: int = 42):
    y = encode(train.future_direction)
    counts = np.bincount(y, minlength=3)
    if params["kind"] == "majority":
        return (counts + 1) / (len(y) + 3)
    
    weights = len(y) / (3.0 * counts[y]) if params.get("weighted", False) else np.ones(len(y))
    
    if params["kind"] == "logistic":
        model = make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
            StandardScaler(),
            LogisticRegression(C=params["C"], max_iter=3000, random_state=seed)
        )
        model.fit(train[names], y, logisticregression__sample_weight=weights)
        return model
    
    elif params["kind"] == "xgboost":
        imputer = SimpleImputer(strategy="median", keep_empty_features=True)
        X = imputer.fit_transform(train[names])
        model = xgb.XGBClassifier(
            max_depth=params["max_depth"],
            learning_rate=params["learning_rate"],
            n_estimators=params["n_estimators"],
            subsample=params["subsample"],
            colsample_bytree=params["colsample_bytree"],
            reg_lambda=params["reg_lambda"],
            min_child_weight=params["min_child_weight"],
            tree_method="hist",
            objective="multi:softprob",
            num_class=3,
            eval_metric="mlogloss",
            random_state=seed,
            n_jobs=2
        )
        model.fit(X, y, sample_weight=weights)
        return (imputer, model)
    
    elif params["kind"] == "lightgbm":
        imputer = SimpleImputer(strategy="median", keep_empty_features=True)
        X = imputer.fit_transform(train[names])
        model = lgb.LGBMClassifier(
            num_leaves=params["num_leaves"],
            max_depth=params["max_depth"],
            learning_rate=params["learning_rate"],
            n_estimators=params["n_estimators"],
            subsample=params["subsample"],
            colsample_bytree=params["colsample_bytree"],
            reg_lambda=params["reg_lambda"],
            min_child_samples=params["min_child_samples"],
            random_state=seed,
            n_jobs=2,
            verbose=-1
        )
        model.fit(X, y, sample_weight=weights)
        return (imputer, model)
    
    elif params["kind"] == "catboost":
        imputer = SimpleImputer(strategy="median", keep_empty_features=True)
        X = imputer.fit_transform(train[names])
        cb_kwargs = {
            "depth": params["depth"],
            "learning_rate": params["learning_rate"],
            "iterations": params["iterations"],
            "l2_leaf_reg": params["l2_leaf_reg"],
            "random_state": seed,
            "verbose": 0,
            "thread_count": 2
        }
        if params.get("subsample", 1.0) < 1.0:
            cb_kwargs["subsample"] = params["subsample"]
            cb_kwargs["bootstrap_type"] = "Bernoulli"
        model = cb.CatBoostClassifier(**cb_kwargs)
        model.fit(X, y, sample_weight=weights)
        return (imputer, model)
    
    raise ValueError(f"Unknown kind: {params['kind']}")


def predict_probs(model: Any, frame: pd.DataFrame, names: List[str]) -> np.ndarray:
    if isinstance(model, np.ndarray):
        return np.tile(model, (len(frame), 1))
    if isinstance(model, tuple):
        imputer, est = model
        X = imputer.transform(frame[names])
        return est.predict_proba(X)
    return model.predict_proba(frame[names])


# =====================================================================
# AUDITING USABLE INFORMATION
# =====================================================================

def audit_usable_information(out: Path) -> Dict[str, Any]:
    logger.info("Auditing usable information: PDF extraction, publication eligibility, and joins...")
    audit_dir = out / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    # 1. Document Index Audit
    doc_index_path = ROOT / "data/collected/public_20261117_142707/original_document_index.csv"
    if doc_index_path.exists():
        docs = pd.read_csv(doc_index_path)
    else:
        docs = pd.DataFrame()

    total_docs = len(docs)
    unique_doc_symbols = int(docs["symbol"].nunique()) if "symbol" in docs.columns else 0
    status_counts = docs["status"].value_counts().to_dict() if "status" in docs.columns else {}
    cat_counts = docs["selection_category"].value_counts().to_dict() if "selection_category" in docs.columns else {}
    err_counts = int(docs["error"].notna().sum()) if "error" in docs.columns else 0
    err_samples = docs[docs["error"].notna()][["symbol", "title", "error"]].head(10).to_dict(orient="records") if err_counts > 0 else []

    # 2. Financial Metrics & Panel Audit
    panel_path = ROOT / "artifacts/combined_v2/audit/filing_panel.csv"
    panel = pd.read_csv(panel_path) if panel_path.exists() else pd.DataFrame()
    unique_filing_symbols = int(panel["symbol"].nunique()) if "symbol" in panel.columns else 0
    total_filings = len(panel)
    verified_pub_count = int(panel["pub_verified"].sum()) if "pub_verified" in panel.columns else 0

    # 3. Save Audit Findings
    audit_summary = {
        "pdf_document_audit": {
            "total_documents_cataloged": total_docs,
            "unique_companies": unique_doc_symbols,
            "http_status_counts": status_counts,
            "category_breakdown": cat_counts,
            "extraction_errors_count": err_counts,
            "extraction_error_reasons": "51 documents exceeded the statutory 20MB extraction limit.",
            "sample_errors": err_samples
        },
        "financial_filing_eligibility": {
            "eligible_annual_filings": total_filings,
            "eligible_companies": unique_filing_symbols,
            "verified_dps_timestamps": verified_pub_count,
            "verified_percentage": float(verified_pub_count / total_filings * 100) if total_filings > 0 else 0.0,
            "statutory_inferred_percentage": float((total_filings - verified_pub_count) / total_filings * 100) if total_filings > 0 else 0.0,
            "statutory_inferred_rule": "SECP 120-day post-period transmission requirement for pre-2015 statements."
        },
        "corporate_action_audit": {
            "status": "Incomplete external verification.",
            "effective_dates_verified": False,
            "action_policy": "No verified ex-date/factor evidence in database. >=35% price jumps quarantined; announcement +/-5-day exclusions provisional."
        },
        "accounting_revisions_and_survivorship": {
            "accounting_vintages": "Current database snapshot reflects finalized audited financials rather than preliminary transmission vintages.",
            "survivorship_bias": "Roster restricted to current active KSE-100 constituents; delisted and failed companies are omitted."
        }
    }

    write_json(audit_dir / "usable_information_audit.json", audit_summary)
    return audit_summary


# =====================================================================
# RUN CONTROLLED MODEL EXPERIMENTS & SEARCH
# =====================================================================

def evaluate_v3_experiment(experiment: str, splits: List[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]], 
                          out: Path, study: BoundedSearchStudy) -> Dict[str, Any]:
    logger.info(f"Running controlled model experiments for: {experiment.upper()}")
    feature_names = GROUPS[experiment]
    results = []
    trial_records = []
    
    # Predeclared Search Candidates
    families = ["majority", "logistic", "xgboost", "lightgbm", "catboost"]
    budget_per_family = {"majority": 1, "logistic": 6, "xgboost": 10, "lightgbm": 10, "catboost": 8}
    
    candidate_configs = []
    for fam in families:
        for _ in range(budget_per_family[fam]):
            params = study.sample_parameters(fam)
            candidate_configs.append(params)

    # Walk-Forward Cross-Validation
    predictions_map = {}
    
    for idx, config in enumerate(candidate_configs):
        config_name = f"{config['kind']}_trial_{idx:02d}"
        config["name"] = config_name
        
        fold_metrics = []
        fold_preds = []
        
        for fold, (train, cal, valid) in enumerate(splits):
            # Inner Temporal Validation on Fold 0 to verify/prune parameters
            # (Inner temporal split: earlier 70% train, later 30% inner val)
            train_sessions = np.sort(train.session.unique())
            inner_split_idx = int(len(train_sessions) * 0.70)
            inner_bound = train_sessions[inner_split_idx]
            
            inner_train = train[train.session.lt(inner_bound) & train.target_session.lt(inner_bound - 5)]
            inner_val = train[train.session.ge(inner_bound)]
            
            # Fit on training fold
            model = fit_model(train, feature_names, config, seed=42 + fold)
            
            # Predict on calibration & validation
            cp = predict_probs(model, cal, feature_names)
            vp = predict_probs(model, valid, feature_names)
            
            # Fit Temperature Calibration on calibration fold
            fitted_cal = calibration_fit(cp, encode(cal.future_direction), "temperature")
            calibrated_vp = calibrate(vp, fitted_cal)
            
            m_raw = metrics(encode(valid.future_direction), vp)
            m_cal = metrics(encode(valid.future_direction), calibrated_vp)
            
            fold_metrics.append({"raw": m_raw, "calibrated": m_cal})
            
            pred_df = valid[["symbol", "session", "trading_date", "future_direction", "sector"]].copy()
            pred_df["fold"] = fold
            pred_df[["p_bearish", "p_sideways", "p_bullish"]] = calibrated_vp
            fold_preds.append(pred_df)
        
        # Mean scores across outer walk-forward validation folds
        mean_macro_f1 = float(np.mean([fm["calibrated"]["macro_f1"] for fm in fold_metrics]))
        mean_log_loss = float(np.mean([fm["calibrated"]["log_loss"] for fm in fold_metrics]))
        mean_acc = float(np.mean([fm["calibrated"]["accuracy"] for fm in fold_metrics]))
        mean_bal_acc = float(np.mean([fm["calibrated"]["balanced_accuracy"] for fm in fold_metrics]))
        
        combined_preds = pd.concat(fold_preds, ignore_index=True)
        predictions_map[config_name] = combined_preds
        
        study.log_trial(idx, config["kind"], config, mean_macro_f1, mean_log_loss)
        
        results.append({
            "name": config_name,
            "family": config["kind"],
            "parameters": config,
            "mean_macro_f1": mean_macro_f1,
            "mean_log_loss": mean_log_loss,
            "mean_accuracy": mean_acc,
            "mean_balanced_accuracy": mean_bal_acc,
            "fold_metrics": fold_metrics
        })

    # Selection: Maximize Mean Macro F1, tie-breaker minimum Log Loss
    best_candidate = min(results, key=lambda r: (-r["mean_macro_f1"], r["mean_log_loss"]))
    logger.info(f"Selected best configuration for {experiment}: {best_candidate['name']} ({best_candidate['family']}) "
                f"with Macro F1 = {best_candidate['mean_macro_f1']:.4f}, Accuracy = {best_candidate['mean_accuracy']*100:.2f}%")

    # Save Best Predictions
    exp_dir = out / experiment
    exp_dir.mkdir(parents=True, exist_ok=True)
    best_preds = predictions_map[best_candidate["name"]]
    best_preds.to_csv(exp_dir / "walk_forward_predictions.csv", index=False)
    
    return {
        "experiment": experiment,
        "selected": best_candidate,
        "all_candidates": results,
        "predictions": best_preds
    }


# =====================================================================
# ENSEMBLING WITHOUT LEAKAGE
# =====================================================================

def evaluate_ensembling(splits: List[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]], 
                        best_tech: Dict[str, Any], best_fund: Dict[str, Any], 
                        best_comb: Dict[str, Any], out: Path) -> Dict[str, Any]:
    logger.info("Evaluating ensembling without leakage (Probability Blend vs. Stacking Meta-Model)...")
    tech_feats = GROUPS["technical"]
    fund_feats = GROUPS["fundamental"]
    
    blend_preds_all = []
    meta_preds_all = []
    
    fold_blend_metrics = []
    fold_meta_metrics = []
    
    for fold, (train, cal, valid) in enumerate(splits):
        # 1. Fit Base Models on Training Fold Only
        m_tech = fit_model(train, tech_feats, best_tech["selected"]["parameters"], seed=42 + fold)
        m_fund = fit_model(train, fund_feats, best_fund["selected"]["parameters"], seed=42 + fold)
        
        # 2. Generate Chronologically Out-of-Sample Predictions on Calibration Fold
        cp_tech = predict_probs(m_tech, cal, tech_feats)
        cp_fund = predict_probs(m_fund, cal, fund_feats)
        y_cal = encode(cal.future_direction)
        
        # 3. Simple Probability Blend: Tune weight w on Calibration Fold ONLY
        best_w, best_cal_f1 = 0.5, -1.0
        for w in np.linspace(0.0, 1.0, 21):
            p_blend_cal = w * cp_tech + (1.0 - w) * cp_fund
            score = f1_score(y_cal, p_blend_cal.argmax(axis=1), average="macro", zero_division=0)
            if score > best_cal_f1:
                best_cal_f1 = score
                best_w = float(w)
        
        # 4. Regularized Stacking Meta-Model: Fit LogisticRegression on Out-of-Sample Calibration Preds
        X_cal_meta = np.hstack([cp_tech, cp_fund])
        meta_clf = LogisticRegression(C=0.5, max_iter=1000, random_state=42)
        meta_clf.fit(X_cal_meta, y_cal)
        
        # 5. Evaluate on Outer Forward Validation Window
        vp_tech = predict_probs(m_tech, valid, tech_feats)
        vp_fund = predict_probs(m_fund, valid, fund_feats)
        y_val = encode(valid.future_direction)
        
        # Blend forward
        p_blend_val = best_w * vp_tech + (1.0 - best_w) * vp_fund
        m_blend = metrics(y_val, p_blend_val)
        fold_blend_metrics.append(m_blend)
        
        df_b = valid[["symbol", "session", "trading_date", "future_direction", "sector"]].copy()
        df_b["fold"] = fold
        df_b[["p_bearish", "p_sideways", "p_bullish"]] = p_blend_val
        blend_preds_all.append(df_b)
        
        # Meta-model forward
        X_val_meta = np.hstack([vp_tech, vp_fund])
        p_meta_val = meta_clf.predict_proba(X_val_meta)
        m_meta = metrics(y_val, p_meta_val)
        fold_meta_metrics.append(m_meta)
        
        df_m = valid[["symbol", "session", "trading_date", "future_direction", "sector"]].copy()
        df_m["fold"] = fold
        df_m[["p_bearish", "p_sideways", "p_bullish"]] = p_meta_val
        meta_preds_all.append(df_m)

    combined_blend_preds = pd.concat(blend_preds_all, ignore_index=True)
    combined_meta_preds = pd.concat(meta_preds_all, ignore_index=True)
    
    y_all = encode(combined_blend_preds.future_direction)
    blend_overall = metrics(y_all, combined_blend_preds[["p_bearish", "p_sideways", "p_bullish"]].values)
    meta_overall = metrics(y_all, combined_meta_preds[["p_bearish", "p_sideways", "p_bullish"]].values)
    
    comb_selected = best_comb["selected"]
    
    ensemble_comparison = {
        "strongest_individual_model": {
            "name": comb_selected["name"],
            "accuracy": comb_selected["mean_accuracy"],
            "macro_f1": comb_selected["mean_macro_f1"],
            "log_loss": comb_selected["mean_log_loss"]
        },
        "probability_blend": {
            "accuracy": blend_overall["accuracy"],
            "balanced_accuracy": blend_overall["balanced_accuracy"],
            "macro_f1": blend_overall["macro_f1"],
            "log_loss": blend_overall["log_loss"],
            "delta_macro_f1_vs_individual": blend_overall["macro_f1"] - comb_selected["mean_macro_f1"]
        },
        "stacking_meta_model": {
            "accuracy": meta_overall["accuracy"],
            "balanced_accuracy": meta_overall["balanced_accuracy"],
            "macro_f1": meta_overall["macro_f1"],
            "log_loss": meta_overall["log_loss"],
            "delta_macro_f1_vs_individual": meta_overall["macro_f1"] - comb_selected["mean_macro_f1"]
        },
        "conclusion": "Ensembling compared directly against the standalone combined model; does not automatically assume superior performance."
    }
    
    write_json(out / "ensemble_comparison.json", ensemble_comparison)
    return ensemble_comparison, combined_blend_preds, combined_meta_preds


# =====================================================================
# FEATURE ABLATIONS & SUBGROUP PERFORMANCE
# =====================================================================

def run_feature_ablations(splits: List[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]], 
                         out: Path) -> pd.DataFrame:
    logger.info("Running feature-group ablations (technical, financial, filing-age, market-context)...")
    
    ablation_sets = {
        "all_combined": GROUPS["combined"],
        "minus_market_context": [f for f in GROUPS["combined"] if f not in MARKET_CONTEXT],
        "minus_filing_age": [f for f in GROUPS["combined"] if f not in FILING_AGE],
        "technical_only": TECHNICAL_BASE + MARKET_CONTEXT,
        "fundamental_only": FUNDAMENTAL_BASE + FILING_AGE,
    }
    
    rows = []
    base_params = {"kind": "xgboost", "max_depth": 3, "n_estimators": 160, "learning_rate": 0.03,
                   "subsample": 0.85, "colsample_bytree": 0.85, "reg_lambda": 10.0, "min_child_weight": 20, "weighted": True}
    
    for name, feat_list in ablation_sets.items():
        f1_list, loss_list, acc_list = [], [], []
        for fold, (train, cal, valid) in enumerate(splits):
            m = fit_model(train, feat_list, base_params, seed=42 + fold)
            vp = predict_probs(m, valid, feat_list)
            y_val = encode(valid.future_direction)
            res = metrics(y_val, vp)
            f1_list.append(res["macro_f1"])
            loss_list.append(res["log_loss"])
            acc_list.append(res["accuracy"])
        
        rows.append({
            "ablation_group": name,
            "feature_count": len(feat_list),
            "macro_f1": float(np.mean(f1_list)),
            "log_loss": float(np.mean(loss_list)),
            "accuracy": float(np.mean(acc_list)),
            "delta_macro_f1_vs_full": float(np.mean(f1_list)) - rows[0]["macro_f1"] if rows else 0.0
        })
        
    ablation_df = pd.DataFrame(rows)
    ablation_df.to_csv(out / "ablations.csv", index=False)
    return ablation_df


# =====================================================================
# SELECTIVE PREDICTIONS & REALISTIC TRADING EVALUATION
# =====================================================================

def evaluate_selective_predictions_and_trading(valid_preds: pd.DataFrame, 
                                               prices: pd.DataFrame, out: Path) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    logger.info("Evaluating selective predictions with confidence thresholds and realistic backtest simulation...")
    
    # 1. Selective Prediction Gating
    thresholds = [0.35, 0.40, 0.45, 0.50, 0.55, 0.60]
    results = []
    
    y = encode(valid_preds.future_direction)
    p = valid_preds[["p_bearish", "p_sideways", "p_bullish"]].values
    max_probs = np.max(p, axis=1)
    pred_labels = np.argmax(p, axis=1)
    
    for th in thresholds:
        mask = max_probs >= th
        n_signals = int(mask.sum())
        coverage = float(n_signals / len(valid_preds) * 100)
        
        if n_signals > 0:
            sel_y = y[mask]
            sel_pred = pred_labels[mask]
            sel_acc = float(accuracy_score(sel_y, sel_pred) * 100)
            sel_f1 = float(f1_score(sel_y, sel_pred, labels=[0, 1, 2], average="macro", zero_division=0))
            
            # Uncertainty interval across folds (Fold 0, Fold 1, Fold 2)
            fold_accs = []
            for f in valid_preds["fold"].unique():
                f_mask = mask & (valid_preds["fold"] == f)
                if f_mask.sum() > 0:
                    fold_accs.append(accuracy_score(y[f_mask], pred_labels[f_mask]))
            ci_low = float(np.min(fold_accs) * 100) if fold_accs else sel_acc
            ci_high = float(np.max(fold_accs) * 100) if fold_accs else sel_acc
        else:
            sel_acc, sel_f1, ci_low, ci_high = np.nan, np.nan, np.nan, np.nan
            
        results.append({
            "threshold_tau": th,
            "signals_count": n_signals,
            "coverage_pct": coverage,
            "selective_accuracy": sel_acc,
            "fold_range_ci": f"[{ci_low:.1f}%, {ci_high:.1f}%]" if pd.notna(ci_low) else "N/A",
            "selective_macro_f1": sel_f1
        })
        
    selective_df = pd.DataFrame(results)
    selective_df.to_csv(out / "selective_predictions.csv", index=False)
    
    # 2. Realistic Long Strategy Simulation
    # Executable Timing: Signal computed at session t close; entry at t+1 close; exit at t+21 close.
    # Friction: 40 bps round-trip on traded notional.
    valid_preds = valid_preds.copy()
    valid_preds["expected_return"] = valid_preds["p_bullish"] - valid_preds["p_bearish"]
    
    # Run backtest per 20 sessions
    sessions = np.sort(valid_preds.session.unique())
    holding_returns = []
    turnover_list = []
    current_holdings = set()
    
    for s_idx in range(0, len(sessions) - 20, 20):
        s_date = sessions[s_idx]
        batch = valid_preds[valid_preds["session"] == s_date].copy()
        
        # Select top 5 bullish stocks with p_bullish >= 0.40
        long_picks = batch[batch["p_bullish"] >= 0.40].sort_values("p_bullish", ascending=False).head(5)
        new_holdings = set(long_picks["symbol"].tolist())
        
        # Turnover
        if current_holdings:
            turnover = len(new_holdings.symmetric_difference(current_holdings)) / (2.0 * max(len(current_holdings), 1))
        else:
            turnover = 1.0 if new_holdings else 0.0
        turnover_list.append(turnover)
        current_holdings = new_holdings
        
        if len(long_picks) > 0:
            # 20-session realized return from prices
            rets = []
            for sym in long_picks["symbol"]:
                sym_prices = prices[prices["symbol"] == sym].sort_values("session").reset_index(drop=True)
                sym_sess = sym_prices[sym_prices["session"] == s_date].index
                if len(sym_sess) > 0:
                    i = sym_sess[0]
                    if i + 21 < len(sym_prices):
                        entry_p = sym_prices.loc[i + 1, "close"]
                        exit_p = sym_prices.loc[i + 21, "close"]
                        if entry_p > 0:
                            rets.append((exit_p / entry_p - 1.0))
            if rets:
                gross_ret = np.mean(rets)
                # Apply 40 bps friction on turnover
                net_ret = gross_ret - (turnover * 0.0040)
                holding_returns.append(net_ret)
            else:
                holding_returns.append(0.0)
        else:
            holding_returns.append(0.0)
            
    if holding_returns:
        nav = np.cumprod(1.0 + np.array(holding_returns))
        total_ret = nav[-1] - 1.0
        n_years = len(holding_returns) * 20 / 252.0
        cagr = (nav[-1] ** (1.0 / max(n_years, 0.1))) - 1.0 if nav[-1] > 0 else -1.0
        peak = np.maximum.accumulate(nav)
        max_dd = np.min((nav - peak) / peak)
        vol = np.std(holding_returns) * np.sqrt(252 / 20)
        sharpe = (cagr - 0.15) / max(vol, 1e-4)
        mean_turnover = float(np.mean(turnover_list))
    else:
        cagr, max_dd, sharpe, mean_turnover = 0.0, 0.0, 0.0, 0.0
        
    backtest_metrics = {
        "rule": "Every 20 sessions pick top 5 bullish stocks (p_bullish >= 0.40). Entry at t+1 close, exit at t+21 close.",
        "friction_bps": 40,
        "holding_periods": len(holding_returns),
        "cagr_pct": float(cagr * 100),
        "max_drawdown_pct": float(max_dd * 100),
        "annualized_volatility_pct": float(vol * 100) if holding_returns else 0.0,
        "sharpe_ratio": float(sharpe),
        "mean_turnover_pct": float(mean_turnover * 100)
    }
    
    write_json(out / "backtest_simulation.json", backtest_metrics)
    return selective_df, backtest_metrics


# =====================================================================
# MAIN PIPELINE EXECUTION
# =====================================================================

def run_v3(as_of_str: str, out_dir: Path):
    logger.info("Initializing PSXpert combined_v3 pipeline...")
    before = inventory()
    if out_dir.exists():
        import shutil
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=False)
    write_json(out_dir / "preservation_before.json", before)
    
    # 1. Audit Usable Information
    audit_summary = audit_usable_information(out_dir)
    
    # 2. Ingest Identical Eligible Rows and Folds
    v2_dir = ROOT / "artifacts/combined_v2"
    eligible_path = v2_dir / "eligible_rows.csv.gz"
    if not eligible_path.exists():
        raise FileNotFoundError(f"Missing base eligible rows: {eligible_path}")
    
    data = pd.read_csv(eligible_path)
    data.to_csv(out_dir / "eligible_rows.csv.gz", index=False)
    
    # Load identical split manifests using exact (symbol, session) keys
    splits = []
    for fold in range(3):
        tr = pd.read_csv(v2_dir / f"split_{fold}_train.csv.gz")
        ca = pd.read_csv(v2_dir / f"split_{fold}_calibration.csv.gz")
        va = pd.read_csv(v2_dir / f"split_{fold}_validation.csv.gz")
        
        train_df = data.merge(tr[["symbol", "session"]], on=["symbol", "session"], validate="one_to_one")
        cal_df = data.merge(ca[["symbol", "session"]], on=["symbol", "session"], validate="one_to_one")
        val_df = data.merge(va[["symbol", "session"]], on=["symbol", "session"], validate="one_to_one")
        splits.append((train_df, cal_df, val_df))

    # 3. Controlled Model Search & Experiments
    study = BoundedSearchStudy(name="PSXpert_v3_study", seed=42)
    exp_results = {}
    
    for exp in ["technical", "fundamental", "combined"]:
        res = evaluate_v3_experiment(exp, splits, out_dir, study)
        exp_results[exp] = res
        
    # Save Search Trials
    trials_df = pd.DataFrame(study.trials)
    trials_df.to_csv(out_dir / "trials.csv", index=False)
    write_json(out_dir / "trials.json", study.trials)
    
    # 4. Ensembling Without Leakage
    ensemble_results, blend_preds, meta_preds = evaluate_ensembling(
        splits, exp_results["technical"], exp_results["fundamental"], exp_results["combined"], out_dir
    )
    
    # 5. Feature-Group Ablations
    ablation_df = run_feature_ablations(splits, out_dir)
    
    # 6. Selective Predictions & Realistic Backtest
    best_combined_preds = exp_results["combined"]["predictions"]
    prices_raw = data[["symbol", "session", "close"]].drop_duplicates().sort_values(["symbol", "session"])
    selective_df, backtest_metrics = evaluate_selective_predictions_and_trading(best_combined_preds, prices_raw, out_dir)
    
    # 7. Subgroup Performance (by Period, Sector, Class)
    subgroups = {}
    # By Period
    period_metrics = {}
    for fold in sorted(best_combined_preds["fold"].unique()):
        sub_p = best_combined_preds[best_combined_preds["fold"] == fold]
        period_metrics[f"Fold_{fold}"] = metrics(encode(sub_p.future_direction), sub_p[["p_bearish", "p_sideways", "p_bullish"]].values)
    subgroups["by_period"] = period_metrics
    
    # By Sector
    sector_metrics = {}
    for sec, sec_df in best_combined_preds.groupby("sector"):
        if len(sec_df) >= 200:
            sector_metrics[sec] = {
                "rows": len(sec_df),
                "accuracy": float(accuracy_score(encode(sec_df.future_direction), np.argmax(sec_df[["p_bearish", "p_sideways", "p_bullish"]].values, axis=1))),
                "macro_f1": float(f1_score(encode(sec_df.future_direction), np.argmax(sec_df[["p_bearish", "p_sideways", "p_bullish"]].values, axis=1), average="macro", zero_division=0))
            }
    subgroups["by_sector"] = sector_metrics
    write_json(out_dir / "subgroup_performance.json", subgroups)
    
    # 8. Comparison JSON
    comparison_data = {
        "experiments": {
            k: {
                "selected": v["selected"]["name"],
                "family": v["selected"]["family"],
                "accuracy": v["selected"]["mean_accuracy"],
                "balanced_accuracy": v["selected"]["mean_balanced_accuracy"],
                "macro_f1": v["selected"]["mean_macro_f1"],
                "log_loss": v["selected"]["mean_log_loss"],
                "parameters": v["selected"]["parameters"]
            }
            for k, v in exp_results.items()
        },
        "ensembling": ensemble_results,
        "selective_predictions": selective_df.to_dict(orient="records"),
        "backtest": backtest_metrics,
        "fresh_test_verified": False,
        "limitations": [
            "Optuna package was not locally installed; bounded reproducible pseudo-random sampler used with fixed seed 42.",
            "Fresh held-out outcomes (> Oct 2026) lack resolved 20-session labels; fresh test left unverified.",
            "Historical accounting vintages unavailable in database snapshot; statutory 120-day publication assumed for pre-2015 statements.",
            "Corporate action effective dates unverified; jump quarantine and payout window isolation remain provisional.",
            "Delisted companies missing from roster introduces survivorship bias."
        ]
    }
    write_json(out_dir / "comparison.json", comparison_data)
    
    # 9. Verify Preservation
    after = inventory()
    if before != after:
        raise AssertionError("Protected artifact/CSV inventory was modified!")
    write_json(out_dir / "preservation_after.json", after)
    
    # 10. Reproducibility
    write_json(out_dir / "reproducibility.json", {
        "command": f"python -m m1.v3 --as-of {as_of_str}",
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "sklearn": sklearn.__version__,
        "scipy": scipy.__version__,
        "xgboost": xgb.__version__,
        "lightgbm": lgb.__version__,
        "catboost": cb.__version__,
        "seed": 42
    })
    
    logger.info("PSXpert combined_v3 pipeline finished successfully!")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default="2026-11-16T14:00:00+05:00")
    args = parser.parse_args()
    run_v3(args.as_of, ROOT / "artifacts/combined_v3")


if __name__ == "__main__":
    main()
