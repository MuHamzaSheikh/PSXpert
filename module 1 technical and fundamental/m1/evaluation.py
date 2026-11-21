"""Chronological experiment splits and held-out scoring."""

import numpy as np
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score, log_loss, mean_absolute_error,
    precision_score, recall_score, roc_auc_score, root_mean_squared_error,
)

from .settings import CLASSES
from .sources import DataUnavailable


def temporal_splits(data, embargo_sessions):
    sessions = np.sort(data["session"].unique())
    if len(sessions) < 180:
        raise DataUnavailable("At least 180 common eligible sessions are required for three temporal folds")
    test_at = int(len(sessions) * 0.80)
    edges = [int(len(sessions) * fraction) for fraction in (0.35, 0.50, 0.65)]
    folds = []
    for start, end in zip(edges, edges[1:] + [test_at]):
        boundary = sessions[start]
        # Global session ordinals enforce the same purge for every ticker.
        train = data.loc[data["session"].lt(boundary)
                         & data["target_session"].lt(boundary - embargo_sessions)]
        valid = data.loc[data["session"].ge(boundary) & data["session"].lt(sessions[end])
                         & data["target_session"].lt(sessions[end] - embargo_sessions)]
        if train.empty or valid.empty:
            raise DataUnavailable("Empty training or validation partition after purging")
        folds.append((train, valid))
    test = data.loc[data["session"].ge(sessions[test_at])]
    return folds, test


def describe_split(frame):
    return {
        "rows": len(frame), "tickers": int(frame["symbol"].nunique()),
        "first_signal": frame["prediction_timestamp"].min(),
        "last_signal": frame["prediction_timestamp"].max(),
        "last_label": frame["target_timestamp"].max(),
        "classes": frame["future_direction"].value_counts().to_dict(),
    }


def classification(y, probability):
    pred = probability.argmax(axis=1)
    labels = np.arange(len(CLASSES))
    one_hot = np.eye(len(CLASSES))[y]
    reliability = {}
    edges = np.linspace(0, 1, 11)
    for index, name in enumerate(CLASSES):
        p = probability[:, index]
        buckets = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, 9)
        reliability[name] = [
            {"bin_lower": edges[b], "bin_upper": edges[b + 1], "count": int(mask.sum()),
             "mean_probability": float(p[mask].mean()), "observed_frequency": float(one_hot[mask, index].mean())}
            for b in range(10) if (mask := buckets == b).any()
        ]
    return {
        "accuracy": accuracy_score(y, pred),
        "balanced_accuracy": balanced_accuracy_score(y, pred),
        "precision_macro": precision_score(y, pred, labels=labels, average="macro", zero_division=0),
        "recall_macro": recall_score(y, pred, labels=labels, average="macro", zero_division=0),
        "f1_macro": f1_score(y, pred, labels=labels, average="macro", zero_division=0),
        "confusion_matrix": confusion_matrix(y, pred, labels=labels).tolist(),
        "class_order": list(CLASSES),
        "roc_auc_ovr_macro": roc_auc_score(y, probability, labels=labels, multi_class="ovr")
        if len(np.unique(y)) == len(labels) else None,
        "log_loss": log_loss(y, probability, labels=labels),
        "multiclass_brier": float(np.mean(np.sum((probability - one_hot) ** 2, axis=1))),
        "classwise_calibration": reliability,
    }


def regression(actual, predicted, historical_mean):
    return {
        "mae": mean_absolute_error(actual, predicted),
        "rmse": root_mean_squared_error(actual, predicted),
        "zero_baseline_mae": float(np.abs(actual).mean()),
        "zero_baseline_rmse": float(np.sqrt(np.mean(actual ** 2))),
        "training_mean_baseline_mae": float(np.abs(actual - historical_mean).mean()),
        "training_mean_baseline_rmse": float(np.sqrt(np.mean((actual - historical_mean) ** 2))),
    }
