"""Diagnostic script to investigate:

1. Extreme regression RMSE, actual-return vs predicted-return quantiles, top 50 errors.
2. Target computation, price adjustment vs unadjusted forward close.
3. Corporate actions, stock splits, bonuses, rights during the test period.
4. Valuation ratios, publication dates, and PIT merges.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import joblib

from src.ml.pipeline.quantitative_pipeline import (
    DataAuditor,
    FeatureEngine,
    WalkForwardValidator,
    TECHNICAL_FEATURE_COLS,
    FUNDAMENTAL_FEATURE_COLS,
    COMBINED_FEATURE_COLS,
)

def run_diagnostics():
    print("=== 1. Loading data and extracting features ===")
    prices, index_df, funds, ann = DataAuditor.load_raw_inputs()
    tech_df = FeatureEngine.build_technical_features(prices, index_df)
    fund_df = FeatureEngine.build_point_in_time_fundamentals(funds, ann)
    full_df = FeatureEngine.merge_point_in_time(tech_df, fund_df)
    train_df, val_df, test_df, fresh_df = WalkForwardValidator.get_splits(full_df)

    valid_test = test_df[test_df["target_ret_20d"].notna()].copy()
    y_true = valid_test["target_ret_20d"].values

    print("\n=== Actual 20d Forward Return Quantiles on Test Fold (N={}) ===".format(len(y_true)))
    print("Min:", y_true.min(), "Max:", y_true.max(), "Mean:", y_true.mean(), "Std:", y_true.std())
    print(pd.Series(y_true).quantile([0.0001, 0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 0.999, 0.9999]))

    # Load models
    tech_reg = joblib.load("artifacts/technical/technical_regressor.pkl")
    fund_reg = joblib.load("artifacts/fundamental/fundamental_regressor.pkl")
    comb_reg = joblib.load("artifacts/combined/combined_regressor.pkl")

    pred_tech = tech_reg.predict(valid_test[TECHNICAL_FEATURE_COLS])
    pred_fund = fund_reg.predict(valid_test[FUNDAMENTAL_FEATURE_COLS])
    pred_comb = comb_reg.predict(valid_test[COMBINED_FEATURE_COLS])

    print("\n=== Predicted Return Summary ===")
    for name, pred in [("Technical Regressor", pred_tech), ("Fundamental Regressor", pred_fund), ("Combined Regressor", pred_comb)]:
        print(f"\n{name}:")
        print("Min:", pred.min(), "Max:", pred.max(), "Mean:", pred.mean(), "Std:", pred.std())
        print("RMSE:", np.sqrt(np.mean((y_true - pred)**2)))
        print("MAE:", np.mean(np.abs(y_true - pred)))
        print("Quantiles:")
        print(pd.Series(pred).quantile([0.001, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 0.999]))

    valid_test["pred_comb"] = pred_comb
    valid_test["pred_tech"] = pred_tech
    valid_test["pred_fund"] = pred_fund
    valid_test["sq_err_comb"] = (y_true - pred_comb)**2
    valid_test["abs_err_comb"] = np.abs(y_true - pred_comb)

    top50 = valid_test.sort_values("sq_err_comb", ascending=False).head(50)
    print("\n=== Top 50 Largest Squared Errors for Combined Regressor ===")
    cols_to_show = ["symbol", "trading_date", "close", "fwd_close_20d", "target_ret_20d", "pred_comb", "abs_err_comb"]
    print(top50[cols_to_show].to_string())

    # Save top 50 to CSV for reference
    top50.to_csv("reports/model_evaluation/top50_regression_errors.csv", index=False)
    print("\nSaved top 50 errors to reports/model_evaluation/top50_regression_errors.csv")

if __name__ == "__main__":
    run_diagnostics()
