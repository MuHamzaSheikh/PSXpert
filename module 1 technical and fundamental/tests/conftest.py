import numpy as np
import pandas as pd
import pytest

from m1.features import build_dataset


def statement_rows(symbol, period, exact=None):
    metrics = {
        "total_revenue": 400_000, "net_income": 100_000, "common_stock_equity": 500_000,
        "total_assets": 1_000_000, "basic_eps": 4, "total_debt": 130_000,
        "operating_cash_flow": 110_000, "free_cash_flow": 90_000, "net_interest_income": 200_000,
    }
    return [
        {"symbol": symbol, "period_end_date": period, "exact_publication": exact,
         "metric_name": key, "metric_value": value, "statement_type": "INCOME_STATEMENT",
         "unit": "PKR", "origin": "isolated test"}
        for key, value in metrics.items()
    ]


def report(symbol, period, release):
    title = pd.Timestamp(period).strftime("Transmission of Annual Report for the Year Ended %B %d, %Y")
    return {"symbol": symbol, "posting_date": release, "title": title, "origin": "PSX_DPS"}


@pytest.fixture(scope="session")
def fixtures():
    dates = pd.bdate_range("2022-01-03", periods=490)
    prices, companies, statements, announcements = [], [], [], []
    for i, (symbol, sector) in enumerate((("AAA", "CEMENT"), ("BBB", "COMMERCIAL BANKS"), ("CCC", "CHEMICAL"))):
        clock = np.arange(len(dates))
        close = (120 + 10 * i) * np.exp(0.11 * np.sin((clock + 10 * i) / 11) + 0.0001 * clock)
        prices.append(pd.DataFrame(
            {"symbol": symbol, "trading_date": dates, "open": close * 0.998, "high": close * 1.02,
             "low": close * .985, "close": close, "volume": 1234 + clock * 10,
             "market_cap": close * 30_000, "origin": "isolated test", "price_source": "database"}
        ))
        companies.append({"symbol": symbol, "sector": sector, "sector_category": None, "is_kse100": True})
        for year in (2021, 2022, 2023):
            period, release = f"{year}-12-31", f"{year + 1}-02-10"
            statements.extend(statement_rows(symbol, period))
            announcements.append(report(symbol, period, release))
    sources = (pd.concat(prices), pd.DataFrame({"trading_date": dates}), pd.DataFrame(companies),
               pd.DataFrame(statements), pd.DataFrame(announcements), pd.DataFrame(), {})
    cutoff = pd.Timestamp("2024-01-01", tz="Asia/Karachi")
    return sources, cutoff, *build_dataset(sources, cutoff)
