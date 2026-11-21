"""Unit and integration tests for Append-Only Forward Paper Evaluation Engine."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

from m1.paper_evaluation import PaperEvaluationEngine, run_paper_replay, PaperPosition


@pytest.fixture
def temp_eval_dir(tmp_path: Path) -> Path:
    eval_dir = tmp_path / "paper_eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    return eval_dir


def test_engine_initialization(temp_eval_dir: Path):
    engine = PaperEvaluationEngine(
        eval_dir=temp_eval_dir,
        initial_capital=10_000_000.0,
        holding_period=10,
        decision_threshold=0.50,
        top_fraction=0.20,
    )
    assert engine.last_processed_session is None
    assert engine.cash["Policy_A"] == 10_000_000.0
    assert engine.cash["Policy_B"] == 10_000_000.0
    assert len(engine.positions["Policy_A"]) == 0
    assert len(engine.positions["Policy_B"]) == 0


def test_append_only_enforcement(temp_eval_dir: Path):
    engine = PaperEvaluationEngine(eval_dir=temp_eval_dir)
    engine.last_processed_session = 5905
    engine._save_state()

    # Attempting to process an older or equal session must raise ValueError
    with pytest.raises(ValueError, match="already processed"):
        engine.process_session(
            session=5905,
            prices_df=pd.DataFrame(),
            panel_df=pd.DataFrame(),
            benchmark_df=pd.DataFrame(),
        )

    with pytest.raises(ValueError, match="already processed"):
        engine.process_session(
            session=5900,
            prices_df=pd.DataFrame(),
            panel_df=pd.DataFrame(),
            benchmark_df=pd.DataFrame(),
        )


def test_separate_signals_and_intended_orders_schema(temp_eval_dir: Path):
    # Run replay test on a tiny slice (3 sessions: 5900, 5901, 5902)
    run_paper_replay(start_session=5900, end_session=5902, eval_dir=temp_eval_dir)

    # Verify separate signal logs exist
    fund_signals_path = temp_eval_dir / "signals_fundamental.csv"
    tech_signals_path = temp_eval_dir / "signals_technical.csv"
    intended_orders_path = temp_eval_dir / "intended_orders.csv"
    ledger_path = temp_eval_dir / "order_ledger.csv"
    daily_state_path = temp_eval_dir / "portfolio_daily_state.csv"

    assert fund_signals_path.exists(), "signals_fundamental.csv must exist"
    assert tech_signals_path.exists(), "signals_technical.csv must exist"
    assert intended_orders_path.exists(), "intended_orders.csv must exist"
    assert ledger_path.exists(), "order_ledger.csv must exist"
    assert daily_state_path.exists(), "portfolio_daily_state.csv must exist"

    # Verify fundamental signals schema
    df_fund = pd.read_csv(fund_signals_path)
    expected_fund_cols = {
        "timestamp", "session", "symbol", "fundamental_score",
        "shortlist_flag", "value_score", "momentum_score"
    }
    assert expected_fund_cols.issubset(set(df_fund.columns))
    assert (df_fund["session"] >= 5900).all()

    # Verify technical signals schema
    df_tech = pd.read_csv(tech_signals_path)
    expected_tech_cols = {
        "timestamp", "session", "symbol", "technical_prob",
        "threshold", "signal_flag"
    }
    assert expected_tech_cols.issubset(set(df_tech.columns))

    # Verify intended orders schema
    df_intended = pd.read_csv(intended_orders_path)
    expected_order_cols = {
        "timestamp", "session", "timing", "order_id",
        "policy", "symbol", "side", "intended_spend", "status"
    }
    assert expected_order_cols.issubset(set(df_intended.columns))
    assert (df_intended["status"] == "PENDING").all()


def test_intended_order_precedes_ledger(temp_eval_dir: Path):
    run_paper_replay(start_session=5900, end_session=5902, eval_dir=temp_eval_dir)

    intended_path = temp_eval_dir / "intended_orders.csv"
    ledger_path = temp_eval_dir / "order_ledger.csv"

    df_intended = pd.read_csv(intended_path)
    df_ledger = pd.read_csv(ledger_path)

    # Every executed buy order in ledger should have originated from an intended order
    intended_order_ids = set(df_intended["order_id"])
    buy_fills = df_ledger[df_ledger["side"] == "BUY"]
    for _, row in buy_fills.iterrows():
        assert row["order_id"] in intended_order_ids


def test_maturity_delay_enforcement(temp_eval_dir: Path):
    # Run only 5 sessions (5900 to 5904).
    # Since holding_period = 10, no technical outcomes generated at session 5900 can mature by session 5904!
    run_paper_replay(start_session=5900, end_session=5904, eval_dir=temp_eval_dir)

    matured_tech_path = temp_eval_dir / "matured_technical_outcomes.csv"
    if matured_tech_path.exists():
        df_matured = pd.read_csv(matured_tech_path)
        assert len(df_matured) == 0, "No technical outcomes should mature before t+10"

    # Now advance beyond 10 sessions (5905 to 5911)
    run_paper_replay(start_session=5905, end_session=5911, eval_dir=temp_eval_dir)
    assert matured_tech_path.exists()
    df_matured = pd.read_csv(matured_tech_path)
    assert len(df_matured) > 0, "Outcomes for session 5900 and 5901 should now have matured"
    # Verify that the maturity session is strictly session + 10
    for _, row in df_matured.iterrows():
        assert row["maturity_session"] == row["session"] + 10
        assert row["maturity_session"] <= 5911


def test_accounting_integrity_and_fees(temp_eval_dir: Path):
    run_paper_replay(start_session=5900, end_session=5915, eval_dir=temp_eval_dir)

    daily_state_path = temp_eval_dir / "portfolio_daily_state.csv"
    ledger_path = temp_eval_dir / "order_ledger.csv"

    df_state = pd.read_csv(daily_state_path)
    df_ledger = pd.read_csv(ledger_path)

    # Check fee calculation: fee should equal gross_amount * 0.0025 (half of 0.005 round-trip)
    for _, fill in df_ledger.iterrows():
        expected_fee = round(fill["gross_amount"] * 0.0025, 4)
        assert abs(fill["fee"] - expected_fee) < 0.05

    # Check total equity equation: equity = cash + market_value
    for _, row in df_state.iterrows():
        assert abs(row["total_equity"] - (row["cash"] + row["holdings_value"])) < 0.01
