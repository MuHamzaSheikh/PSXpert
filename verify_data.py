import os
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

print("=" * 60)
print("DATASET VERIFICATION & INTEGRITY REPORT")
print("=" * 60)

files = [
    "kse100_index_history_2002_2026.csv",
    "kse100_constituents.csv",
    "psx_companies_directory.csv",
    "psx_market_snapshot_ohlcv.csv",
    "kse100_stocks_historical_2002_2026.csv",
    "financial_news.csv",
]

for fname in files:
    fpath = os.path.join(DATA_DIR, fname)
    if os.path.exists(fpath):
        size_kb = os.path.getsize(fpath) / 1024
        df = pd.read_csv(fpath, low_memory=False)
        print(f"\n[FILE] {fname}")
        print(f"  Size: {size_kb:,.1f} KB")
        print(f"  Rows: {len(df):,}")
        print(f"  Columns ({len(df.columns)}): {list(df.columns)}")
        if "date" in df.columns:
            print(f"  Date Range: {df['date'].min()} -> {df['date'].max()}")
        print("  First row:\n ", dict(df.iloc[0]))
    else:
        print(f"\n[MISSING] {fname}")

stocks_dir = os.path.join(DATA_DIR, "stocks_historical")
if os.path.exists(stocks_dir):
    stock_files = [f for f in os.listdir(stocks_dir) if f.endswith(".csv")]
    print(f"\n[DIRECTORY] stocks_historical/: {len(stock_files)} individual CSV stock files created.")
print("=" * 60)
