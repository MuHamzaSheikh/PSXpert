"""Train, evaluate and publish a versioned classifier/regressor pair per experiment."""

import json
import re
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from scipy.special import softmax

from .backtest import simulate
from .evaluation import classification, describe_split, regression, temporal_splits
from .explain import save_global, save_return_plot
from .features import GROUPS, directions, research_rows
from .settings import CLASSES, FEATURE_VERSION, PRICE_BASIS, ROOT, Settings, TZ
from .sources import DataUnavailable

MODEL_PARAMETERS = {
    "n_estimators": 120, "max_depth": 3, "learning_rate": 0.05, "subsample": 0.85,
    "colsample_bytree": 0.85, "tree_method": "hist", "n_jobs": 2,
}


def encode(values):
    codes = values.map({label: index for index, label in enumerate(CLASSES)})
    if codes.isna().any():
        raise DataUnavailable("Invalid or missing direction labels")
    return codes.to_numpy(dtype=int)


def models(train, names, settings, labels=None, with_regression=True):
    labels = encode(train["future_direction"] if labels is None else labels)
    if len(np.unique(labels)) != len(CLASSES):
        raise DataUnavailable("All three direction classes must occur in every classifier training partition")
    parameters = {**MODEL_PARAMETERS, "random_state": settings.seed}
    classifier = xgb.XGBClassifier(**parameters, objective="multi:softprob", num_class=len(CLASSES),
                                   eval_metric="mlogloss").fit(train[names], labels)
    regressor = None
    if with_regression:
        regressor = xgb.XGBRegressor(**parameters, objective="reg:squarederror").fit(
            train[names], train["future_20_day_return_pct"]
        )
    return classifier, regressor


def probability(classifier, features, calibration=None):
    if calibration is None:
        return classifier.predict_proba(features)
    margins = classifier.predict(features, output_margin=True)
    return softmax(margins @ np.asarray(calibration["coef"]).T + calibration["intercept"], axis=1)


def fit_calibration(classifier, features, y):
    counts = np.bincount(y, minlength=len(CLASSES))
    if counts.min() < 20:
        return None
    margins = classifier.predict(features, output_margin=True)
    calibrator = LogisticRegression(max_iter=500).fit(margins, y)
    return {"coef": calibrator.coef_.tolist(), "intercept": calibrator.intercept_.tolist(),
            "method": "multinomial logistic recalibration on terminal validation only"}


def write_json(path, value):
    def convert(obj):
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, Path):
            return str(obj)
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        raise TypeError(f"Cannot serialize {type(obj).__name__}")
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, default=convert, indent=2, allow_nan=False)
        output.write("\n")


def validate_version(version):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", version, flags=re.ASCII):
        raise ValueError("Invalid model version")
    return version


def train_all(data, source_metadata, version, settings=Settings(), root=ROOT / "artifacts"):
    validate_version(version)
    common = research_rows(data)
    if common.empty:
        raise DataUnavailable("No common rows have an eligible filing, 20-session label and warmed technical data")
    folds, test = temporal_splits(common, settings.embargo_sessions)
    root.mkdir(parents=True, exist_ok=True)
    plots = root / "plots" / version
    if (root / version).exists() or plots.exists() or version in {"plots", "scores"}:
        raise FileExistsError(f"Artifacts for {version} already exist")
    with TemporaryDirectory(dir=root) as temporary:
        work = Path(temporary) / version
        work.mkdir()
        report = {}
        for experiment, names in GROUPS.items():
            experiment_dir = work / experiment
            experiment_dir.mkdir()
            validation = []
            for train, valid in folds:
                classifier, regressor = models(train, names, settings)
                y = encode(valid["future_direction"])
                preds = valid[names]
                uncalibrated = probability(classifier, preds)
                validation.append({
                    "train": describe_split(train), "validation": describe_split(valid),
                    "classification": classification(y, uncalibrated),
                    "regression": regression(valid["future_20_day_return_pct"], regressor.predict(preds),
                                             train["future_20_day_return_pct"].mean()),
                })
            calibration = fit_calibration(classifier, valid[names], y)
            # The terminal validation period is used for calibration, so the artifact cutoff includes it.
            alternatives = {}
            if experiment == "combined":
                for threshold in (2.0, 5.0):
                    config = Settings(bearish=-threshold, bullish=threshold, seed=settings.seed)
                    training_labels = directions(train["future_20_day_return_pct"], config)
                    alternative_y = directions(valid["future_20_day_return_pct"], config)
                    try:
                        alternative, _ = models(train, names, settings, training_labels, with_regression=False)
                    except DataUnavailable as exc:
                        alternatives[str(threshold)] = {"status": str(exc)}
                    else:
                        alternatives[str(threshold)] = classification(
                            encode(alternative_y), probability(alternative, valid[names])
                        )
            held_features = test[names]
            y_test = encode(test["future_direction"])
            p_test = probability(classifier, held_features, calibration)
            r_test = regressor.predict(held_features)
            predictions = test[["symbol", "session", "prediction_timestamp", "target_timestamp"]].copy()
            predictions["actual_return_pct"] = test["future_20_day_return_pct"]
            predictions["actual_direction"] = test["future_direction"]
            predictions["direction"] = np.asarray(CLASSES)[p_test.argmax(axis=1)]
            predictions["expected_return_pct"] = r_test
            for i, name in enumerate(CLASSES):
                predictions[f"p_{name.lower()}"] = p_test[:, i]
            predictions.to_csv(experiment_dir / "held_out_predictions.csv", index=False)
            result = {
                "validation": validation, "validation_alternative_symmetric_thresholds": alternatives,
                "held_out": describe_split(test), "classification": classification(y_test, p_test),
                "regression": regression(predictions["actual_return_pct"], r_test,
                                         train["future_20_day_return_pct"].mean()),
                "uncalibrated_test_log_loss": log_loss(y_test, probability(classifier, held_features),
                                                       labels=np.arange(len(CLASSES))),
                "backtest": simulate(predictions, data, horizon=settings.horizon),
            }
            classifier.save_model(experiment_dir / "classifier.ubj")
            regressor.save_model(experiment_dir / "regressor.ubj")
            metadata = {
                "model_version": version, "experiment": experiment, "feature_version": FEATURE_VERSION,
                "features": names, "classes": list(CLASSES), "training_configuration": asdict(settings),
                "model_parameters": MODEL_PARAMETERS, "calibration": calibration,
                "model_training_cutoff": valid["target_timestamp"].max(),
                "estimator_training_cutoff": train["target_timestamp"].max(),
                "source_metadata": source_metadata, "price_basis": PRICE_BASIS,
                "timezone": TZ, "xgboost": xgb.__version__, "scikit_learn": sklearn.__version__,
            }
            write_json(experiment_dir / "metadata.json", metadata)
            write_json(experiment_dir / "evaluation.json", result)
            plot_dir = Path(temporary) / "plots" / experiment
            plot_dir.mkdir(parents=True)
            shap_features = held_features.sample(min(1000, len(held_features)), random_state=settings.seed)
            write_json(plot_dir / "shap_global.json", save_global(classifier, regressor, shap_features, plot_dir))
            save_return_plot(predictions, plot_dir)
            report[experiment] = {
                "mean_validation_macro_f1_uncalibrated": float(np.mean([
                    part["classification"]["f1_macro"] for part in validation
                ])),
                "mean_validation_rmse": float(np.mean([part["regression"]["rmse"] for part in validation])),
                "held_out_macro_f1": result["classification"]["f1_macro"],
                "held_out_rmse": result["regression"]["rmse"],
                "probabilities_calibrated": calibration is not None,
                "held_out_log_loss": result["classification"]["log_loss"],
                "held_out_rows": len(test),
            }
        comparison = {"experiments": report,
                      "best_validation_macro_f1": max(report, key=lambda key: report[key]["mean_validation_macro_f1_uncalibrated"]),
                      "best_validation_rmse": min(report, key=lambda key: report[key]["mean_validation_rmse"])}
        write_json(work / "comparison.json", comparison)
        plots.parent.mkdir(exist_ok=True)
        staged_plots = Path(temporary) / "plots"
        staged_plots.rename(plots)
        try:
            work.rename(root / version)
        except OSError:
            plots.rename(staged_plots)
            raise
    return comparison


def load_models(version, root=ROOT / "artifacts"):
    directory = root / validate_version(version) / "combined"
    try:
        with (directory / "metadata.json").open(encoding="utf-8") as file:
            metadata = json.load(file)
        if (metadata["features"] != GROUPS["combined"] or metadata["classes"] != list(CLASSES)
                or metadata["feature_version"] != FEATURE_VERSION or metadata["model_version"] != version):
            raise DataUnavailable("Combined artifact feature schema or metadata is incompatible")
        classifier, regressor = xgb.XGBClassifier(), xgb.XGBRegressor()
        classifier.load_model(directory / "classifier.ubj")
        regressor.load_model(directory / "regressor.ubj")
        if any(estimator.get_booster().feature_names != metadata["features"]
               for estimator in (classifier, regressor)):
            raise DataUnavailable("Saved model feature names differ from artifact metadata")
    except (OSError, KeyError, ValueError, xgb.core.XGBoostError) as exc:
        raise DataUnavailable(f"Combined model {version} is unavailable or unreadable") from exc
    return classifier, regressor, metadata
