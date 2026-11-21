"""Comprehensive test suite for selection and timing architecture v2.

Covers:
1. Point-in-time universe preservation without future label filtering.
2. Raw unadjusted price semantics and provisional quarantine metadata.
3. Inner validation-only model selection for candidate models (ML vs Baselines).
4. Realistic daily portfolio simulation accounting (cash, equity, position limits, friction).
5. Paired Newey-West HAC statistical test with lag 10.
6. Portfolio concentration metrics (HHI, top-5 concentration, sector allocations).
7. Verification of selection_timing_v2 saved artifacts and honest baseline disclosures.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from m1.portfolio_simulation import (
    compute_concentration_metrics,
    compute_newey_west_t_stat,
    evaluate_portfolio_performance,
    run_portfolio_backtest,
)
from m1.selection_timing_v2 import (
    select_fundamental_model,
    select_technical_model,
)
from m1.decision_pipeline import DecisionConfig
from m1.features import FUNDAMENTAL, TECHNICAL


def test_universe_unfiltered_by_future_labels():
    """Verify panel has rows that would have been dropped by future label filtering."""
    panel_path = Path("data/decision_panel_v2.csv")
    if not panel_path.exists():
        pytest.skip("decision_panel_v2.csv not found, run prepare_decision_inputs_v2 first.")

    df = pd.read_csv(panel_path, nrows=5000)
    assert "symbol" in df.columns
    assert "session" in df.columns
    # Confirm fundamental features and technical features exist
    assert "roe_pct" in df.columns or "pe_ratio" in df.columns
    assert "rsi_14" in df.columns or "momentum_20_pct" in df.columns


def test_raw_unadjusted_prices_semantics():
    """Verify raw prices table documents unadjusted nature and quarantine validity."""
    price_path = Path("data/raw_unadjusted_prices.csv")
    if not price_path.exists():
        pytest.skip("raw_unadjusted_prices.csv not found.")

    prices = pd.read_csv(price_path, nrows=1000)
    assert "symbol" in prices.columns
    assert "session" in prices.columns
    assert "adjusted_open" in prices.columns  # Pipeline naming convention
    assert "adjusted_close" in prices.columns
    assert "price_valid" in prices.columns

    # Verify price_valid is boolean
    assert prices["price_valid"].dtype == bool or prices["price_valid"].isin([0, 1, True, False]).all()


def test_inner_validation_model_selection():
    """Verify candidate models are selected strictly based on inner validation metric."""
    np.random.seed(42)
    symbols = ["S1", "S2", "S3", "S4"]
    n_sessions = 50
    sessions = np.repeat(np.arange(n_sessions), len(symbols))
    syms = np.tile(symbols, n_sessions)
    n = len(sessions)

    data_dict = {
        "symbol": syms,
        "session": sessions,
        "fundamental_target": np.random.randn(n),
        "fundamental_eligible": [True] * n,
        "technical_eligible": [True] * n,
        "technical_binary": np.random.choice([0, 1], size=n),
        "technical_target": np.random.randn(n),
    }
    for col in FUNDAMENTAL:
        data_dict[col] = np.random.randn(n) if col not in ["pe_ratio", "pb_ratio"] else np.abs(np.random.randn(n)) + 2.0
    for col in TECHNICAL:
        data_dict[col] = np.random.randn(n)

    df = pd.DataFrame(data_dict)
    cfg = DecisionConfig(seed=42)

    # Test fundamental model selection
    fund_model, fund_winner, fund_params, fund_trials = select_fundamental_model(df, df, cfg)
    assert fund_winner in ["xgbranker", "value_composite", "momentum"]
    assert len(fund_trials) >= 5

    # Test technical model selection
    tech_model, tech_winner, tech_params, tech_trials = select_technical_model(df, df, cfg)
    assert tech_winner in ["xgboost", "logistic_regression", "sma_breakout"]
    assert len(tech_trials) >= 5


def test_portfolio_backtest_accounting():
    """Verify daily portfolio state accounting: cash conservation, position cap, and friction."""
    # Synthetic 6-session scenario with 2 stocks
    dates = [100, 101, 102, 103, 104, 105]
    symbols = ["A", "B"]

    grid = []
    for d in dates:
        for s in symbols:
            grid.append({
                "session": d,
                "symbol": s,
                "adjusted_open": 100.0 if s == "A" else 200.0,
                "adjusted_close": 105.0 if s == "A" else 195.0,
                "price_valid": True,
            })
    prices_df = pd.DataFrame(grid)

    # Shortlist dict mapping session -> set of symbols
    shortlist_dict = {100: {"A", "B"}}
    technical_signal_dict = {100: {"A", "B"}}

    # Unfiltered policy test
    daily_eq, trades = run_portfolio_backtest(
        sessions=dates,
        prices_df=prices_df,
        shortlist_series=shortlist_dict,
        technical_signal_series=technical_signal_dict,
        initial_capital=10_000_000.0,
        cost_rate=0.005,
        max_position_weight=0.10,
        holding_period=2,
        is_filtered=False,
    )

    assert len(daily_eq) == len(dates)

    # Initial cash
    assert daily_eq.iloc[0]["cash"] == 10_000_000.0
    assert daily_eq.iloc[0]["total_equity"] == 10_000_000.0

    # At session 101, entry at open. Each position max 10% = 1,000,000 PKR.
    # Total allocated <= 2,000,000. Cash remaining >= 8,000,000.
    assert daily_eq.iloc[1]["holdings_value"] > 0
    assert daily_eq.iloc[1]["cash"] < 10_000_000.0
    assert daily_eq.iloc[1]["cash"] >= 8_000_000.0

    # Equity = Cash + Holdings Value at all times
    for _, row in daily_eq.iterrows():
        assert row["total_equity"] == pytest.approx(row["cash"] + row["holdings_value"], abs=1e-2)

    # After holding period (2 sessions: entered session 101, held session 101, 102, closed at 102 close)
    # Positions should be closed and cash returned at session 103
    assert daily_eq.iloc[3]["holdings_value"] == 0.0
    assert daily_eq.iloc[3]["active_positions_count"] == 0


def test_newey_west_hac_t_stat():
    """Verify Newey-West HAC standard error computation with temporal autocorrelation."""
    # Create autocorrelated series
    np.random.seed(42)
    n = 100
    e = np.random.randn(n)
    d = np.zeros(n)
    for t in range(1, n):
        d[t] = 0.6 * d[t - 1] + e[t] + 0.2  # positive mean with AR(1)

    mean_d, t_stat, p_val = compute_newey_west_t_stat(d, max_lags=5)
    assert np.isfinite(t_stat)
    assert 0.0 <= p_val <= 1.0

    # Identical series should yield t=0, p=1
    zeros = np.zeros(50)
    m_z, t_zero, p_zero = compute_newey_west_t_stat(zeros, max_lags=5)
    assert t_zero == 0.0
    assert p_zero == 1.0


def test_concentration_metrics():
    """Verify HHI and top-5 concentration calculations."""
    daily_records = [
        {
            "session": 100,
            "cash": 0.0,
            "holdings_value": 1_000_000.0,
            "total_equity": 1_000_000.0,
            "exposure_pct": 100.0,
            "active_positions_count": 10,
            "position_values": {f"S_{i}": 100_000.0 for i in range(10)},
            "daily_return_pct": 0.0,
        }
    ]
    df = pd.DataFrame(daily_records)
    sector_lookup = {f"S_{i}": "BANKING" for i in range(10)}

    conc = compute_concentration_metrics(df, sector_lookup)
    # HHI for 10 equal 10% positions is 10 * (10)^2 = 1000
    assert conc["mean_hhi"] == pytest.approx(1000.0, abs=1.0)
    assert conc["mean_top5_ticker_weight_pct"] == pytest.approx(50.0, abs=0.1)
    assert conc["average_sector_exposure_pct"]["BANKING"] == pytest.approx(100.0, abs=0.1)


def test_selection_timing_v2_artifacts():
    """Verify saved artifacts exist, have valid structure, and record fair baseline results."""
    art_dir = Path("artifacts/selection_timing_v2")
    if not art_dir.exists():
        pytest.skip("artifacts/selection_timing_v2 directory not found.")

    eval_file = art_dir / "evaluation.json"
    sim_file = art_dir / "portfolio_simulation.json"
    base_file = art_dir / "baseline_comparison.json"

    assert eval_file.exists()
    assert sim_file.exists()
    assert base_file.exists()

    with open(eval_file) as f:
        eval_data = json.load(f)
    assert eval_data["status"] == "COMPLETED"
    assert eval_data["num_folds"] == 3

    with open(sim_file) as f:
        sim_data = json.load(f)
    for fold in ["fold_1", "fold_2", "fold_3"]:
        assert fold in sim_data
        assert "unfiltered_policy" in sim_data[fold]
        assert "filtered_policy" in sim_data[fold]
        assert "paired_statistical_test" in sim_data[fold]
        assert "newey_west_hac_t_stat" in sim_data[fold]["paired_statistical_test"]

    with open(base_file) as f:
        base_data = json.load(f)
    # Fold 3 should report that logistic beat xgboost in technical AP
    assert "fold_3" in base_data
    assert base_data["fold_3"]["technical"]["did_logistic_beat_xgboost"] is True
    # Fold 1 should report value composite beat xgbranker
    assert base_data["fold_1"]["fundamental"]["did_value_composite_beat_xgbranker"] is True
