"""Exact XGBoost TreeSHAP via its native contribution API."""

import os

import numpy as np
import xgboost as xgb

from .features import TECHNICAL
from .settings import CLASSES, ROOT


def contribution_arrays(classifier, regressor, features):
    matrix = xgb.DMatrix(features)
    classes = classifier.get_booster().predict(matrix, pred_contribs=True, strict_shape=True)
    expected = regressor.get_booster().predict(matrix, pred_contribs=True, strict_shape=True)[:, 0, :]
    return classes, expected


def _local(names, vector):
    groups = {name: "technical" if name in TECHNICAL else "fundamental" for name in names}
    entries = [
        {"feature": name, "group": groups[name], "contribution": float(value)}
        for name, value in zip(names, vector[:-1])
    ]
    return {
        "base_value": float(vector[-1]),
        "output": float(vector.sum()),
        "group_totals": {group: sum(item["contribution"] for item in entries if item["group"] == group)
                         for group in ("technical", "fundamental")},
        "features": sorted(entries, key=lambda item: abs(item["contribution"]), reverse=True),
    }


def explain_prediction(classifier, regressor, features):
    direction, expected = contribution_arrays(classifier, regressor, features)
    return {
        "direction_output_scale": "uncalibrated logit",
        "return_output_scale": "percentage points",
        "direction_by_class": {
            label: _local(features.columns, direction[0, index]) for index, label in enumerate(CLASSES)
        },
        "expected_return": _local(features.columns, expected[0]),
    }


def save_global(classifier, regressor, features, destination):
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "artifacts" / ".matplotlib"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    direction, expected = contribution_arrays(classifier, regressor, features)
    vectors = {
        **{f"direction_{label.lower()}": direction[:, i, :-1] for i, label in enumerate(CLASSES)},
        "expected_return": expected[:, :-1],
    }
    results = {}
    for output, vector in vectors.items():
        magnitude = np.abs(vector).mean(axis=0)
        pairs = sorted(zip(features.columns, magnitude), key=lambda pair: pair[1])
        results[output] = {name: float(value) for name, value in reversed(pairs)}
        figure, axis = plt.subplots(figsize=(9, 6))
        names, values = zip(*pairs[-15:])
        axis.barh(names, values, color=["#245779" if n in TECHNICAL else "#b47929" for n in names])
        axis.set_xlabel("Mean absolute SHAP contribution")
        axis.set_title(output.replace("_", " ").capitalize())
        figure.tight_layout()
        figure.savefig(destination / f"{output}.png", dpi=140)
        plt.close(figure)
    return results


def save_return_plot(predictions, destination):
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(7, 6))
    axis.scatter(predictions["actual_return_pct"], predictions["expected_return_pct"], alpha=0.25, s=10)
    axis.axhline(0, color="#777777", linewidth=1)
    axis.axvline(0, color="#777777", linewidth=1)
    axis.set(xlabel="Actual 20-session return (%)", ylabel="Predicted 20-session return (%)")
    figure.tight_layout()
    figure.savefig(destination / "predicted_vs_actual.png", dpi=140)
    plt.close(figure)
