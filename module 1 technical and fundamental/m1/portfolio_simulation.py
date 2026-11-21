"""Realistic daily multi-asset portfolio simulation and paired date-block evaluation.

Compares:
Policy A: Unfiltered Fundamental Shortlist (top 20% fundamental stocks)
Policy B: Technically Filtered Fundamental Shortlist (top 20% fundamental + technical entry signal)

Constraints & Accounting:
- Identical initial capital (PKR 10,000,000)
- Single-position cap: 10% maximum portfolio weight
- Execution: Signal at session t close -> buy at session t+1 open -> hold 10 sessions -> exit at session t+10 close
- Explicit transaction friction: 0.50% round-trip on all traded volume
- Cash balance and overlapping positions tracked daily
- Paired date-level return differences evaluated via Newey-West HAC standard errors (lag 10)
- Ticker and sector concentration diagnostics (HHI, top-5 share)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class PortfolioPosition:
    symbol: str
    entry_session: int
    entry_price: float
    shares: float
    exit_session: int


def run_portfolio_backtest(
    sessions: list[int],
    prices_df: pd.DataFrame,
    shortlist_series: pd.Series,
    technical_signal_series: pd.Series,
    initial_capital: float = 10_000_000.0,
    cost_rate: float = 0.005,  # 0.5% round-trip (0.25% buy, 0.25% sell)
    max_position_weight: float = 0.10,
    holding_period: int = 10,
    is_filtered: bool = False,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Execute realistic daily portfolio simulation with overlapping position tracking."""
    # Pre-index prices by (symbol, session)
    price_map = prices_df.set_index(["symbol", "session"])[["adjusted_open", "adjusted_close", "price_valid"]].to_dict("index")

    cash = float(initial_capital)
    active_positions: list[PortfolioPosition] = []
    trade_history: list[dict[str, Any]] = []
    daily_records: list[dict[str, Any]] = []

    sessions_sorted = sorted(sessions)

    for i, s in enumerate(sessions_sorted):
        # 1. Process EXITS at session s close for positions where exit_session == s
        remaining_positions: list[PortfolioPosition] = []
        for pos in active_positions:
            if pos.exit_session == s:
                p_info = price_map.get((pos.symbol, s))
                exit_price = p_info["adjusted_close"] if p_info and p_info.get("price_valid", True) else pos.entry_price
                gross_proceeds = pos.shares * exit_price
                exit_fee = gross_proceeds * (cost_rate / 2.0)
                net_proceeds = gross_proceeds - exit_fee
                cash += net_proceeds

                ret_pct = 100.0 * (exit_price / pos.entry_price - 1.0) - (cost_rate * 100.0)
                trade_history.append({
                    "symbol": pos.symbol,
                    "entry_session": pos.entry_session,
                    "exit_session": s,
                    "entry_price": pos.entry_price,
                    "exit_price": exit_price,
                    "shares": pos.shares,
                    "net_return_pct": ret_pct,
                })
            else:
                remaining_positions.append(pos)
        active_positions = remaining_positions

        # 2. Process NEW ENTRIES generated at session s-1 close, executing at session s open
        if i > 0:
            prev_session = sessions_sorted[i - 1]
            # Identify eligible candidates generated at prev_session close
            prev_shortlisted = shortlist_series.get(prev_session, set())
            if is_filtered:
                prev_signals = technical_signal_series.get(prev_session, set())
                candidates = prev_shortlisted.intersection(prev_signals)
            else:
                candidates = prev_shortlisted

            # Exclude symbols already held in active positions
            held_symbols = {pos.symbol for pos in active_positions}
            eligible_candidates = sorted(candidates - held_symbols)

            # Available slots (up to 1 / max_position_weight positions)
            max_total_positions = int(1.0 / max_position_weight)
            available_slots = max(0, max_total_positions - len(active_positions))

            if available_slots > 0 and len(eligible_candidates) > 0:
                selected_for_entry = eligible_candidates[:available_slots]
                # Value of portfolio equity estimate
                est_equity = cash + sum(
                    pos.shares * price_map.get((pos.symbol, s), {}).get("adjusted_open", pos.entry_price)
                    for pos in active_positions
                )
                target_allocation_per_stock = min(cash / len(selected_for_entry), est_equity * max_position_weight)

                for sym in selected_for_entry:
                    p_info = price_map.get((sym, s))
                    if not p_info or not p_info.get("price_valid", True) or p_info.get("adjusted_open", 0) <= 0:
                        continue
                    open_price = float(p_info["adjusted_open"])
                    buy_capital = min(cash, target_allocation_per_stock)
                    buy_fee = buy_capital * (cost_rate / 2.0)
                    invested_capital = buy_capital - buy_fee
                    if invested_capital > 1000 and open_price > 0:
                        shares = invested_capital / open_price
                        cash -= buy_capital
                        active_positions.append(PortfolioPosition(
                            symbol=sym,
                            entry_session=s,
                            entry_price=open_price,
                            shares=shares,
                            exit_session=s + holding_period,
                        ))

        # 3. Mark to Market at session s close
        holdings_value = 0.0
        pos_breakdown = {}
        for pos in active_positions:
            p_info = price_map.get((pos.symbol, s))
            curr_price = p_info["adjusted_close"] if p_info and p_info.get("price_valid", True) else pos.entry_price
            val = pos.shares * curr_price
            holdings_value += val
            pos_breakdown[pos.symbol] = pos_breakdown.get(pos.symbol, 0.0) + val

        total_equity = cash + holdings_value
        exposure_pct = 100.0 * (holdings_value / total_equity) if total_equity > 0 else 0.0

        daily_records.append({
            "session": s,
            "cash": cash,
            "holdings_value": holdings_value,
            "total_equity": total_equity,
            "exposure_pct": exposure_pct,
            "active_positions_count": len(active_positions),
            "position_values": pos_breakdown,
        })

    df = pd.DataFrame(daily_records)
    df["daily_return_pct"] = df["total_equity"].pct_change().fillna(0.0) * 100.0
    return df, trade_history


def compute_newey_west_t_stat(d: np.ndarray, max_lags: int = 10) -> tuple[float, float, float]:
    """Compute Newey-West HAC standard error, t-statistic, and two-tailed p-value."""
    n = len(d)
    if n <= max_lags + 1:
        return float(np.mean(d)), 0.0, 1.0

    mean_d = float(np.mean(d))
    dem = d - mean_d
    # Gamma 0 (sample variance)
    gamma_0 = float(np.sum(dem ** 2) / n)

    # Autocovariances with Bartlett kernel weights
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


def evaluate_portfolio_performance(df: pd.DataFrame, trades: list[dict[str, Any]],
                                   initial_capital: float = 10_000_000.0) -> dict[str, Any]:
    """Compute standard quantitative portfolio performance metrics."""
    equity = df["total_equity"].to_numpy()
    daily_returns = df["daily_return_pct"].to_numpy() / 100.0
    n_days = len(df)
    years = n_days / 252.0 if n_days > 0 else 1.0

    total_return_pct = 100.0 * (equity[-1] / initial_capital - 1.0)
    cagr_pct = 100.0 * ((equity[-1] / initial_capital) ** (1.0 / years) - 1.0) if equity[-1] > 0 and years > 0 else 0.0

    vol_annual_pct = float(np.std(daily_returns) * np.sqrt(252) * 100.0)
    # Annualized excess Sharpe ratio (using 0% benchmark return for zero-beta excess)
    sharpe = float((np.mean(daily_returns) * 252.0) / (np.std(daily_returns) * np.sqrt(252.0))) if np.std(daily_returns) > 0 else 0.0

    # Drawdown
    peaks = np.maximum.accumulate(equity)
    drawdowns = (equity - peaks) / peaks
    max_drawdown_pct = float(abs(np.min(drawdowns)) * 100.0)

    # Turnover: total dollar volume traded / average portfolio equity
    total_traded_volume = sum(t["shares"] * (t["entry_price"] + t["exit_price"]) for t in trades)
    avg_equity = float(np.mean(equity))
    turnover_annual = (total_traded_volume / (2.0 * avg_equity)) / years if avg_equity > 0 and years > 0 else 0.0

    # Trade stats
    trade_returns = [t["net_return_pct"] for t in trades]
    win_rate = float((np.array(trade_returns) > 0).mean() * 100.0) if len(trade_returns) else 0.0

    return {
        "final_equity_pkr": float(equity[-1]),
        "total_return_pct": float(total_return_pct),
        "cagr_pct": float(cagr_pct),
        "annualized_volatility_pct": float(vol_annual_pct),
        "sharpe_ratio": float(sharpe),
        "max_drawdown_pct": float(max_drawdown_pct),
        "average_exposure_pct": float(df["exposure_pct"].mean()),
        "max_exposure_pct": float(df["exposure_pct"].max()),
        "annualized_turnover": float(turnover_annual),
        "total_trades_count": len(trades),
        "win_rate_pct": float(win_rate),
        "mean_trade_return_pct": float(np.mean(trade_returns)) if len(trade_returns) else 0.0,
    }


def compute_concentration_metrics(df: pd.DataFrame, sector_lookup: dict[str, str]) -> dict[str, Any]:
    """Compute Herfindahl-Hirschman Index (HHI), Top-5 ticker weight share, and sector allocation."""
    hhi_list = []
    top5_list = []
    sector_exposure = {}

    for row in df.itertuples():
        pos_vals = row.position_values
        total_h = row.holdings_value
        if total_h > 0 and pos_vals:
            weights = np.array([v / total_h for v in pos_vals.values()])
            hhi = float(np.sum(weights ** 2) * 10_000)
            hhi_list.append(hhi)
            sorted_w = sorted(weights, reverse=True)
            top5_list.append(float(np.sum(sorted_w[:5]) * 100.0))

            # Sector weights
            for sym, val in pos_vals.items():
                sec = sector_lookup.get(sym, "OTHER")
                sector_exposure[sec] = sector_exposure.get(sec, 0.0) + (val / row.total_equity)

    n_days = max(1, len(df))
    avg_sector_exposure = {sec: float((val / n_days) * 100.0) for sec, val in sector_exposure.items()}

    return {
        "mean_hhi": float(np.mean(hhi_list)) if hhi_list else 0.0,
        "mean_top5_ticker_weight_pct": float(np.mean(top5_list)) if top5_list else 0.0,
        "average_sector_exposure_pct": dict(sorted(avg_sector_exposure.items(), key=lambda x: x[1], reverse=True)),
    }
