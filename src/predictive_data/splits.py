"""
Chronological Split Definitions & Overlapping-Label Purge Policy.

Enforces strict temporal separation across Train / Validation / Test sets
and multi-fold expanding Walk-Forward Validation with explicit 20-trading-day
purge buffers to eliminate overlapping future-return label leakage.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Any
import pandas as pd


MAX_LABEL_HORIZON_DAYS = 20
PURGE_BUFFER_TRADING_DAYS = 25  # Exceeds max_cal_diff (23) for 20-bar forward horizons with up to 3 skipped sessions


@dataclass(frozen=True)
class SplitBoundary:
    name: str
    start_date: str
    end_date: str
    trading_days: int
    purpose: str


def build_chronological_splits(
    trading_dates: pd.Series,
    train_end: str = "2021-12-31",
    val_end: str = "2024-06-28",
    purge_days: int = PURGE_BUFFER_TRADING_DAYS,
) -> Dict[str, Any]:
    """
    Constructs leak-free chronological split mappings on the real PSX trading calendar.

    Rows in the trailing `purge_days` sessions before each boundary are labeled
    PURGE_TRAIN_VAL / PURGE_VAL_TEST because their 20-day forward return horizons
    overlap into the next split.
    """
    cal = (
        pd.DataFrame({"trading_date": pd.to_datetime(trading_dates).dt.date})
        .drop_duplicates()
        .sort_values("trading_date")
        .reset_index(drop=True)
    )
    cal["cal_idx"] = cal.index
    cal["date_str"] = cal["trading_date"].astype(str)

    train_cut = pd.to_datetime(train_end).date()
    val_cut = pd.to_datetime(val_end).date()

    train_mask = cal["trading_date"] <= train_cut
    val_mask = (cal["trading_date"] > train_cut) & (cal["trading_date"] <= val_cut)
    test_mask = cal["trading_date"] > val_cut

    train_last_idx = int(cal.loc[train_mask, "cal_idx"].max())
    val_first_idx = int(cal.loc[val_mask, "cal_idx"].min())
    val_last_idx = int(cal.loc[val_mask, "cal_idx"].max())
    test_first_idx = int(cal.loc[test_mask, "cal_idx"].min())

    # Purge trailing `purge_days` sessions before Validation and before Test
    train_eff_last_idx = train_last_idx - purge_days
    val_eff_last_idx = val_last_idx - purge_days

    def _label_split(idx: int) -> str:
        if idx <= train_eff_last_idx:
            return "TRAIN"
        if idx <= train_last_idx:
            return "PURGE_TRAIN_VAL"
        if idx <= val_eff_last_idx:
            return "VAL"
        if idx <= val_last_idx:
            return "PURGE_VAL_TEST"
        return "TEST"

    cal["split"] = cal["cal_idx"].apply(_label_split)

    # Also build Fundamentals-Complete Sub-Split (2022-01-03 .. 2026-10-13)
    # for models requiring dense audited IFRS financial ratios
    fund_start_cut = pd.to_datetime("2022-01-01").date()
    fund_train_cut = pd.to_datetime("2024-06-28").date()
    fund_val_cut = pd.to_datetime("2025-06-30").date()

    f_train_last = int(cal.loc[(cal["trading_date"] >= fund_start_cut) & (cal["trading_date"] <= fund_train_cut), "cal_idx"].max())
    f_val_last = int(cal.loc[(cal["trading_date"] > fund_train_cut) & (cal["trading_date"] <= fund_val_cut), "cal_idx"].max())
    f_start_idx = int(cal.loc[cal["trading_date"] >= fund_start_cut, "cal_idx"].min())

    def _label_fund_split(idx: int) -> str:
        if idx < f_start_idx:
            return "PRE_FUNDAMENTALS"
        if idx <= f_train_last - purge_days:
            return "FUND_TRAIN"
        if idx <= f_train_last:
            return "FUND_PURGE_TRAIN_VAL"
        if idx <= f_val_last - purge_days:
            return "FUND_VAL"
        if idx <= f_val_last:
            return "FUND_PURGE_VAL_TEST"
        return "FUND_TEST"

    cal["fundamentals_regime_split"] = cal["cal_idx"].apply(_label_fund_split)

    # Build 5 Annual Expanding Walk-Forward Validation Folds (2022..2026) with purge
    wf_folds: List[Dict[str, Any]] = []
    fold_windows = [
        ("2021-12-31", "2022-01-03", "2022-12-30"),
        ("2022-12-30", "2023-01-02", "2023-12-29"),
        ("2023-12-29", "2024-01-01", "2024-12-31"),
        ("2024-12-31", "2025-01-01", "2025-12-31"),
        ("2025-12-31", "2026-01-01", "2026-10-13"),
    ]
    for fold_id, (tr_end_s, te_start_s, te_end_s) in enumerate(fold_windows, start=1):
        tr_end_d = pd.to_datetime(tr_end_s).date()
        te_start_d = pd.to_datetime(te_start_s).date()
        te_end_d = pd.to_datetime(te_end_s).date()

        tr_rows = cal[cal["trading_date"] <= tr_end_d]
        tr_eff_end_idx = int(tr_rows["cal_idx"].max()) - purge_days
        tr_eff_end_date = str(cal.loc[cal["cal_idx"] == tr_eff_end_idx, "trading_date"].iloc[0])

        te_rows = cal[(cal["trading_date"] >= te_start_d) & (cal["trading_date"] <= te_end_d)]
        wf_folds.append({
            "fold": fold_id,
            "train_start": str(cal["trading_date"].iloc[0]),
            "train_effective_end": tr_eff_end_date,
            "purge_start": str(cal.loc[cal["cal_idx"] == tr_eff_end_idx + 1, "trading_date"].iloc[0]),
            "purge_end": str(tr_rows["trading_date"].iloc[-1]),
            "purge_days": purge_days,
            "test_start": str(te_rows["trading_date"].iloc[0]),
            "test_end": str(te_rows["trading_date"].iloc[-1]),
            "train_sessions": int(tr_eff_end_idx + 1),
            "test_sessions": int(len(te_rows)),
        })

    # Compute summary table per split
    split_summaries = []
    for name in ["TRAIN", "PURGE_TRAIN_VAL", "VAL", "PURGE_VAL_TEST", "TEST"]:
        sub = cal[cal["split"] == name]
        split_summaries.append(asdict(SplitBoundary(
            name=name,
            start_date=str(sub["trading_date"].iloc[0]),
            end_date=str(sub["trading_date"].iloc[-1]),
            trading_days=int(len(sub)),
            purpose={
                "TRAIN": "Model fitting, scaler/feature-selector estimation, HMM parameter training",
                "PURGE_TRAIN_VAL": f"{purge_days}-session purge buffer separating Train 20d targets (<=23 cal span) from Val",
                "VAL": "Hyperparameter tuning, ensemble calibration, early stopping",
                "PURGE_VAL_TEST": f"{purge_days}-session purge buffer separating Val 20d targets (<=23 cal span) from Test",
                "TEST": "Strictly unseen out-of-sample final generalization benchmark",
            }[name],
        )))

    return {
        "calendar_df": cal,
        "summary": {
            "calendar_source": "PSX KSE-100 Exchange Trading Days (market_indices)",
            "total_trading_days": int(len(cal)),
            "start_date": str(cal["trading_date"].iloc[0]),
            "end_date": str(cal["trading_date"].iloc[-1]),
            "max_target_horizon_days": purge_days,
            "purge_policy": f"{purge_days} trading days purged before every Validation/Test start",
            "primary_splits": split_summaries,
            "fundamentals_subsplits": [
                {
                    "name": s_name,
                    "start_date": str(cal.loc[cal["fundamentals_regime_split"] == s_name, "trading_date"].iloc[0]),
                    "end_date": str(cal.loc[cal["fundamentals_regime_split"] == s_name, "trading_date"].iloc[-1]),
                    "trading_days": int((cal["fundamentals_regime_split"] == s_name).sum()),
                }
                for s_name in ["FUND_TRAIN", "FUND_PURGE_TRAIN_VAL", "FUND_VAL", "FUND_PURGE_VAL_TEST", "FUND_TEST"]
            ],
            "walk_forward_folds": wf_folds,
        },
    }

