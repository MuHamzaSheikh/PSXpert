"""Targeted acceptance test suite for PSXpert Append-Only Paper Evaluation Engine.

Verifies:
1. Matching outcome definitions to training:
   - Technical Ground Truth Target:
     net_stock_return_pct = 100 * (close[t+10] / open[t+1] - 1) - cost_pct
     label = int(net_stock_return_pct > entry_margin_pct)
     Does NOT subtract benchmark return when constructing this label.
     Benchmark-relative return is kept as a separately named diagnostic.
     Requires strictly valid 11-session contiguous price window (sessions t through t+10).
   - Fundamental Ranking: Evaluates excess return against KSE-100 benchmark from session t
     adjusted close to session t+126 adjusted close over a strictly contiguous valid window.
   - Discriminating test: stock net return = 3%, benchmark return = 4%, hurdle = 2% yields positive label.
2. Transactional Recovery & Idempotency:
   - Uses processing_session transaction identity, not execution or signal dates.
   - Successful session t commit preserves intended orders scheduled for t+1 across restart.
   - Rollback removes only records from uncommitted transactions (processing_session > committed_session),
     including matured outcomes whose signal sessions were earlier.
   - Handles failure during the very first session too.
   - Restart after close executes next-open order exactly once.
   - Crash before commit followed by restart and retry gives identical result to uninterrupted run.
   - Crash while writing matured outcomes.
   - Crash during first processed session.
3. Market-session continuity enforcement & unresolved outcome queue.
4. Frozen release contract enforcement & configuration immutability.
5. Documented risk controls (25% drawdown circuit breaker).
6. Prospective paper vs historical replay isolation and provenance metadata.
7. End-to-end 128-session synthetic fixture exercising BOTH technical (10) and fundamental (126) horizons.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from m1.features import FUNDAMENTAL, TECHNICAL
from m1.paper_evaluation import PaperEvaluationEngine, PRIMARY_KEYS


@pytest.fixture
def temp_eval_dir(tmp_path: Path) -> Path:
    eval_dir = tmp_path / "paper_eval_test"
    eval_dir.mkdir(parents=True, exist_ok=True)
    return eval_dir


def create_synthetic_market_data(num_sessions: int = 128, symbols: list[str] = None):
    if symbols is None:
        symbols = ["AAA", "BBB", "CCC"]

    start_date = datetime(2023, 1, 1, 13, 0, tzinfo=timezone.utc)
    panel_rows = []
    price_rows = []
    bench_rows = []

    np.random.seed(42)

    for s in range(1, num_sessions + 1):
        s_date = start_date + timedelta(days=s)
        pred_ts = s_date.isoformat()
        avail_ts = (s_date - timedelta(days=30)).isoformat()

        # Benchmark
        b_close = 40000.0 * (1.0 + 0.0005 * s + 0.01 * np.sin(s / 10.0))
        bench_rows.append({
            "session": s,
            "adjusted_close": b_close,
            "benchmark_close": b_close,
            "price_valid": True,
        })

        for sym in symbols:
            # Price
            base_p = 100.0 + (hash(sym) % 50)
            stk_p = base_p * (1.0 + 0.001 * s + 0.02 * np.cos(s / 8.0))
            price_rows.append({
                "session": s,
                "symbol": sym,
                "open": stk_p * 0.995,
                "high": stk_p * 1.01,
                "low": stk_p * 0.99,
                "close": stk_p,
                "adjusted_open": stk_p * 0.995,
                "adjusted_close": stk_p,
                "volume": 1_000_000.0,
                "price_valid": True,
            })

            # Features
            row_dict = {
                "session": s,
                "symbol": sym,
                "prediction_timestamp": pred_ts,
                "available_from_timestamp": avail_ts,
                "pe_ratio": 8.5,
                "pb_ratio": 1.2,
                "momentum_20_pct": 2.5,
            }
            # Fill all technical and fundamental columns with valid floats
            for col in TECHNICAL:
                if col not in row_dict:
                    row_dict[col] = float(np.random.normal(0.0, 1.0))
            for col in FUNDAMENTAL:
                if col not in row_dict:
                    row_dict[col] = float(np.random.uniform(5.0, 20.0))

            panel_rows.append(row_dict)

    return (
        pd.DataFrame(panel_rows),
        pd.DataFrame(price_rows),
        pd.DataFrame(bench_rows),
    )


# ==============================================================================
# 1. FROZEN RELEASE CONTRACT TESTS
# ==============================================================================

def test_frozen_release_contract_enforcement(temp_eval_dir: Path):
    engine = PaperEvaluationEngine(eval_dir=temp_eval_dir)
    assert engine.last_processed_session is None

    fake_release_dir = temp_eval_dir / "fake_release"
    fake_release_dir.mkdir(parents=True)
    fake_manifest = fake_release_dir / "release_manifest.json"
    fake_manifest.write_text(json.dumps({
        "release_files": {"non_existent.joblib": "0000000000000000"}
    }))

    with pytest.raises((RuntimeError, FileNotFoundError)):
        PaperEvaluationEngine(eval_dir=temp_eval_dir / "sub", release_dir=fake_release_dir)


def test_configuration_immutability_on_resume(temp_eval_dir: Path):
    engine = PaperEvaluationEngine(eval_dir=temp_eval_dir, decision_threshold=0.50)
    assert engine.decision_threshold == 0.50

    with pytest.raises(ValueError, match="Configuration mutation on resume prohibited"):
        PaperEvaluationEngine(eval_dir=temp_eval_dir, decision_threshold=0.55)


def test_publication_timestamp_lookahead_validation(temp_eval_dir: Path):
    panel, prices, bench = create_synthetic_market_data(num_sessions=2)
    engine = PaperEvaluationEngine(eval_dir=temp_eval_dir)

    panel.loc[0, "available_from_timestamp"] = "2029-01-01T00:00:00Z"
    panel.loc[0, "prediction_timestamp"] = "2023-01-01T00:00:00Z"

    with pytest.raises(ValueError, match="Lookahead bias detected"):
        engine.process_session(session=1, prices_df=prices, panel_df=panel, benchmark_df=bench)


# ==============================================================================
# 2. CONTINUITY & RECOVERY TESTS
# ==============================================================================

def test_session_continuity_enforcement(temp_eval_dir: Path):
    panel, prices, bench = create_synthetic_market_data(num_sessions=5)
    engine = PaperEvaluationEngine(eval_dir=temp_eval_dir)

    engine.process_session(session=1, prices_df=prices, panel_df=panel, benchmark_df=bench)
    assert engine.last_processed_session == 1

    with pytest.raises(ValueError, match="Market-session continuity violation"):
        engine.process_session(session=3, prices_df=prices, panel_df=panel, benchmark_df=bench)

    with pytest.raises(ValueError, match="Append-only violation"):
        engine.process_session(session=1, prices_df=prices, panel_df=panel, benchmark_df=bench)


def test_successful_close_restart_next_open_order_executes_exactly_once(temp_eval_dir: Path):
    """Session t commit preserves intended orders scheduled for t+1 across restart; executes once."""
    panel, prices, bench = create_synthetic_market_data(num_sessions=5)
    engine = PaperEvaluationEngine(eval_dir=temp_eval_dir)

    # Process session 1: generates intended orders for session 2 Open
    engine.process_session(session=1, prices_df=prices, panel_df=panel, benchmark_df=bench)
    assert engine.last_processed_session == 1

    intended_file = temp_eval_dir / "intended_orders.csv"
    assert intended_file.exists()
    df_intended = pd.read_csv(intended_file)
    assert not df_intended.empty
    # Orders planned in session 1 for execution in session 2
    assert (df_intended["processing_session"] == 1).all()
    assert (df_intended["execution_session"] == 2).all()

    # Restart engine (simulate clean reboot)
    engine_restarted = PaperEvaluationEngine(eval_dir=temp_eval_dir)
    assert engine_restarted.last_processed_session == 1

    # Verify intended orders for session 2 were preserved by restart recovery
    df_intended_after = pd.read_csv(intended_file)
    assert len(df_intended_after) == len(df_intended)

    # Process session 2: pending orders execute at Open
    engine_restarted.process_session(session=2, prices_df=prices, panel_df=panel, benchmark_df=bench)
    assert engine_restarted.last_processed_session == 2

    # Check ledger: order executed exactly once
    ledger_file = temp_eval_dir / "order_ledger.csv"
    assert ledger_file.exists()
    df_ledger = pd.read_csv(ledger_file)
    buy_fills = df_ledger[(df_ledger["execution_session"] == 2) & (df_ledger["side"] == "BUY")]
    assert len(buy_fills) == len(df_intended)
    # Check distinct order IDs
    assert buy_fills["order_id"].nunique() == len(buy_fills)

    # Restart engine again and run session 3: orders from session 2 must NOT re-execute
    engine_restart_2 = PaperEvaluationEngine(eval_dir=temp_eval_dir)
    engine_restart_2.process_session(session=3, prices_df=prices, panel_df=panel, benchmark_df=bench)
    df_ledger_final = pd.read_csv(ledger_file)
    buy_fills_s2 = df_ledger_final[(df_ledger_final["execution_session"] == 2) & (df_ledger_final["side"] == "BUY")]
    assert len(buy_fills_s2) == len(buy_fills), "Next-open order must never re-execute after restart"


def test_crash_before_commit_restart_retry_identical(tmp_path: Path):
    """Crash before commit followed by restart and retry gives identical result to uninterrupted execution."""
    panel, prices, bench = create_synthetic_market_data(num_sessions=5)

    dir_uninterrupted = tmp_path / "uninterrupted"
    dir_crashed = tmp_path / "crashed"

    # 1. Uninterrupted run for sessions 1, 2, 3
    engine_ref = PaperEvaluationEngine(eval_dir=dir_uninterrupted)
    for s in [1, 2, 3]:
        engine_ref.process_session(session=s, prices_df=prices, panel_df=panel, benchmark_df=bench)

    # 2. Crashed run
    engine_test = PaperEvaluationEngine(eval_dir=dir_crashed)
    # Run session 1 normally
    engine_test.process_session(session=1, prices_df=prices, panel_df=panel, benchmark_df=bench)
    assert engine_test.last_processed_session == 1

    # Simulate crash during session 2:
    # Run session 2 internal operations by calling process_session but manually resetting state back to session 1
    engine_test.process_session(session=2, prices_df=prices, panel_df=panel, benchmark_df=bench)
    # Now simulate a crash that happened before state write committed: reset state file to session 1
    ref_state_s1 = json.loads((dir_uninterrupted / "engine_state.json").read_text())
    # Find session 1 state snapshot
    state_s1_dict = {
        "config": engine_test._active_config_dict(),
        "last_processed_session": 1,
        "cash": {"Policy_A": 10000000.0, "Policy_B": 10000000.0},
        "peak_equity": {"Policy_A": 10000000.0, "Policy_B": 10000000.0},
        "circuit_breaker": engine_test.circuit_breaker,
        "next_order_id": 2,
        "next_position_id": 1,
        "positions": {"Policy_A": [], "Policy_B": []},
        "unresolved_matured_outcomes": [],
        "baselines": {"value_composite": "SCORE_ONLY_RANKING_BASELINE", "momentum": "SCORE_ONLY_RANKING_BASELINE"},
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (dir_crashed / "engine_state.json").write_text(json.dumps(state_s1_dict, indent=2))

    # CSV files in dir_crashed now contain uncommitted rows with processing_session = 2
    fund_csv = dir_crashed / "signals_fundamental.csv"
    df_fund = pd.read_csv(fund_csv)
    assert (df_fund["processing_session"] == 2).any()

    # Re-instantiate engine: crash recovery must roll back uncommitted session 2 rows
    restarted_engine = PaperEvaluationEngine(eval_dir=dir_crashed)
    assert restarted_engine.last_processed_session == 1

    df_recovered = pd.read_csv(fund_csv)
    assert not (df_recovered["processing_session"] == 2).any(), "Uncommitted session 2 rows must be rolled back"

    # Re-run session 2 and then session 3
    restarted_engine.process_session(session=2, prices_df=prices, panel_df=panel, benchmark_df=bench)
    restarted_engine.process_session(session=3, prices_df=prices, panel_df=panel, benchmark_df=bench)

    # Compare terminal state and records
    state_ref = json.loads((dir_uninterrupted / "engine_state.json").read_text())
    state_crashed = json.loads((dir_crashed / "engine_state.json").read_text())

    assert state_crashed["last_processed_session"] == state_ref["last_processed_session"]
    assert state_crashed["cash"] == pytest.approx(state_ref["cash"])

    # Compare order ledger
    df_led_ref = pd.read_csv(dir_uninterrupted / "order_ledger.csv")
    df_led_crashed = pd.read_csv(dir_crashed / "order_ledger.csv")
    assert len(df_led_crashed) == len(df_led_ref)
    assert np.allclose(df_led_crashed["gross_amount"].to_numpy(), df_led_ref["gross_amount"].to_numpy())


def test_crash_while_writing_matured_outcomes(temp_eval_dir: Path):
    """Crash while writing matured outcomes rolls back uncommitted outcome records."""
    panel, prices, bench = create_synthetic_market_data(num_sessions=15)
    engine = PaperEvaluationEngine(eval_dir=temp_eval_dir, holding_period=10)

    # Process sessions 1 through 10
    for s in range(1, 11):
        engine.process_session(session=s, prices_df=prices, panel_df=panel, benchmark_df=bench)
    assert engine.last_processed_session == 10

    # Simulate crash while writing matured outcomes for session 11:
    # Manually append a mock matured outcome record with processing_session = 11, signal_session = 1
    matured_file = temp_eval_dir / "matured_technical_outcomes.csv"
    mock_row = pd.DataFrame([{
        "model_version": "v1.0.0-frozen",
        "outcome_type": "technical",
        "transaction_id": "tx_s11",
        "processing_session": 11,
        "creation_session": 1,
        "signal_session": 1,
        "entry_session": 2,
        "execution_session": 2,
        "maturity_session": 11,
        "session": 1,
        "symbol": "AAA",
        "evaluation_mode": "HISTORICAL_REPLAY",
        "is_prospective": False,
        "wall_clock_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "technical_prob": 0.65,
        "decision_threshold": 0.50,
        "threshold": 0.50,
        "signal_flag": 1,
        "stock_open_price": 100.0,
        "stock_close_price": 105.0,
        "gross_stock_return_pct": 5.0,
        "cost_deduction_pct": 0.50,
        "net_stock_return_pct": 4.5,
        "target_hurdle_pct": 2.0,
        "entry_margin_pct": 2.0,
        "realized_hurdle_label": 1,
        "benchmark_forward_return_pct": 1.0,
        "benchmark_relative_excess_return_pct": 3.5,
        "is_valid_price_window": True,
        "is_delayed_resolution": False,
    }])
    mock_row.to_csv(matured_file, index=False)

    # State file still has last_processed_session = 10 (uncommitted transaction 11)
    # Restart engine
    restarted_engine = PaperEvaluationEngine(eval_dir=temp_eval_dir, holding_period=10)
    assert restarted_engine.last_processed_session == 10

    # Verify mock uncommitted matured outcome was rolled back
    assert not matured_file.exists() or not (pd.read_csv(matured_file)["processing_session"] == 11).any(), "Uncommitted session 11 outcome must be rolled back"

    # Now execute session 11 normally
    restarted_engine.process_session(session=11, prices_df=prices, panel_df=panel, benchmark_df=bench)
    assert restarted_engine.last_processed_session == 11

    df_mat_clean = pd.read_csv(matured_file)
    assert not df_mat_clean.empty
    assert (df_mat_clean["processing_session"] == 11).all()


def test_crash_during_first_processed_session(temp_eval_dir: Path):
    """Crash during the very first session rolls back partial writes and resets cleanly."""
    panel, prices, bench = create_synthetic_market_data(num_sessions=3)

    # In a fresh directory (last_processed_session is None), inject mock records with processing_session = 1
    fund_csv = temp_eval_dir / "signals_fundamental.csv"
    mock_fund = pd.DataFrame([{
        "transaction_id": "tx_s1",
        "processing_session": 1,
        "signal_session": 1,
        "session": 1,
        "symbol": "AAA",
        "fundamental_score": 0.8,
        "shortlist_flag": 1,
    }])
    mock_fund.to_csv(fund_csv, index=False)

    # Start engine: last_processed_session is None
    engine = PaperEvaluationEngine(eval_dir=temp_eval_dir)
    assert engine.last_processed_session is None

    # Verify recovery wiped uncommitted records cleanly
    assert not fund_csv.exists() or len(pd.read_csv(fund_csv)) == 0, "Uncommitted first session records must be wiped"

    # Now execute session 1 normally
    engine.process_session(session=1, prices_df=prices, panel_df=panel, benchmark_df=bench)
    assert engine.last_processed_session == 1

    df_final = pd.read_csv(fund_csv)
    assert len(df_final) > 0
    assert (df_final["processing_session"] == 1).all()


# ==============================================================================
# 3. DISCRIMINATING TECHNICAL GROUND TRUTH TEST
# ==============================================================================

def test_technical_ground_truth_discriminating_excess_return(temp_eval_dir: Path):
    """Discriminating Test: Stock net return = 3%, Benchmark return = 4%, Hurdle = 2%.

    The technical label MUST be positive (1), because net_stock_return (3%) > hurdle (2%),
    even though benchmark-relative excess return is negative (3% - 4% = -1%).
    """
    symbols = ["AAA"]
    num_sessions = 15
    panel, prices, bench = create_synthetic_market_data(num_sessions=num_sessions, symbols=symbols)

    # Tailor prices for symbol AAA:
    # At session 1 (signal session): entry open at session 2 = 100.0
    # At session 11 (maturity session = 1 + 10): close = 103.50
    # Cost = 0.50%, so gross return = 3.50%, net return = 3.00%
    prices.loc[(prices["session"] == 2) & (prices["symbol"] == "AAA"), "open"] = 100.0
    prices.loc[(prices["session"] == 2) & (prices["symbol"] == "AAA"), "adjusted_open"] = 100.0
    prices.loc[(prices["session"] == 11) & (prices["symbol"] == "AAA"), "close"] = 103.50
    prices.loc[(prices["session"] == 11) & (prices["symbol"] == "AAA"), "adjusted_close"] = 103.50

    # Ensure all 11 bars (session 1 through 11) have price_valid = True, positive open and close
    prices.loc[prices["session"].between(1, 11), "price_valid"] = True

    # Tailor benchmark: session 2 open = 100.0, session 11 close = 104.0 (benchmark return = 4.00%)
    bench.loc[bench["session"] == 2, "adjusted_close"] = 100.0
    bench.loc[bench["session"] == 2, "benchmark_close"] = 100.0
    bench.loc[bench["session"] == 11, "adjusted_close"] = 104.0
    bench.loc[bench["session"] == 11, "benchmark_close"] = 104.0

    engine = PaperEvaluationEngine(eval_dir=temp_eval_dir, holding_period=10, cost_rate=0.005)

    # Step through session 1 to 11
    for s in range(1, 12):
        engine.process_session(session=s, prices_df=prices, panel_df=panel, benchmark_df=bench)

    assert engine.last_processed_session == 11

    matured_file = temp_eval_dir / "matured_technical_outcomes.csv"
    assert matured_file.exists()
    df_mat = pd.read_csv(matured_file)
    s1_row = df_mat[(df_mat["signal_session"] == 1) & (df_mat["symbol"] == "AAA")]
    assert not s1_row.empty
    row = s1_row.iloc[0]

    # Verify exact calculations
    # Gross stock return = (103.5 / 100.0 - 1) * 100 = 3.5%
    # Net stock return = 3.5% - 0.5% cost = 3.0%
    assert abs(row["net_stock_return_pct"] - 3.0) < 1e-4

    # Benchmark return = (104.0 / 100.0 - 1) * 100 = 4.0%
    assert abs(row["benchmark_forward_return_pct"] - 4.0) < 1e-4

    # Diagnostic excess return = 3.0% - 4.0% = -1.0% (NEGATIVE)
    assert abs(row["benchmark_relative_excess_return_pct"] - (-1.0)) < 1e-4

    # Ground truth label MUST BE POSITIVE (1) because 3.0% > 2.0% hurdle!
    assert row["realized_hurdle_label"] == 1, (
        f"Ground truth label must be 1 (positive) because net return 3.0% > 2.0% hurdle. "
        f"Benchmark return must NOT be subtracted from the label."
    )
    assert row["is_valid_price_window"] == True


# ==============================================================================
# 4. RISK CONTROLS & DRAWDOWN CIRCUIT BREAKER TESTS
# ==============================================================================

def test_drawdown_circuit_breaker_and_administrative_resume(temp_eval_dir: Path):
    panel, prices, bench = create_synthetic_market_data(num_sessions=15)
    engine = PaperEvaluationEngine(eval_dir=temp_eval_dir, max_position_weight=1.0, max_drawdown_limit_pct=25.0)

    for s in range(1, 6):
        engine.process_session(session=s, prices_df=prices, panel_df=panel, benchmark_df=bench)

    assert not engine.circuit_breaker["Policy_A"]["active"]

    prices_crash = prices.copy()
    prices_crash.loc[prices_crash["session"] >= 6, "close"] *= 0.30
    prices_crash.loc[prices_crash["session"] >= 6, "adjusted_close"] *= 0.30

    engine.process_session(session=6, prices_df=prices_crash, panel_df=panel, benchmark_df=bench)

    assert engine.circuit_breaker["Policy_A"]["active"], "Circuit breaker must trigger on >25% drawdown"
    assert engine.circuit_breaker["Policy_A"]["triggered_session"] == 6

    engine.process_session(session=7, prices_df=prices_crash, panel_df=panel, benchmark_df=bench)
    rej_file = temp_eval_dir / "rejected_orders.csv"
    if rej_file.exists():
        df_rej = pd.read_csv(rej_file)
        assert (df_rej["reason"] == "CIRCUIT_BREAKER_HALT").any()

    engine_restarted = PaperEvaluationEngine(eval_dir=temp_eval_dir, max_position_weight=1.0, max_drawdown_limit_pct=25.0)
    assert engine_restarted.circuit_breaker["Policy_A"]["active"]

    with pytest.raises(ValueError, match="at least 10 characters"):
        engine_restarted.resume_after_circuit_breaker(policy="Policy_A", audit_rationale="short")

    engine_restarted.resume_after_circuit_breaker(
        policy="Policy_A",
        audit_rationale="Formal audit conducted by risk committee; volatility regime normalized."
    )
    assert not engine_restarted.circuit_breaker["Policy_A"]["active"]


# ==============================================================================
# 5. UNRESOLVED MATURED OUTCOMES QUEUE TEST
# ==============================================================================

def test_unresolved_matured_outcomes_queue(temp_eval_dir: Path):
    panel, prices, bench = create_synthetic_market_data(num_sessions=15)
    engine = PaperEvaluationEngine(eval_dir=temp_eval_dir, holding_period=10)

    for s in range(1, 11):
        engine.process_session(session=s, prices_df=prices, panel_df=panel, benchmark_df=bench)

    prices_halt = prices.copy()
    prices_halt.loc[(prices_halt["session"] == 11) & (prices_halt["symbol"] == "AAA"), "price_valid"] = False

    engine.process_session(session=11, prices_df=prices_halt, panel_df=panel, benchmark_df=bench)

    unresolved = [u for u in engine.unresolved_matured_outcomes if u["symbol"] == "AAA"]
    assert len(unresolved) > 0, "Suspended stock outcome must be queued in unresolved_matured_outcomes"
    assert unresolved[0]["signal_session"] == 1


# ==============================================================================
# 6. END-TO-END 128-SESSION ACCEPTANCE FIXTURE (BOTH HORIZONS EXERCISED)
# ==============================================================================

def test_synthetic_128_session_fixture_both_horizons_exercised(temp_eval_dir: Path):
    """Executes 128 sessions so that both Technical (T+10) and Fundamental (T+126) horizons mature."""
    num_sessions = 128
    panel, prices, bench = create_synthetic_market_data(num_sessions=num_sessions)

    engine = PaperEvaluationEngine(
        eval_dir=temp_eval_dir,
        holding_period=10,
        evaluation_mode="PROSPECTIVE_PAPER",
    )

    for s in range(1, num_sessions + 1):
        engine.process_session(
            session=s,
            prices_df=prices,
            panel_df=panel,
            benchmark_df=bench,
        )

    # A. Verify Technical Outcomes (T+10)
    tech_outcomes_file = temp_eval_dir / "matured_technical_outcomes.csv"
    assert tech_outcomes_file.exists()
    df_tech_out = pd.read_csv(tech_outcomes_file)
    assert not df_tech_out.empty

    s1_tech = df_tech_out[df_tech_out["signal_session"] == 1]
    assert not s1_tech.empty
    assert (s1_tech["maturity_session"] == 11).all()
    assert (s1_tech["processing_session"] == 11).all()
    assert (s1_tech["decision_threshold"] == 0.50).all()
    assert (s1_tech["target_hurdle_pct"] == 2.0).all()
    assert (s1_tech["evaluation_mode"] == "PROSPECTIVE_PAPER").all()
    assert (s1_tech["is_prospective"] == True).all()

    # B. Verify Fundamental Outcomes (T+126)
    fund_outcomes_file = temp_eval_dir / "matured_fundamental_outcomes.csv"
    assert fund_outcomes_file.exists()
    df_fund_out = pd.read_csv(fund_outcomes_file)
    assert not df_fund_out.empty

    s1_fund = df_fund_out[df_fund_out["signal_session"] == 1]
    assert not s1_fund.empty
    assert (s1_fund["maturity_session"] == 127).all()
    assert (s1_fund["processing_session"] == 127).all()

    for _, row in s1_fund.iterrows():
        p1 = row["stock_start_adj_close"]
        p127 = row["stock_end_adj_close"]
        b1 = row["benchmark_start_adj_close"]
        b127 = row["benchmark_end_adj_close"]
        expected_excess = 100.0 * (p127 / p1 - b127 / b1)
        assert abs(row["fundamental_training_target_excess_return_pct"] - expected_excess) < 1e-4
        assert "executable_open_to_close_return_pct" in row
        assert pd.notna(row["executable_open_to_close_return_pct"])
        assert row["is_valid_target_window"] == True


# ==============================================================================
# 7. FIXED-HORIZON INTEGRITY & DELAYED RESOLUTION AUDIT TESTS
# ==============================================================================

def test_delayed_resolution_t15_quote_cannot_become_t10_label(temp_eval_dir: Path):
    """Prove that a t+15 quote CANNOT become a t+10 label when t+10 quote is missing."""
    panel, prices, bench = create_synthetic_market_data(num_sessions=16)
    # Invalidate quote for session 11 (t+10 for signal at session 1)
    prices_missing_t10 = prices.copy()
    prices_missing_t10.loc[(prices_missing_t10["session"] == 11) & (prices_missing_t10["symbol"] == "AAA"), "price_valid"] = False

    # Stock trades at a dramatically different price at session 15 (e.g. 500.0)
    prices_missing_t10.loc[(prices_missing_t10["session"] == 15) & (prices_missing_t10["symbol"] == "AAA"), ["open", "close", "adjusted_open", "adjusted_close"]] = 500.0

    engine = PaperEvaluationEngine(eval_dir=temp_eval_dir, holding_period=10)
    for s in range(1, 16):
        engine.process_session(session=s, prices_df=prices_missing_t10, panel_df=panel, benchmark_df=bench)

    tech_outcomes_file = temp_eval_dir / "matured_technical_outcomes.csv"
    if tech_outcomes_file.exists():
        df_out = pd.read_csv(tech_outcomes_file)
        s1_out = df_out[(df_out["signal_session"] == 1) & (df_out["symbol"] == "AAA")]
        # Must NOT have resolved using session 15's 500.0 price
        if not s1_out.empty:
            assert (s1_out["stock_close_price"] != 500.0).all(), "Today's (t+15) quote must never be substituted for t+10 label"

    # Session 1 for AAA must remain in unresolved_matured_outcomes
    unresolved_aaa = [u for u in engine.unresolved_matured_outcomes if u["symbol"] == "AAA" and u["signal_session"] == 1]
    assert len(unresolved_aaa) > 0, "Signal at t=1 must remain unresolved when t=11 quote is invalid"


def test_late_arriving_historical_t10_quote_resolves_correct_outcome(temp_eval_dir: Path):
    """Prove that a late-arriving historical t+10 quote resolves the correct outcome."""
    panel, prices, bench = create_synthetic_market_data(num_sessions=16)

    # During sessions 1 to 14, session 11 price for AAA is missing
    prices_phase1 = prices.copy()
    prices_phase1.loc[(prices_phase1["session"] == 11) & (prices_phase1["symbol"] == "AAA"), "price_valid"] = False

    engine = PaperEvaluationEngine(eval_dir=temp_eval_dir, holding_period=10)
    for s in range(1, 15):
        engine.process_session(session=s, prices_df=prices_phase1, panel_df=panel, benchmark_df=bench)

    # Verify AAA is queued as unresolved after session 14
    unresolved = [u for u in engine.unresolved_matured_outcomes if u["symbol"] == "AAA" and u["signal_session"] == 1]
    assert len(unresolved) == 1

    # At session 15, backfilled historical data arrives with exact session 11 quote = 110.0
    # and session 15 quote = 200.0
    prices_phase2 = prices.copy()
    prices_phase2.loc[(prices_phase2["session"] == 11) & (prices_phase2["symbol"] == "AAA"), "price_valid"] = True
    prices_phase2.loc[(prices_phase2["session"] == 11) & (prices_phase2["symbol"] == "AAA"), ["close", "adjusted_close"]] = 110.0
    prices_phase2.loc[(prices_phase2["session"] == 15) & (prices_phase2["symbol"] == "AAA"), ["close", "adjusted_close"]] = 200.0

    engine.process_session(session=15, prices_df=prices_phase2, panel_df=panel, benchmark_df=bench)

    # Outcome must now be resolved
    tech_outcomes_file = temp_eval_dir / "matured_technical_outcomes.csv"
    assert tech_outcomes_file.exists()
    df_out = pd.read_csv(tech_outcomes_file)
    s1_aaa = df_out[(df_out["signal_session"] == 1) & (df_out["symbol"] == "AAA")]
    assert len(s1_aaa) == 1
    row = s1_aaa.iloc[0]
    # Close price must be 110.0 (the historical session 11 quote), NEVER 200.0!
    assert row["stock_close_price"] == pytest.approx(110.0)
    assert row["maturity_session"] == 11
    assert row["processing_session"] == 15
    assert row["is_delayed_resolution"] == True
    assert row["outcome_status"] == "RESOLVED_DELAYED"

    # Must be dequeued from unresolved_matured_outcomes
    still_unresolved = [u for u in engine.unresolved_matured_outcomes if u["symbol"] == "AAA" and u["signal_session"] == 1]
    assert len(still_unresolved) == 0


def test_two_older_signals_one_stock_resolve_same_transaction(temp_eval_dir: Path):
    """Prove two older signals for one stock can resolve in one transaction without either being dropped."""
    panel, prices, bench = create_synthetic_market_data(num_sessions=16)

    # Invalidate session 11 and session 12 quotes for AAA initially
    prices_init = prices.copy()
    prices_init.loc[(prices_init["session"].isin([11, 12])) & (prices_init["symbol"] == "AAA"), "price_valid"] = False

    engine = PaperEvaluationEngine(eval_dir=temp_eval_dir, holding_period=10)
    for s in range(1, 15):
        engine.process_session(session=s, prices_df=prices_init, panel_df=panel, benchmark_df=bench)

    # Both signal 1 and signal 2 for AAA are unresolved
    unresolved_aaa = [u for u in engine.unresolved_matured_outcomes if u["symbol"] == "AAA"]
    assert len(unresolved_aaa) == 2
    sig_sessions = {u["signal_session"] for u in unresolved_aaa}
    assert sig_sessions == {1, 2}

    # At session 15, late historical data for sessions 11 and 12 arrives
    prices_resolved = prices.copy()
    prices_resolved.loc[(prices_resolved["session"].isin([11, 12])) & (prices_resolved["symbol"] == "AAA"), "price_valid"] = True

    engine.process_session(session=15, prices_df=prices_resolved, panel_df=panel, benchmark_df=bench)

    tech_outcomes_file = temp_eval_dir / "matured_technical_outcomes.csv"
    assert tech_outcomes_file.exists()
    df_out = pd.read_csv(tech_outcomes_file)
    aaa_resolved = df_out[(df_out["symbol"] == "AAA") & (df_out["processing_session"] == 15)]

    # CRITICAL: Both older delayed signals must be recorded! Neither dropped!
    delayed_aaa = aaa_resolved[aaa_resolved["is_delayed_resolution"] == True]
    assert len(delayed_aaa) == 2
    resolved_sig_sessions = set(delayed_aaa["signal_session"].tolist())
    assert resolved_sig_sessions == {1, 2}
    assert (delayed_aaa["outcome_type"] == "technical").all()


def test_original_probabilities_and_flags_survive_delayed_resolution(temp_eval_dir: Path):
    """Prove that original probabilities and flags survive delayed resolution intact."""
    panel, prices, bench = create_synthetic_market_data(num_sessions=16)

    # Invalidate session 11 quote for AAA
    prices_p1 = prices.copy()
    prices_p1.loc[(prices_p1["session"] == 11) & (prices_p1["symbol"] == "AAA"), "price_valid"] = False

    engine = PaperEvaluationEngine(eval_dir=temp_eval_dir, holding_period=10)
    for s in range(1, 15):
        engine.process_session(session=s, prices_df=prices_p1, panel_df=panel, benchmark_df=bench)

    # Check original prediction logged in signals_technical.csv
    df_signals = pd.read_csv(temp_eval_dir / "signals_technical.csv")
    s1_sig = df_signals[(df_signals["signal_session"] == 1) & (df_signals["symbol"] == "AAA")].iloc[0]
    expected_prob = float(s1_sig["technical_prob"])
    expected_flag = int(s1_sig["signal_flag"])
    expected_thresh = float(s1_sig["decision_threshold"])

    # Resolve at session 15
    prices_p2 = prices.copy()
    prices_p2.loc[(prices_p2["session"] == 11) & (prices_p2["symbol"] == "AAA"), "price_valid"] = True
    engine.process_session(session=15, prices_df=prices_p2, panel_df=panel, benchmark_df=bench)

    df_out = pd.read_csv(temp_eval_dir / "matured_technical_outcomes.csv")
    s1_out = df_out[(df_out["signal_session"] == 1) & (df_out["symbol"] == "AAA")].iloc[0]

    # Verify original prediction identity is preserved exactly
    assert s1_out["technical_prob"] == pytest.approx(expected_prob)
    assert int(s1_out["signal_flag"]) == expected_flag
    assert s1_out["decision_threshold"] == pytest.approx(expected_thresh)
    assert s1_out["model_version"] == "v1.0.0-frozen"


def test_restarting_does_not_duplicate_resolved_outcomes(temp_eval_dir: Path):
    """Prove that restarting the engine does not duplicate resolved outcomes."""
    panel, prices, bench = create_synthetic_market_data(num_sessions=16)

    engine = PaperEvaluationEngine(eval_dir=temp_eval_dir, holding_period=10)
    for s in range(1, 16):
        engine.process_session(session=s, prices_df=prices, panel_df=panel, benchmark_df=bench)

    tech_outcomes_file = temp_eval_dir / "matured_technical_outcomes.csv"
    assert tech_outcomes_file.exists()
    df_before = pd.read_csv(tech_outcomes_file)
    count_before = len(df_before)
    assert count_before > 0

    # Normal restart
    restarted_engine = PaperEvaluationEngine(eval_dir=temp_eval_dir, holding_period=10)
    assert restarted_engine.last_processed_session == 15

    # Process session 16
    restarted_engine.process_session(session=16, prices_df=prices, panel_df=panel, benchmark_df=bench)

    df_after = pd.read_csv(tech_outcomes_file)
    # Filter for session <= 15 outcomes: must be identical count
    s15_outcomes = df_after[df_after["processing_session"] <= 15]
    assert len(s15_outcomes) == count_before

    # Verify composite primary key uniqueness across entire file
    pk_cols = ["model_version", "signal_session", "symbol", "outcome_type"]
    assert not df_after.duplicated(subset=pk_cols).any(), "No duplicate outcomes permitted"
