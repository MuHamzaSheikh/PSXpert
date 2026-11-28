"""
Scan all data files to identify the complete universe of PSX companies.
"""
import glob
import csv
import os

print("=== SCANNING ALL CSV FILES FOR COMPANIES ===")
for root_dir in ["data", "data/raw", "data/processed", "data/cleaned", "data/news", "data/predictive"]:
    for f in glob.glob(f"{root_dir}/*.*"):
        if f.endswith(".csv"):
            try:
                with open(f, "r", encoding="utf-8", errors="replace") as fp:
                    r = csv.reader(fp)
                    h = next(r)
                    h_lower = [c.lower() for c in h]
                    sym_col = None
                    for candidate in ["symbol", "ticker", "tickers"]:
                        if candidate in h_lower:
                            sym_col = h_lower.index(candidate)
                            break
                    if sym_col is not None:
                        symbols = set()
                        for row in r:
                            if len(row) > sym_col and row[sym_col].strip():
                                symbols.add(row[sym_col].strip())
                        print(f"{f}: {len(symbols)} unique symbols in column '{h[sym_col]}'")
            except Exception as e:
                pass

# Let's inspect data/psx_market_snapshot_ohlcv.csv in detail
snapshot_path = "data/psx_market_snapshot_ohlcv.csv"
if os.path.exists(snapshot_path):
    print("\n=== DETAIL ON psx_market_snapshot_ohlcv.csv ===")
    with open(snapshot_path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        rows = list(r)
        print(f"Total rows in snapshot: {len(rows)}")
        symbols = [r["symbol"] for r in rows]
        print(f"Sample 10 symbols: {symbols[:10]}")
        print("Sample row 0:", rows[0])
        print("Sample row 1:", rows[1])
