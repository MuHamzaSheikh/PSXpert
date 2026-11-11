#!/usr/bin/env python3
"""
PSXpert — Master Predictive Dataset Preparation Orchestrator.

Executes Steps 1–6 cleanly without modifying dashboard or backend logic:
1. Audits existing PostgreSQL warehouse, CSVs, and quantitative modules.
2. Builds daily causal forecasting feature dataset (8 feature domains, 726 equities).
3. Builds schema-complete intraday dataset templates (strictly separated; 0 rows due to missing intraday feed).
4. Builds multi-horizon future prediction targets (1d, 5d, 20d) with volatility + PSX tx-cost 3-class thresholds.
5. Fits preprocessing & feature screening strictly on chronological TRAIN split only.
6. Emits complete audit, leakage, split, and feature dictionary deliverables.
"""

import json
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.database.connection import get_engine
from src.predictive_data.audit import run_comprehensive_audit
from src.predictive_data.daily_builder import build_daily_forecasting_datasets
from src.predictive_data.intraday_builder import audit_intraday_availability, create_empty_intraday_deliverables
from src.predictive_data.preprocessing import fit_train_only_preprocessing_and_screening
from src.predictive_data.reports import write_all_deliverable_reports


def _summarize_targets(targets_df: pd.DataFrame) -> dict:
    summary = {}
    for h in (1, 5, 20):
        v_mask = targets_df[f"target_valid_{h}d"] == 1
        valid_n = int(v_mask.sum())
        invalid_n = int((~v_mask).sum())
        dirs = targets_df.loc[v_mask, f"target_dir_{h}d"]
        summary[f"{h}d"] = {
            "valid_count": valid_n,
            "invalid_count": invalid_n,
            "up_pct": round(float((dirs == 1).mean() * 100), 2) if valid_n > 0 else 0.0,
            "neutral_pct": round(float((dirs == 0).mean() * 100), 2) if valid_n > 0 else 0.0,
            "down_pct": round(float((dirs == -1).mean() * 100), 2) if valid_n > 0 else 0.0,
        }
    return summary


def main():
    t0 = time.time()
    project_root = Path(__file__).resolve().parent
    out_data_dir = project_root / "data" / "predictive"
    out_reports_dir = project_root / "reports" / "predictive"
    out_data_dir.mkdir(parents=True, exist_ok=True)
    out_reports_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("PSXPERT — PREDICTIVE DATASET PREPARATION PIPELINE")
    print("=" * 72)

    engine = get_engine()

    # Step 1: Audit
    print("\n[1/6] Auditing PostgreSQL tables, CSVs, and quantitative modules...")
    audit_res = run_comprehensive_audit(engine, project_root)
    audit_json_path = out_data_dir / "data_audit_metrics.json"
    audit_json_path.write_text(json.dumps(audit_res, indent=2, default=str), encoding="utf-8")
    print(f"      Raw stock_prices: {audit_res['stock_prices']['total_rows']:,} | Intraday: {audit_res['intraday_availability']['historical_intraday_rows_available']}")

    # Step 2 & 4: Daily Features + Multi-Horizon Targets
    print("\n[2/6] Building point-in-time daily features & multi-horizon targets...")
    features_df, targets_df, daily_meta = build_daily_forecasting_datasets(engine)
    target_stats = _summarize_targets(targets_df)

    daily_feat_pq = out_data_dir / "daily_features.parquet"
    daily_tgt_pq = out_data_dir / "daily_targets.parquet"
    features_df.to_parquet(daily_feat_pq, index=False, compression="snappy")
    targets_df.to_parquet(daily_tgt_pq, index=False, compression="snappy")

    # Also export a KSE-100 target-label CSV (and full daily_targets Parquet) for easy tabular inspection
    kse_tgt_csv = out_data_dir / "daily_targets_kse100_sample.csv"
    kse_syms = set(features_df.loc[features_df["is_current_kse100"] == 1, "symbol"].unique())
    targets_df[targets_df["symbol"].isin(kse_syms)].to_csv(kse_tgt_csv, index=False)

    print(f"      Daily features: {len(features_df):,} rows x {len(features_df.columns)} cols -> {daily_feat_pq}")
    print(f"      Daily targets:  {len(targets_df):,} rows x {len(targets_df.columns)} cols -> {daily_tgt_pq}")
    print(f"      Target stats:   {target_stats}")

    # Step 3: Intraday Separation & Template Deliverables
    print("\n[3/6] Checking intraday data availability and creating strict intraday templates...")
    intraday_audit = audit_intraday_availability(engine, project_root)
    intraday_meta = create_empty_intraday_deliverables(out_data_dir, intraday_audit)
    print(f"      Intraday status: {intraday_audit['status']} (0 rows; schema templates generated)")

    # Step 5: Train-Only Preprocessing & Feature Screening
    print("\n[4/6] Fitting preprocessing & feature screening STRICTLY on TRAIN split...")
    prep_meta = fit_train_only_preprocessing_and_screening(features_df, targets_df, out_data_dir)
    print(f"      Evaluated {prep_meta['feature_count']} numeric features on {prep_meta['train_row_count']:,} TRAIN rows only.")

    # Step 6: Documentation Deliverables
    print("\n[5/6] Generating Audit, Missing-Data/Leakage, Feature Dictionary, and Splits reports...")
    report_files = write_all_deliverable_reports(
        reports_dir=out_reports_dir,
        data_dir=out_data_dir,
        audit_res=audit_res,
        daily_meta=daily_meta,
        intraday_meta=intraday_meta,
        prep_meta=prep_meta,
        target_stats=target_stats,
    )

    # Save master build manifest
    manifest = {
        "elapsed_seconds": round(time.time() - t0, 2),
        "daily_meta": daily_meta,
        "target_stats": target_stats,
        "preprocessing_summary": prep_meta,
        "intraday_summary": intraday_meta,
        "report_files": report_files,
    }
    manifest_path = out_data_dir / "build_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    print("\n[6/6] Predictive dataset build complete in {:.2f}s!".format(manifest["elapsed_seconds"]))
    print("=" * 72)


if __name__ == "__main__":
    main()

