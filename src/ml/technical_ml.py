"""Technical Analysis ML Model: training, causal labeling, calibration, evaluation, and live inference."""

from __future__ import annotations

import hashlib
import json
import logging
import platform
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb_pkg
from sklearn.base import BaseEstimator, ClassifierMixin, TransformerMixin
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.utils.class_weight import compute_sample_weight
from sqlalchemy import text
from sqlalchemy.engine import Connection
from xgboost import XGBClassifier

from src.analysis.common import (
    get_company_metadata,
    load_clean_symbol_prices,
    load_trading_calendar,
    resolve_effective_as_of_date,
    safe_float,
    sanitize_for_json,
)
from src.ml.conviction_filter import (
    ConvictionTier,
    SelectiveAction,
    classify_conviction,
    compute_dynamic_barriers,
)
from src.ml.metrics import evaluate_by_regime, evaluate_multiclass_predictions
from src.predictive_data.daily_builder import (
    _compute_causal_wilder_rsi,
    _compute_stock_features_and_candlesticks,
)
from src.predictive_data.regime_causal import CausalMarketRegimeHMM
from src.predictive_data.splits import build_chronological_splits

logger = logging.getLogger(__name__)

TECHNICAL_MODEL_VERSION = "psxpert_tech_ml_v2.0"
LABEL_NAMES = ["Bearish", "Neutral", "Bullish"]  # indices 0, 1, 2
DEFAULT_ARTIFACTS_DIR = Path("artifacts/technical")
DEFAULT_MODEL_DIR = DEFAULT_ARTIFACTS_DIR
DEFAULT_REPORTS_DIR = Path("reports/ml")

# Strictly causal, stationary feature schema aligned with Step 2 & feature_dictionary.csv.
# Excludes raw price levels, future targets, fundamental ratios, news counts, and
# the independent long-horizon target components (pos_252d, ker_90d, ir_126d).
TECHNICAL_FEATURE_COLS: list[str] = [
    # 1. Returns & OHLCV bar dynamics
    "ret_1d",
    "ret_2d",
    "ret_5d",
    "ret_10d",
    "ret_20d",
    "log_ret_1d",
    "overnight_gap_pct",
    "intraday_ret_pct",
    # 2. Moving Average distances & spreads
    "dist_sma_20",
    "dist_sma_50",
    "dist_sma_200",
    "dist_ema_20",
    "ema_20_50_spread",
    "ema_50_200_spread",
    # 3. Oscillators & Trend Strength
    "rsi_14",
    "macd_diff_pct",
    "bb_bandwidth",
    "bb_percent_b",
    "atr_pct",
    "dmi_plus_14",
    "dmi_minus_14",
    "adx_14",
    "dmi_diff",
    "obv_zscore_20",
    "stoch_k",
    "stoch_d",
    "stoch_k_minus_d",
    # 4. Candlestick anatomy & pattern signals (true-OHLC guarded)
    "candle_body_pct",
    "candle_range_pct",
    "upper_shadow_ratio",
    "lower_shadow_ratio",
    "body_to_range_ratio",
    "close_position_in_range",
    "candlestick_pattern_signal_num",
    "is_bullish_pattern",
    "is_bearish_pattern",
    "is_doji_true_ohlc",
    "bullish_patterns_5d",
    "bearish_patterns_5d",
    "is_true_ohlc",
    # 5. Volatility & Liquidity
    "vol_5d",
    "vol_20d",
    "vol_60d",
    "vol_ratio_5_20",
    "parkinson_vol_20d",
    "log_volume",
    "log_turnover_pkr",
    "volume_ratio_20d",
    "amihud_illiquidity_20d",
    "zero_volume_days_20d",
    "hl_spread_pct",
    "trailing_20d_adv_rank",
    "listing_age_sessions",
    "calendar_gap_days",
    # 6. Causal HMM market regime & KSE-100 / Cross-Sectional Market Context
    "hmm_mkt_prob_bullish",
    "hmm_mkt_prob_bearish",
    "hmm_mkt_prob_sideways",
    "hmm_mkt_regime_id",
    "hmm_mkt_entropy",
    "hmm_mkt_regime_duration",
    "kse100_ret_1d",
    "kse100_ret_5d",
    "kse100_ret_20d",
    "kse100_vol_20d",
    "kse100_dist_sma50",
    "kse100_dist_sma200",
    "kse100_rsi_14",
    "rel_strength_kse100_5d",
    "rel_strength_kse100_20d",
    "rolling_beta_60d",
    "rolling_corr_kse100_60d",
    "mkt_median_ret_1d",
    "mkt_pct_above_sma50",
    "mkt_adv_decline_ratio",
]

# Documented volatility-aware forward 5-session technical market condition labeling
FORWARD_LABEL_SPEC = {
    "target_name": "technical_market_condition_5d_volatility_aware",
    "horizon_sessions": 5,
    "source_column": "target_label_5d",
    "threshold_formula": "0.0050 + 0.35 * max(vol_20d[t], 0.005) * sqrt(5)",
    "classes": {0: "Bearish", 1: "Neutral", 2: "Bullish"},
    "rules": {
        "Bullish": "target_ret_5d >= +threshold_5d (UP in daily_targets.parquet)",
        "Bearish": "target_ret_5d <= -threshold_5d (DOWN in daily_targets.parquet)",
        "Neutral": "|target_ret_5d| < threshold_5d (NEUTRAL in daily_targets.parquet)",
    },
    "filters": [
        "target_valid_5d == 1 (exact 5-session span, non-glitch horizon window, finite causal vol_20d)",
        "is_zero_volume == 0 (active exchange session)",
        "TRAIN uses non-overlapping stride cal_idx % 5 == 0 to eliminate multi-day target overlap",
    ],
    "scope_note": (
        "Single-modality technical condition classification using technical/market indicators only; "
        "not the final multi-modal expected-return / multi-horizon forecasting model."
    ),
}

# Criteria for strictly causal multi-quarter structural technical regime labeling (preserved helper)
LABEL_SPEC = {
    "target_name": "causal_structural_technical_condition",
    "classes": {0: "Bearish", 1: "Neutral", 2: "Bullish"},
    "lookback_horizons_sessions": {
        "realized_information_ratio": 126,
        "kaufman_path_efficiency": 90,
        "donchian_channel_range": 252,
    },
    "rules": {
        "Bullish": "ir_126d >= 0.45 AND ker_90d >= 0.05 AND pos_252d >= 0.55",
        "Bearish": "ir_126d <= -0.45 AND ker_90d <= -0.05 AND pos_252d <= 0.45",
        "Neutral": "All remaining active observations (range-bound, transitional, or choppy regimes)",
    },
    "leakage_guarantee": "Uses exclusively <= t split-adjusted historical OHLC; zero future bars t+k used anywhere.",
}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_causal_technical_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate strictly future-independent technical-condition labels (Bearish=0, Neutral=1, Bullish=2)
    from realized causal price-path efficiency, risk-adjusted drift, and 252-day channel position.
    Expects panel sorted by ['symbol', 'cal_idx'].
    """
    g = df.groupby("symbol", sort=False)
    close = pd.to_numeric(df["adj_close"], errors="coerce")

    high_252 = g["adj_high"].transform(lambda s: pd.to_numeric(s, errors="coerce").rolling(252, min_periods=180).max())
    low_252 = g["adj_low"].transform(lambda s: pd.to_numeric(s, errors="coerce").rolling(252, min_periods=180).min())
    pos_252 = (close - low_252) / (high_252 - low_252).replace(0.0, np.nan)

    abs_diff_1d = g["adj_close"].transform(lambda s: pd.to_numeric(s, errors="coerce").diff().abs())
    sum_abs_90 = abs_diff_1d.groupby(df["symbol"], sort=False).transform(lambda s: s.rolling(90, min_periods=90).sum())
    net_90 = g["adj_close"].transform(lambda s: pd.to_numeric(s, errors="coerce") - pd.to_numeric(s, errors="coerce").shift(90))
    ker_90 = net_90 / sum_abs_90.replace(0.0, np.nan)

    log_ret_1d = g["adj_close"].transform(lambda s: np.log(pd.to_numeric(s, errors="coerce") / pd.to_numeric(s, errors="coerce").shift(1)))
    mean_126 = log_ret_1d.groupby(df["symbol"], sort=False).transform(lambda s: s.rolling(126, min_periods=126).mean())
    std_126 = log_ret_1d.groupby(df["symbol"], sort=False).transform(lambda s: s.rolling(126, min_periods=126).std())
    ir_126 = (mean_126 / std_126.replace(0.0, np.nan)) * np.sqrt(126.0)

    valid = (
        pos_252.notna()
        & ker_90.notna()
        & ir_126.notna()
        & df["dist_sma_200"].notna()
        & (df["is_zero_volume"] == 0)
    )

    is_bull = (ir_126 >= 0.45) & (ker_90 >= 0.05) & (pos_252 >= 0.55)
    is_bear = (ir_126 <= -0.45) & (ker_90 <= -0.05) & (pos_252 <= 0.45)
    y = np.where(is_bull, 2, np.where(is_bear, 0, 1)).astype(np.int8)

    return pd.DataFrame(
        {
            "target_cls": y,
            "target_valid": valid.astype(np.int8),
            "pos_252d": pos_252.astype(np.float32),
            "ker_90d": ker_90.astype(np.float32),
            "ir_126d": ir_126.astype(np.float32),
        },
        index=df.index,
    )


def compute_rule_baselines(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Compute Majority, Simple MA/RSI Rule, and TechnicalAnalysisEngine-equivalent rule baselines."""
    n = len(df)
    majority_pred = np.ones(n, dtype=np.int8)  # 1 = Neutral

    # Baseline 1: Simple MA Crossover + RSI(14) rule
    simple_bull = (df["ema_50_200_spread"] > 0) & (df["dist_sma_50"] > 0) & (df["rsi_14"] >= 50.0)
    simple_bear = (df["ema_50_200_spread"] < 0) & (df["dist_sma_50"] < 0) & (df["rsi_14"] <= 50.0)
    simple_rule_pred = np.where(simple_bull, 2, np.where(simple_bear, 0, 1)).astype(np.int8)

    # Baseline 2: TechnicalAnalysisEngine weighted rule approximation (non-ML existing engine logic)
    trend_sub = np.clip(
        np.where(df["dist_ema_20"] > 0, 40.0, -40.0)
        + np.where(
            (df["dist_sma_50"] > 0) & (df["dist_sma_200"] > 0),
            40.0,
            np.where((df["dist_sma_50"] < 0) & (df["dist_sma_200"] < 0), -40.0, 0.0),
        )
        + np.where(df["adx_14"] >= 20.0, np.where(df["dmi_diff"] > 0, 20.0, -20.0), 0.0),
        -100.0,
        100.0,
    )
    mom_sub = np.clip(
        np.where(
            df["rsi_14"] >= 70.0,
            15.0,
            np.where(
                df["rsi_14"] >= 55.0,
                40.0,
                np.where(df["rsi_14"] <= 30.0, -15.0, np.where(df["rsi_14"] <= 45.0, -40.0, 0.0)),
            ),
        )
        + np.where(df["macd_diff_pct"] > 0, 35.0, -35.0),
        -100.0,
        100.0,
    )
    obv_sub = np.where(df["obv_zscore_20"] > 0, 50.0, -50.0)
    pat_sub = (df["is_bullish_pattern"].fillna(0) - df["is_bearish_pattern"].fillna(0)) * 35.0
    hmm_sub = (df["hmm_mkt_prob_bullish"].fillna(0) - df["hmm_mkt_prob_bearish"].fillna(0)) * 100.0
    comp = 0.35 * trend_sub + 0.25 * mom_sub + 0.15 * obv_sub + 0.10 * pat_sub + 0.15 * hmm_sub
    engine_rule_pred = np.where(comp >= 15.0, 2, np.where(comp <= -15.0, 0, 1)).astype(np.int8)

    return {
        "majority_baseline": majority_pred,
        "simple_ma_rsi_rule": simple_rule_pred,
        "rule_engine_baseline": engine_rule_pred,
    }


class TrainOnlyPreprocessor(BaseEstimator, TransformerMixin):
    """Winsorization and imputation fitted strictly on training data to eliminate split leakage."""

    def __init__(self, feature_cols: list[str], impute_missing: bool = False) -> None:
        self.feature_cols = list(feature_cols)
        self.impute_missing = bool(impute_missing)
        self.clip_bounds: dict[str, tuple[float, float]] = {}
        self.medians: dict[str, float] = {}

    def fit(self, df_train: pd.DataFrame, y: Any = None) -> "TrainOnlyPreprocessor":
        for col in self.feature_cols:
            arr = pd.to_numeric(df_train[col], errors="coerce").to_numpy(dtype=np.float64)
            finite = arr[np.isfinite(arr)]
            if len(finite) > 0:
                if len(np.unique(finite)) <= 12:
                    q01, q99 = float(np.min(finite)), float(np.max(finite))
                else:
                    q01, q99 = np.percentile(finite, [0.5, 99.5])
                    if q99 <= q01:
                        q01, q99 = float(np.min(finite)), float(np.max(finite))
                med = float(np.median(finite))
            else:
                q01, q99, med = -1e9, 1e9, 0.0
            self.clip_bounds[col] = (float(q01), float(q99))
            self.medians[col] = med
        return self

    def transform_gbdt(self, df: pd.DataFrame) -> np.ndarray:
        """Winsorize finite features while keeping NaNs intact for GBDT native sparsity handling."""
        missing_cols = [c for c in self.feature_cols if c not in df.columns]
        if missing_cols:
            raise ValueError(f"Input is missing {len(missing_cols)} required feature column(s): {missing_cols[:5]}")
        mat = np.empty((len(df), len(self.feature_cols)), dtype=np.float32)
        for j, col in enumerate(self.feature_cols):
            arr = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=np.float64)
            lo, hi = self.clip_bounds[col]
            arr = np.where(np.isfinite(arr), np.clip(arr, lo, hi), np.nan)
            mat[:, j] = arr.astype(np.float32)
        return mat

    def transform_imputed(self, df: pd.DataFrame) -> np.ndarray:
        """Winsorize and fill NaNs using TRAIN medians for RandomForest compatibility."""
        mat = self.transform_gbdt(df).copy()
        for j, col in enumerate(self.feature_cols):
            med = self.medians[col]
            mask = ~np.isfinite(mat[:, j])
            if mask.any():
                mat[mask, j] = np.float32(med)
        return mat

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """Standard scikit-learn Transformer API respecting selected model's missing-value policy."""
        return self.transform_imputed(df) if self.impute_missing else self.transform_gbdt(df)


class CalibratedModelWrapper(BaseEstimator, ClassifierMixin):
    """Fitted multiclass classifier wrapping a base estimator and VAL-fitted log-odds calibrator."""

    def __init__(self, estimator: Any, calibrator: LogisticRegression, classes: Optional[np.ndarray] = None) -> None:
        self.estimator = estimator
        self.calibrator = calibrator
        self.classes_ = np.array([0, 1, 2], dtype=np.int32) if classes is None else classes
        self.n_features_in_ = getattr(estimator, "n_features_in_", len(TECHNICAL_FEATURE_COLS))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        raw = self.estimator.predict_proba(X)
        clipped = np.clip(raw, 1e-6, 1.0 - 1e-6)
        return self.calibrator.predict_proba(np.log(clipped))

    def predict(self, X: np.ndarray) -> np.ndarray:
        probs = self.predict_proba(X)
        return self.classes_[np.argmax(probs, axis=1)]

    @property
    def feature_importances_(self) -> np.ndarray:
        return getattr(self.estimator, "feature_importances_", np.ones(self.n_features_in_))


def _regime_labels_from_df(df: pd.DataFrame) -> pd.Series:
    return df["hmm_mkt_regime_id"].map({1.0: "BULLISH", 0.0: "SIDEWAYS", -1.0: "BEARISH"}).fillna("UNKNOWN")


def _fit_val_calibrator(raw_probs_val: np.ndarray, y_val: np.ndarray) -> tuple[Optional[LogisticRegression], bool, dict[str, Any]]:
    """
    Evaluate 5-fold stratified temperature/Platt calibration on VAL logits; keep calibrator
    only if cross-validated Log-Loss improves meaningfully without collapsing VAL Macro-F1.
    """
    eps = 1e-6
    clipped = np.clip(raw_probs_val, eps, 1.0 - eps)
    log_odds = np.log(clipped)

    skf = StratifiedKFold(n_splits=5, shuffle=False)
    oof_cal = np.zeros_like(clipped)
    for tr_i, te_i in skf.split(log_odds, y_val):
        lr = LogisticRegression(C=2.0, max_iter=500)
        lr.fit(log_odds[tr_i], y_val[tr_i])
        oof_cal[te_i] = lr.predict_proba(log_odds[te_i])

    raw_metrics = evaluate_multiclass_predictions(y_val, np.argmax(clipped, axis=1), clipped, LABEL_NAMES)
    cal_metrics = evaluate_multiclass_predictions(y_val, np.argmax(oof_cal, axis=1), oof_cal, LABEL_NAMES)

    use_cal = bool(
        (cal_metrics["log_loss"] < raw_metrics["log_loss"] - 0.002)
        and (cal_metrics["f1_macro"] >= raw_metrics["f1_macro"] - 0.015)
    )
    final_lr = None
    if use_cal:
        final_lr = LogisticRegression(C=2.0, max_iter=500)
        final_lr.fit(log_odds, y_val)

    return final_lr, use_cal, {
        "val_raw_log_loss": raw_metrics["log_loss"],
        "val_cv_calibrated_log_loss": cal_metrics["log_loss"],
        "val_raw_ece": raw_metrics["ece"],
        "val_cv_calibrated_ece": cal_metrics["ece"],
        "val_raw_f1_macro": raw_metrics["f1_macro"],
        "val_cv_calibrated_f1_macro": cal_metrics["f1_macro"],
        "applied": use_cal,
    }


def _apply_calibrator(probs: np.ndarray, calibrator: Optional[LogisticRegression]) -> np.ndarray:
    if calibrator is None:
        return probs
    clipped = np.clip(probs, 1e-6, 1.0 - 1e-6)
    return calibrator.predict_proba(np.log(clipped))


def train_and_evaluate_technical_models(
    parquet_path: str | Path = "data/predictive/daily_features.parquet",
    out_dir: str | Path = DEFAULT_ARTIFACTS_DIR,
    targets_path: str | Path = "data/predictive/daily_targets.parquet",
    reports_dir: str | Path = DEFAULT_REPORTS_DIR,
) -> dict[str, Any]:
    """
    Train & compare LightGBM (initial primary), XGBoost & Random Forest on documented
    volatility-aware 5d historical future-price outcomes, select strictly on VAL Macro-F1,
    verify untouched TEST generalization, and export `.pkl` + JSON artifacts to `artifacts/technical/`.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    rep_path = Path(reports_dir)
    rep_path.mkdir(parents=True, exist_ok=True)

    import lightgbm as lgb_pkg
    from lightgbm import LGBMClassifier, early_stopping, log_evaluation

    feat_load_cols = sorted(
        set(
            TECHNICAL_FEATURE_COLS
            + [
                "symbol",
                "trading_date",
                "cal_idx",
                "split",
                "is_trailing_top100_liquid",
                "is_zero_volume",
            ]
        )
    )
    tgt_load_cols = ["symbol", "cal_idx", "target_label_5d", "target_valid_5d", "target_ret_5d", "target_threshold_5d"]

    logger.info("Loading %s feature columns from %s & volatility targets from %s...", len(feat_load_cols), parquet_path, targets_path)
    feat_df = pd.read_parquet(parquet_path, columns=feat_load_cols)
    tgt_df = pd.read_parquet(targets_path, columns=tgt_load_cols)
    df = feat_df.merge(tgt_df, on=["symbol", "cal_idx"], how="inner")
    del feat_df, tgt_df

    df = df.sort_values(["symbol", "cal_idx"]).reset_index(drop=True)
    label_map = {"DOWN": 0, "NEUTRAL": 1, "UP": 2}
    df["target_cls"] = df["target_label_5d"].map(label_map).fillna(-1).astype(np.int8)

    valid_mask = (df["target_valid_5d"] == 1) & (df["is_zero_volume"] == 0) & (df["target_cls"] >= 0)
    # Non-overlapping 5-session stride inside TRAIN eliminates overlapping 5d target auto-correlation
    train_df = df[valid_mask & (df["split"] == "TRAIN") & ((df["cal_idx"] % 5) == 0)].reset_index(drop=True)
    val_df = df[valid_mask & (df["split"] == "VAL")].reset_index(drop=True)
    test_df = df[valid_mask & (df["split"] == "TEST")].reset_index(drop=True)

    preproc = TrainOnlyPreprocessor(TECHNICAL_FEATURE_COLS, impute_missing=False).fit(train_df)
    x_train_gbdt = preproc.transform_gbdt(train_df)
    x_val_gbdt = preproc.transform_gbdt(val_df)
    x_test_gbdt = preproc.transform_gbdt(test_df)

    x_train_imp = preproc.transform_imputed(train_df)
    x_val_imp = preproc.transform_imputed(val_df)
    x_test_imp = preproc.transform_imputed(test_df)

    y_train = train_df["target_cls"].to_numpy(dtype=np.int32)
    y_val = val_df["target_cls"].to_numpy(dtype=np.int32)
    y_test = test_df["target_cls"].to_numpy(dtype=np.int32)

    # Mild inverse class-frequency weighting (exponent 0.7) addresses Neutral majority without log-loss collapse
    sw_train = np.power(compute_sample_weight("balanced", y_train), 0.7).astype(np.float32)

    lgb_params = {
        "objective": "multiclass",
        "num_class": 3,
        "n_estimators": 600,
        "learning_rate": 0.025,
        "num_leaves": 31,
        "max_depth": 6,
        "min_child_samples": 250,
        "subsample": 0.8,
        "subsample_freq": 1,
        "colsample_bytree": 0.7,
        "reg_alpha": 2.0,
        "reg_lambda": 10.0,
        "random_state": 42,
        "n_jobs": -1,
        "verbose": -1,
    }
    logger.info("Training Primary Model: LightGBM (n_train=%d non-overlapping 5d rows)...", len(train_df))
    lgb = LGBMClassifier(**lgb_params)
    lgb.fit(
        x_train_gbdt,
        y_train,
        sample_weight=sw_train,
        eval_X=x_val_gbdt,
        eval_y=y_val,
        callbacks=[early_stopping(stopping_rounds=35, verbose=False), log_evaluation(0)],
    )

    xgb_params = {
        "objective": "multi:softprob",
        "num_class": 3,
        "eval_metric": "mlogloss",
        "n_estimators": 600,
        "learning_rate": 0.025,
        "max_depth": 5,
        "min_child_weight": 250,
        "subsample": 0.8,
        "colsample_bytree": 0.7,
        "reg_alpha": 2.0,
        "reg_lambda": 10.0,
        "tree_method": "hist",
        "early_stopping_rounds": 35,
        "random_state": 42,
        "n_jobs": -1,
    }
    logger.info("Training Benchmark 1: XGBoost...")
    xgb = XGBClassifier(**xgb_params)
    xgb.fit(x_train_gbdt, y_train, sample_weight=sw_train, eval_set=[(x_val_gbdt, y_val)], verbose=False)

    rf_params = {
        "n_estimators": 140,
        "max_depth": 12,
        "min_samples_leaf": 150,
        "max_features": "sqrt",
        "random_state": 42,
        "n_jobs": -1,
    }
    logger.info("Training Benchmark 2: Random Forest...")
    rf = RandomForestClassifier(**rf_params)
    rf.fit(x_train_imp, y_train, sample_weight=sw_train)

    candidates = {
        "lightgbm": (lgb, x_val_gbdt, x_test_gbdt, "gbdt", {**lgb_params, "best_iteration": int(getattr(lgb, "best_iteration_", lgb_params["n_estimators"]))}),
        "xgboost": (xgb, x_val_gbdt, x_test_gbdt, "gbdt", {**xgb_params, "best_iteration": int(getattr(xgb, "best_iteration", xgb_params["n_estimators"]))}),
        "random_forest": (rf, x_val_imp, x_test_imp, "imputed", rf_params),
    }

    val_results: dict[str, Any] = {}
    for mname, (mdl, x_v, _, _, _) in candidates.items():
        probs_v = mdl.predict_proba(x_v)
        preds_v = np.argmax(probs_v, axis=1)
        val_results[mname] = {
            "metrics": evaluate_multiclass_predictions(y_val, preds_v, probs_v, LABEL_NAMES),
            "by_regime": evaluate_by_regime(y_val, preds_v, probs_v, _regime_labels_from_df(val_df), LABEL_NAMES),
        }

    # Select winning model strictly by VAL Macro-F1
    selected_name = max(candidates.keys(), key=lambda k: val_results[k]["metrics"]["f1_macro"])
    best_model, x_v_best, x_t_best, input_kind, selected_hparams = candidates[selected_name]
    preproc.impute_missing = (input_kind == "imputed")

    raw_probs_val = best_model.predict_proba(x_v_best)
    calibrator, used_cal, cal_audit = _fit_val_calibrator(raw_probs_val, y_val)
    exported_model = CalibratedModelWrapper(best_model, calibrator) if (used_cal and calibrator is not None) else best_model

    # Evaluate baselines on VAL & untouched TEST
    val_base_preds = compute_rule_baselines(val_df)
    test_base_preds = compute_rule_baselines(test_df)
    for bname, bpred in val_base_preds.items():
        val_results[bname] = {"metrics": evaluate_multiclass_predictions(y_val, bpred, None, LABEL_NAMES)}

    test_results: dict[str, Any] = {}
    for mname, (mdl, _, x_t, _, _) in candidates.items():
        raw_pt = mdl.predict_proba(x_t)
        cal_pt = exported_model.predict_proba(x_t) if mname == selected_name else raw_pt
        pred_t = np.argmax(cal_pt, axis=1)
        liq_mask = (test_df["is_trailing_top100_liquid"] == 1).to_numpy()
        test_results[mname] = {
            "metrics": evaluate_multiclass_predictions(y_test, pred_t, cal_pt, LABEL_NAMES),
            "raw_probability_metrics": evaluate_multiclass_predictions(y_test, np.argmax(raw_pt, axis=1), raw_pt, LABEL_NAMES)
            if (mname == selected_name and used_cal)
            else None,
            "by_regime": evaluate_by_regime(y_test, pred_t, cal_pt, _regime_labels_from_df(test_df), LABEL_NAMES),
            "liquid_top100": evaluate_multiclass_predictions(y_test[liq_mask], pred_t[liq_mask], cal_pt[liq_mask], LABEL_NAMES),
        }

    for bname, bpred in test_base_preds.items():
        test_results[bname] = {
            "metrics": evaluate_multiclass_predictions(y_test, bpred, None, LABEL_NAMES),
            "by_regime": evaluate_by_regime(y_test, bpred, None, _regime_labels_from_df(test_df), LABEL_NAMES),
        }

    # Global Feature Importance table (Normalized gain/impurity from all 3 models)
    lgb_imp = lgb.booster_.feature_importance(importance_type="gain")
    lgb_imp = lgb_imp / max(float(lgb_imp.sum()), 1e-12)
    xgb_imp = xgb.feature_importances_
    xgb_imp = xgb_imp / max(float(xgb_imp.sum()), 1e-12)
    rf_imp = rf.feature_importances_
    rf_imp = rf_imp / max(float(rf_imp.sum()), 1e-12)

    fi_df = (
        pd.DataFrame(
            {
                "feature": TECHNICAL_FEATURE_COLS,
                "lightgbm_gain_share": np.round(lgb_imp, 6),
                "xgboost_gain_share": np.round(xgb_imp, 6),
                "random_forest_gini_share": np.round(rf_imp, 6),
            }
        )
        .sort_values(f"{selected_name}_{'gini' if selected_name == 'random_forest' else 'gain'}_share", ascending=False)
        .reset_index(drop=True)
    )
    fi_csv_path = rep_path / "technical_feature_importance.csv"
    fi_df.to_csv(fi_csv_path, index=False)

    trained_at = datetime.now(timezone.utc).isoformat()

    # Export clean `.pkl` artifacts + JSON schema/metadata into artifacts/technical/
    model_pkl_path = out_path / "technical_model.pkl"
    preproc_pkl_path = out_path / "technical_preprocessor.pkl"
    features_json_path = out_path / "technical_features.json"
    metadata_json_path = out_path / "technical_metadata.json"

    joblib.dump(exported_model, model_pkl_path, compress=3)
    joblib.dump(preproc, preproc_pkl_path, compress=3)

    features_schema = sanitize_for_json(
        {
            "model_name": "PSXpert Technical Analysis ML Classifier",
            "version": TECHNICAL_MODEL_VERSION,
            "feature_count": len(TECHNICAL_FEATURE_COLS),
            "feature_cols": TECHNICAL_FEATURE_COLS,
            "classes": {str(i): LABEL_NAMES[i] for i in range(3)},
            "missing_value_policy": (
                "Quantile-winsorized [0.5%, 99.5%] fitted on TRAIN; discrete flags (unique <= 12) unclipped; "
                + ("TRAIN-median imputed for tree split compatibility." if preproc.impute_missing else "native NaN sparsity preserved for GBDT routing.")
            ),
        }
    )
    features_json_path.write_text(json.dumps(features_schema, indent=2), encoding="utf-8")

    def _cls_dist(arr: np.ndarray) -> dict[str, Any]:
        return {LABEL_NAMES[i]: {"count": int((arr == i).sum()), "pct": round(float((arr == i).mean() * 100), 2)} for i in range(3)}

    lib_versions = {
        "python": platform.python_version(),
        "joblib": joblib.__version__,
        "scikit_learn": sklearn.__version__,
        "lightgbm": lgb_pkg.__version__,
        "xgboost": xgb_pkg.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
    }

    metadata = sanitize_for_json(
        {
            "model_name": "PSXpert Technical Analysis ML Classifier",
            "algorithm": selected_name,
            "estimator_class": type(exported_model).__name__,
            "selected_model_name": selected_name,
            "version": TECHNICAL_MODEL_VERSION,
            "model_version": TECHNICAL_MODEL_VERSION,
            "trained_at": trained_at,
            "training_dataset_range": {
                "train_start": str(pd.to_datetime(train_df["trading_date"]).min().date()),
                "train_end": str(pd.to_datetime(train_df["trading_date"]).max().date()),
                "val_start": str(pd.to_datetime(val_df["trading_date"]).min().date()),
                "val_end": str(pd.to_datetime(val_df["trading_date"]).max().date()),
                "test_start": str(pd.to_datetime(test_df["trading_date"]).min().date()),
                "test_end": str(pd.to_datetime(test_df["trading_date"]).max().date()),
            },
            "training_policy": {
                "train_split": "TRAIN (2002-01-01 to 2021-11-26, 5d non-overlapping stride cal_idx % 5 == 0)",
                "val_split": "VAL (2022-01-03 to 2024-05-20, 25d purge after TRAIN)",
                "test_split": "TEST (2024-07-01 to 2026-10-13, 25d purge after VAL, untouched)",
                "class_imbalance_strategy": "Inverse class-frequency weighting with exponent 0.7 fitted strictly on TRAIN",
                "survivorship_policy": "All 726 historical PSX symbols including inactive/delisted firms preserved.",
                "feature_count": len(TECHNICAL_FEATURE_COLS),
            },
            "feature_names": TECHNICAL_FEATURE_COLS,
            "target_definition": FORWARD_LABEL_SPEC,
            "label_specification": FORWARD_LABEL_SPEC,
            "sample_counts": {
                "train_strided_valid": int(len(train_df)),
                "val_valid": int(len(val_df)),
                "test_valid": int(len(test_df)),
            },
            "class_distributions": {
                "train": _cls_dist(y_train),
                "val": _cls_dist(y_val),
                "test": _cls_dist(y_test),
            },
            "selected_hyperparameters": selected_hparams,
            "calibration_audit_on_val": cal_audit,
            "validation_metrics": {k: v["metrics"] for k, v in val_results.items()},
            "final_test_metrics": {k: v["metrics"] for k, v in test_results.items()},
            "python_and_library_versions": lib_versions,
            "top_15_features": fi_df.head(15).to_dict(orient="records"),
            "artifact_files": {
                "model_pkl": str(model_pkl_path),
                "preprocessor_pkl": str(preproc_pkl_path),
                "features_json": str(features_json_path),
                "metadata_json": str(metadata_json_path),
                "evaluation_report_json": str(rep_path / "technical_evaluation_report.json"),
                "feature_importance_csv": str(fi_csv_path),
            },
            "artifact_checksums_sha256": {
                "technical_model.pkl": _sha256_file(model_pkl_path),
                "technical_preprocessor.pkl": _sha256_file(preproc_pkl_path),
            },
        }
    )

    eval_report = sanitize_for_json(
        {
            "metadata": metadata,
            "validation_results": val_results,
            "test_results": test_results,
        }
    )

    metadata_json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (rep_path / "technical_evaluation_report.json").write_text(json.dumps(eval_report, indent=2), encoding="utf-8")

    return eval_report


class TechnicalMLPredictor:
    """Loads persisted `.pkl` Technical ML artifacts and performs reproducible inference with TreeSHAP explanations."""

    def __init__(self, model_dir: str | Path = DEFAULT_ARTIFACTS_DIR, reports_dir: str | Path = DEFAULT_REPORTS_DIR) -> None:
        self.model_dir = Path(model_dir)
        self.reports_dir = Path(reports_dir)
        self._bundle: Optional[dict[str, Any]] = None
        self._metadata: Optional[dict[str, Any]] = None
        self._features_schema: Optional[dict[str, Any]] = None
        self._eval_report: Optional[dict[str, Any]] = None
        self._load_error: Optional[str] = None
        self._load_count: int = 0
        self._hmm_cache: dict[tuple[str, str, int], pd.DataFrame] = {}

    def is_available(self) -> bool:
        pkl_pair = (self.model_dir / "technical_model.pkl").exists() and (self.model_dir / "technical_preprocessor.pkl").exists()
        legacy_joblib = (self.model_dir / "technical_model_bundle.joblib").exists()
        return pkl_pair or legacy_joblib

    def preload(self, verify_checksum: bool = True) -> bool:
        """Load artifacts once at startup without raising on missing/corrupt files; returns readiness flag."""
        self._load_error = None
        try:
            self._ensure_loaded(verify_checksum=verify_checksum)
            return True
        except Exception as exc:
            self._bundle = None
            self._load_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Technical ML startup preload incomplete (%s): %s", self.model_dir, self._load_error)
            return False

    def _ensure_loaded(self, verify_checksum: bool = True) -> dict[str, Any]:
        if self._bundle is not None:
            return self._bundle

        model_pkl = self.model_dir / "technical_model.pkl"
        preproc_pkl = self.model_dir / "technical_preprocessor.pkl"
        feat_json = self.model_dir / "technical_features.json"
        meta_json = self.model_dir / "technical_metadata.json"

        if model_pkl.exists() or preproc_pkl.exists():
            if not model_pkl.exists() or not preproc_pkl.exists():
                raise FileNotFoundError(
                    f"Incomplete Technical ML artifact pair in {self.model_dir} (technical_model.pkl / technical_preprocessor.pkl)."
                )
            if meta_json.exists():
                self._metadata = json.loads(meta_json.read_text(encoding="utf-8"))
            if feat_json.exists():
                self._features_schema = json.loads(feat_json.read_text(encoding="utf-8"))

            if verify_checksum and self._metadata and "artifact_checksums_sha256" in self._metadata:
                expected_hashes = self._metadata["artifact_checksums_sha256"]
                for fname, fpath in (("technical_model.pkl", model_pkl), ("technical_preprocessor.pkl", preproc_pkl)):
                    exp_h = expected_hashes.get(fname)
                    if exp_h and _sha256_file(fpath) != exp_h:
                        raise ValueError(f"Checksum mismatch for {fpath} — artifact may be corrupted.")

            model = joblib.load(model_pkl)
            preproc = joblib.load(preproc_pkl)
            self._load_count += 1
            if not hasattr(model, "predict_proba") or not hasattr(preproc, "transform"):
                raise ValueError("Loaded Technical .pkl artifacts do not expose predict_proba / transform.")

            expected_cols = (
                (self._features_schema or {}).get("feature_cols")
                or (self._metadata or {}).get("feature_names")
                or list(getattr(preproc, "feature_cols", TECHNICAL_FEATURE_COLS))
            )
            if list(getattr(preproc, "feature_cols", [])) != list(expected_cols):
                raise ValueError("Preprocessor feature schema does not match technical_features.json.")
            n_in = getattr(model, "n_features_in_", len(expected_cols))
            if int(n_in) != len(expected_cols):
                raise ValueError(f"Model expects {n_in} features but schema defines {len(expected_cols)}.")

            rep_file = self.reports_dir / "technical_evaluation_report.json"
            if rep_file.exists():
                try:
                    self._eval_report = json.loads(rep_file.read_text(encoding="utf-8"))
                except Exception:
                    self._eval_report = None

            meta = self._metadata or {}
            self._bundle = {
                "model_version": meta.get("version", TECHNICAL_MODEL_VERSION),
                "selected_model_name": meta.get("algorithm", "lightgbm"),
                "input_kind": "imputed" if getattr(preproc, "impute_missing", False) else "gbdt",
                "model": model,
                "calibrator": getattr(model, "calibrator", None),
                "preprocessor": preproc,
                "feature_cols": list(expected_cols),
                "label_names": list(LABEL_NAMES),
                "label_spec": meta.get("target_definition", FORWARD_LABEL_SPEC),
                "trained_at": meta.get("trained_at"),
                "artifact_dir": str(self.model_dir),
            }
            self._load_error = None
            return self._bundle

        # Legacy `.joblib` fallback if explicit directory still uses bundle format
        bpath = self.model_dir / "technical_model_bundle.joblib"
        if not bpath.exists():
            raise FileNotFoundError(
                f"Technical ML artifact missing at {model_pkl} (and {bpath}). Run train_ml_models.py first."
            )
        self._bundle = joblib.load(bpath)
        self._load_count += 1
        mpath = self.model_dir / "model_metadata.json"
        if mpath.exists():
            self._metadata = json.loads(mpath.read_text(encoding="utf-8"))
        epath = self.model_dir / "evaluation_report.json"
        if epath.exists():
            self._eval_report = json.loads(epath.read_text(encoding="utf-8"))
        self._load_error = None
        return self._bundle

    def get_status_summary(self) -> dict[str, Any]:
        exists = self.is_available()
        if not exists:
            return {
                "status": "NOT_TRAINED",
                "artifact_exists": False,
                "loaded_successfully": False,
                "model_available": False,
                "ready_for_inference": False,
                "error": self._load_error or "Technical model artifact not found.",
            }
        try:
            bundle = self._ensure_loaded()
        except Exception as exc:
            self._load_error = f"{type(exc).__name__}: {exc}"
            return {
                "status": "CORRUPT_OR_INVALID_ARTIFACT",
                "artifact_exists": True,
                "loaded_successfully": False,
                "model_available": False,
                "ready_for_inference": False,
                "error": self._load_error,
            }

        meta = self._metadata or {}
        eval_rep = self._eval_report or {}
        test_res = eval_rep.get("test_results", {})
        val_res = eval_rep.get("validation_results", {})
        return sanitize_for_json(
            {
                "status": "READY",
                "artifact_exists": True,
                "loaded_successfully": True,
                "model_available": True,
                "ready_for_inference": True,
                "model_type": bundle["selected_model_name"],
                "selected_algorithm": bundle["selected_model_name"],
                "estimator_class": meta.get("estimator_class", type(bundle["model"]).__name__),
                "version": bundle["model_version"],
                "model_version": bundle["model_version"],
                "trained_at": bundle.get("trained_at"),
                "feature_count": len(bundle["feature_cols"]),
                "classes": bundle["label_names"],
                "label_specification": bundle["label_spec"],
                "calibration_applied": bundle.get("calibrator") is not None,
                "validation_comparison": {k: v["metrics"] for k, v in val_res.items()} if val_res else meta.get("validation_metrics", {}),
                "test_comparison": {k: v["metrics"] for k, v in test_res.items()} if test_res else meta.get("final_test_metrics", {}),
                "top_15_features": meta.get("top_15_features", []),
                "error": None,
            }
        )

    def predict_from_features(
        self,
        features: dict[str, Any] | pd.DataFrame,
        close_price: Optional[float] = None,
    ) -> dict[str, Any]:
        """Run inference directly from a raw feature dictionary or single-row DataFrame using the loaded `.pkl` pipeline."""
        bundle = self._ensure_loaded()
        fcols: list[str] = bundle["feature_cols"]
        if isinstance(features, dict):
            missing = [c for c in fcols if c not in features]
            if missing:
                raise ValueError(f"Missing {len(missing)} required Technical feature(s): {missing[:5]}")
            row_df = pd.DataFrame([{c: features[c] for c in fcols}])
        elif isinstance(features, pd.DataFrame):
            if len(features) != 1:
                raise ValueError(f"Expected 1 feature observation row; received {len(features)}.")
            missing = [c for c in fcols if c not in features.columns]
            if missing:
                raise ValueError(f"Missing {len(missing)} required Technical feature(s): {missing[:5]}")
            row_df = features[fcols].reset_index(drop=True)
        else:
            raise ValueError("features must be a mapping or single-row DataFrame.")

        preproc: TrainOnlyPreprocessor = bundle["preprocessor"]
        model = bundle["model"]
        calibrator = bundle.get("calibrator")

        x_mat = preproc.transform(row_df) if hasattr(preproc, "transform") else (
            preproc.transform_gbdt(row_df) if bundle.get("input_kind") == "gbdt" else preproc.transform_imputed(row_df)
        )
        if hasattr(model, "predict_proba") and isinstance(model, CalibratedModelWrapper):
            probs = model.predict_proba(x_mat)[0]
        else:
            raw_probs = model.predict_proba(x_mat)[0]
            probs = _apply_calibrator(raw_probs.reshape(1, -1), calibrator)[0]

        pred_idx = int(np.argmax(probs))
        pred_label = bundle["label_names"][pred_idx]
        confidence_val = safe_float(float(probs[pred_idx]), 4)
        top_contributors = self._explain_prediction(bundle, x_mat, pred_idx, row_df)

        adx_val = safe_float(row_df["adx_14"].iloc[0] if "adx_14" in row_df else None, 2)
        if adx_val is None:
            trend_strength = "UNAVAILABLE"
        elif adx_val >= 40.0:
            trend_strength = "VERY_STRONG"
        elif adx_val >= 25.0:
            trend_strength = "STRONG"
        elif adx_val >= 18.0:
            trend_strength = "MODERATE"
        else:
            trend_strength = "WEAK_OR_RANGEBOUND"

        atr_val = safe_float(row_df["atr_pct"].iloc[0] if "atr_pct" in row_df else None, 4)
        prob_dist = {
            "Bearish": safe_float(float(probs[0]), 4),
            "Neutral": safe_float(float(probs[1]), 4),
            "Bullish": safe_float(float(probs[2]), 4),
        }

        # Conviction gating & dynamic ATR barriers
        conviction_info = classify_conviction(pred_label, confidence_val, prob_dist)
        barriers_info = compute_dynamic_barriers(
            close_price=close_price,
            atr_pct=atr_val,
            direction=pred_label,
            multiplier_tp=1.5,
            multiplier_sl=1.0,
            horizon_sessions=5,
        )

        non_null = int(np.isfinite(x_mat[0]).sum())
        return sanitize_for_json(
            {
                "status": "OK",
                "model_version": bundle["model_version"],
                "model_type": bundle["selected_model_name"],
                "selected_algorithm": bundle["selected_model_name"],
                "trained_at": bundle.get("trained_at"),
                "feature_count": len(fcols),
                "finite_input_features": non_null,
                "calibration_applied": calibrator is not None,
                "predicted_condition": pred_label,
                "confidence": confidence_val,
                "probabilities": prob_dist,
                "conviction_tier": conviction_info["tier"],
                "is_actionable": conviction_info["is_actionable"],
                "selective_action": conviction_info["selective_action"],
                "historical_expected_win_rate_pct": conviction_info["historical_expected_win_rate_pct"],
                "alpha_expectation_pct": conviction_info["alpha_expectation_pct"],
                "take_profit_target_pct": barriers_info["take_profit_target_pct"],
                "stop_loss_limit_pct": barriers_info["stop_loss_limit_pct"],
                "conviction_gating": conviction_info,
                "dynamic_volatility_barriers": barriers_info,
                "trend_strength": trend_strength,
                "adx_14": adx_val,
                "top_contributing_features": top_contributors,
                "target_definition": bundle["label_spec"].get("target_name", FORWARD_LABEL_SPEC["target_name"]),
                "is_expected_return_regression": False,
                "is_future_return_prediction": bundle["label_spec"].get("target_name") == FORWARD_LABEL_SPEC["target_name"],
            }
        )

    def predict_for_symbol(
        self,
        conn: Connection,
        symbol: str,
        as_of_date: Optional[date | datetime | str] = None,
    ) -> dict[str, Any]:
        """Compute exact point-in-time features for `symbol <= as_of_date` and run Technical ML prediction."""
        bundle = self._ensure_loaded()
        sym = symbol.strip().upper()
        meta = get_company_metadata(conn, sym)
        req_cutoff, mkt_cutoff = resolve_effective_as_of_date(conn, sym, as_of_date)

        cal_df = load_trading_calendar(conn, max_date=mkt_cutoff)
        adj_df, cal_df, _ = load_clean_symbol_prices(conn, sym, max_date=mkt_cutoff, cal_df=cal_df)
        if adj_df.empty or len(adj_df) < 200:
            return sanitize_for_json(
                {
                    "symbol": sym,
                    "as_of_date": mkt_cutoff.isoformat(),
                    "status": "INSUFFICIENT_HISTORY",
                    "model_version": bundle["model_version"],
                    "model_type": bundle["selected_model_name"],
                    "selected_algorithm": bundle["selected_model_name"],
                    "trained_at": bundle.get("trained_at"),
                    "predicted_condition": None,
                    "probabilities": None,
                    "note": f"Requires >= 200 active trading sessions <= {mkt_cutoff}; observed {len(adj_df)} sessions.",
                }
            )

        feat_row = self._build_live_feature_row(conn, sym, meta, adj_df, cal_df, mkt_cutoff)
        latest_close = safe_float(adj_df["adj_close"].iloc[-1], 2)
        pred_out = self.predict_from_features(feat_row, close_price=latest_close)
        latest_trade_date = pd.to_datetime(adj_df["trading_date"].iloc[-1]).date()

        pred_out.update(
            {
                "symbol": sym,
                "as_of_date": mkt_cutoff.isoformat(),
                "latest_trading_date": latest_trade_date.isoformat(),
            }
        )
        return sanitize_for_json(pred_out)

    def _explain_prediction(
        self,
        bundle: dict[str, Any],
        x_mat: np.ndarray,
        pred_idx: int,
        row_df: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        fcols = bundle["feature_cols"]
        mdl = getattr(bundle["model"], "estimator", bundle["model"])
        name = bundle["selected_model_name"]
        contribs: Optional[np.ndarray] = None

        try:
            if name == "lightgbm":
                raw_c = mdl.predict(x_mat, pred_contrib=True)
                stride = len(fcols) + 1
                contribs = raw_c[0, pred_idx * stride : pred_idx * stride + len(fcols)]
            elif name == "xgboost":
                dm = xgb_pkg.DMatrix(x_mat)
                raw_c = mdl.get_booster().predict(dm, pred_contribs=True)
                contribs = raw_c[0, pred_idx, : len(fcols)]
        except Exception as exc:
            logger.debug("TreeSHAP fallback triggered: %s", exc)
            contribs = None

        if contribs is None:
            imps = getattr(mdl, "feature_importances_", np.ones(len(fcols)))
            order = np.argsort(imps)[::-1][:8]
            return [
                {
                    "feature": fcols[i],
                    "value": safe_float(row_df[fcols[i]].iloc[0], 4),
                    "global_importance": safe_float(float(imps[i]), 4),
                    "contribution_logit": None,
                }
                for i in order
            ]

        order = np.argsort(np.abs(contribs))[::-1][:8]
        return [
            {
                "feature": fcols[i],
                "value": safe_float(row_df[fcols[i]].iloc[0], 4),
                "contribution_logit": safe_float(float(contribs[i]), 4),
                "direction": "Supports Predicted Class" if contribs[i] >= 0 else "Opposes Predicted Class",
            }
            for i in order
        ]

    def _build_live_feature_row(
        self,
        conn: Connection,
        sym: str,
        meta: dict[str, Any],
        adj_df: pd.DataFrame,
        cal_df: pd.DataFrame,
        mkt_cutoff: date,
    ) -> dict[str, Any]:
        """Compute exact point-in-time feature vector matching daily_builder.py definitions."""
        df_sym = adj_df.copy()
        df_sym["trading_date"] = pd.to_datetime(df_sym["trading_date"]).dt.date
        df_sym = df_sym.sort_values("cal_idx").reset_index(drop=True)
        feat_df = _compute_stock_features_and_candlesticks(df_sym)
        feat_df["listing_age_sessions"] = np.arange(1, len(feat_df) + 1, dtype=np.int32)

        # KSE-100 index context & strictly causal HMM probabilities
        idx_df = cal_df.sort_values("trading_date").reset_index(drop=True)
        idx_dates = pd.to_datetime(idx_df["trading_date"]).dt.date
        train_cutoff = min(mkt_cutoff, date(2021, 11, 26))
        cache_key = (train_cutoff.isoformat(), mkt_cutoff.isoformat(), len(idx_df))
        if cache_key in self._hmm_cache:
            hmm_daily = self._hmm_cache[cache_key]
        else:
            train_slice = idx_df[idx_dates <= train_cutoff].copy()
            if len(train_slice) < 252:
                train_slice = idx_df.copy()
            hmm = CausalMarketRegimeHMM(n_states=3, random_state=42).fit(train_slice)
            hmm_daily = hmm.filter_causal_probabilities(idx_df)
            self._hmm_cache[cache_key] = hmm_daily

        idx_close = pd.to_numeric(idx_df["close"], errors="coerce")
        idx_df["kse100_ret_1d"] = idx_close.pct_change(1)
        idx_df["kse100_ret_5d"] = idx_close.pct_change(5)
        idx_df["kse100_ret_20d"] = idx_close.pct_change(20)
        idx_df["kse100_log_ret_1d"] = np.log(idx_close / idx_close.shift(1))
        idx_df["kse100_vol_20d"] = idx_df["kse100_log_ret_1d"].rolling(20, min_periods=20).std()
        idx_df["kse100_dist_sma50"] = (idx_close / idx_close.rolling(50, min_periods=50).mean()) - 1.0
        idx_df["kse100_dist_sma200"] = (idx_close / idx_close.rolling(200, min_periods=200).mean()) - 1.0
        idx_df["kse100_rsi_14"] = _compute_causal_wilder_rsi(idx_close, 14)

        idx_df["td_key"] = pd.to_datetime(idx_df["trading_date"]).dt.date
        hmm_daily_k = hmm_daily.copy()
        hmm_daily_k["td_key"] = pd.to_datetime(hmm_daily_k["trading_date"]).dt.date

        feat_df["td_key"] = feat_df["trading_date"]
        merged = feat_df.merge(
            idx_df.drop(columns=["trading_date", "open", "high", "low", "close", "volume"], errors="ignore"),
            on="td_key",
            how="left",
        ).merge(
            hmm_daily_k.drop(columns=["trading_date"], errors="ignore"),
            on="td_key",
            how="left",
        )

        # 60-day rolling Beta & Correlation vs KSE-100
        tail60 = merged.tail(60)
        pair = tail60[["log_ret_1d", "kse100_log_ret_1d"]].dropna()
        beta60 = np.nan
        corr60 = np.nan
        if len(pair) >= 40:
            v_mkt = float(pair["kse100_log_ret_1d"].var())
            if v_mkt > 1e-12:
                beta60 = float(pair.cov().iloc[0, 1] / v_mkt)
            c_val = float(pair["log_ret_1d"].corr(pair["kse100_log_ret_1d"]))
            if np.isfinite(c_val):
                corr60 = c_val

        last = merged.iloc[-1].to_dict()
        last["rel_strength_kse100_5d"] = (
            float(last["ret_5d"] - last["kse100_ret_5d"])
            if pd.notna(last.get("ret_5d")) and pd.notna(last.get("kse100_ret_5d"))
            else np.nan
        )
        last["rel_strength_kse100_20d"] = (
            float(last["ret_20d"] - last["kse100_ret_20d"])
            if pd.notna(last.get("ret_20d")) and pd.notna(last.get("kse100_ret_20d"))
            else np.nan
        )
        last["rolling_beta_60d"] = beta60
        last["rolling_corr_kse100_60d"] = corr60

        # Cross-sectional market breadth & ADV liquidity rank on latest stock session date
        target_td = last["td_key"]
        breadth_metrics = self._query_cross_sectional_breadth(conn, sym, target_td)
        last.update(breadth_metrics)

        return {col: last.get(col, np.nan) for col in TECHNICAL_FEATURE_COLS}

    def _query_cross_sectional_breadth(self, conn: Connection, sym: str, target_td: date) -> dict[str, Any]:
        """Compute cross-sectional breadth & 20d ADV rank on `target_td` via trailing 65 calendar sessions."""
        min_d = target_td - pd.Timedelta(days=110)
        q = text(
            """
            SELECT sp.symbol, sp.trading_date, sp.close, sp.volume
            FROM stock_prices sp
            JOIN market_indices mi ON mi.trading_date = sp.trading_date AND mi.index_symbol = 'KSE100'
            WHERE sp.trading_date BETWEEN :min_d AND :max_d
              AND sp.close > 0
            ORDER BY sp.symbol, sp.trading_date
            """
        )
        cs = pd.read_sql(q, conn, params={"min_d": min_d.date() if isinstance(min_d, pd.Timestamp) else min_d, "max_d": target_td})
        if cs.empty:
            return {
                "trailing_20d_adv_rank": np.nan,
                "mkt_median_ret_1d": np.nan,
                "mkt_pct_above_sma50": np.nan,
                "mkt_adv_decline_ratio": np.nan,
            }

        cs["trading_date"] = pd.to_datetime(cs["trading_date"]).dt.date
        cs = cs.drop_duplicates(subset=["symbol", "trading_date"], keep="last").sort_values(["symbol", "trading_date"])
        cs["turnover"] = cs["close"] * cs["volume"].astype(float)
        g = cs.groupby("symbol", sort=False)
        cs["ret_1d"] = g["close"].pct_change(1)
        cs["sma_50"] = g["close"].transform(lambda s: s.rolling(50, min_periods=50).mean())
        cs["adv_20"] = g["turnover"].transform(lambda s: s.rolling(20, min_periods=10).mean())

        snap = cs[cs["trading_date"] == target_td].copy()
        if snap.empty:
            return {
                "trailing_20d_adv_rank": np.nan,
                "mkt_median_ret_1d": np.nan,
                "mkt_pct_above_sma50": np.nan,
                "mkt_adv_decline_ratio": np.nan,
            }

        snap["adv_rank"] = snap["adv_20"].rank(ascending=False, method="min")
        sym_row = snap[snap["symbol"].str.upper() == sym]
        sym_rank = float(sym_row["adv_rank"].iloc[0]) if not sym_row.empty and pd.notna(sym_row["adv_rank"].iloc[0]) else np.nan

        clean_r1 = snap.loc[snap["ret_1d"].abs() <= 0.35, "ret_1d"].dropna()
        adv_cnt = int((clean_r1 > 0).sum())
        dec_cnt = int((clean_r1 < 0).sum())
        tot_cnt = len(clean_r1)
        adv_dec_ratio = ((adv_cnt - dec_cnt) / tot_cnt) if tot_cnt > 0 else np.nan
        med_r1 = float(clean_r1.median()) if tot_cnt > 0 else np.nan

        above50 = snap["sma_50"].dropna()
        pct_above50 = float((snap.loc[above50.index, "close"] > above50).mean()) if len(above50) > 0 else np.nan

        return {
            "trailing_20d_adv_rank": sym_rank,
            "mkt_median_ret_1d": med_r1,
            "mkt_pct_above_sma50": pct_above50,
            "mkt_adv_decline_ratio": adv_dec_ratio,
        }
