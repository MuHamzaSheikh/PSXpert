import hashlib
import sqlite3

import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from m1.sources import DataUnavailable, compare_prices, fetch_pypsx, sqlite_engine, ticker


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_sqlite_read_only_and_no_source_file_change(tmp_path):
    path = tmp_path / "source.db"
    csv = tmp_path / "source.csv"
    csv.write_text("ticker,close\nOGDC,125\n", encoding="utf-8")
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE prices (ticker TEXT, close REAL)")
        connection.execute("INSERT INTO prices VALUES ('OGDC', 125)")
    before = [digest(path), digest(csv)]
    engine = sqlite_engine(path)
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA query_only")).scalar_one() == 1
        assert connection.execute(text("SELECT close FROM prices")).scalar_one() == 125
        with pytest.raises(OperationalError, match="readonly"):
            connection.execute(text("DELETE FROM prices"))
    engine.dispose()
    assert [digest(path), digest(csv)] == before
    assert list(tmp_path.glob("source.db*")) == [path]


@pytest.mark.parametrize(("value", "expected"), [(" ogdc ", "OGDC"), ("P-123", "P-123")])
def test_ticker_valid(value, expected):
    assert ticker(value) == expected


@pytest.mark.parametrize("value", ["", "a/b", "OGDC.KA", "أ", "a b"])
def test_ticker_invalid(value):
    with pytest.raises(ValueError):
        ticker(value)


def test_pypsx_adapter_and_source_conflicts():
    def sdk(symbol, **kwargs):
        assert symbol == "OGDC"
        assert kwargs == {"start": "2026-05-10", "end": "2026-05-12", "interval": "1d", "adjust_splits": False}
        return pd.DataFrame(
            {"Open": [12, 12, 13], "High": [13, 13, 14], "Low": [11, 11, 12],
             "Close": [12, 12, 13], "Volume": [123, 124, 125]},
            index=pd.DatetimeIndex(["2026-05-10 20:00Z", "2026-05-10 20:00Z", "2026-05-11 20:00Z"]),
        )

    secondary = fetch_pypsx("ogdc", "2026-05-10", "2026-05-12", sdk)
    assert secondary["trading_date"].dt.day.tolist() == [11, 11, 12]
    assert secondary["price_source"].eq("pypsx").all()
    primary = secondary.iloc[[0]].assign(symbol=" OGDC ", price_source="database", close=12.3)
    audit, conflicts = compare_prices(primary, secondary)
    assert audit["overlap_rows"] == audit["pypsx_duplicate_rows"] == audit["conflict_rows"] == 2
    assert audit["pypsx_only_rows"] == 1
    assert audit["conflicts_by_field"]["volume"] == 1
    assert conflicts["close_db"].eq(12.3).all()
    assert primary["close"].iat[0] == 12.3
    with pytest.raises(DataUnavailable, match="Duplicate database"):
        compare_prices(pd.concat([primary, primary]), secondary)


def test_pypsx_missing_fields():
    with pytest.raises(DataUnavailable, match="lack OHLCV"):
        fetch_pypsx("OGDC", "2026-05-10", "2026-05-12",
                    lambda *args, **kwargs: pd.DataFrame({"close": [1]}))
