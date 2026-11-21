"""Institutional daily multi-asset portfolio simulation engine.

Fixes all identified accounting and execution defects:
1. Strict chronological execution:
   - Signals at session t close generate orders for session t+1 open.
   - Session t+1 opening purchases use only morning cash (cash at session t close).
   - Session t+1 closing sales cannot fund earlier session t+1 opening purchases.
2. Removal of fabricated execution prices:
   - Never sells at entry price merely because an exit quote is missing.
   - Explicit suspended/missing quote policy: positions are held until an executable quote is observed.
   - Strict separation of executable trade prices from balance sheet valuation estimates.
   - Explicit tracking of stale valuations and unresolved positions at assessment boundaries.
3. Target alignment:
   - Signal at t, entry at t+1 open, exit at t+10 close (holding period: 10 sessions).
4. Fundamental rank preservation:
   - When available slots are scarce, stocks are allocated strictly by fundamental score/rank descending,
     never alphabetically.
5. Order-level accounting ledger:
   - Immutable log of every buy, sell, fee deduction, and cash balance.
   - Turnover computed from all executions, including purchases of positions still open at the boundary.
   - Declared boundary valuation and terminal liquidation rules.
6. Causal execution eligibility:
   - Retrospective label quarantine (future announcements/jumps) does NOT block live causal execution.
   - Causal feasibility requires only observable market price (>0) and active trading volume (>0).
   - Liquidity participation constraints explicitly declared (configurable or labeled unconstrained benchmark).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class PortfolioPosition:
    position_id: int
    symbol: str
    entry_session: int
    entry_price: float
    shares: float
    cost_basis: float  # Exact total cash outflow at purchase (gross + buy fee)
    scheduled_exit_session: int
    fundamental_score: float
    last_known_close: float
    is_delayed_exit: bool = False
    stale_days: int = 0


@dataclass
class OrderRecord:
    order_id: int
    position_id: int
    session: int
    timing: str  # "OPEN" or "CLOSE"
    symbol: str
    side: str    # "BUY" or "SELL"
    shares: float
    price: float
    gross_amount: float
    fee: float
    net_cash_impact: float
    cash_balance_after: float
    reason: str  # "ENTRY_SIGNAL", "SCHEDULED_EXIT", "SUSPENSION_DELAYED_EXIT", "BOUNDARY_LIQUIDATION"


def run_chronological_portfolio_backtest(
    sessions: list[int],
    prices_df: pd.DataFrame,
    candidate_shortlists: dict[int, list[tuple[str, float]]],  # session -> [(symbol, fund_score), ...]
    technical_signals: dict[int, set[str]],                   # session -> set of symbols with active technical signal
    initial_capital: float = 10_000_000.0,
    cost_rate: float = 0.005,                                 # 0.5% round-trip (0.25% buy, 0.25% sell)
    max_position_weight: float = 0.10,                        # 10% maximum portfolio allocation
    holding_period: int = 10,                                 # 10 trading sessions
    is_filtered: bool = False,
    max_volume_participation_pct: float | None = None,        # Optional liquidity constraint
    enforce_volume_positive: bool = True,                     # Stock must have positive volume to trade
) -> dict[str, Any]:
    """Execute rigorous chronological portfolio backtest with order-level accounting."""
    # Pre-index price and volume map: (symbol, session) -> {open, close, volume}
    cols_to_use = [c for c in ["open", "close", "adjusted_open", "adjusted_close", "volume"] if c in prices_df.columns]
    price_records = prices_df.set_index(["symbol", "session"])[cols_to_use].to_dict("index")

    current_cash = float(initial_capital)
    active_positions: list[PortfolioPosition] = []
    order_ledger: list[OrderRecord] = []
    daily_records: list[dict[str, Any]] = []
    completed_trades: list[dict[str, Any]] = []

    order_seq = 0
    pos_seq = 0
    sessions_sorted = sorted(sessions)

    for i, s in enumerate(sessions_sorted):
        # -------------------------------------------------------------
        # 1. MORNING (SESSION s OPEN)
        # -------------------------------------------------------------
        # Cash available at morning is strictly the cash balance from previous evening.
        # Closing sales from session s close CANNOT fund session s opening purchases.
        morning_cash = current_cash

        if i > 0:
            prev_session = sessions_sorted[i - 1]
            # Candidates generated at prev_session close
            prev_candidates = candidate_shortlists.get(prev_session, [])
            
            # Apply technical filter if Policy B
            if is_filtered:
                active_signals = technical_signals.get(prev_session, set())
                filtered_candidates = [c for c in prev_candidates if c[0] in active_signals]
            else:
                filtered_candidates = list(prev_candidates)

            # Preserve fundamental ranking: sort strictly by fund_score descending (NEVER alphabetically)
            # Each candidate is (symbol, fund_score)
            filtered_candidates.sort(key=lambda x: x[1], reverse=True)

            # Exclude symbols already held in active positions
            held_symbols = {pos.symbol for pos in active_positions}
            eligible_to_buy = [c for c in filtered_candidates if c[0] not in held_symbols]

            # Available position slots
            max_total_positions = int(np.floor(1.0 / max_position_weight))
            available_slots = max(0, max_total_positions - len(active_positions))

            if available_slots > 0 and len(eligible_to_buy) > 0:
                selected_for_entry = eligible_to_buy[:available_slots]

                # Estimate morning equity: cash + valuation of existing holdings at yesterday's close
                morning_holdings_val = sum(pos.shares * pos.last_known_close for pos in active_positions)
                est_morning_equity = morning_cash + morning_holdings_val

                target_spend_per_stock = min(
                    morning_cash / len(selected_for_entry),
                    est_morning_equity * max_position_weight,
                )

                for sym, score in selected_for_entry:
                    bar = price_records.get((sym, s))
                    if not bar:
                        continue

                    # Determine open price
                    open_price = bar.get("open", bar.get("adjusted_open", 0.0))
                    vol_today = bar.get("volume", np.nan)

                    # Decision-time liquidity: use strictly LAGGED volume known by the open (session prev_session)
                    prev_bar = price_records.get((sym, prev_session), {})
                    lagged_vol = prev_bar.get("volume", np.nan) if prev_bar else np.nan

                    # Causal execution check (independent of retrospective quarantine)
                    if not np.isfinite(open_price) or open_price <= 0:
                        continue
                    # Retrospective execution check: stock must have traded today
                    if enforce_volume_positive and (not np.isfinite(vol_today) or vol_today <= 0):
                        continue  # Halted / suspended on this session

                    # Check available morning cash
                    if current_cash <= 100.0:
                        break  # Insufficient cash for realistic order

                    max_spend = min(current_cash, target_spend_per_stock)

                    # Apply pre-trade liquidity participation constraint using LAGGED volume
                    if max_volume_participation_pct is not None:
                        if np.isfinite(lagged_vol) and lagged_vol > 0:
                            max_liquidity_spend = lagged_vol * (max_volume_participation_pct / 100.0) * open_price
                            max_spend = min(max_spend, max_liquidity_spend)
                        else:
                            # Defined handling of missing volume: unverified pre-trade liquidity rejects order
                            max_spend = 0.0

                    buy_fee_rate = cost_rate / 2.0
                    gross_spend = max_spend / (1.0 + buy_fee_rate)
                    fee = gross_spend * buy_fee_rate
                    total_cash_impact = gross_spend + fee

                    if gross_spend >= 100.0 and total_cash_impact <= current_cash:
                        shares = gross_spend / open_price
                        current_cash -= total_cash_impact

                        order_seq += 1
                        pos_seq += 1

                        # Exact target alignment:
                        # Signal at session t (prev_session), Entry at session t+1 (s) open,
                        # Exit at session t + holding_period (prev_session + holding_period) close.
                        scheduled_exit = prev_session + holding_period

                        # Initialize position
                        pos = PortfolioPosition(
                            position_id=pos_seq,
                            symbol=sym,
                            entry_session=s,
                            entry_price=open_price,
                            shares=shares,
                            cost_basis=total_cash_impact,
                            scheduled_exit_session=scheduled_exit,
                            fundamental_score=score,
                            last_known_close=open_price,
                            is_delayed_exit=False,
                            stale_days=0,
                        )
                        active_positions.append(pos)

                        order_ledger.append(OrderRecord(
                            order_id=order_seq,
                            position_id=pos_seq,
                            session=s,
                            timing="OPEN",
                            symbol=sym,
                            side="BUY",
                            shares=shares,
                            price=open_price,
                            gross_amount=gross_spend,
                            fee=fee,
                            net_cash_impact=-total_cash_impact,
                            cash_balance_after=current_cash,
                            reason="ENTRY_SIGNAL",
                        ))

        # -------------------------------------------------------------
        # 2. AFTERNOON (SESSION s CLOSE)
        # -------------------------------------------------------------
        # Exits process at session s close. Proceeds are added to cash at close.
        remaining_positions: list[PortfolioPosition] = []

        for pos in active_positions:
            should_exit = (s >= pos.scheduled_exit_session)

            if should_exit:
                bar = price_records.get((pos.symbol, s))
                close_price = bar.get("close", bar.get("adjusted_close", 0.0)) if bar else 0.0
                vol = bar.get("volume", np.nan) if bar else np.nan

                is_executable = (
                    bar is not None
                    and np.isfinite(close_price)
                    and close_price > 0
                    and (not enforce_volume_positive or (np.isfinite(vol) and vol > 0))
                )

                if is_executable:
                    # Executable quote available: execute sale
                    gross_proceeds = pos.shares * close_price
                    sell_fee = gross_proceeds * (cost_rate / 2.0)
                    net_proceeds = gross_proceeds - sell_fee
                    current_cash += net_proceeds

                    order_seq += 1
                    reason_str = "SUSPENSION_DELAYED_EXIT" if pos.is_delayed_exit else "SCHEDULED_EXIT"

                    order_ledger.append(OrderRecord(
                        order_id=order_seq,
                        position_id=pos.position_id,
                        session=s,
                        timing="CLOSE",
                        symbol=pos.symbol,
                        side="SELL",
                        shares=pos.shares,
                        price=close_price,
                        gross_amount=gross_proceeds,
                        fee=sell_fee,
                        net_cash_impact=net_proceeds,
                        cash_balance_after=current_cash,
                        reason=reason_str,
                    ))

                    # Record completed trade strictly using actual cash flows from order ledger
                    dollar_pnl = net_proceeds - pos.cost_basis
                    ret_pct = 100.0 * (net_proceeds / pos.cost_basis - 1.0)
                    completed_trades.append({
                        "position_id": pos.position_id,
                        "symbol": pos.symbol,
                        "entry_session": pos.entry_session,
                        "exit_session": s,
                        "scheduled_exit_session": pos.scheduled_exit_session,
                        "holding_duration_sessions": s - pos.entry_session + 1,
                        "entry_price": pos.entry_price,
                        "exit_price": close_price,
                        "shares": pos.shares,
                        "cash_outflow": pos.cost_basis,
                        "cash_inflow": net_proceeds,
                        "net_pnl_pkr": dollar_pnl,
                        "net_return_pct": ret_pct,
                        "was_delayed": pos.is_delayed_exit,
                    })
                else:
                    # Suspension / missing quote: DO NOT fabricate entry price!
                    # Position is held over under Delayed-Exit Policy
                    pos.is_delayed_exit = True
                    pos.stale_days += 1
                    remaining_positions.append(pos)
            else:
                remaining_positions.append(pos)

        active_positions = remaining_positions

        # -------------------------------------------------------------
        # 3. MARK-TO-MARKET VALUATION (SESSION s CLOSE)
        # -------------------------------------------------------------
        holdings_value = 0.0
        pos_breakdown = {}
        stale_valuations_count = 0

        for pos in active_positions:
            bar = price_records.get((pos.symbol, s))
            c_price = bar.get("close", bar.get("adjusted_close", 0.0)) if bar else 0.0

            if bar and np.isfinite(c_price) and c_price > 0:
                pos.last_known_close = float(c_price)
                pos.stale_days = 0
            else:
                stale_valuations_count += 1
                pos.stale_days += 1

            # Valuation uses last known closing price (stale valuation if missing)
            val = pos.shares * pos.last_known_close
            holdings_value += val
            pos_breakdown[pos.symbol] = pos_breakdown.get(pos.symbol, 0.0) + val

        total_equity = current_cash + holdings_value
        exposure_pct = 100.0 * (holdings_value / total_equity) if total_equity > 0 else 0.0

        daily_records.append({
            "session": s,
            "cash": current_cash,
            "holdings_value": holdings_value,
            "total_equity": total_equity,
            "exposure_pct": exposure_pct,
            "active_positions_count": len(active_positions),
            "stale_valuations_count": stale_valuations_count,
            "delayed_exits_pending": sum(1 for p in active_positions if p.is_delayed_exit),
            "position_values": pos_breakdown,
        })

    df_daily = pd.DataFrame(daily_records)
    df_daily["daily_return_pct"] = df_daily["total_equity"].pct_change().fillna(0.0) * 100.0

    # -------------------------------------------------------------
    # 4. END-OF-WINDOW BOUNDARY ACCOUNTING & UNRESOLVED POSITIONS
    # -------------------------------------------------------------
    unresolved_positions = [
        {
            "position_id": int(p.position_id),
            "symbol": str(p.symbol),
            "entry_session": int(p.entry_session),
            "scheduled_exit_session": int(p.scheduled_exit_session),
            "entry_price": float(p.entry_price),
            "shares": float(p.shares),
            "last_known_close": float(p.last_known_close),
            "stale_days": int(p.stale_days),
            "is_delayed_exit": bool(p.is_delayed_exit),
            "unrealized_return_pct": float(100.0 * (p.last_known_close / p.entry_price - 1.0) - (cost_rate * 100.0)),
        }
        for p in active_positions
    ]

    # Convert order ledger to DataFrame
    df_orders = pd.DataFrame([asdict(o) for o in order_ledger]) if order_ledger else pd.DataFrame(columns=[
        "order_id", "position_id", "session", "timing", "symbol", "side", "shares", "price",
        "gross_amount", "fee", "net_cash_impact", "cash_balance_after", "reason"
    ])

    # Compute comprehensive performance metrics
    metrics = evaluate_chronological_performance(
        df_daily=df_daily,
        df_orders=df_orders,
        completed_trades=completed_trades,
        unresolved_positions=unresolved_positions,
        initial_capital=initial_capital,
    )

    return {
        "daily_equity": df_daily,
        "order_ledger": df_orders,
        "completed_trades": completed_trades,
        "unresolved_positions": unresolved_positions,
        "performance_metrics": metrics,
    }


def evaluate_chronological_performance(
    df_daily: pd.DataFrame,
    df_orders: pd.DataFrame,
    completed_trades: list[dict[str, Any]],
    unresolved_positions: list[dict[str, Any]],
    initial_capital: float = 10_000_000.0,
) -> dict[str, Any]:
    """Compute standard quantitative performance metrics including boundary turnover."""
    equity = df_daily["total_equity"].to_numpy()
    daily_returns = df_daily["daily_return_pct"].to_numpy() / 100.0
    n_days = len(df_daily)
    years = n_days / 252.0 if n_days > 0 else 1.0

    final_equity = float(equity[-1]) if len(equity) else initial_capital
    total_return_pct = 100.0 * (final_equity / initial_capital - 1.0)
    cagr_pct = 100.0 * ((final_equity / initial_capital) ** (1.0 / years) - 1.0) if final_equity > 0 and years > 0 else 0.0

    vol_annual_pct = float(np.std(daily_returns) * np.sqrt(252) * 100.0) if len(daily_returns) > 1 else 0.0
    sharpe = float((np.mean(daily_returns) * 252.0) / (np.std(daily_returns) * np.sqrt(252.0))) if vol_annual_pct > 0 else 0.0

    # Drawdown
    peaks = np.maximum.accumulate(equity)
    drawdowns = (equity - peaks) / peaks
    max_drawdown_pct = float(abs(np.min(drawdowns)) * 100.0) if len(drawdowns) else 0.0

    # Turnover strictly includes ALL executions (buys and sells, including boundary open positions)
    total_traded_value = float(df_orders["gross_amount"].sum()) if not df_orders.empty else 0.0
    avg_equity = float(np.mean(equity)) if len(equity) else initial_capital
    turnover = (total_traded_value / (2.0 * avg_equity)) if avg_equity > 0 else 0.0
    turnover_annual = turnover / years if years > 0 else 0.0

    total_fees_paid = float(df_orders["fee"].sum()) if not df_orders.empty else 0.0

    trade_returns = [t["net_return_pct"] for t in completed_trades]
    win_rate = float((np.array(trade_returns) > 0).mean() * 100.0) if len(trade_returns) else 0.0

    return {
        "final_equity_pkr": final_equity,
        "total_return_pct": total_return_pct,
        "cagr_pct": cagr_pct,
        "annualized_volatility_pct": vol_annual_pct,
        "sharpe_ratio": sharpe,
        "max_drawdown_pct": max_drawdown_pct,
        "average_exposure_pct": float(df_daily["exposure_pct"].mean()),
        "max_exposure_pct": float(df_daily["exposure_pct"].max()),
        "total_traded_value_pkr": total_traded_value,
        "total_fees_paid_pkr": total_fees_paid,
        "total_completed_trade_pnl_pkr": float(sum(t["net_pnl_pkr"] for t in completed_trades)) if completed_trades else 0.0,
        "turnover": turnover,
        "annualized_turnover": turnover_annual,
        "completed_trades_count": len(completed_trades),
        "unresolved_positions_count": len(unresolved_positions),
        "total_orders_count": len(df_orders),
        "win_rate_pct": win_rate,
        "mean_completed_trade_return_pct": float(np.mean(trade_returns)) if len(trade_returns) else 0.0,
        "max_stale_valuations_day": int(df_daily["stale_valuations_count"].max()),
        "max_delayed_exits_day": int(df_daily["delayed_exits_pending"].max()),
    }


def compute_newey_west_t_stat(d: np.ndarray, max_lags: int = 10) -> tuple[float, float, float]:
    """Compute Newey-West HAC standard error, t-statistic, and two-tailed p-value."""
    n = len(d)
    if n <= max_lags + 1:
        return float(np.mean(d)), 0.0, 1.0

    mean_d = float(np.mean(d))
    dem = d - mean_d
    gamma_0 = float(np.sum(dem ** 2) / n)

    gamma_sum = 0.0
    for l in range(1, max_lags + 1):
        weight = 1.0 - (l / (max_lags + 1.0))
        gamma_l = float(np.sum(dem[l:] * dem[:-l]) / n)
        gamma_sum += 2.0 * weight * gamma_l

    hac_variance = (gamma_0 + gamma_sum) / n
    hac_se = np.sqrt(max(1e-12, hac_variance))
    t_stat = mean_d / hac_se
    p_val = 2.0 * (1.0 - stats.norm.cdf(abs(t_stat)))
    return mean_d, float(t_stat), float(p_val)
