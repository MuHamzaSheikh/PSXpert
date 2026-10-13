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
    "financial_news_historical_2002_2026.csv",
    "kse100_fundamentals_annual.csv",
    "kse100_fundamentals_quarterly.csv",
    "kse100_financial_ratios.csv",
    "kse100_corporate_announcements.csv",
    "kse100_corporate_payouts_2001_2026.csv",
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
        elif "posting_date" in df.columns:
            print(f"  Posting Date Range: {df['posting_date'].min()} -> {df['posting_date'].max()}")
            if "category" in df.columns:
                print(f"  Categories: {df['category'].value_counts().to_dict()}")
        elif "announcement_date" in df.columns:
            print(f"  Announcement Date Range: {df['announcement_date'].min()} -> {df['announcement_date'].max()}")
            if "payout_type" in df.columns:
                print(f"  Payout Types: {df['payout_type'].value_counts().to_dict()}")
        elif "fiscal_year" in df.columns:
            print(f"  Fiscal Year Range: {df['fiscal_year'].min()} -> {df['fiscal_year'].max()}")
            if "fiscal_quarter" in df.columns:
                print(f"  Quarters: {sorted(df['fiscal_quarter'].dropna().unique())}")
        print("  First row:\n ", dict(df.iloc[0]))
    else:
        print(f"\n[MISSING] {fname}")

stocks_dir = os.path.join(DATA_DIR, "stocks_historical")
if os.path.exists(stocks_dir):
    stock_files = [f for f in os.listdir(stocks_dir) if f.endswith(".csv")]
    print(f"\n[DIRECTORY] stocks_historical/: {len(stock_files)} individual CSV stock files created.")

fund_dir = os.path.join(DATA_DIR, "fundamentals_company")
if os.path.exists(fund_dir):
    fund_files = [f for f in os.listdir(fund_dir) if f.endswith(".csv")]
    print(f"[DIRECTORY] fundamentals_company/: {len(fund_files)} individual company fundamental CSV files created.")

ann_dir = os.path.join(DATA_DIR, "announcements_company")
if os.path.exists(ann_dir):
    ann_files = [f for f in os.listdir(ann_dir) if f.endswith(".csv")]
    print(f"[DIRECTORY] announcements_company/: {len(ann_files)} individual company announcement CSV files created.")
print("=" * 60)
