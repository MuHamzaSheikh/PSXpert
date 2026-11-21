"""Prepare audited decision pipeline inputs v2 directly from point-in-time sources.

Fixes:
1. Rebuilds the feature panel without filtering signal rows by availability
   of the old future 20-session label.
2. Determines prediction eligibility using only information observable at
   prediction timestamp.
3. Produces raw unadjusted prices with explicitly documented provisional
   quarantine flags, distinguishing them from verified corporate actions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .features import FUNDAMENTAL, TECHNICAL, as_of, build_dataset
from .settings import REPO, ROOT, Settings


def prepare_inputs_v2(output_dir: Path | None = None) -> dict:
    if output_dir is None:
        output_dir = ROOT / "data"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load raw point-in-time sources
    stmts_path = ROOT / "artifacts/combined_v2/audit/filing_source_metrics.csv.gz"
    anns_path = ROOT / "artifacts/combined_v2/audit/filing_source_announcements.csv.gz"
    sp_path = REPO / "data/processed/stock_prices_clean.csv"
    bench_path = REPO / "data/processed/market_indices_clean.csv"
    comp_path = REPO / "data/processed/companies_clean.csv"
    payout_path = REPO / "data/processed/corporate_payouts_clean.csv"

    for p in (stmts_path, anns_path, sp_path, bench_path, comp_path, payout_path):
        if not p.exists():
            raise FileNotFoundError(f"Missing required source file: {p}")

    stmts = pd.read_csv(stmts_path)
    anns = pd.read_csv(anns_path)
    prices_raw = pd.read_csv(sp_path)
    sessions = pd.read_csv(bench_path)
    companies = pd.read_csv(comp_path)
    payouts = pd.read_csv(payout_path)

    # 2. Build point-in-time dataset WITHOUT filtering by future 20-session label
    cutoff = as_of("2026-11-17T00:00:00+05:00")
    sources = (prices_raw, sessions, companies, stmts, anns, payouts, {})

    # Set labels=False so NO future 20-day return filtering is performed!
    data, meta = build_dataset(sources, cutoff, settings=Settings(), labels=False, research_only=False)

    # Filter to companies with at least one published financial report or valid trading history
    # Determine prediction eligibility strictly using point-in-time information:
    # A row is prediction-eligible if it has observable market data today
    panel_df = data.copy()
    panel_df["symbol"] = panel_df["symbol"].astype(str)

    # Prediction timestamp and available timestamp
    panel_df["prediction_timestamp"] = pd.to_datetime(panel_df["prediction_timestamp"], utc=True)
    panel_df["available_from_timestamp"] = pd.to_datetime(panel_df["available_from_timestamp"], utc=True)

    # Prediction eligibility flags based solely on information available at session t
    has_financials = panel_df[FUNDAMENTAL].notna().any(axis=1)
    age_days = (panel_df["prediction_timestamp"] - panel_df["available_from_timestamp"]).dt.total_seconds() / 86400
    panel_df["fundamental_eligible"] = has_financials & age_days.between(0, 550)
    panel_df["technical_eligible"] = panel_df[TECHNICAL].notna().any(axis=1)

    # Focus panel on sessions where fundamental filings are available (from session 5107 to 6126)
    # This aligns the global calendar while preserving all valid point-in-time rows
    min_session = 5107
    max_session = int(panel_df["session"].max())
    panel_clean = panel_df[panel_df["session"].between(min_session, max_session)].sort_values(
        ["session", "symbol"]
    ).reset_index(drop=True)

    # 3. Build Benchmark Calendar (Contiguous sessions)
    kse = sessions[sessions["index_symbol"].str.upper() == "KSE100"].sort_values("trading_date").reset_index(drop=True)
    kse["session"] = kse.index.astype(int)
    kse_filtered = kse[kse["session"].between(min_session, max_session)].sort_values("session").reset_index(drop=True)

    benchmark = pd.DataFrame({
        "session": kse_filtered["session"].astype(int),
        "adjusted_close": kse_filtered["close"].astype(float),
        "price_valid": (
            kse_filtered["close"].gt(0)
            & np.isfinite(kse_filtered["close"])
        ).astype(bool),
    })

    # 4. Build Raw Prices with Explicit Provisional Heuristic Quarantine
    calendar_sessions = np.arange(min_session, max_session + 1)
    merged_sp = prices_raw.merge(kse[["trading_date", "session"]], on="trading_date", how="inner")
    symbols = sorted(panel_clean["symbol"].unique())
    merged_sp = merged_sp[
        merged_sp["symbol"].isin(symbols)
        & merged_sp["session"].isin(calendar_sessions)
    ].sort_values(["symbol", "session"]).reset_index(drop=True)

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

        # Provisional jump heuristic: flag jumps >= 35% in close price
        jump = g["close"].pct_change(fill_method=None).abs().ge(0.35)
        jump_mask = jump.rolling(11, center=True, min_periods=1).max().gt(0).fillna(False)
        quarantine_audit["price_jump_bars_quarantined"] += int(jump_mask.sum())
        valid &= ~jump_mask

        # Provisional payout heuristic: flag corporate action announcements (+/- 5 sessions)
        sym_payouts = payout_map.get(sym, set())
        is_payout = g["date_str"].isin(sym_payouts)
        payout_mask = is_payout.rolling(11, center=True, min_periods=1).max().gt(0).fillna(False)
        quarantine_audit["payout_announcement_bars_quarantined"] += int(payout_mask.sum())
        valid &= ~payout_mask

        # Note: Raw prices are unadjusted. adjusted_open and adjusted_close store raw unadjusted prices.
        # price_valid flags whether the bar is free of provisional heuristic quarantine.
        g["adjusted_open"] = g["open"]
        g["adjusted_close"] = g["close"]
        g["price_valid"] = valid.astype(bool)
        price_rows.append(g[["symbol", "session", "adjusted_open", "adjusted_close", "price_valid"]])

    prices = pd.concat(price_rows, ignore_index=True).sort_values(["session", "symbol"]).reset_index(drop=True)

    # 5. Save Artifacts
    panel_cols = [
        "symbol", "session", "trading_date", "prediction_timestamp", "available_from_timestamp",
        "open", "high", "low", "close", "volume", "market_cap", "sector",
        "fundamental_eligible", "technical_eligible",
        *FUNDAMENTAL, *TECHNICAL
    ]
    # Filter to available columns
    available_cols = [c for c in panel_cols if c in panel_clean.columns]
    clean_panel = panel_clean[available_cols].copy()

    panel_path = output_dir / "decision_panel_v2.csv"
    prices_path = output_dir / "raw_unadjusted_prices.csv"
    bench_path = output_dir / "audited_benchmark.csv"

    clean_panel.to_csv(panel_path, index=False)
    prices.to_csv(prices_path, index=False)
    benchmark.to_csv(bench_path, index=False)

    summary = {
        "status": "SUCCESS",
        "panel_path": str(panel_path),
        "prices_path": str(prices_path),
        "benchmark_path": str(bench_path),
        "panel_rows": len(clean_panel),
        "panel_symbols": len(symbols),
        "panel_sessions": [min_session, max_session],
        "fundamental_eligible_rows": int(clean_panel["fundamental_eligible"].sum()),
        "technical_eligible_rows": int(clean_panel["technical_eligible"].sum()),
        "price_rows": len(prices),
        "price_valid_pct": float(prices["price_valid"].mean()),
        "quarantine_audit": quarantine_audit,
        "price_validity_clarification": [
            "PRICES ARE RAW UNADJUSTED: PSX historical prices do not include certified share adjustment factors.",
            "PROVISIONAL QUARANTINE ONLY: Setting price_valid=False on announcement windows (+/-5 sessions) and jump breaks (>=35%) is a heuristic safeguard, not certified corporate action adjustment.",
            "LABEL UNCERTAINTY: Unannounced corporate actions or payout yields below 35% outside announcement windows remain in raw prices as residual return noise.",
        ],
        "input_universe_clarification": [
            "NO FUTURE LABEL FILTERING: Rows were NOT filtered by future_direction.notna(). Eligibility was determined strictly by data available at session t close.",
            "RECOVERED OBSERVATIONS: Observations previously dropped due to future 20-session label gaps are now fully preserved at prediction time.",
        ],
    }

    audit_path = output_dir / "panel_audit_v2.json"
    audit_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    res = prepare_inputs_v2(args.output)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
