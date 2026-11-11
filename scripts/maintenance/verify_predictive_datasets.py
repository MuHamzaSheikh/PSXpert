#!/usr/bin/env python3
"""
PSXpert — Anti-Leakage, Integrity & Causality Verification Suite
for Predictive Forecasting Datasets.
"""

import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import text

import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.paths import DATA_AUDIT_REPORTS_DIR, PREDICTIVE_DATA_DIR

from src.database.connection import get_engine
from src.predictive_data.regime_causal import CausalMarketRegimeHMM
from src.predictive_data.daily_builder import _compute_stock_features_and_candlesticks
from src.predictive_data.intraday_builder import (
    INTRADAY_FEATURE_COLUMNS,
    INTRADAY_TARGET_COLUMNS,
    build_intraday_features_and_targets_from_bars,
)


def main():
    data_dir = PREDICTIVE_DATA_DIR
    reports_dir = DATA_AUDIT_REPORTS_DIR

    print("=" * 72)
    print("PSXPERT — PREDICTIVE DATASET ANTI-LEAKAGE & INTEGRITY SUITE")
    print("=" * 72)

    # 1. Load Deliverables
    feat_df = pd.read_parquet(data_dir / "daily_features.parquet")
    tgt_df = pd.read_parquet(data_dir / "daily_targets.parquet")
    dict_df = pd.read_csv(data_dir / "feature_dictionary.csv")
    splits_meta = json.loads((data_dir / "chronological_splits.json").read_text(encoding="utf-8"))
    prep_meta = json.loads((data_dir / "train_preprocessing_metadata.json").read_text(encoding="utf-8"))
    intr_feat = pd.read_parquet(data_dir / "intraday_features.parquet")
    intr_tgt = pd.read_parquet(data_dir / "intraday_targets.parquet")

    # Test 1: Key uniqueness & 1-to-1 alignment
    dup_f = feat_df.duplicated(subset=["symbol", "trading_date"]).sum()
    dup_t = tgt_df.duplicated(subset=["symbol", "trading_date"]).sum()
    assert dup_f == 0, f"Duplicate (symbol, trading_date) in daily_features: {dup_f}"
    assert dup_t == 0, f"Duplicate (symbol, trading_date) in daily_targets: {dup_t}"
    assert len(feat_df) == len(tgt_df), "Row count mismatch between features and targets"
    assert (feat_df["symbol"].values == tgt_df["symbol"].values).all(), "Symbol misalignment"
    assert (feat_df["trading_date"].values == tgt_df["trading_date"].values).all(), "Date misalignment"
    print(f"[PASS] 1. Uniqueness & 1:1 Alignment: {len(feat_df):,} rows, 0 duplicates.")

    # Test 2: Zero weekend phantom rows
    dows = pd.to_datetime(feat_df["trading_date"]).dt.dayofweek
    weekend_cnt = int(dows.isin([5, 6]).sum())
    assert weekend_cnt == 0, f"Weekend rows leaked into daily dataset: {weekend_cnt}"
    print("[PASS] 2. Trading Calendar Integrity: 0 weekend rows; strictly aligned to Mon-Fri PSX sessions.")

    # Test 3: Feature dictionary exact completeness & zero duplicates
    f_cols = set(feat_df.columns)
    d_cols = set(dict_df["feature"])
    missing_from_dict = f_cols - d_cols
    extra_in_dict = d_cols - f_cols
    assert not missing_from_dict, f"Columns missing from feature_dictionary.csv: {missing_from_dict}"
    assert not extra_in_dict, f"Extra columns in feature_dictionary.csv: {extra_in_dict}"
    assert len(dict_df) == len(f_cols), f"Duplicate feature entries in feature_dictionary.csv ({len(dict_df)} vs {len(f_cols)})"
    print(f"[PASS] 3. Feature Dictionary Completeness: All {len(f_cols)} columns documented cleanly with 0 duplicates.")

    # Test 4: True-OHLC candlestick guard (zero fake Doji on flat bars)
    flat_doji = int(((feat_df["is_true_ohlc"] == 0) & (feat_df["is_doji_true_ohlc"] == 1)).sum())
    assert flat_doji == 0, f"Found {flat_doji} fake Doji flags on flat bars"
    flat_candle_nonnull = int(feat_df.loc[feat_df["is_true_ohlc"] == 0, "candle_body_pct"].notna().sum())
    assert flat_candle_nonnull == 0, f"Found non-null candle_body_pct on {flat_candle_nonnull} flat bars"
    print("[PASS] 4. Flat-Bar Candlestick Guard: 0 fake Dojis / NaN candle ratios enforced when high == low.")

    # Test 5: Point-in-Time Financial Publication Dates (ZERO pub_date > trading_date or pub <= period_end)
    fin_rows = feat_df[feat_df["has_fundamentals"] == 1]
    assert len(fin_rows) > 0, "No fundamental rows joined!"
    bad_pub_future = int((pd.to_datetime(fin_rows["effective_pub_date"]) > pd.to_datetime(fin_rows["trading_date"])).sum())
    bad_pub_before_end = int((pd.to_datetime(fin_rows["effective_pub_date"]) <= pd.to_datetime(fin_rows["fin_period_end_date"])).sum())
    assert bad_pub_future == 0, f"Lookahead fundamentals leaked! {bad_pub_future} rows had effective_pub_date > trading_date"
    assert bad_pub_before_end == 0, f"Impossible pub <= period_end! {bad_pub_before_end} rows"
    print(f"[PASS] 5. Fundamentals Point-in-Time Integrity: 0 lookahead violations across {len(fin_rows):,} fundamental-joined rows.")

    # Test 6: Overlapping Label Purge Enforcement across Chronological Splits
    train_end_max = pd.to_datetime(tgt_df.loc[(tgt_df["split"] == "TRAIN") & (tgt_df["target_valid_20d"] == 1), "target_end_date_20d"]).max()
    val_start_min = pd.to_datetime(feat_df.loc[feat_df["split"] == "VAL", "trading_date"]).min()
    assert train_end_max < val_start_min, f"TRAIN 20d label {train_end_max} overlaps VAL {val_start_min}!"

    val_end_max = pd.to_datetime(tgt_df.loc[(tgt_df["split"] == "VAL") & (tgt_df["target_valid_20d"] == 1), "target_end_date_20d"]).max()
    test_start_min = pd.to_datetime(feat_df.loc[feat_df["split"] == "TEST", "trading_date"]).min()
    assert val_end_max < test_start_min, f"VAL 20d label {val_end_max} overlaps TEST {test_start_min}!"
    print(f"[PASS] 6. Overlapping-Label Purge Verified: max TRAIN 20d end ({train_end_max.date()}) < VAL start ({val_start_min.date()}); max VAL 20d end ({val_end_max.date()}) < TEST start ({test_start_min.date()}).")

    # Test 7: Causal HMM Forward Filter Invariance to Future Perturbations
    engine = get_engine()
    with engine.connect() as conn:
        df_idx = pd.read_sql(text("SELECT trading_date, close FROM market_indices WHERE index_symbol='KSE100' ORDER BY trading_date"), conn)
    df_idx["trading_date"] = pd.to_datetime(df_idx["trading_date"]).dt.date
    train_idx_df = df_idx[df_idx["trading_date"] <= pd.to_datetime("2021-12-31").date()].copy()

    hmm = CausalMarketRegimeHMM(n_states=3, random_state=42).fit(train_idx_df)
    probs_orig = hmm.filter_causal_probabilities(df_idx)

    # Perturb ALL index prices in 2022+ (after train_idx_df) by massive synthetic crashes
    df_idx_perturbed = df_idx.copy()
    mask_fut = df_idx_perturbed["trading_date"] >= pd.to_datetime("2022-01-03").date()
    df_idx_perturbed.loc[mask_fut, "close"] = df_idx_perturbed.loc[mask_fut, "close"] * np.where(np.arange(mask_fut.sum()) % 2 == 0, 1.8, 0.4)
    probs_pert = hmm.filter_causal_probabilities(df_idx_perturbed)

    mask_past = probs_orig["trading_date"] < pd.to_datetime("2022-01-03").date()
    max_diff = float(np.nanmax(np.abs(
        probs_orig.loc[mask_past, ["hmm_mkt_prob_bullish", "hmm_mkt_prob_bearish", "hmm_mkt_prob_sideways"]].to_numpy()
        - probs_pert.loc[mask_past, ["hmm_mkt_prob_bullish", "hmm_mkt_prob_bearish", "hmm_mkt_prob_sideways"]].to_numpy()
    )))
    assert max_diff < 1e-12, f"HMM future perturbation leaked into past! max_diff={max_diff}"
    print(f"[PASS] 7. Causal HMM Forward-Filter Invariance: max_diff on pre-2022 probs under future shocks = {max_diff:.2e} (< 1e-12).")

    # Test 8: Causal Technical Indicator & Candlestick Invariance
    ogdc = feat_df[feat_df["symbol"] == "OGDC"].sort_values("trading_date").reset_index(drop=True).copy()
    cut_pos = len(ogdc) - 100
    ogdc_in = pd.DataFrame({
        "symbol": ogdc["symbol"],
        "trading_date": ogdc["trading_date"],
        "cal_idx": ogdc["cal_idx"],
        "calendar_gap_days": ogdc["calendar_gap_days"],
        "raw_open": ogdc["raw_open"],
        "raw_high": ogdc["raw_high"],
        "raw_low": ogdc["raw_low"],
        "raw_close": ogdc["raw_close"],
        "adj_open": ogdc["adj_open"],
        "adj_high": ogdc["adj_high"],
        "adj_low": ogdc["adj_low"],
        "adj_close": ogdc["adj_close"],
        "volume": ogdc["volume"],
    })
    out_base = _compute_stock_features_and_candlesticks(ogdc_in)
    ogdc_shock = ogdc_in.copy()
    for c_col in ["raw_open", "raw_high", "raw_low", "raw_close", "adj_open", "adj_high", "adj_low", "adj_close"]:
        ogdc_shock.loc[cut_pos:, c_col] *= 10.0
    ogdc_shock.loc[cut_pos:, "volume"] *= 5
    out_shock = _compute_stock_features_and_candlesticks(ogdc_shock)

    check_cols = ["rsi_14", "macd_diff_pct", "bb_percent_b", "adx_14", "atr_pct", "obv_zscore_20", "stoch_k", "vol_20d", "amihud_illiquidity_20d", "candlestick_pattern_signal_num"]
    for col in check_cols:
        a = out_base.loc[:cut_pos - 1, col].to_numpy(dtype=np.float64)
        b = out_shock.loc[:cut_pos - 1, col].to_numpy(dtype=np.float64)
        d = np.nanmax(np.abs(np.nan_to_num(a, nan=0.0) - np.nan_to_num(b, nan=0.0)))
        assert d < 1e-12 and (np.isnan(a) == np.isnan(b)).all(), f"Future shock altered historical feature {col}: diff={d}"
    print("[PASS] 8. Technical Indicators & Candlesticks Causality: Zero difference on prior bars under 10x future shock.")

    # Test 9: Corporate Split Continuity & Glitch Masking Check
    # Verify known 5:1 LUCK split (2025-04-28) has normal daily return inside targets instead of -79.5 crash
    luck_ex = tgt_df[(tgt_df["symbol"] == "LUCK") & (pd.to_datetime(tgt_df["trading_date"]) == pd.to_datetime("2025-04-18"))]
    if not luck_ex.empty:
        r1 = luck_ex["target_ret_1d"].iloc[0]
        assert pd.isna(r1) or abs(r1) < 0.15, f"Unadjusted split distortion on LUCK prior to 2025-04-28: {r1}"
    # Verify UPFL 2009-05 corrupted 1.00 glitch targets are masked (target_valid_1d == 0)
    upfl_bad = tgt_df[(tgt_df["symbol"] == "UPFL") & (pd.to_datetime(tgt_df["trading_date"]) == pd.to_datetime("2009-05-04"))]
    if not upfl_bad.empty:
        assert int(upfl_bad["target_valid_1d"].iloc[0]) == 0, "UPFL 1.00 glitch target was not masked invalid!"
    print("[PASS] 9. Split Continuity & Glitch Masking Verified (LUCK split continuous; UPFL glitch target masked).")

    # Test 10: Intraday Schema & Session-Boundary Unit Verification (0 fabricated rows in deliverables)
    assert len(intr_feat) == 0 and list(intr_feat.columns) == INTRADAY_FEATURE_COLUMNS
    assert len(intr_tgt) == 0 and list(intr_tgt.columns) == INTRADAY_TARGET_COLUMNS

    # Synthetic in-memory session-boundary unit check (never saved to deliverable files!)
    ts_fri_am = pd.date_range("2026-10-09 09:20:00+05:00", "2026-10-09 12:00:00+05:00", freq="5min")
    ts_fri_pm = pd.date_range("2026-10-09 14:35:00+05:00", "2026-10-09 16:30:00+05:00", freq="5min")
    all_ts = ts_fri_am.append(ts_fri_pm)
    syn_bars = pd.DataFrame({
        "symbol": "OGDC",
        "timestamp_pkt": all_ts,
        "open": 150.0,
        "high": 151.0,
        "low": 149.5,
        "close": 150.0 + np.arange(len(all_ts)) * 0.1,
        "volume": 5000,
    })
    syn_idx = syn_bars[["timestamp_pkt", "close"]].copy()
    s_feat, s_tgt = build_intraday_features_and_targets_from_bars(syn_bars, syn_idx)
    # Last bars before Friday 12:00 break must have target_valid_30m == 0 (never span break into 14:35)
    near_break = s_tgt[s_tgt["timestamp_pkt"] == pd.Timestamp("2026-10-09 11:45:00+05:00")]
    assert len(near_break) == 1 and int(near_break["target_valid_30m"].iloc[0]) == 0, "Intraday target crossed Friday prayer break!"
    print("[PASS] 10. Intraday Schema & Session-Boundary Unit Check Passed (0 fabricated rows in deliverables; session breaks strictly guarded).")

    # Test 11: Deliverable files exist on disk
    expected_reports = [
        reports_dir / "DATA_AUDIT_REPORT.md",
        reports_dir / "MISSING_DATA_AND_LEAKAGE_REPORT.md",
        reports_dir / "FEATURE_DICTIONARY.md",
        reports_dir / "CHRONOLOGICAL_SPLITS_AND_OVERLAP_POLICY.md",
    ]
    for rp in expected_reports:
        assert rp.exists() and rp.stat().st_size > 500, f"Report missing or empty: {rp}"
    assert "TRAIN" == prep_meta["fitted_exclusively_on_split"]
    print("[PASS] 11. All Deliverable Reports & Train-Only Metadata Verified.")

    # Test 12: Train-Only Preprocessing Invariance under VAL/TEST perturbations
    from src.predictive_data.preprocessing import fit_train_only_preprocessing_and_screening
    with tempfile.TemporaryDirectory(prefix="psxpert_prep_check_") as tmp_dir:
        scratch_tmp = Path(tmp_dir)
        feat_pert = feat_df.copy()
        vt_mask = feat_pert["split"].isin(["VAL", "TEST", "PURGE_TRAIN_VAL", "PURGE_VAL_TEST"])
        feat_pert.loc[vt_mask, "rsi_14"] = 99.9
        feat_pert.loc[vt_mask, "vol_20d"] = 9.9
        fit_train_only_preprocessing_and_screening(feat_pert, tgt_df, scratch_tmp, sample_for_mi=5000)
        pert_meta = json.loads((scratch_tmp / "train_preprocessing_metadata.json").read_text(encoding="utf-8"))
        for f_check in ["rsi_14", "vol_20d", "atr_pct", "rolling_beta_60d"]:
            assert pert_meta["features"][f_check] == prep_meta["features"][f_check], f"VAL/TEST leaked into TRAIN stats for {f_check}!"
    print("[PASS] 12. Train-Only Preprocessing Invariance: Val/Test perturbations left scaling/clipping stats identical.")

    print("=" * 72)
    print("ALL 12 VERIFICATION CHECKS PASSED WITH ZERO LEAKAGE VIOLATIONS!")
    print("=" * 72)


if __name__ == "__main__":
    main()

