import os
import pandas as pd

candidates = [
    ("data/raw/kse100_fundamentals_annual.csv", "Raw Annual Fundamentals"),
    ("data/raw/kse100_fundamentals_quarterly.csv", "Raw Quarterly Fundamentals"),
    ("data/raw/kse100_corporate_announcements.csv", "Raw Corporate Announcements"),
    ("data/raw/kse100_corporate_payouts_2001_2026.csv", "Raw Corporate Payouts"),
    ("data/raw/kse100_financial_ratios.csv", "Raw Financial Ratios"),
    ("data/raw/financial_news_historical_2002_2026.csv", "Raw Financial News"),
    ("data/processed/company_financials_clean.csv", "Processed Financials"),
    ("data/processed/corporate_announcements_clean.csv", "Processed Announcements"),
    ("data/processed/corporate_payouts_clean.csv", "Processed Payouts"),
    ("data/processed/news_articles_clean.csv", "Processed News"),
    ("module 1 technical and fundamental/data/collected/public_20261117_142707/sarmaaya_announcements.csv.gz", "Module 1 Sarmaaya Announcements"),
    ("module 1 technical and fundamental/data/collected/public_20261117_142707/filing_document_links.csv.gz", "Module 1 Filing Links (DPS PSX)"),
    ("module 1 technical and fundamental/data/collected/public_20261117_142707/financial_metrics.csv.gz", "Module 1 Financial Metrics"),
    ("module 1 technical and fundamental/data/collected/public_20261117_142707/corporate_action_candidates.csv.gz", "Module 1 Corporate Actions"),
    ("module 1 technical and fundamental/data/collected/public_20261117_142707/investify_announcements.csv.gz", "Module 1 Investify Announcements"),
]

for path, desc in candidates:
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, low_memory=False)
            print(f"=== {desc} ===")
            print(f"Path: {path}")
            print(f"Rows: {len(df):,}, Columns: {len(df.columns)}")
            ticker_col = next((c for c in ['symbol', 'ticker', 'company_symbol'] if c in df.columns), None)
            if ticker_col:
                print(f"Unique Tickers: {df[ticker_col].nunique()}")
            for c in df.columns:
                lc = c.lower()
                if any(k in lc for k in ['date', 'year', 'period', 'fiscal', 'time']):
                    s = pd.to_datetime(df[c], errors='coerce').dropna()
                    if len(s) > 0 and s.dt.year.min() > 1990:
                        print(f"  Column '{c}': {s.min().strftime('%Y-%m-%d')} to {s.max().strftime('%Y-%m-%d')} (valid dates: {len(s):,})")
                    else:
                        print(f"  Column '{c}': min={df[c].dropna().min()} max={df[c].dropna().max()}")
            print()
        except Exception as e:
            print(f"Error {path}: {e}")
