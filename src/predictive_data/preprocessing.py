"""
Train-Only Preprocessing & Feature Screening Pipeline (Step 5).

Fits all clipping quantiles, imputation medians, scaling statistics (mean/std),
and univariate predictive relevance diagnostics (Spearman correlation, Mutual Info)
STRICTLY on rows belonging to `split == 'TRAIN'`, never reading Validation or Test data.
"""

import json
from pathlib import Path
from typing import Dict, List, Any
import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_classif


NON_FEATURE_METADATA_COLS = {
    "symbol",
    "trading_date",
    "sector",
    "split",
    "fundamentals_regime_split",
    "cal_idx",
    "candlestick_pattern_name",
    "fin_period_end_date",
    "effective_pub_date",
    # Raw nominal prices kept for reference/audit, not scale-invariant inputs
    "raw_open",
    "raw_high",
    "raw_low",
    "raw_close",
    "adj_open",
    "adj_high",
    "adj_low",
    "adj_close",
    "market_cap",
    "kse100_close",
    "obv",
    "sma_20",
    "sma_50",
    "sma_200",
    "ema_12",
    "ema_26",
    "ema_20",
    "ema_50",
    "ema_200",
    "bb_middle",
    "bb_upper",
    "bb_lower",
    "macd_line",
    "macd_signal",
    "macd_diff",
    "atr_14",
}


def select_model_feature_columns(features_df: pd.DataFrame) -> List[str]:
    """Returns deterministic list of scale-invariant causal numeric model features."""
    cols = []
    for col in features_df.columns:
        if col in NON_FEATURE_METADATA_COLS:
            continue
        if pd.api.types.is_numeric_dtype(features_df[col]):
            cols.append(col)
    return cols


def fit_train_only_preprocessing_and_screening(
    features_df: pd.DataFrame,
    targets_df: pd.DataFrame,
    out_dir: Path,
    sample_for_mi: int = 25_000,
) -> Dict[str, Any]:
    """
    Fits winsorization quantiles, imputation medians, standardization params,
    and mutual-information screening EXCLUSIVELY on `split == 'TRAIN'`.
    """
    train_mask = features_df["split"] == "TRAIN"
    train_x = features_df.loc[train_mask]
    train_y = targets_df.loc[train_mask]

    feature_cols = select_model_feature_columns(features_df)
    n_train = len(train_x)
    val_miss_map = features_df.loc[features_df["split"] == "VAL", feature_cols].isna().mean().to_dict()
    test_miss_map = features_df.loc[features_df["split"] == "TEST", feature_cols].isna().mean().to_dict()

    stats: Dict[str, Dict[str, Any]] = {}
    screening_rows = []

    # Prepare MI evaluation sample strictly inside TRAIN where target_valid_1d == 1
    valid_1d = train_y["target_valid_1d"] == 1
    valid_5d = train_y["target_valid_5d"] == 1
    valid_20d = train_y["target_valid_20d"] == 1

    # Deterministic subsample inside TRAIN for MI speed across 1.5M train rows
    rng = np.random.default_rng(42)
    idx_1d = np.flatnonzero(valid_1d.to_numpy())
    if len(idx_1d) > sample_for_mi:
        sub_idx = np.sort(rng.choice(idx_1d, size=sample_for_mi, replace=False))
    else:
        sub_idx = idx_1d

    y_mi_1d = train_y.iloc[sub_idx]["target_dir_1d"].astype(int).to_numpy()
    mi_matrix = np.zeros((len(sub_idx), len(feature_cols)), dtype=np.float64)

    for j, col in enumerate(feature_cols):
        s_tr = pd.to_numeric(train_x[col], errors="coerce").to_numpy(dtype=np.float64)
        missing_rate_train = float(np.isnan(s_tr).mean())

        finite = s_tr[np.isfinite(s_tr)]
        if len(finite) > 0:
            q01, q99 = np.percentile(finite, [1.0, 99.0])
            clipped = np.clip(finite, q01, q99)
            med = float(np.median(finite))
            mean_c = float(np.mean(clipped))
            std_c = float(np.std(clipped))
            min_v = float(np.min(finite))
            max_v = float(np.max(finite))
        else:
            q01 = q99 = med = mean_c = std_c = min_v = max_v = np.nan

        stats[col] = {
            "train_count": int(len(finite)),
            "train_missing_rate": round(missing_rate_train, 6),
            "clip_p01": None if np.isnan(q01) else round(float(q01), 6),
            "clip_p99": None if np.isnan(q99) else round(float(q99), 6),
            "impute_median": None if np.isnan(med) else round(float(med), 6),
            "clipped_mean": None if np.isnan(mean_c) else round(float(mean_c), 6),
            "clipped_std": None if np.isnan(std_c) else round(float(std_c), 6),
        }

        # Populate MI matrix using Train-only median imputation and Train-only clipping
        s_sub = s_tr[sub_idx]
        if not np.isnan(med):
            s_sub = np.where(np.isfinite(s_sub), np.clip(s_sub, q01, q99), med)
        else:
            s_sub = np.zeros(len(sub_idx), dtype=np.float64)
        mi_matrix[:, j] = s_sub

        # Compute Spearman correlations on TRAIN rows ONLY
        df_tmp = pd.DataFrame({
            "x": s_tr,
            "r1": np.where(valid_1d, train_y["target_ret_1d"].to_numpy(), np.nan),
            "r5": np.where(valid_5d, train_y["target_ret_5d"].to_numpy(), np.nan),
            "r20": np.where(valid_20d, train_y["target_ret_20d"].to_numpy(), np.nan),
        })
        # Use deterministic <= 60k subsample for fast Spearman rank correlation
        step = max(1, len(df_tmp) // 60_000)
        df_corr_sub = df_tmp.iloc[::step]

        c1 = df_corr_sub[["x", "r1"]].dropna()
        c5 = df_corr_sub[["x", "r5"]].dropna()
        c20 = df_corr_sub[["x", "r20"]].dropna()

        sp1 = float(c1["x"].corr(c1["r1"], method="spearman")) if len(c1) >= 100 and c1["x"].nunique() > 1 else 0.0
        sp5 = float(c5["x"].corr(c5["r5"], method="spearman")) if len(c5) >= 100 and c5["x"].nunique() > 1 else 0.0
        sp20 = float(c20["x"].corr(c20["r20"], method="spearman")) if len(c20) >= 100 and c20["x"].nunique() > 1 else 0.0

        val_miss = float(val_miss_map.get(col, 0.0))
        test_miss = float(test_miss_map.get(col, 0.0))

        screening_rows.append({
            "feature": col,
            "train_missing_pct": round(missing_rate_train * 100, 2),
            "val_missing_pct": round(val_miss * 100, 2),
            "test_missing_pct": round(test_miss * 100, 2),
            "train_std_clipped": round(float(std_c), 6) if not np.isnan(std_c) else 0.0,
            "train_spearman_ret_1d": round(0.0 if np.isnan(sp1) else sp1, 5),
            "train_spearman_ret_5d": round(0.0 if np.isnan(sp5) else sp5, 5),
            "train_spearman_ret_20d": round(0.0 if np.isnan(sp20) else sp20, 5),
            "zero_variance_in_train": int(np.isnan(std_c) or std_c <= 1e-12),
        })

    # Mutual Information on TRAIN subsample only
    mi_scores = mutual_info_classif(mi_matrix, y_mi_1d, discrete_features=False, random_state=42)
    for j, row in enumerate(screening_rows):
        row["train_mi_dir_1d"] = round(float(mi_scores[j]), 6)

    screen_df = pd.DataFrame(screening_rows).sort_values("train_mi_dir_1d", ascending=False).reset_index(drop=True)
    screen_csv = out_dir / "train_feature_screening.csv"
    screen_df.to_csv(screen_csv, index=False)

    # Also fit scaling stats strictly on FUND_TRAIN (2022-2024) for models using audited IFRS ratios
    fund_train_mask = features_df["fundamentals_regime_split"] == "FUND_TRAIN"
    fund_train_x = features_df.loc[fund_train_mask]
    fund_stats: Dict[str, Dict[str, Any]] = {}
    for col in feature_cols:
        s_ft = pd.to_numeric(fund_train_x[col], errors="coerce").to_numpy(dtype=np.float64)
        miss_ft = float(np.isnan(s_ft).mean()) if len(s_ft) > 0 else 1.0
        fin_ft = s_ft[np.isfinite(s_ft)]
        if len(fin_ft) > 0:
            fq01, fq99 = np.percentile(fin_ft, [1.0, 99.0])
            fclip = np.clip(fin_ft, fq01, fq99)
            fmed = float(np.median(fin_ft))
            fmean = float(np.mean(fclip))
            fstd = float(np.std(fclip))
        else:
            fq01 = fq99 = fmed = fmean = fstd = np.nan
        fund_stats[col] = {
            "train_count": int(len(fin_ft)),
            "train_missing_rate": round(miss_ft, 6),
            "clip_p01": None if np.isnan(fq01) else round(float(fq01), 6),
            "clip_p99": None if np.isnan(fq99) else round(float(fq99), 6),
            "impute_median": None if np.isnan(fmed) else round(float(fmed), 6),
            "clipped_mean": None if np.isnan(fmean) else round(float(fmean), 6),
            "clipped_std": None if np.isnan(fstd) else round(float(fstd), 6),
        }

    meta = {
        "fitted_exclusively_on_split": "TRAIN",
        "train_row_count": int(n_train),
        "val_row_count_excluded_from_fit": int((features_df["split"] == "VAL").sum()),
        "test_row_count_excluded_from_fit": int((features_df["split"] == "TEST").sum()),
        "mi_sample_size_train": int(len(sub_idx)),
        "selected_model_feature_count": len(feature_cols),
        "features": stats,
        "fundamentals_subsplit_train_row_count": int(len(fund_train_x)),
        "fundamentals_regime_features": fund_stats,
    }
    meta_path = out_dir / "train_preprocessing_metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return {
        "feature_count": len(feature_cols),
        "train_row_count": int(n_train),
        "val_row_count_excluded_from_fit": int((features_df["split"] == "VAL").sum()),
        "test_row_count_excluded_from_fit": int((features_df["split"] == "TEST").sum()),
        "screening_csv": str(screen_csv),
        "metadata_json": str(meta_path),
        "zero_variance_features": screen_df.loc[screen_df["zero_variance_in_train"] == 1, "feature"].tolist(),
        "top_10_features_by_train_mi": screen_df.head(10)[["feature", "train_mi_dir_1d", "train_spearman_ret_1d", "train_missing_pct"]].to_dict(orient="records"),
    }
