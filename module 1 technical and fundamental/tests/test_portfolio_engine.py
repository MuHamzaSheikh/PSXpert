"""Comprehensive unit tests for the institutional chronological portfolio engine.

Each test is hand-calculable and verifies specific accounting rules:
1. Chronological execution: morning buys cannot use afternoon sales proceeds; cash never negative.
2. Removal of fabricated execution prices: suspended stocks are never liquidated at entry price.
3. Valuation estimates vs executable prices: stale valuations tracked; unresolved positions reported.
4. Target alignment: signal at t -> entry at t+1 open -> exit at t+10 close (holding period: 10 sessions).
5. Fundamental ranking preservation: scarce slots allocated by fundamental score descending, not alphabetically.
6. Order-level ledger and boundary turnover: boundary purchases included in turnover.
7. Causal execution eligibility: retrospective label quarantine does not block live causal orders.
"""
import numpy as np
import pandas as pd
import pytest

from m1.portfolio_engine import (
    OrderRecord,
    PortfolioPosition,
    evaluate_chronological_performance,
    run_chronological_portfolio_backtest,
)


def test_chronological_execution_and_cash_integrity():
    """Verify that morning opening purchases can only use cash available from previous close,
    and afternoon closing sales cannot fund earlier morning purchases."""
    # 3 sessions: 1, 2, 3
    sessions = [1, 2, 3]

    # Prices:
    # Stock A: enters on session 2 open, exits on session 2 close (1 session hold for test)
    # Stock B: enters on session 2 open
    # Initial capital: 100,000 PKR. Max weight: 50% (50,000 PKR per stock)
    grid = [
        {"session": 1, "symbol": "A", "open": 100.0, "close": 100.0, "volume": 1000},
        {"session": 1, "symbol": "B", "open": 50.0, "close": 50.0, "volume": 1000},
        {"session": 2, "symbol": "A", "open": 100.0, "close": 110.0, "volume": 1000},
        {"session": 2, "symbol": "B", "open": 50.0, "close": 50.0, "volume": 1000},
        {"session": 3, "symbol": "A", "open": 110.0, "close": 110.0, "volume": 1000},
        {"session": 3, "symbol": "B", "open": 50.0, "close": 50.0, "volume": 1000},
    ]
    prices_df = pd.DataFrame(grid)

    # Signal at session 1 close for Stock A and Stock B
    candidate_shortlists = {
        1: [("A", 10.0), ("B", 5.0)]
    }

    res = run_chronological_portfolio_backtest(
        sessions=sessions,
        prices_df=prices_df,
        candidate_shortlists=candidate_shortlists,
        technical_signals={},
        initial_capital=100_000.0,
        cost_rate=0.005,  # 0.25% buy, 0.25% sell
        max_position_weight=0.50,
        holding_period=1,  # entered session 2 open, scheduled exit session 1 + 1 = 2 close
        is_filtered=False,
    )

    ledger = res["order_ledger"]
    daily = res["daily_equity"]

    # On session 2 open:
    # Available cash was strictly 100,000 PKR.
    # Stock A and Stock B each allocated min(100k/2, 100k*0.5) = 50,000 PKR.
    # Cash after morning buys: 100,000 - 50,000 - 50,000 = 0 PKR.
    buy_orders = ledger[ledger["side"] == "BUY"]
    assert len(buy_orders) == 2
    assert buy_orders.iloc[0]["timing"] == "OPEN"
    assert buy_orders.iloc[0]["session"] == 2
    assert buy_orders.iloc[1]["timing"] == "OPEN"
    assert buy_orders.iloc[1]["session"] == 2

    # Check cash balance after both buys was ~0 (never negative)
    cash_after_buys = buy_orders.iloc[1]["cash_balance_after"]
    assert cash_after_buys >= 0.0
    assert cash_after_buys < 1.0

    # On session 2 close:
    # Stock A and B exit at session 2 close and generate sale proceeds.
    sell_orders = ledger[ledger["side"] == "SELL"]
    assert len(sell_orders) == 2
    assert sell_orders.iloc[0]["timing"] == "CLOSE"
    assert sell_orders.iloc[0]["session"] == 2

    # Cash at session 2 close now has proceeds from sales
    cash_eod_2 = daily.loc[daily["session"] == 2, "cash"].iloc[0]
    assert cash_eod_2 > 100_000.0  # Stock A gained 10%

    # Crucially, morning buys on session 2 did NOT have access to cash_eod_2!
    for _, row in buy_orders.iterrows():
        assert row["cash_balance_after"] < 100_000.0


def test_removal_of_fabricated_prices_and_delayed_exit():
    """Verify simulator never fabricates execution at entry price when exit quote is missing,
    and properly delays exit until an executable quote exists."""
    sessions = [1, 2, 3, 4, 5]
    # Stock X enters at session 2 open (100 PKR).
    # Holding period: 2 sessions (scheduled exit at session 1 + 2 = 3 close).
    # On session 3 close: Stock X is suspended / volume is 0!
    # On session 4 close: Stock X resumes trading at 125 PKR with volume 5000.
    grid = [
        {"session": 1, "symbol": "X", "open": 100.0, "close": 100.0, "volume": 1000},
        {"session": 2, "symbol": "X", "open": 100.0, "close": 105.0, "volume": 1000},
        {"session": 3, "symbol": "X", "open": 105.0, "close": np.nan, "volume": 0},      # Suspended on exit date!
        {"session": 4, "symbol": "X", "open": 120.0, "close": 125.0, "volume": 5000},   # Resumed trading
        {"session": 5, "symbol": "X", "open": 125.0, "close": 125.0, "volume": 1000},
    ]
    prices_df = pd.DataFrame(grid)
    candidate_shortlists = {1: [("X", 10.0)]}

    res = run_chronological_portfolio_backtest(
        sessions=sessions,
        prices_df=prices_df,
        candidate_shortlists=candidate_shortlists,
        technical_signals={},
        initial_capital=100_000.0,
        cost_rate=0.005,
        max_position_weight=1.0,
        holding_period=2,
        is_filtered=False,
    )

    ledger = res["order_ledger"]
    trades = res["completed_trades"]

    # Verify NO sale executed on session 3 (scheduled exit)
    sells_session_3 = ledger[(ledger["side"] == "SELL") & (ledger["session"] == 3)]
    assert len(sells_session_3) == 0

    # Verify sale executed on session 4 close at 125 PKR under delayed exit policy
    sells_session_4 = ledger[(ledger["side"] == "SELL") & (ledger["session"] == 4)]
    assert len(sells_session_4) == 1
    assert sells_session_4.iloc[0]["price"] == 125.0
    assert sells_session_4.iloc[0]["reason"] == "SUSPENSION_DELAYED_EXIT"

    # Trade record confirms delay and actual 125 PKR price (NOT entry price 100 PKR!)
    assert len(trades) == 1
    trade = trades[0]
    assert trade["exit_session"] == 4
    assert trade["scheduled_exit_session"] == 3
    assert trade["was_delayed"] is True
    assert trade["exit_price"] == 125.0
    # Gross return was +25%, net cash-flow return ~24.38% after 0.25% buy + 0.25% sell fees
    assert trade["net_return_pct"] == pytest.approx(24.38, abs=0.05)


def test_stale_valuation_vs_executable_price_and_unresolved():
    """Verify that suspended stocks use stale valuation on balance sheet and are reported
    as unresolved positions if window ends before resumption."""
    sessions = [1, 2, 3]
    # Stock Y enters on session 2 open at 100 PKR, closes session 2 at 110 PKR.
    # On session 3, Stock Y is suspended (no price, volume 0). Backtest ends at session 3.
    grid = [
        {"session": 1, "symbol": "Y", "open": 100.0, "close": 100.0, "volume": 1000},
        {"session": 2, "symbol": "Y", "open": 100.0, "close": 110.0, "volume": 1000},
        {"session": 3, "symbol": "Y", "open": np.nan, "close": np.nan, "volume": 0},
    ]
    prices_df = pd.DataFrame(grid)
    candidate_shortlists = {1: [("Y", 10.0)]}

    res = run_chronological_portfolio_backtest(
        sessions=sessions,
        prices_df=prices_df,
        candidate_shortlists=candidate_shortlists,
        technical_signals={},
        initial_capital=100_000.0,
        holding_period=5,  # Scheduled exit beyond window
        is_filtered=False,
    )

    daily = res["daily_equity"]
    unresolved = res["unresolved_positions"]
    trades = res["completed_trades"]

    # Zero completed trades
    assert len(trades) == 0

    # 1 unresolved position at boundary
    assert len(unresolved) == 1
    assert unresolved[0]["symbol"] == "Y"
    # Valuation marked to last known close (110 PKR)
    assert unresolved[0]["last_known_close"] == 110.0
    assert unresolved[0]["stale_days"] == 1

    # Session 3 daily equity recorded 1 stale valuation
    assert daily.loc[daily["session"] == 3, "stale_valuations_count"].iloc[0] == 1


def test_exact_target_alignment():
    """Prove exact target alignment: signal at t -> entry at t+1 open -> exit at t+10 close."""
    # 15 sessions: 100 through 114
    sessions = list(range(100, 115))
    grid = []
    for s in sessions:
        grid.append({"session": s, "symbol": "TARGET_SYM", "open": 100.0, "close": 105.0, "volume": 1000})
    prices_df = pd.DataFrame(grid)

    # Signal generated at session t = 100 close
    candidate_shortlists = {100: [("TARGET_SYM", 25.0)]}

    res = run_chronological_portfolio_backtest(
        sessions=sessions,
        prices_df=prices_df,
        candidate_shortlists=candidate_shortlists,
        technical_signals={},
        initial_capital=100_000.0,
        holding_period=10,
        is_filtered=False,
    )

    ledger = res["order_ledger"]
    trades = res["completed_trades"]

    # Entry must occur strictly at session t+1 = 101 OPEN
    buy_order = ledger[ledger["side"] == "BUY"].iloc[0]
    assert buy_order["session"] == 101
    assert buy_order["timing"] == "OPEN"

    # Exit must occur strictly at session t+10 = 110 CLOSE
    sell_order = ledger[ledger["side"] == "SELL"].iloc[0]
    assert sell_order["session"] == 110
    assert sell_order["timing"] == "CLOSE"

    # Trade history duration: exactly 10 sessions (Sessions 101 to 110 inclusive)
    assert len(trades) == 1
    t = trades[0]
    assert t["entry_session"] == 101
    assert t["exit_session"] == 110
    assert t["holding_duration_sessions"] == 10


def test_fundamental_rank_preservation_not_alphabetical():
    """Verify that when slots are scarce, candidates are selected by fundamental score descending,
    NEVER in alphabetical order."""
    sessions = [1, 2, 3]
    grid = [
        {"session": 1, "symbol": "AAA", "open": 10.0, "close": 10.0, "volume": 1000},
        {"session": 1, "symbol": "MMM", "open": 20.0, "close": 20.0, "volume": 1000},
        {"session": 1, "symbol": "ZZZ", "open": 30.0, "close": 30.0, "volume": 1000},
        {"session": 2, "symbol": "AAA", "open": 10.0, "close": 10.0, "volume": 1000},
        {"session": 2, "symbol": "MMM", "open": 20.0, "close": 20.0, "volume": 1000},
        {"session": 2, "symbol": "ZZZ", "open": 30.0, "close": 30.0, "volume": 1000},
        {"session": 3, "symbol": "AAA", "open": 10.0, "close": 10.0, "volume": 1000},
        {"session": 3, "symbol": "MMM", "open": 20.0, "close": 20.0, "volume": 1000},
        {"session": 3, "symbol": "ZZZ", "open": 30.0, "close": 30.0, "volume": 1000},
    ]
    prices_df = pd.DataFrame(grid)

    # 3 candidates:
    # "ZZZ" has highest score (99.0)
    # "MMM" has medium score (50.0)
    # "AAA" has lowest score (10.0)
    # Alphabetical order would pick "AAA".
    # Fundamental ranking MUST pick "ZZZ".
    candidate_shortlists = {
        1: [("AAA", 10.0), ("ZZZ", 99.0), ("MMM", 50.0)]
    }

    # Set max_position_weight = 1.0 (only 1 slot available!)
    res = run_chronological_portfolio_backtest(
        sessions=sessions,
        prices_df=prices_df,
        candidate_shortlists=candidate_shortlists,
        technical_signals={},
        initial_capital=100_000.0,
        max_position_weight=1.0,
        holding_period=2,
        is_filtered=False,
    )

    ledger = res["order_ledger"]
    buys = ledger[ledger["side"] == "BUY"]
    assert len(buys) == 1

    # Assert symbol bought was ZZZ (highest fundamental rank)
    assert buys.iloc[0]["symbol"] == "ZZZ"


def test_order_ledger_and_boundary_turnover():
    """Verify that order ledger tracks every transaction and turnover strictly includes
    purchases of positions still open at the assessment boundary."""
    sessions = [1, 2, 3]
    grid = [
        {"session": 1, "symbol": "S1", "open": 100.0, "close": 100.0, "volume": 1000},
        {"session": 1, "symbol": "S2", "open": 50.0, "close": 50.0, "volume": 1000},
        {"session": 2, "symbol": "S1", "open": 100.0, "close": 100.0, "volume": 1000},
        {"session": 2, "symbol": "S2", "open": 50.0, "close": 50.0, "volume": 1000},
        {"session": 3, "symbol": "S1", "open": 100.0, "close": 100.0, "volume": 1000},
        {"session": 3, "symbol": "S2", "open": 50.0, "close": 50.0, "volume": 1000},
    ]
    prices_df = pd.DataFrame(grid)

    # Day 1 close: S1 generates signal -> enters Day 2 open, exits Day 3 close (holding period = 2)
    # Day 2 close: S2 generates signal -> enters Day 3 open, scheduled exit Day 4 (beyond boundary, remains OPEN!)
    candidate_shortlists = {
        1: [("S1", 10.0)],
        2: [("S2", 20.0)],
    }

    res = run_chronological_portfolio_backtest(
        sessions=sessions,
        prices_df=prices_df,
        candidate_shortlists=candidate_shortlists,
        technical_signals={},
        initial_capital=100_000.0,
        cost_rate=0.005,
        max_position_weight=0.50,
        holding_period=2,
        is_filtered=False,
    )

    ledger = res["order_ledger"]
    perf = res["performance_metrics"]

    # 3 total orders:
    # Order 1: BUY S1 on Day 2 open (~50,000 PKR)
    # Order 2: BUY S2 on Day 3 open (~50,000 PKR, remains OPEN at boundary!)
    # Order 3: SELL S1 on Day 3 close (~50,000 PKR)
    assert len(ledger) == 3
    buy_orders = ledger[ledger["side"] == "BUY"]
    assert len(buy_orders) == 2
    sell_orders = ledger[ledger["side"] == "SELL"]
    assert len(sell_orders) == 1
    assert sell_orders.iloc[0]["symbol"] == "S1"

    # Total traded value must sum all 3 orders (~150,000 PKR)
    assert perf["total_traded_value_pkr"] == pytest.approx(150_000.0, abs=1000.0)
    assert perf["unresolved_positions_count"] == 1
    assert perf["completed_trades_count"] == 1

    # Turnover includes the Day 3 boundary buy
    expected_turnover = 150_000.0 / (2.0 * 100_000.0)  # ~0.75
    assert perf["turnover"] == pytest.approx(expected_turnover, abs=0.05)


def test_causal_execution_not_blocked_by_retrospective_quarantine():
    """Verify that causal live execution is not blocked by future events or retrospective quarantine."""
    sessions = [1, 2, 3]
    # Suppose a raw prices DataFrame has price_valid column indicating retrospective quarantine at session 3
    # But on session 2, price is observable and volume is positive.
    grid = [
        {"session": 1, "symbol": "C", "open": 50.0, "close": 50.0, "volume": 1000, "price_valid": True},
        {"session": 2, "symbol": "C", "open": 50.0, "close": 52.0, "volume": 1000, "price_valid": False}, # Retrospectively flagged
        {"session": 3, "symbol": "C", "open": 52.0, "close": 52.0, "volume": 1000, "price_valid": False},
    ]
    prices_df = pd.DataFrame(grid)

    candidate_shortlists = {1: [("C", 10.0)]}

    res = run_chronological_portfolio_backtest(
        sessions=sessions,
        prices_df=prices_df,
        candidate_shortlists=candidate_shortlists,
        technical_signals={},
        initial_capital=100_000.0,
        holding_period=1,
        is_filtered=False,
    )

    ledger = res["order_ledger"]
    # Order MUST execute on session 2 open because price (50.0) and volume (1000) are observable
    assert len(ledger[ledger["side"] == "BUY"]) == 1
    assert ledger.iloc[0]["symbol"] == "C"
    assert ledger.iloc[0]["session"] == 2
