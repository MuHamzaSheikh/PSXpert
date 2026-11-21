"""Causal feature definitions and shared training/inference dataset builder."""

import sys
from collections import Counter
from datetime import timedelta

import numpy as np
import pandas as pd

from .settings import CLASSES, REPO, Settings, TZ
from .sources import DataUnavailable, normalize_prices, ticker

# Existing pure analysis methods are used without the legacy data loading policies.
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.analysis.common import safe_div
from src.analysis.fundamental_engine import FundamentalAnalysisEngine
from src.analysis.technical_indicators import TechnicalIndicatorCalculator
from src.predictive_data.point_in_time import parse_ended_date_from_title


TECHNICAL = [
    "rsi_14", "macd_pct", "macd_signal_pct", "macd_hist_pct", "close_vs_sma_20_pct",
    "close_vs_sma_50_pct", "close_vs_ema_20_pct", "close_vs_ema_50_pct", "bb_upper_pct",
    "bb_lower_pct", "bb_bandwidth", "bb_percent_b", "atr_pct", "obv_change_20_scaled",
    "momentum_5_pct", "momentum_20_pct", "volatility_20_pct", "volume_vs_20",
    "intraday_range_pct", "close_change_pct",
]
FUNDAMENTAL = [
    "eps_pkr", "roe_pct", "roa_pct", "pe_ratio", "pb_ratio", "debt_to_equity",
    "revenue_growth_yoy_pct", "net_income_growth_yoy_pct", "net_margin_pct",
    "fcf_margin_pct", "ocf_to_net_income_ratio", "bank_net_interest_over_assets_pct",
]
GROUPS = {
    "technical": TECHNICAL,
    "fundamental": FUNDAMENTAL,
    "combined": TECHNICAL + FUNDAMENTAL,
}
FILING_FIELDS = ["period_end_date", "publication_timestamp", "publication_date",
                 "available_from_timestamp", "fundamental_source", "filing_source"]
IFRS = {
    "total_revenue": ("total_revenue", "operating_revenue"),
    "net_income": ("net_income", "net_income_common_stockholders"),
    "common_stock_equity": ("common_stock_equity", "stockholders_equity"),
    "shares": ("ordinary_shares_number", "basic_average_shares"),
    "basic_eps": ("basic_eps",),
    "diluted_eps": ("diluted_eps",),
    "total_assets": ("total_assets",),
    "total_debt": ("total_debt",),
    "gross_profit": ("gross_profit",),
    "operating_income": ("operating_income",),
    "ebit": ("ebit",),
    "interest_expense": ("interest_expense",),
    "current_assets": ("current_assets",),
    "current_liabilities": ("current_liabilities",),
    "cash_and_equivalents": ("cash_and_cash_equivalents",),
    "operating_cash_flow": ("operating_cash_flow",),
    "capital_expenditure": ("capital_expenditure",),
    "effective_fcf": ("free_cash_flow",),
    "cash_dividends_paid": ("cash_dividends_paid", "common_stock_dividend_paid"),
    "net_interest_income": ("net_interest_income",),
}


def as_of(value=None):
    if value is None:
        return pd.Timestamp.now(tz=TZ)
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp) or timestamp.tzinfo is None:
        raise ValueError("as_of_timestamp must include a UTC offset")
    return timestamp.tz_convert(TZ)


def eod(dates):
    closed = pd.to_datetime(dates) + pd.Timedelta(hours=23, minutes=59, seconds=59)
    return closed.dt.tz_localize(TZ, ambiguous=False, nonexistent="shift_forward")


def technical_frame(bars):
    """Normalize features for pooled modeling and suppress indicators with missing inputs."""
    calculator = TechnicalIndicatorCalculator(use_ta_lib=False)
    source = bars[["trading_date", "open", "high", "low", "close", "volume"]]
    indicators = calculator.compute_all_indicators(source)
    close = source["close"].reset_index(drop=True)
    volume = source["volume"].reset_index(drop=True)
    valid_range = source["high"].gt(source["low"]) & source["open"].gt(0)
    valid_range &= source["high"].ge(source[["open", "close"]].max(axis=1))
    valid_range &= source["low"].le(source[["open", "close"]].min(axis=1)) & source["low"].gt(0)
    valid_range = valid_range.reset_index(drop=True)
    data = pd.DataFrame(index=indicators.index)
    data["rsi_14"] = indicators["rsi_14"]
    for feature, column in (("macd_pct", "macd_line"), ("macd_signal_pct", "macd_signal"),
                            ("macd_hist_pct", "macd_diff")):
        data[feature] = (100 * indicators[column] / close).where(data.index >= 33)
    for trend in ("sma_20", "sma_50", "ema_20", "ema_50"):
        data[f"close_vs_{trend}_pct"] = (100 * (close / indicators[trend] - 1)).where(
            data.index >= int(trend[-2:]) - 1
        )
    for bound in ("upper", "lower"):
        data[f"bb_{bound}_pct"] = (100 * (indicators[f"bb_{bound}"] / close - 1)).where(data.index >= 19)
    for column in ("bb_bandwidth", "bb_percent_b"):
        data[column] = indicators[column].where(data.index >= 19)
    # Re-run the existing ATR calculation on each uninterrupted valid candle sequence.
    data["atr_pct"] = np.nan
    for _, run in source.reset_index(drop=True).loc[valid_range].groupby((~valid_range).cumsum()):
        if len(run) < 14:
            continue
        warmup = source.reset_index(drop=True).iloc[max(0, run.index[0] - 1):run.index[0]]
        inputs = pd.concat([warmup.assign(high=np.nan, low=np.nan), run])
        atr = calculator.compute_all_indicators(inputs)["atr_pct"].tail(len(run)).to_numpy()
        data.loc[run.index, "atr_pct"] = np.where(np.arange(len(run)) >= 13, atr, np.nan)
    daily_volume = volume.where(volume.gt(0))
    avg_volume = daily_volume.rolling(20).mean()
    data["obv_change_20_scaled"] = indicators["obv"].diff(20).div(20 * avg_volume)
    data["momentum_5_pct"] = 100 * close.pct_change(5, fill_method=None)
    data["momentum_20_pct"] = 100 * close.pct_change(20, fill_method=None)
    data["close_change_pct"] = 100 * close.pct_change(fill_method=None)
    data["volatility_20_pct"] = data["close_change_pct"].rolling(20).std() * np.sqrt(252)
    data["volume_vs_20"] = daily_volume / avg_volume
    data["intraday_range_pct"] = (
        100 * (source["high"] - source["low"]).reset_index(drop=True) / close
    ).where(valid_range)
    return data[TECHNICAL].replace([np.inf, -np.inf], np.nan)


def annual_releases(announcements):
    """Match annual statements to the transmission of an annual report with an exact period."""
    releases = {}
    if announcements.empty:
        return releases
    for item in announcements.itertuples(index=False):
        title = str(item.title).casefold()
        origin = "" if pd.isna(item.origin) else str(item.origin).upper()
        if (
            "annual report" not in title or "transmission" not in title
            or "revised" in title or "corrigendum" in title or "rectif" in title
            or origin != "PSX_DPS"
        ):
            continue
        period = parse_ended_date_from_title(item.title)
        published = pd.Timestamp(item.posting_date).date()
        if period and period < published <= period + timedelta(days=180):
            releases.setdefault((ticker(item.symbol), period), set()).add(published)
    return releases


def publication_gate(period, exact_times, dates):
    """Return exact release, public release date and conservative availability."""
    nonmissing = exact_times.dropna()
    try:
        exact = {as_of(value) for value in nonmissing}
    except ValueError:
        return None
    if exact and len(nonmissing) == len(exact_times):
        if len(exact) != 1:
            return None
        timestamp = next(iter(exact))
        if timestamp.date() < period:
            return None
        return timestamp, timestamp.date(), timestamp, "company_financials.publication_timestamp"
    if len(dates) != 1:
        return None
    public_date = next(iter(dates))
    available = pd.Timestamp(public_date + timedelta(days=1)).tz_localize(TZ, ambiguous=False, nonexistent="shift_forward")
    return pd.NaT, public_date, available, "corporate_announcements: PSX_DPS annual report transmission"


def statement_panel(statements, announcements):
    releases = annual_releases(announcements)
    audit = Counter({"raw_ifrs_rows": len(statements), "annual_report_matches": len(releases)})
    panel = {}
    if statements.empty:
        return panel, {**audit, "eligible_annual_periods": 0, "eligible_tickers": 0}
    values = statements.copy()
    values["symbol"] = values["symbol"].map(ticker)
    values["period_end_date"] = pd.to_datetime(values["period_end_date"]).dt.date
    values["metric_value"] = pd.to_numeric(values["metric_value"], errors="coerce")
    values = values[values["metric_name"].isin(sum(IFRS.values(), ()))]
    values = values[np.isfinite(values["metric_value"]) & values["metric_value"].ne(12121.0)]
    for (symbol, period), rows in values.groupby(["symbol", "period_end_date"]):
        dates = releases.get((symbol, period), set())
        if not dates:
            audit["unmatched_periods"] += 1
            continue
        gate = publication_gate(period, rows["exact_publication"], dates)
        if gate is None:
            audit["ambiguous_periods"] += 1
            continue
        publication, date, available, filing_source = gate
        # A per-period snapshot cannot safely mix different vintages of the same metric.
        if rows.groupby("metric_name")["metric_value"].nunique().gt(1).any():
            audit["conflicting_periods"] += 1
            continue
        raw = rows.drop_duplicates("metric_name").set_index("metric_name")["metric_value"].to_dict()
        statement = {
            key: next((float(raw[name]) for name in aliases if name in raw), None)
            for key, aliases in IFRS.items()
        }
        if any(statement[name] is None for name in ("total_revenue", "net_income", "common_stock_equity", "total_assets")):
            audit["incomplete_periods"] += 1
            continue
        eps = statement["basic_eps"]
        shares = statement["shares"]
        statement["effective_eps"] = eps if eps is not None else safe_div(
            statement["net_income"], shares, require_positive_den=True
        )
        statement["eps_source"] = "reported_ifrs_basic_eps" if eps is not None else "derived_ifrs"
        if statement["effective_fcf"] is None and all(
            statement[name] is not None for name in ("operating_cash_flow", "capital_expenditure")
        ):
            statement["effective_fcf"] = statement["operating_cash_flow"] - abs(statement["capital_expenditure"])
        statement.update(
            period_end_date=period, effective_pub_date=date, pub_verified=True, has_complete_core=True,
            publication_timestamp=publication, publication_date=date, available_from_timestamp=available,
            fundamental_source="company_financials: " + ", ".join(sorted(set(rows["origin"].fillna("unknown")))),
            filing_source=filing_source,
        )
        panel.setdefault(symbol, []).append(statement)
        audit["eligible_annual_periods"] += 1
    audit["eligible_tickers"] = len(panel)
    return panel, dict(audit)


def fundamental_frame(bars, periods, is_bank, settings):
    """Each release recomputes the latest and prior eligible annual periods."""
    columns = FUNDAMENTAL + FILING_FIELDS
    output = pd.DataFrame(index=bars.index, columns=columns)
    if not periods:
        return output
    engine = FundamentalAnalysisEngine()
    releases = sorted({period["available_from_timestamp"] for period in periods})
    for i, release in enumerate(releases):
        eligible = sorted((p for p in periods if p["available_from_timestamp"] <= release),
                          key=lambda p: p["period_end_date"])
        latest = eligible[-1]
        mask = bars["prediction_timestamp"].ge(release)
        if i + 1 < len(releases):
            mask &= bars["prediction_timestamp"].lt(releases[i + 1])
        times = bars["prediction_timestamp"].dt.tz_localize(None).dt.normalize()
        mask &= (times - pd.Timestamp(latest["period_end_date"])).dt.days.le(settings.max_filing_age_days)
        if not mask.any():
            continue
        profitability = engine._analyze_profitability(latest, is_bank=is_bank)
        debt = engine._analyze_financial_health(latest, is_bank=is_bank)
        growth = engine._analyze_growth(eligible, eligible)
        cash = engine._analyze_cash_flow([latest]) if not is_bank else {}
        output.loc[mask, FILING_FIELDS] = [latest[key] for key in FILING_FIELDS]
        ratios = {**profitability, **debt, **growth, **cash}
        for field in set(FUNDAMENTAL).intersection(ratios):
            output.loc[mask, field] = ratios[field]
        for name, denominator in (("pe_ratio", latest["net_income"]), ("pb_ratio", latest["common_stock_equity"])):
            if denominator and denominator > 0:
                output.loc[mask, name] = bars.loc[mask, "market_cap"].where(
                    bars.loc[mask, "market_cap"].gt(0)
                ) / denominator
        if is_bank:
            output.loc[mask, "debt_to_equity"] = np.nan
            net_interest = safe_div(latest["net_interest_income"], latest["total_assets"], require_positive_den=True)
            if net_interest is not None:
                output.loc[mask, "bank_net_interest_over_assets_pct"] = 100 * net_interest
    return output


def directions(returns, settings=Settings()):
    labels = pd.Series(pd.NA, index=returns.index, dtype="string")
    # Stabilize comparisons at exactly representable price-derived thresholds.
    bearish = returns.lt(settings.bearish) & ~np.isclose(returns, settings.bearish, rtol=0, atol=1e-10)
    bullish = returns.gt(settings.bullish) & ~np.isclose(returns, settings.bullish, rtol=0, atol=1e-10)
    labels.loc[bearish] = CLASSES[0]
    labels.loc[returns.notna() & ~bearish & ~bullish] = CLASSES[1]
    labels.loc[bullish] = CLASSES[2]
    return labels


def targets(bars, payouts):
    """Locate the exact 20th KSE-100 session and require an observed close on it."""
    close_at = bars.set_index("trading_date")["close"]
    next_close = bars["target_date"].map(close_at)
    returns = (next_close / bars["close"] - 1) * 100
    # Drop labels exposed to documented action announcement dates or unexplained raw jumps.
    if not payouts.empty:
        events = pd.to_datetime(payouts["announcement_date"]).drop_duplicates()
        for date in events:
            returns = returns.mask((bars["trading_date"] <= date + pd.Timedelta(days=5))
                                   & (bars["target_date"] >= date - pd.Timedelta(days=5)))
    jumps = bars.loc[bars["segment"].diff().fillna(0).gt(0), "trading_date"]
    for jump in jumps:
        returns = returns.mask(bars["trading_date"].lt(jump) & bars["target_date"].ge(jump))
    return returns


def build_dataset(sources, cutoff, settings=Settings(), labels=True, research_only=False):
    prices, sessions, companies, statements, announcements, payouts, metadata = sources
    prices = normalize_prices(prices)
    if prices.duplicated(["symbol", "trading_date"]).any():
        raise DataUnavailable("Duplicate database price keys after normalization")
    metadata = dict(metadata)
    metadata.update(raw_price_rows=len(prices), raw_tickers=prices["symbol"].nunique(),
                    raw_date_min=prices["trading_date"].min(), raw_date_max=prices["trading_date"].max())
    calendar = pd.Series(pd.to_datetime(sessions["trading_date"]).sort_values().unique(), name="trading_date")
    calendar = calendar[calendar.dt.weekday.lt(5) & eod(calendar).le(cutoff)].reset_index(drop=True)
    session_lookup = pd.DataFrame({"trading_date": calendar, "session": calendar.index,
                                   "target_date": calendar.shift(-settings.horizon)})
    prices = prices.merge(session_lookup, on="trading_date", validate="many_to_one")
    prices = prices[np.isfinite(prices["close"]) & prices["close"].gt(0)].copy()
    numeric = ["open", "high", "low", "volume", "market_cap"]
    prices[numeric] = prices[numeric].replace([np.inf, -np.inf], np.nan)
    prices.loc[prices["volume"].le(0), "volume"] = np.nan
    prices["prediction_timestamp"] = eod(prices["trading_date"])
    panel, filing_audit = statement_panel(statements, announcements)
    companies = companies.assign(symbol=companies["symbol"].map(ticker)).set_index("symbol")
    frames = []
    for symbol, bars in prices.groupby("symbol", sort=True):
        sector = companies.loc[symbol, "sector"]
        sector_category = companies.loc[symbol, "sector_category"]
        is_bank = str(sector).upper() == "COMMERCIAL BANKS" or str(sector_category).lower() == "banks"
        bars = bars.sort_values("session").reset_index(drop=True).assign(sector=sector)
        bars["segment"] = bars["close"].pct_change(fill_method=None).abs().ge(0.35).cumsum()
        fundamental = fundamental_frame(bars, panel.get(symbol, []), is_bank, settings)
        has_filing_rows = fundamental["available_from_timestamp"].notna().any()
        if research_only and not has_filing_rows:
            tech = pd.DataFrame(np.nan, index=bars.index, columns=TECHNICAL)
        else:
            tech = pd.concat([technical_frame(run).set_axis(run.index)
                              for _, run in bars.groupby("segment", sort=False)])
        if labels:
            events = payouts[payouts["symbol"].str.upper().eq(symbol)] if not payouts.empty else payouts
            bars["future_20_day_return_pct"] = targets(bars, events)
            bars["future_direction"] = directions(bars["future_20_day_return_pct"], settings)
            bars["target_timestamp"] = eod(bars["target_date"])
            bars["target_session"] = (bars["session"] + settings.horizon).where(bars["target_date"].notna())
        frames.append(pd.concat([bars, tech, fundamental], axis=1))
    if not frames:
        raise DataUnavailable("No positive closes on completed KSE-100 trading sessions")
    data = pd.concat(frames, ignore_index=True).sort_values(
        ["prediction_timestamp", "symbol"], ignore_index=True
    )
    data[FUNDAMENTAL] = data[FUNDAMENTAL].apply(pd.to_numeric, errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    )
    metadata.update(filing_audit=filing_audit, valid_price_rows=len(data),
                    valid_tickers=data["symbol"].nunique(), ticker_list=sorted(data["symbol"].unique()),
                    valid_date_min=data["trading_date"].min(), valid_date_max=data["trading_date"].max(),
                    feature_counts={key: len(features) for key, features in GROUPS.items()},
                    rows_with_fundamentals=int(data[FUNDAMENTAL].notna().any(axis=1).sum()))
    if labels:
        eligible = research_rows(data)
        metadata.update(raw_labeled_rows=int(data["future_direction"].notna().sum()),
                        common_eligible_rows=len(eligible), common_eligible_tickers=eligible["symbol"].nunique())
    return data, metadata


def research_rows(data):
    return data.loc[
        data["future_direction"].notna() & data["momentum_20_pct"].notna()
        & data[FUNDAMENTAL].notna().any(axis=1)
    ].copy()
