"""Shared classification, calibration, and regime-stratified evaluation utilities."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)


def multiclass_brier_score(y_true: np.ndarray, y_prob: np.ndarray, n_classes: int) -> float:
    """Compute multiclass Brier score: mean over samples of sum_k (p_k - y_k)^2."""
    y_oh = np.eye(n_classes, dtype=np.float64)[y_true.astype(int)]
    return float(np.mean(np.sum((y_prob - y_oh) ** 2, axis=1)))


def expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> tuple[float, list[dict[str, Any]]]:
    """
    Compute top-label Expected Calibration Error (ECE) and reliability curve bins
    comparing predicted confidence max_k P(y=k|x) against empirical accuracy.
    """
    conf = np.max(y_prob, axis=1)
    pred = np.argmax(y_prob, axis=1)
    acc = (pred == y_true).astype(np.float64)

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    bins_out: list[dict[str, Any]] = []
    for b in range(n_bins):
        lo, hi = edges[b], edges[b + 1]
        if b == n_bins - 1:
            mask = (conf >= lo) & (conf <= hi)
        else:
            mask = (conf >= lo) & (conf < hi)
        cnt = int(mask.sum())
        if cnt == 0:
            bins_out.append({"bin": f"[{lo:.1f},{hi:.1f}]", "count": 0, "mean_confidence": None, "empirical_accuracy": None})
            continue
        m_conf = float(conf[mask].mean())
        m_acc = float(acc[mask].mean())
        ece += (cnt / max(1, n)) * abs(m_acc - m_conf)
        bins_out.append(
            {
                "bin": f"[{lo:.1f},{hi:.1f}]",
                "count": cnt,
                "mean_confidence": round(m_conf, 4),
                "empirical_accuracy": round(m_acc, 4),
            }
        )
    return float(ece), bins_out


def evaluate_multiclass_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: Optional[np.ndarray],
    class_names: list[str],
) -> dict[str, Any]:
    """Compute complete classification, confusion matrix, ROC-AUC, and calibration metrics."""
    n_classes = len(class_names)
    labels = list(range(n_classes))

    acc = float(accuracy_score(y_true, y_pred))
    prec_macro = float(precision_score(y_true, y_pred, labels=labels, average="macro", zero_division=0))
    rec_macro = float(recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0))
    f1_macro = float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0))
    prec_w = float(precision_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0))
    rec_w = float(recall_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0))
    f1_w = float(f1_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0))

    cm = confusion_matrix(y_true, y_pred, labels=labels)
    cm_norm = cm.astype(np.float64) / np.maximum(cm.sum(axis=1, keepdims=True), 1)
    cls_rep = classification_report(
        y_true,
        y_pred,
        labels=labels,
        target_names=class_names,
        output_dict=True,
        zero_division=0,
    )

    per_class = {
        cname: {
            "precision": round(float(cls_rep[cname]["precision"]), 4),
            "recall": round(float(cls_rep[cname]["recall"]), 4),
            "f1": round(float(cls_rep[cname]["f1-score"]), 4),
            "support": int(cls_rep[cname]["support"]),
        }
        for cname in class_names
    }

    roc_ovr_macro: Optional[float] = None
    roc_ovr_weighted: Optional[float] = None
    brier: Optional[float] = None
    lloss: Optional[float] = None
    ece: Optional[float] = None
    rel_bins: Optional[list[dict[str, Any]]] = None

    if y_prob is not None:
        probs = np.clip(np.asarray(y_prob, dtype=np.float64), 1e-7, 1.0 - 1e-7)
        probs = probs / probs.sum(axis=1, keepdims=True)
        unique_true = np.unique(y_true)
        if len(unique_true) == n_classes:
            try:
                roc_ovr_macro = round(float(roc_auc_score(y_true, probs, multi_class="ovr", average="macro")), 4)
                roc_ovr_weighted = round(float(roc_auc_score(y_true, probs, multi_class="ovr", average="weighted")), 4)
            except ValueError:
                roc_ovr_macro = None
                roc_ovr_weighted = None
        brier = round(multiclass_brier_score(y_true, probs, n_classes), 4)
        lloss = round(float(log_loss(y_true, probs, labels=labels)), 4)
        ece_val, rel_bins = expected_calibration_error(y_true, probs, n_bins=10)
        ece = round(ece_val, 4)

    return {
        "n_samples": int(len(y_true)),
        "accuracy": round(acc, 4),
        "precision_macro": round(prec_macro, 4),
        "recall_macro": round(rec_macro, 4),
        "f1_macro": round(f1_macro, 4),
        "precision_weighted": round(prec_w, 4),
        "recall_weighted": round(rec_w, 4),
        "f1_weighted": round(f1_w, 4),
        "roc_auc_ovr_macro": roc_ovr_macro,
        "roc_auc_ovr_weighted": roc_ovr_weighted,
        "brier_score": brier,
        "log_loss": lloss,
        "ece": ece,
        "calibration_bins": rel_bins,
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_normalized": np.round(cm_norm, 4).tolist(),
        "per_class": per_class,
    }


def evaluate_by_regime(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: Optional[np.ndarray],
    regime_series: pd.Series,
    class_names: list[str],
) -> dict[str, Any]:
    """Stratify evaluation metrics across causal KSE-100 market regimes."""
    out: dict[str, Any] = {}
    reg_vals = regime_series.fillna("UNKNOWN").astype(str)
    for reg_name in sorted(reg_vals.unique()):
        mask = (reg_vals == reg_name).to_numpy()
        if int(mask.sum()) < 5:
            continue
        p_sub = y_prob[mask] if y_prob is not None else None
        res = evaluate_multiclass_predictions(y_true[mask], y_pred[mask], p_sub, class_names)
        # Keep summary concise inside regime map
        out[reg_name] = {
            "n_samples": res["n_samples"],
            "accuracy": res["accuracy"],
            "precision_macro": res["precision_macro"],
            "recall_macro": res["recall_macro"],
            "f1_macro": res["f1_macro"],
            "roc_auc_ovr_macro": res["roc_auc_ovr_macro"],
            "brier_score": res["brier_score"],
            "ece": res["ece"],
        }
    return out

