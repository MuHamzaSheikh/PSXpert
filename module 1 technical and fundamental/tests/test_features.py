import numpy as np
import pandas as pd
import pytest

from conftest import report, statement_rows
from m1.features import FUNDAMENTAL, TECHNICAL, as_of, build_dataset, directions, fundamental_frame, statement_panel
from m1.settings import Settings


def test_intraday_publication_and_banking_ratios():
    period, day, symbol = "2026-03-31", "2026-05-10", "AAA"
    time = day + "T13:30:00+05:00"
    prices = pd.DataFrame({
        "prediction_timestamp": [as_of(day + "T11:00:00+05:00"), as_of(time)],
        "market_cap": [2_000_000, 2_000_000],
    })
    facts = pd.DataFrame(statement_rows(symbol, period, time))
    notices = pd.DataFrame([report(symbol, period, day)])
    filings, _ = statement_panel(facts, notices)
    result = fundamental_frame(prices, filings[symbol], True, Settings())
    assert result.loc[0, FUNDAMENTAL].isna().all()
    assert result.loc[1, "eps_pkr"] == 4
    assert result.loc[1, "roe_pct"] == 20
    assert result.loc[1, "roa_pct"] == 10
    assert result.loc[1, "pe_ratio"] == 20
    assert result.loc[1, "pb_ratio"] == 4
    assert result.loc[1, "net_margin_pct"] == 25
    assert result.loc[1, "bank_net_interest_over_assets_pct"] == 20
    assert pd.isna(result.loc[1, "debt_to_equity"])


def test_publication_date_only_and_missing():
    facts = pd.DataFrame(statement_rows("AAA", "2025-12-31"))
    notices = pd.DataFrame([report("AAA", "2025-12-31", "2026-05-10")])
    filings, _ = statement_panel(facts, notices)
    assert pd.isna(filings["AAA"][0]["publication_timestamp"])
    assert filings["AAA"][0]["available_from_timestamp"] == as_of("2026-05-11T00:00:00+05:00")
    assert not statement_panel(facts, pd.DataFrame())[0]
    conflicting = pd.concat([notices, pd.DataFrame([report("AAA", "2025-12-31", "2026-05-11")])])
    assert not statement_panel(facts, conflicting)[0]
    with pytest.raises(ValueError, match="UTC offset"):
        as_of("2026-05-11T12:00:00")


def test_exact_twentieth_market_session_and_missing_ticker_candle(fixtures):
    sources, cutoff, data, _ = fixtures
    ticker_data = data[data["symbol"].eq("AAA")].reset_index(drop=True)
    assert ticker_data.loc[100, "future_20_day_return_pct"] == pytest.approx(
        100 * (ticker_data.loc[120, "close"] / ticker_data.loc[100, "close"] - 1)
    )
    assert ticker_data["future_20_day_return_pct"].tail(20).isna().all()
    price, calendar, *rest = sources
    missing = price.loc[~(price["symbol"].eq("AAA") & price["trading_date"].eq(ticker_data.loc[120, "trading_date"]))]
    modified, _ = build_dataset((missing, calendar, *rest), cutoff)
    row = modified.loc[modified["symbol"].eq("AAA") & modified["session"].eq(100)].iloc[0]
    assert pd.isna(row["future_20_day_return_pct"])


def test_direction_boundaries_and_missing():
    values = directions(pd.Series([-3.1, -3.0, 0, 3.0, 3.1, np.nan]))
    assert values.tolist()[:5] == ["BEARISH", "SIDEWAYS", "SIDEWAYS", "SIDEWAYS", "BULLISH"]
    assert pd.isna(values.iloc[-1])
    assert directions(pd.Series([(103 / 100 - 1) * 100])).iat[0] == "SIDEWAYS"


def test_past_features_do_not_change_when_future_rows_are_removed(fixtures):
    sources, _, whole, _ = fixtures
    cutoff = as_of("2023-03-01T23:59:59+05:00")
    shortened, _ = build_dataset(sources, cutoff, labels=False)
    past = whole[whole["prediction_timestamp"].le(cutoff)].reset_index(drop=True)
    columns = TECHNICAL + FUNDAMENTAL
    pd.testing.assert_frame_equal(past[columns], shortened[columns])
    assert shortened["rsi_14"].notna().any()
    assert shortened["atr_pct"].notna().any()
    assert shortened["obv_change_20_scaled"].notna().any()
