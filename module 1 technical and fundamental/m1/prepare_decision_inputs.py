"""Prepare audited decision pipeline inputs from project sources.

Produces:
1. data/decision_panel.csv: Point-in-time features with exact publication gate.
2. data/audited_prices.csv: Unadjusted prices with audited corporate-action and jump quarantine.
3. data/audited_benchmark.csv: Contiguous global market-session KSE100 benchmark.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .decision_pipeline import DecisionConfig, build_targets, validate_panel
from .features import FUNDAMENTAL, TECHNICAL
from .settings import REPO, ROOT


def prepare_inputs(output_dir: Path | None = None) -> dict:
    if output_dir is None:
        output_dir = ROOT / "data"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Panel
    panel_source = ROOT / "artifacts/combined_v2/eligible_rows.csv.gz"
    if not panel_source.exists():
        panel_source = REPO / "module 1 technical and fundamental/artifacts/combined_v2/eligible_rows.csv.gz"
    if not panel_source.exists():
        raise FileNotFoundError(f"Cannot find {panel_source}")

    raw_panel = pd.read_csv(panel_source)
    config = DecisionConfig()
    panel = validate_panel(raw_panel, config)
    symbols = sorted(panel["symbol"].unique())
    min_session = int(panel["session"].min())
    max_panel_session = int(panel["session"].max())

    # 2. Benchmark (KSE100 from market_indices_clean.csv)
    bench_source = REPO / "data/processed/market_indices_clean.csv"
    kse = pd.read_csv(bench_source)
    kse = kse[kse["index_symbol"].str.upper() == "KSE100"].sort_values("trading_date").reset_index(drop=True)
    kse["session"] = kse.index.astype(int)
    max_kse_session = int(kse["session"].max())

    # Session calendar spans from min_session of panel to max available session in KSE100
    calendar_sessions = np.arange(min_session, max_kse_session + 1)
    kse_filtered = kse[kse["session"].isin(calendar_sessions)].sort_values("session").reset_index(drop=True)

    benchmark = pd.DataFrame({
        "session": kse_filtered["session"].astype(int),
        "adjusted_close": kse_filtered["close"].astype(float),
        "price_valid": (
            kse_filtered["close"].gt(0)
            & np.isfinite(kse_filtered["close"])
        ).astype(bool),
    })

    # Verify contiguous benchmark sessions
    b_sessions = np.sort(benchmark["session"].unique())
    if not np.array_equal(b_sessions, np.arange(b_sessions[0], b_sessions[-1] + 1)):
        raise ValueError("Benchmark sessions are not contiguous")

    # 3. Stock prices and audit
    sp_source = REPO / "data/processed/stock_prices_clean.csv"
    sp = pd.read_csv(sp_source)
    merged_sp = sp.merge(kse[["trading_date", "session"]], on="trading_date", how="inner")
    merged_sp = merged_sp[
        merged_sp["symbol"].isin(symbols)
        & merged_sp["session"].isin(calendar_sessions)
    ].sort_values(["symbol", "session"]).reset_index(drop=True)

    # Load corporate payouts for quarantine
    payout_source = REPO / "data/processed/corporate_payouts_clean.csv"
    payouts = pd.read_csv(payout_source)
    payouts["date_str"] = pd.to_datetime(payouts["announcement_date"]).dropna().dt.strftime("%Y-%m-%d")
    payout_map = payouts.groupby("symbol")["date_str"].apply(set).to_dict()

    merged_sp["date_str"] = pd.to_datetime(merged_sp["trading_date"]).dt.strftime("%Y-%m-%d")

    price_rows = []
    quarantine_audit = {
        "payout_announcement_bars_quarantined": 0,
        "price_jump_bars_quarantined": 0,
        "invalid_or_missing_price_bars": 0,
    }

    for sym, group in merged_sp.groupby("symbol"):
        g = group.sort_values("session").set_index("session").reindex(calendar_sessions).reset_index()
        g["symbol"] = sym

        valid = (
            g["open"].gt(0)
            & g["close"].gt(0)
            & np.isfinite(g["open"])
            & np.isfinite(g["close"])
        )
        quarantine_audit["invalid_or_missing_price_bars"] += int((~valid).sum())

        # Flag jumps >= 35% in close price
        jump = g["close"].pct_change(fill_method=None).abs().ge(0.35)
        jump_mask = jump.rolling(11, center=True, min_periods=1).max().gt(0).fillna(False)
        quarantine_audit["price_jump_bars_quarantined"] += int(jump_mask.sum())
        valid &= ~jump_mask

        # Flag corporate action announcements (+/- 5 sessions)
        sym_payouts = payout_map.get(sym, set())
        is_payout = g["date_str"].isin(sym_payouts)
        payout_mask = is_payout.rolling(11, center=True, min_periods=1).max().gt(0).fillna(False)
        quarantine_audit["payout_announcement_bars_quarantined"] += int(payout_mask.sum())
        valid &= ~payout_mask

        g["adjusted_open"] = g["open"]
        g["adjusted_close"] = g["close"]
        g["price_valid"] = valid.astype(bool)
        price_rows.append(g[["symbol", "session", "adjusted_open", "adjusted_close", "price_valid"]])

    prices = pd.concat(price_rows, ignore_index=True).sort_values(["session", "symbol"]).reset_index(drop=True)

    # 4. Save CSV files
    panel_cols = ["symbol", "session", "prediction_timestamp", "available_from_timestamp", *FUNDAMENTAL, *TECHNICAL]
    clean_panel = panel[panel_cols].copy()

    panel_path = output_dir / "decision_panel.csv"
    prices_path = output_dir / "audited_prices.csv"
    bench_path = output_dir / "audited_benchmark.csv"

    clean_panel.to_csv(panel_path, index=False)
    prices.to_csv(prices_path, index=False)
    benchmark.to_csv(bench_path, index=False)

    # Also mirror to root data directory if different
    root_data = REPO / "data"
    if root_data != output_dir:
        root_data.mkdir(parents=True, exist_ok=True)
        clean_panel.to_csv(root_data / "decision_panel.csv", index=False)
        prices.to_csv(root_data / "audited_prices.csv", index=False)
        benchmark.to_csv(root_data / "audited_benchmark.csv", index=False)

    # 5. Verify by building targets
    targets = build_targets(clean_panel, prices, benchmark, config)
    f_valid = int(targets["fundamental_target"].notna().sum())
    t_valid = int(targets["technical_target"].notna().sum())

    audit_summary = {
        "panel_rows": len(clean_panel),
        "panel_symbols": len(symbols),
        "panel_session_range": [min_session, max_panel_session],
        "benchmark_sessions": len(benchmark),
        "benchmark_session_range": [int(b_sessions[0]), int(b_sessions[-1])],
        "price_rows": len(prices),
        "price_valid_pct": float(prices["price_valid"].mean()),
        "fundamental_targets_available": f_valid,
        "fundamental_target_dates": int(targets[targets["fundamental_target"].notna()]["session"].nunique()),
        "fundamental_target_mean_pct": float(targets["fundamental_target"].mean()) if f_valid else None,
        "technical_targets_available": t_valid,
        "technical_target_positive_rate": float(targets["technical_target"].gt(config.entry_margin_pct).mean()) if t_valid else None,
        "quarantine_audit": quarantine_audit,
        "unresolved_blockers": [
            "Corporate actions have not been retrospectively adjusted; unadjusted prices are quarantined during corporate action announcement windows (+/- 5 sessions) and jump breaks (>= 35%).",
            "Targets spanning any quarantined bar are set to NaN to prevent distorted return calculations.",
            "Historical financial statements use actual point-in-time publication dates from PSX DPS annual report transmissions; banks lack D/E and FCF.",
        ],
    }

    return audit_summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    summary = prepare_inputs(args.output)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
