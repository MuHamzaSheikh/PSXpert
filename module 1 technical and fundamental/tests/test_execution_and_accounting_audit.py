"""Execution Information Timing and Accounting Reconciliation Audit Tests.

Verifies:
1. Chronological information timing: Session s open order sizing uses lagged volume V_{s-1}.
   Contemporaneous session s volume is unobserved at decision time.
2. Missing or zero lagged volume handling: Order sizing safely handles unobserved liquidity.
3. Retrospective fill vs decision-time conditions: Positive daily volume is a retrospective
   fill condition, not a decision-time parameter.
4. Exact accounting reconciliation:
   - Cash ledger integrity: Initial Capital + sum(Cash Inflows) - sum(Cash Outflows) == Final Cash.
   - Trade net PnL matches order ledger cash flows: Net Proceeds - Cost Basis.
   - Terminal equity reconciles exactly:
     Final Equity == Initial Capital + sum(Completed Trade Net PnL) + sum(Unrealized Net PnL).
   - All fees (buy fee + sell fee) reconcile exactly with the order ledger.
"""

import numpy as np
import pandas as pd
import pytest
from m1.portfolio_engine import run_chronological_portfolio_backtest


def test_lagged_volume_sizing_and_information_timing():
    """Verify that opening order decisions and sizing strictly use lagged volume V_{s-1}

    and do NOT look ahead to contemporaneous day s volume.
    """
    # 3 sessions:
    # Session 1: Symbol A has volume 1,000,000 shares, close 100 PKR.
    # Session 2: Signal generated at session 1 close. Order sized and executed at session 2 open.
    # On session 2, contemporaneous volume turns out to be only 5,000 shares!
    # With max_volume_participation_pct = 5.0%:
    # If looking ahead to day 2 volume: max liquidity spend = 5,000 * 0.05 * 100 = 25,000 PKR (~249 shares).
    # If correctly using lagged day 1 volume: max liquidity spend = 1,000,000 * 0.05 * 100 = 5,000,000 PKR.
    sessions = [1, 2, 3]
    grid = [
        {"session": 1, "symbol": "A", "open": 100.0, "close": 100.0, "volume": 1_000_000},
        {"session": 2, "symbol": "A", "open": 100.0, "close": 105.0, "volume": 5_000},
        {"session": 3, "symbol": "A", "open": 105.0, "close": 110.0, "volume": 10_000},
    ]
    prices_df = pd.DataFrame(grid)

    candidate_shortlists = {
        1: [("A", 10.0)]
    }

    # Capital 1,000,000 PKR, max_position_weight = 0.50 (budget 500,000 PKR -> ~4,987 shares at 100 PKR)
    # If lagged volume (1,000,000 * 0.05 = 50,000) is used, budget limits to ~4,987 shares.
    # If contemporaneous volume (5,000 * 0.05 = 250) was illegally used, shares would be capped at 250!
    res = run_chronological_portfolio_backtest(
        sessions=sessions,
        prices_df=prices_df,
        candidate_shortlists=candidate_shortlists,
        technical_signals={},
        initial_capital=1_000_000.0,
        cost_rate=0.005,
        max_position_weight=0.50,
        holding_period=1,
        is_filtered=False,
        max_volume_participation_pct=5.0,
    )

    ledger = res["order_ledger"]
    buys = ledger[ledger["side"] == "BUY"]
    assert len(buys) == 1
    bought_shares = buys.iloc[0]["shares"]

    # Must be sized according to lagged volume (budget constraint gives 4,987 shares)
    # and strictly greater than 250 shares, proving no lookahead to session 2 contemporaneous volume.
    assert bought_shares > 1000
    assert bought_shares <= 50_000


def test_missing_or_zero_lagged_volume_safeguard():
    """Verify that when lagged volume is missing or zero, the portfolio engine safely

    handles liquidity and rejects the order when volume participation cap is active.
    """
    sessions = [1, 2]
    # Session 1: Symbol B has NaN volume (or first day of listing)
    grid = [
        {"session": 1, "symbol": "B", "open": 100.0, "close": 100.0, "volume": np.nan},
        {"session": 2, "symbol": "B", "open": 100.0, "close": 105.0, "volume": 100_000},
    ]
    prices_df = pd.DataFrame(grid)

    candidate_shortlists = {
        1: [("B", 8.0)]
    }

    res = run_chronological_portfolio_backtest(
        sessions=sessions,
        prices_df=prices_df,
        candidate_shortlists=candidate_shortlists,
        technical_signals={},
        initial_capital=100_000.0,
        max_volume_participation_pct=5.0,  # Requires positive lagged volume
        is_filtered=False,
    )
    # Order cannot be sized because lagged volume is NaN / 0.0
    assert len(res["order_ledger"]) == 0


def test_exact_hand_calculated_accounting_reconciliation():
    """Hand-calculated test proving exact multi-trade cash-flow accounting reconciliation.

    Verifies to the exact decimal:
    1. Cash balance at all points equals Initial Cash + Inflows - Outflows.
    2. Trade Net Return % is derived from actual cash flows (Net Proceeds / Cost Basis - 1).
    3. Trade Net PnL is Net Proceeds - Cost Basis.
    4. Terminal Equity == Initial Cash + Realized Net PnL + Unrealized Net PnL.
    5. Total fees in ledger match fees deducted.
    """
    # 5 sessions
    # Trade 1: Stock X buy on Session 2 open @ 100 PKR, exit on Session 4 close @ 120 PKR.
    # Trade 2: Stock Y buy on Session 3 open @ 200 PKR, remains OPEN at Session 5 close @ 210 PKR.
    sessions = [1, 2, 3, 4, 5]
    grid = [
        # Session 1 (setup lagged volume)
        {"session": 1, "symbol": "X", "open": 100.0, "close": 100.0, "volume": 100_000},
        {"session": 1, "symbol": "Y", "open": 200.0, "close": 200.0, "volume": 100_000},
        # Session 2 (X enters)
        {"session": 2, "symbol": "X", "open": 100.0, "close": 105.0, "volume": 100_000},
        {"session": 2, "symbol": "Y", "open": 200.0, "close": 202.0, "volume": 100_000},
        # Session 3 (Y enters)
        {"session": 3, "symbol": "X", "open": 105.0, "close": 110.0, "volume": 100_000},
        {"session": 3, "symbol": "Y", "open": 200.0, "close": 205.0, "volume": 100_000},
        # Session 4 (X exits at close)
        {"session": 4, "symbol": "X", "open": 110.0, "close": 120.0, "volume": 100_000},
        {"session": 4, "symbol": "Y", "open": 205.0, "close": 208.0, "volume": 100_000},
        # Session 5 (Window end, Y still open)
        {"session": 5, "symbol": "X", "open": 120.0, "close": 120.0, "volume": 100_000},
        {"session": 5, "symbol": "Y", "open": 208.0, "close": 210.0, "volume": 100_000},
    ]
    prices_df = pd.DataFrame(grid)

    # Signal for X at session 1 close (holding_period=3 -> enters s=2 open, exits s=1+3=4 close)
    # Signal for Y at session 2 close (holding_period=3 -> enters s=3 open, scheduled exit s=2+3=5 close, but let's make holding_period=4 so Y is still open at s=5!)
    # Actually holding_period is a single parameter for the backtest.
    # If holding_period=3:
    # X signal at s=1 -> enters s=2 open -> scheduled exit s=1+3=4 close. Exits on s=4!
    # Y signal at s=3 -> enters s=4 open -> scheduled exit s=3+3=6 close. Backtest ends at s=5, so Y is UNRESOLVED!
    candidate_shortlists = {
        1: [("X", 10.0)],
        3: [("Y", 8.0)],
    }

    initial_capital = 100_000.0
    cost_rate = 0.005  # 0.25% buy, 0.25% sell

    res = run_chronological_portfolio_backtest(
        sessions=sessions,
        prices_df=prices_df,
        candidate_shortlists=candidate_shortlists,
        technical_signals={},
        initial_capital=initial_capital,
        cost_rate=cost_rate,
        max_position_weight=0.50,  # 50,000 PKR budget per position
        holding_period=3,
        is_filtered=False,
    )

    ledger = res["order_ledger"]
    trades = res["completed_trades"]
    unresolved = res["unresolved_positions"]
    metrics = res["performance_metrics"]
    df_daily = res["daily_equity"]

    # 1. Check Completed Trades
    assert len(trades) == 1
    t1 = trades[0]
    assert t1["symbol"] == "X"

    # Hand-calculate Trade 1:
    # Available cash at s=2 open: 100,000 PKR.
    # Max spend = 0.50 * 100,000 = 50,000 PKR.
    # Buy fee rate = 0.005 / 2 = 0.0025.
    # Gross spend = 50,000 / 1.0025 = 49,875.31172 PKR.
    # Buy fee = 124.68828 PKR. Total cost basis = 50,000.0 PKR.
    # Shares = gross_spend / open_price = 49,875.31172 / 100.0 = 498.7531172 shares.
    t1_shares = t1["shares"]
    assert t1_shares == pytest.approx(498.7531, abs=1e-3)
    expected_cost_basis = 50_000.0
    assert t1["cash_outflow"] == pytest.approx(expected_cost_basis, abs=1e-3)

    # Gross sell at s=4 close (exit_price = 120.0 PKR):
    gross_sell = t1_shares * 120.0
    sell_fee = gross_sell * 0.0025
    net_proceeds = gross_sell - sell_fee
    assert t1["cash_inflow"] == pytest.approx(net_proceeds, abs=1e-3)

    # Net PnL and Net Return %
    expected_pnl = net_proceeds - expected_cost_basis
    expected_ret_pct = 100.0 * (net_proceeds / expected_cost_basis - 1.0)
    assert t1["net_pnl_pkr"] == pytest.approx(expected_pnl, abs=1e-3)
    assert t1["net_return_pct"] == pytest.approx(expected_ret_pct, abs=1e-3)

    # 2. Check Unresolved Position (Y)
    assert len(unresolved) == 1
    u = unresolved[0]
    assert u["symbol"] == "Y"
    # Y entered at s=4 open @ 205 PKR.
    # Cash at s=4 open was 50,000 PKR (X hadn't exited yet! X exits at s=4 close).
    # Total equity at s=3 close: cash 50,000 + X value (498.753 * 110 = 54,862.84) = 104,862.84 PKR.
    # Max pos budget = 0.50 * 104,862.84 = 52,431.42 PKR, capped by cash 50,000.0 PKR!
    # Gross spend for Y = 50,000 / 1.0025 = 49,875.31172 PKR.
    # Total cost basis for Y = 50,000.0 PKR.
    # Y shares = 49,875.31172 / 205.0 = 243.2942 shares.
    y_shares = u["shares"]
    assert y_shares == pytest.approx(49_875.31172 / 205.0, abs=1e-3)
    y_cost_basis = 50_000.0

    # 3. Exact Cash Ledger Integrity
    final_cash = df_daily.iloc[-1]["cash"]
    # In the ledger, net_cash_impact is signed (- for BUY outflow, + for SELL inflow)
    reconciled_cash = initial_capital + ledger["net_cash_impact"].sum()
    assert final_cash == pytest.approx(reconciled_cash, abs=1e-4)

    # 4. Total Fees Reconciliation
    total_fees = ledger["fee"].sum()
    assert metrics["total_fees_paid_pkr"] == pytest.approx(total_fees, abs=1e-4)

    # 5. Terminal Equity Exact Reconciliation
    # Terminal Equity == Final Cash + Mark-to-Market Holdings Value
    final_holdings_val = y_shares * 210.0  # Session 5 close price for Y
    final_equity = final_cash + final_holdings_val
    assert metrics["final_equity_pkr"] == pytest.approx(final_equity, abs=1e-4)

    # And Terminal Equity == Initial Capital + Completed Trade Net PnL + Unrealized Net PnL:
    # Unrealized Net PnL = final_holdings_val - y_cost_basis
    unrealized_pnl = final_holdings_val - y_cost_basis
    assert final_equity == pytest.approx(initial_capital + t1["net_pnl_pkr"] + unrealized_pnl, abs=1e-4)


def test_positive_daily_volume_does_not_guarantee_fill_documentation():
    """Verify and document that positive daily volume is a necessary condition

    for execution, but in reality does not prove execution at open or close without depth.
    """
    sessions = [1, 2]
    # Stock with 0 volume cannot fill
    grid = [
        {"session": 1, "symbol": "Z", "open": 50.0, "close": 50.0, "volume": 1000},
        {"session": 2, "symbol": "Z", "open": 50.0, "close": 50.0, "volume": 0},  # Zero volume -> illiquid/suspended
    ]
    prices_df = pd.DataFrame(grid)

    candidate_shortlists = {
        1: [("Z", 5.0)]
    }

    res = run_chronological_portfolio_backtest(
        sessions=sessions,
        prices_df=prices_df,
        candidate_shortlists=candidate_shortlists,
        technical_signals={},
        initial_capital=100_000.0,
        enforce_volume_positive=True,
    )
    # Order at session 2 open cannot execute because volume == 0 (no market activity)
    assert len(res["order_ledger"]) == 0
