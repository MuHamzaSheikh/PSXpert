"""
PSXpert - Historical Stock Price & Metadata Ingestion for Historical Constituents
Fetches historical daily prices and profiles for former KSE-100 constituents
using SarmayaPSXScraper and stores them in SQLite (stock_prices, companies)
and data/stocks_historical/.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
from src.scraper import SarmayaPSXScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("HistoricalPrices")

DATA_DIR = Path("data")
STOCKS_DIR = DATA_DIR / "stocks_historical"
STOCKS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "psxpert.db"

# List of former KSE-100 constituents that rotated in/out across 2016-2026
HISTORICAL_SYMBOLS = [
    "UNITY", "PKGP", "AVN", "EFUG", "EPCL", "MUGHAL", "NPL", "AGL",
    "HUMNL", "PABC", "RMPL", "HASCOL", "ASL", "ANL", "GATM", "ARPL",
    "SHJS", "NCL", "CPBM", "SPWL", "LPL", "CSAP", "BIPL", "KOSM",
    "NRL", "HSM", "POML", "FCEPL", "SHEL"
]


def ingest_historical_stock_data():
    scraper = SarmayaPSXScraper()
    conn = sqlite3.connect(DB_PATH)

    existing_companies = set(pd.read_sql("SELECT symbol FROM companies", conn)["symbol"].tolist())
    logger.info("Found %d existing companies in database.", len(existing_companies))

    for sym in HISTORICAL_SYMBOLS:
        sym_clean = sym.strip().upper()
        csv_file = STOCKS_DIR / f"{sym_clean}.csv"

        # Check if already present in database
        cur = conn.cursor()
        existing_price_count = cur.execute("SELECT COUNT(*) FROM stock_prices WHERE symbol = ?", (sym_clean,)).fetchone()[0]

        if existing_price_count > 500 and csv_file.exists():
            logger.info("Stock %s already has %d price rows in DB. Skipping API scrape.", sym_clean, existing_price_count)
            continue

        logger.info("Fetching profile and price history for %s...", sym_clean)
        profile = scraper.get_stock_profile(sym_clean)
        cname = profile.get("name", sym_clean)
        sec = profile.get("sectorName", "UNCLASSIFIED")
        cat = profile.get("sectorCategory", "Corporates")
        isin = profile.get("isin", f"{sym_clean}-PK")
        is_shariah = profile.get("isshariah", False)

        # Register company if not exists
        if sym_clean not in existing_companies:
            conn.execute("""
                INSERT OR REPLACE INTO companies (symbol, company_name, sector, sector_category, isin, is_shariah, is_kse100, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 0, 1)
            """, (sym_clean, cname, sec, cat, isin, 1 if is_shariah else 0))
            conn.commit()
            existing_companies.add(sym_clean)
            logger.info("Registered company: %s (%s - %s)", sym_clean, cname, sec)

        # Fetch full daily history
        df_prices = scraper.get_stock_price_history(sym_clean, days=8000)
        if df_prices.empty:
            logger.warning("No price history returned for %s", sym_clean)
            continue

        # Format price dataframe
        df_prices["symbol"] = sym_clean
        df_prices["trading_date"] = pd.to_datetime(df_prices["date"]).dt.strftime("%Y-%m-%d")
        for col in ["open", "high", "low"]:
            if col not in df_prices.columns:
                df_prices[col] = df_prices["close"]

        # Save to CSV
        csv_cols = ["date", "close", "open", "high", "low", "volume"]
        available_cols = [c for c in csv_cols if c in df_prices.columns]
        df_prices.to_csv(csv_file, index=False)

        # Insert into SQLite
        rows_to_insert = []
        for _, r in df_prices.iterrows():
            rows_to_insert.append((
                sym_clean,
                r["trading_date"],
                float(r["open"]) if pd.notna(r["open"]) else float(r["close"]),
                float(r["high"]) if pd.notna(r["high"]) else float(r["close"]),
                float(r["low"]) if pd.notna(r["low"]) else float(r["close"]),
                float(r["close"]),
                int(r["volume"]) if pd.notna(r["volume"]) else 0,
                float(r["marketCap"]) if "marketCap" in r and pd.notna(r["marketCap"]) else None,
            ))

        conn.executemany("""
            INSERT OR IGNORE INTO stock_prices (symbol, trading_date, open, high, low, close, volume, market_cap)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, rows_to_insert)
        conn.commit()
        logger.info("Ingested %d price rows for %s (%s to %s)", len(rows_to_insert), sym_clean, df_prices["trading_date"].min(), df_prices["trading_date"].max())
        time.sleep(0.2)

    conn.close()
    logger.info("Historical stock prices ingestion complete!")


if __name__ == "__main__":
    ingest_historical_stock_data()
