"""Long/cash portfolio simulation for a predeclared 20-session signal schedule."""

import numpy as np
import pandas as pd


def simulate(signals, prices, horizon=20, commission_bps=15, slippage_bps=10, adjusted=False):
    strategy = {
        "rule": "Every 20 market sessions pick up to five positive-return BULLISH signals "
                "ranked by expected return. Buy equal cash weights at the next session close. "
                "Exit at the twenty-first session close, then rebalance. Hold cash between trades.",
        "annualization_sessions": 252, "risk_free_rate": 0.0,
        "commission_bps_per_side": commission_bps, "slippage_bps_per_side": slippage_bps,
    }
    if not adjusted:
        return {**strategy, "status": "unavailable", "reason": "No verified corporate-action-adjusted execution series"}
    if signals.empty:
        return {**strategy, "status": "unavailable", "reason": "No held-out signals"}
    if not all(np.isfinite(cost) and 0 <= cost < 5000 for cost in (commission_bps, slippage_bps)):
        raise ValueError("Invalid backtest cost assumptions")
    cost = (commission_bps + slippage_bps) / 10000.0
    if cost >= 1:
        raise ValueError("Combined one-sided costs must be below 100 percent")
    quotes = prices.pivot(index="session", columns="symbol", values="close").sort_index()
    first, last = int(signals["session"].min()), int(signals["session"].max())
    nav, turnover = [1.0], 0.0
    for day in range(first, last - horizon, horizon):
        eligible = signals.loc[signals["session"].eq(day)
                               & signals["direction"].eq("BULLISH") & signals["expected_return_pct"].gt(0)]
        names = eligible.sort_values(["expected_return_pct", "symbol"], ascending=[False, True])["symbol"].head(5)
        sessions = range(day + 1, day + horizon + 2)
        starting_nav = nav[-1]
        if names.empty:
            nav.extend([starting_nav] * horizon)
            continue
        marks = quotes.reindex(index=sessions, columns=names)
        if marks.isna().any().any() or not np.isfinite(marks).all().all() or marks.le(0).any().any():
            return {**strategy, "status": "unavailable", "reason": "Selected holding lacks executable close or daily mark"}
        holdings = starting_nav / (1 + cost)
        wealth = holdings * marks.div(marks.iloc[0]).mean(axis=1)
        # Consecutive periods share the execution close; combine sell and buy on that mark.
        nav[-1] = float(wealth.iloc[0])
        nav.extend(wealth.iloc[1:-1].tolist())
        nav.append(float(wealth.iloc[-1] * (1 - cost)))
        turnover += (holdings + float(wealth.iloc[-1])) / starting_nav
    if len(nav) == 1:
        return {**strategy, "status": "unavailable", "reason": "Insufficient held-out sessions"}
    curve = pd.Series([1.0] + nav[1:])
    daily = curve.pct_change().dropna()
    sd = daily.std()
    return {**strategy, "status": "ok", "sessions": len(daily),
            "annualized_return": float(curve.iloc[-1] ** (252 / len(daily)) - 1),
            "sharpe": float(np.sqrt(252) * daily.mean() / sd) if sd > 0 else None,
            "max_drawdown": float((curve / curve.cummax() - 1).min()),
            "annualized_turnover": float(turnover * 252 / len(daily))}
