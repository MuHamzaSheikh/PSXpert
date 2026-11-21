"""Read-only project database and optional authenticated pyPSX raw OHLCV checks."""

import os
import re
from contextlib import contextmanager

import numpy as np
import pandas as pd
from dotenv import dotenv_values
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError

from .settings import REPO, TZ

PRICE = ["open", "high", "low", "close", "volume"]
KEY = ["symbol", "trading_date"]
TABLES = (
    "companies", "stock_prices", "market_indices", "data_sources",
    "company_financials", "corporate_announcements", "corporate_payouts",
)


class DataUnavailable(RuntimeError):
    pass


def ticker(value):
    symbol = str(value).strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{0,19}", symbol, flags=re.ASCII):
        raise ValueError("Invalid PSX ticker syntax")
    return symbol


def project_config():
    return {**dotenv_values(REPO / ".env"), **os.environ}


def sqlite_engine(path):
    from sqlite3 import connect

    path = path.resolve(strict=True)
    for suffix in ("-wal", "-journal"):
        pending = path.with_name(path.name + suffix)
        if pending.exists() and pending.stat().st_size:
            raise DataUnavailable("SQLite snapshot has an active WAL or rollback journal")

    def open_snapshot():
        connection = connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
        connection.execute("PRAGMA query_only=ON")
        return connection

    return create_engine("sqlite://", creator=open_snapshot)


@contextmanager
def database():
    config = project_config()
    url = config.get("MODULE1_DATABASE_URL") or config.get("DATABASE_URL")
    if url:
        url = make_url(url)
    elif config.get("POSTGRES_PASSWORD"):
        url = URL.create(
            "postgresql+psycopg2", username=config.get("POSTGRES_USER", "postgres"),
            password=config["POSTGRES_PASSWORD"], host=config.get("POSTGRES_HOST", "localhost"),
            port=int(config.get("POSTGRES_PORT", "5432")),
            database=config.get("POSTGRES_DB", "psxpert"),
        )
    if url and url.get_backend_name() == "postgresql":
        engine = create_engine(url.set(drivername="postgresql+psycopg2"), connect_args={
            "options": "-c default_transaction_read_only=on -c default_transaction_isolation=repeatable\\ read",
            "connect_timeout": 4,
        })
        try:
            connection = engine.connect()
        except OperationalError as exc:
            engine.dispose()
            if config.get("MODULE1_DATABASE_URL") or "refused" not in str(exc.orig).lower():
                raise DataUnavailable("Configured PostgreSQL connection failed") from None
        else:
            try:
                with connection:
                    if connection.execute(text("SHOW transaction_read_only")).scalar_one() != "on":
                        raise DataUnavailable("PostgreSQL did not enforce read-only mode")
                    yield connection
                return
            finally:
                engine.dispose()
    elif url and url.get_backend_name() != "sqlite":
        raise DataUnavailable("Only PostgreSQL and SQLite are supported")

    from pathlib import Path

    path = Path(url.database) if url and url.get_backend_name() == "sqlite" and url.database else REPO / "data/psxpert.db"
    if not path.is_absolute():
        path = REPO / path
    if not path.is_file():
        raise DataUnavailable("Existing SQLite snapshot is unavailable")
    engine = sqlite_engine(path)
    try:
        with engine.connect() as connection:
            yield connection
    finally:
        engine.dispose()


def read_sources(connection, symbol=None, cutoff=None):
    tables = set(inspect(connection).get_table_names())
    missing = set(TABLES[:4]) - tables
    if missing:
        raise DataUnavailable("Missing database tables: " + ", ".join(sorted(missing)))

    def read(sql, params=None):
        return pd.read_sql_query(text(sql), connection, params=params)

    lookup = "SELECT symbol, sector, sector_category, is_kse100 FROM companies"
    if symbol:
        companies = read(lookup + " WHERE UPPER(symbol) = :symbol", {"symbol": symbol})
    else:
        companies = read(lookup + " WHERE is_kse100 = TRUE")
    if companies.empty:
        if symbol:
            raise KeyError(symbol)
        raise DataUnavailable("No companies in the database KSE-100 universe")
    if symbol and not bool(companies.iloc[0]["is_kse100"]):
        raise DataUnavailable("Ticker is outside the module's KSE-100 universe")

    def scoped(projection, table, column, condition=""):
        clauses = [condition] if condition else []
        params = {}
        if symbol and table != "market_indices":
            clauses.append("UPPER(t.symbol) = :symbol")
            params["symbol"] = symbol
        elif not symbol and table != "market_indices":
            clauses.append("t.symbol IN (SELECT symbol FROM companies WHERE is_kse100 = TRUE)")
        if cutoff:
            clauses.append(f"t.{column} <= :cutoff")
            params["cutoff"] = cutoff
        where = " AND ".join(clauses) or "1=1"
        join = "" if table == "market_indices" else " LEFT JOIN data_sources s ON t.source_id = s.id"
        return read(f"SELECT {projection} FROM {table} t{join} WHERE {where}", params)

    prices = scoped(
        "t.symbol, t.trading_date, t.open, t.high, t.low, t.close, t.volume, "
        "t.market_cap, s.source_name AS origin", "stock_prices", "trading_date",
    )
    calendar = scoped("DISTINCT t.trading_date", "market_indices", "trading_date",
                      "t.index_symbol = 'KSE100' AND t.close > 0")
    statements = pd.DataFrame()
    financial_counts = {}
    if "company_financials" in tables:
        financial_counts = {
            row.statement_type: int(row.count)
            for row in read("SELECT statement_type, COUNT(*) AS count FROM company_financials "
                            "GROUP BY statement_type").itertuples()
        }
        extra = "t.publication_timestamp" if "publication_timestamp" in {
            c["name"] for c in inspect(connection).get_columns("company_financials")
        } else "NULL"
        statements = scoped(
            f"t.symbol, t.period_end_date, {extra} AS exact_publication, "
            "t.statement_type, t.metric_name, t.metric_value, t.unit, s.source_name AS origin",
            "company_financials", "period_end_date",
            "t.statement_type IN ('INCOME_STATEMENT', 'BALANCE_SHEET', 'CASH_FLOW')",
        )
    announcements = pd.DataFrame()
    if "corporate_announcements" in tables:
        announcements = scoped(
            "t.symbol, t.posting_date, t.title, s.source_name AS origin",
            "corporate_announcements", "posting_date",
            "t.category = 'Earnings Announcements'",
        )
    payouts = pd.DataFrame()
    if "corporate_payouts" in tables:
        payouts = scoped("t.symbol, t.announcement_date, t.payout_type", "corporate_payouts",
                         "announcement_date", "t.payout_type IN ('split', 'bonus')")
    metadata = {
        "database": connection.dialect.name, "tables_read": sorted(set(TABLES) & tables),
        "technical_indicators_table_present": "technical_indicators" in tables,
        "financial_table_counts": financial_counts,
    }
    prices["price_source"] = "database"
    return prices, calendar, companies, statements, announcements, payouts, metadata


def normalize_prices(frame):
    result = frame.copy()
    result["symbol"] = result["symbol"].map(ticker)
    result["trading_date"] = pd.to_datetime(result["trading_date"], errors="raise").dt.normalize()
    for name in PRICE + ["market_cap"]:
        result[name] = pd.to_numeric(result[name], errors="coerce") if name in result else np.nan
    if result[KEY].isna().any().any():
        raise DataUnavailable("An OHLCV record has a missing trading date")
    return result


def compare_prices(primary, secondary):
    """Audit overlaps and duplicates with database priority and no gap imputation."""
    primary = normalize_prices(primary)
    secondary = normalize_prices(secondary)
    report = {}
    for name, frame in (("database", primary), ("pypsx", secondary)):
        report[f"{name}_duplicate_rows"] = int(frame.duplicated(KEY, keep=False).sum())
        if name == "database" and report[f"{name}_duplicate_rows"]:
            raise DataUnavailable("Duplicate database price keys after ticker normalization")
    overlapping = primary[KEY + PRICE].merge(secondary[KEY + PRICE], on=KEY, suffixes=("_db", "_pypsx"))
    equal = np.column_stack([
        np.isclose(overlapping[f"{name}_db"], overlapping[f"{name}_pypsx"],
                   rtol=0, atol=0.005 if name != "volume" else 0, equal_nan=True)
        for name in PRICE
    ])
    report["overlap_rows"] = len(overlapping)
    report["conflicts_by_field"] = {name: int((~equal[:, i]).sum()) for i, name in enumerate(PRICE)}
    report["conflict_rows"] = int((~equal.all(axis=1)).sum())
    report["pypsx_only_rows"] = int(secondary[KEY].merge(primary[KEY], on=KEY, how="left", indicator=True)
                                    ["_merge"].eq("left_only").sum())
    return report, overlapping.loc[~equal.all(axis=1)].copy()


def fetch_pypsx(symbol, start, end, getter=None):
    """Use the documented SDK raw daily endpoint, with an injectable transport for tests."""
    symbol = ticker(symbol)
    start, end = pd.Timestamp(start).date(), pd.Timestamp(end).date()
    if start > end:
        raise ValueError("Start date must precede end date")
    if getter is None:
        config = project_config()
        keys = ("PYPSX_API_KEY_ID", "PYPSX_API_SECRET_KEY")
        if not all(config.get(key) for key in keys):
            raise DataUnavailable("pyPSX requires PYPSX_API_KEY_ID and PYPSX_API_SECRET_KEY")
        try:
            from pypsx import get_ohlcv
        except ImportError:
            raise DataUnavailable("Install the documented pypsx distribution first") from None
        for key in keys:
            os.environ.setdefault(key, config[key])
        getter = get_ohlcv
    try:
        raw = getter(symbol, start=str(start), end=str(end), interval="1d", adjust_splits=False)
    except Exception as exc:
        raise DataUnavailable(f"pyPSX daily OHLCV request failed ({type(exc).__name__})") from None
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        raise DataUnavailable("pyPSX returned no daily bars")
    frame = raw.copy()
    frame.columns = [str(column).lower() for column in frame.columns]
    if not set(PRICE).issubset(frame):
        raise DataUnavailable("pyPSX daily bars lack OHLCV fields")
    provider_symbol = "symbol" if "symbol" in frame else "ticker" if "ticker" in frame else None
    if provider_symbol and not frame[provider_symbol].map(ticker).eq(symbol).all():
        raise DataUnavailable("pyPSX returned an unexpected symbol")
    date_col = next((c for c in ("date", "datetime", "timestamp", "trading_date") if c in frame), None)
    dates = pd.DatetimeIndex(pd.to_datetime(frame[date_col] if date_col else frame.index))
    if date_col is None and not isinstance(frame.index, pd.DatetimeIndex):
        raise DataUnavailable("pyPSX daily bars have no recognized date column or datetime index")
    if dates.tz is not None:
        dates = dates.tz_convert(TZ).tz_localize(None)
    frame["trading_date"] = dates.normalize()
    frame["symbol"], frame["price_source"], frame["origin"] = symbol, "pypsx", "pypsx.get_ohlcv"
    frame = normalize_prices(frame[KEY + PRICE + ["price_source", "origin"]])
    return frame[frame["trading_date"].between(pd.Timestamp(start), pd.Timestamp(end))]
