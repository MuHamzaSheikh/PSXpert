"""
Inspect psx_market_snapshot_ohlcv.csv in detail.
"""
import csv

with open("data/psx_market_snapshot_ohlcv.csv", "r", encoding="utf-8") as f:
    r = csv.DictReader(f)
    rows = list(r)

print(f"Total rows in psx_market_snapshot_ohlcv.csv: {len(rows)}")
unique_symbols = set(r["symbol"] for r in rows)
print(f"Unique symbols: {len(unique_symbols)}")

# Check how many are in KSE-100 constituents
kse100_symbols = set()
with open("data/kse100_constituents.csv", "r", encoding="utf-8") as f:
    r2 = csv.DictReader(f)
    kse100_symbols = set(row["symbol"] for row in r2)

in_kse = unique_symbols.intersection(kse100_symbols)
not_in_kse = unique_symbols - kse100_symbols
print(f"In KSE-100: {len(in_kse)}")
print(f"Non-KSE-100 companies: {len(not_in_kse)}")
print("Sample 10 Non-KSE-100 companies:")
for sym in sorted(list(not_in_kse))[:10]:
    row = next(r for r in rows if r["symbol"] == sym)
    print(f"  {sym:<8} | {row['name']} | Close: {row['close']} | Change: {row['changepercentage']}%")
