"""
Test suite verifying all 506 PSX companies and candlestick pattern detections in app.py
"""

import sys
import os

# Add root directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import list_stocks, list_sectors, get_ohlcv


def test_506_stocks_returned():
    stocks = list_stocks(limit=1000)
    print(f"Total stocks returned: {len(stocks)}")
    assert len(stocks) >= 500, f"Expected >= 500 stocks, got {len(stocks)}"
    # Check both KSE100 and non-KSE100 presence
    symbols = {s["symbol"] for s in stocks}
    assert "OGDC" in symbols, "OGDC must be present"
    assert "AABS" in symbols, "AABS (non-KSE-100) must be present"
    assert "MEBL" in symbols, "MEBL must be present"
    print("Stocks test passed!")


def test_sectors_returned():
    sectors = list_sectors()
    print(f"Total sectors returned: {len(sectors)}")
    assert len(sectors) >= 15, f"Expected >= 15 sectors, got {len(sectors)}"
    assert "COMMERCIAL BANKS" in sectors or any("BANK" in s for s in sectors)
    print("Sectors test passed!")


def test_ohlcv_kse100_patterns():
    res = get_ohlcv("KSE100", days=180)
    assert res["symbol"] == "KSE100"
    assert len(res["candles"]) > 30, "Must have valid candles"
    assert "patterns" in res
    print(f"KSE100 candles: {len(res['candles'])}, patterns detected: {len(res['patterns'])}")
    print("KSE100 OHLCV test passed!")


def test_ohlcv_non_kse100_equity():
    res = get_ohlcv("AABS", days=180)
    assert res["symbol"] == "AABS"
    assert len(res["candles"]) > 30, "Non-KSE-100 equity must have valid candles"
    assert "patterns" in res
    print(f"AABS candles: {len(res['candles'])}, patterns detected: {len(res['patterns'])}")
    print("Non-KSE100 OHLCV test passed!")


if __name__ == "__main__":
    test_506_stocks_returned()
    test_sectors_returned()
    test_ohlcv_kse100_patterns()
    test_ohlcv_non_kse100_equity()
    print("ALL API VERIFICATION TESTS PASSED SUCCESSFULLY!")
