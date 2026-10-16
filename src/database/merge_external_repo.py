"""
PSXpert - External Repository Data Merger
Accesses dataset from https://github.com/Immad-Baber/PSX-Data-
Merges non-duplicate data into the existing PSXpert PostgreSQL/SQLite database.

Rules:
- If (symbol, trading_date) already exists in stock_prices: DO NOT ADD.
- If symbol does not exist in companies: ADD symbol and sector mapping first.
- If fundamental metric already exists: DO NOT ADD.
- Add provenance tracking in data_sources.
"""

import math
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Set

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
from sqlalchemy import text
from src.database.connection import get_engine, is_postgres
from src.database.models import DataSource

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    psycopg2 = None
    execute_values = None


def to_snake_case(s: str) -> str:
    s = re.sub(r"[^\w\s]", "", str(s).strip())
    s = re.sub(r"\s+", "_", s)
    return s.lower()


class ExternalRepoMerger:
    def __init__(self, repo_dir: str):
        self.repo_dir = Path(repo_dir)
        self.engine = get_engine()
        self.is_pg = is_postgres()
        print(f"Initialized ExternalRepoMerger with database: {'PostgreSQL' if self.is_pg else 'SQLite'}")

    def register_data_source(self) -> int:
        print("\n--- 1. REGISTER DATA SOURCE ---")
        src_name = "IMMAD_BABER_PSX_DATA"
        src_url = "https://github.com/Immad-Baber/PSX-Data-"
        notes = "Comprehensive historical PSX dataset spanning 810 listed tickers, balance sheets, cash flows, and income statements (2000-2026)."

        with self.engine.begin() as conn:
            existing = conn.execute(text("SELECT id FROM data_sources WHERE source_name = :name"), {"name": src_name}).fetchone()
            if existing:
                source_id = existing[0]
            else:
                if self.is_pg:
                    stmt = text("""
                        INSERT INTO data_sources (source_name, source_type, base_url, status, provenance_notes)
                        VALUES (:name, 'GITHUB_REPO', :url, 'SUCCESS', :notes)
                        RETURNING id;
                    """)
                    row = conn.execute(stmt, {"name": src_name, "url": src_url, "notes": notes}).fetchone()
                    source_id = row[0]
                else:
                    conn.execute(text("""
                        INSERT INTO data_sources (source_name, source_type, base_url, status, provenance_notes)
                        VALUES (:name, 'GITHUB_REPO', :url, 'SUCCESS', :notes);
                    """), {"name": src_name, "url": src_url, "notes": notes})
                    row = conn.execute(text("SELECT id FROM data_sources WHERE source_name = :name"), {"name": src_name}).fetchone()
                    source_id = row[0]

        print(f"Registered data source '{src_name}' with ID: {source_id}")
        return source_id

    def merge_companies(self) -> int:
        print("\n--- 2. MERGING NEW COMPANIES & TICKERS ---")
        # Existing symbols
        with self.engine.connect() as conn:
            existing_syms = set(pd.read_sql(text("SELECT symbol FROM companies"), conn)["symbol"].str.upper())

        print(f"Existing companies in DB: {len(existing_syms)}")

        # Gather all symbols in external repo
        psx_csv = self.repo_dir / "psx.csv"
        sar_csv = self.repo_dir / "Sarmaaya_All_Historical_Data.csv"

        df_psx_syms = pd.read_csv(psx_csv, usecols=["Ticker"])["Ticker"].dropna().astype(str).str.strip().str.upper().unique()
        df_sar_syms = pd.read_csv(sar_csv, usecols=["Symbol"])["Symbol"].dropna().astype(str).str.replace("PSX:", "", regex=False).str.strip().str.upper().unique()

        all_repo_syms = set(df_psx_syms).union(set(df_sar_syms))
        new_syms = sorted(list(all_repo_syms - existing_syms))
        print(f"Found {len(new_syms)} new company symbols to add to 'companies' table.")

        if not new_syms:
            print("No new companies needed.")
            return 0

        # Load metadata directory to match names and sectors
        meta_dict = {}
        snap_path = Path("data/psx_market_snapshot_ohlcv.csv")
        if snap_path.exists():
            df_snap = pd.read_csv(snap_path)
            for _, r in df_snap.iterrows():
                s = str(r.get("symbol", "")).strip().upper()
                meta_dict[s] = {
                    "company_name": str(r.get("company_name", s)),
                    "sector": str(r.get("sector", "OTHER / UNCLASSIFIED")).upper()
                }

        companies_to_insert = []
        for sym in new_syms:
            meta = meta_dict.get(sym, {
                "company_name": f"{sym} Limited",
                "sector": "OTHER / PSX HISTORICAL"
            })
            companies_to_insert.append({
                "symbol": sym,
                "company_name": meta["company_name"][:255],
                "sector": meta["sector"][:120],
                "sector_category": "EQUITY",
                "is_shariah": False,
                "is_kse100": False,
                "is_active": True if sym in meta_dict else False
            })

        df_new_companies = pd.DataFrame(companies_to_insert)

        with self.engine.begin() as conn:
            if self.is_pg:
                stmt = text("""
                    INSERT INTO companies (symbol, company_name, sector, sector_category, is_shariah, is_kse100, is_active)
                    VALUES (:symbol, :company_name, :sector, :sector_category, :is_shariah, :is_kse100, :is_active)
                    ON CONFLICT (symbol) DO NOTHING;
                """)
            else:
                stmt = text("""
                    INSERT OR IGNORE INTO companies (symbol, company_name, sector, sector_category, is_shariah, is_kse100, is_active)
                    VALUES (:symbol, :company_name, :sector, :sector_category, :is_shariah, :is_kse100, :is_active);
                """)
            conn.execute(stmt, df_new_companies.to_dict(orient="records"))

        print(f"Successfully added {len(df_new_companies)} new companies to database.")
        return len(df_new_companies)

    def merge_stock_prices(self, source_id: int) -> int:
        print("\n--- 3. MERGING STOCK PRICES (ZERO DUPLICATES RULE) ---")
        with self.engine.connect() as conn:
            initial_count = conn.execute(text("SELECT COUNT(*) FROM stock_prices")).scalar()
        print(f"Initial DB stock price count: {initial_count:,}")

        # Check existing (symbol, date) set or rely on ON CONFLICT DO NOTHING
        # We process Sarmaaya_All_Historical_Data.csv (up to 2026) and psx.csv (early 2000s)
        # Using ON CONFLICT (symbol, trading_date) DO NOTHING guarantees that:
        # If the price record already exists, it is NOT added.
        # If it does not exist, it is added.

        files_to_process = [
            ("Sarmaaya_All_Historical_Data.csv", "Symbol", "Date", True),
            ("psx.csv", "Ticker", "Date", False),
        ]

        total_inserted = 0
        batch_size = 25000

        for fname, sym_col, date_col, strip_psx in files_to_process:
            fpath = self.repo_dir / fname
            if not fpath.exists():
                continue

            print(f"\nProcessing {fname} in chunks of {batch_size:,}...")
            start_t = time.time()
            chunk_num = 0

            for chunk in pd.read_csv(fpath, chunksize=batch_size, low_memory=False):
                chunk_num += 1
                # Standardize columns
                chunk = chunk[[sym_col, date_col, "Open", "High", "Low", "Close", "Volume"]].dropna(subset=[sym_col, date_col])
                if strip_psx:
                    chunk["symbol"] = chunk[sym_col].astype(str).str.replace("PSX:", "", regex=False).str.strip().str.upper()
                else:
                    chunk["symbol"] = chunk[sym_col].astype(str).str.strip().str.upper()

                chunk["trading_date"] = pd.to_datetime(chunk[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
                chunk = chunk.dropna(subset=["trading_date", "symbol"])
                chunk = chunk[chunk["trading_date"].str.len() == 10]

                chunk["open"] = pd.to_numeric(chunk["Open"], errors="coerce")
                chunk["high"] = pd.to_numeric(chunk["High"], errors="coerce")
                chunk["low"] = pd.to_numeric(chunk["Low"], errors="coerce")
                chunk["close"] = pd.to_numeric(chunk["Close"], errors="coerce")
                chunk["volume"] = pd.to_numeric(chunk["Volume"], errors="coerce").fillna(0).astype("int64")
                chunk["source_id"] = source_id
                chunk["market_cap"] = None

                records = chunk[["symbol", "trading_date", "open", "high", "low", "close", "volume", "market_cap", "source_id"]].to_dict(orient="records")

                with self.engine.begin() as conn:
                    if self.is_pg:
                        stmt = text("""
                            INSERT INTO stock_prices (symbol, trading_date, open, high, low, close, volume, market_cap, source_id)
                            VALUES (:symbol, :trading_date, :open, :high, :low, :close, :volume, :market_cap, :source_id)
                            ON CONFLICT (symbol, trading_date) DO NOTHING;
                        """)
                    else:
                        stmt = text("""
                            INSERT OR IGNORE INTO stock_prices (symbol, trading_date, open, high, low, close, volume, market_cap, source_id)
                            VALUES (:symbol, :trading_date, :open, :high, :low, :close, :volume, :market_cap, :source_id);
                        """)
                    conn.execute(stmt, records)

                if chunk_num % 10 == 0:
                    print(f"  Processed chunk {chunk_num} ({chunk_num * batch_size:,} candidate rows evaluated)")

            print(f"Finished {fname} in {time.time() - start_t:.1f}s")

        with self.engine.connect() as conn:
            final_count = conn.execute(text("SELECT COUNT(*) FROM stock_prices")).scalar()

        new_rows = final_count - initial_count
        print(f"\nStock Prices Merge Summary:")
        print(f"  Initial DB count: {initial_count:,}")
        print(f"  Final DB count:   {final_count:,}")
        print(f"  NEW records added: {new_rows:,} (all pre-existing duplicates were preserved/skipped)")
        return new_rows

    def merge_fundamentals(self, source_id: int) -> int:
        print("\n--- 4. MERGING COMPANY FUNDAMENTALS ---")
        with self.engine.connect() as conn:
            initial_count = conn.execute(text("SELECT COUNT(*) FROM company_financials")).scalar()
            valid_symbols = set(pd.read_sql(text("SELECT symbol FROM companies"), conn)["symbol"].str.upper())
        print(f"Initial DB financial metrics count: {initial_count:,}")

        fundamental_files = [
            ("PSX_Fundamentals_Balance_Sheet.csv", "BALANCE_SHEET"),
            ("PSX_Fundamentals_Cash_Flow.csv", "CASH_FLOW"),
            ("PSX_Fundamentals_Income_Statement.csv", "INCOME_STATEMENT"),
        ]

        total_new_metrics = 0

        for fname, stype in fundamental_files:
            fpath = self.repo_dir / fname
            if not fpath.exists():
                continue

            df = pd.read_csv(fpath)
            df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
            df = df[df["Symbol"].isin(valid_symbols)]
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
            df = df.dropna(subset=["Date", "Symbol"])

            metric_cols = [c for c in df.columns if c not in ("Symbol", "Date")]
            print(f"Processing {fname}: {len(df)} statements across {len(metric_cols)} metrics...")

            # Melt dataframe
            df_melted = pd.melt(
                df,
                id_vars=["Symbol", "Date"],
                value_vars=metric_cols,
                var_name="raw_metric",
                value_name="metric_value"
            )
            df_melted = df_melted.dropna(subset=["metric_value"])
            df_melted["metric_value"] = pd.to_numeric(df_melted["metric_value"], errors="coerce")
            df_melted = df_melted.dropna(subset=["metric_value"])

            df_melted["metric_name"] = df_melted["raw_metric"].apply(to_snake_case)
            df_melted["fiscal_year"] = pd.to_datetime(df_melted["Date"]).dt.year
            df_melted["fiscal_period"] = "FY"
            df_melted["statement_type"] = stype
            df_melted["period_end_date"] = df_melted["Date"]
            df_melted["publication_date"] = df_melted["Date"]
            df_melted["source_id"] = source_id

            df_melted = df_melted.rename(columns={"Symbol": "symbol"})
            records = df_melted[[
                "symbol", "statement_type", "fiscal_year", "fiscal_period",
                "period_end_date", "publication_date", "metric_name", "metric_value", "source_id"
            ]].to_dict(orient="records")

            batch_size = 5000
            num_batches = math.ceil(len(records) / batch_size)

            with self.engine.begin() as conn:
                if self.is_pg:
                    stmt = text("""
                        INSERT INTO company_financials (
                            symbol, statement_type, fiscal_year, fiscal_period,
                            period_end_date, publication_date, metric_name, metric_value, source_id
                        )
                        VALUES (
                            :symbol, :statement_type, :fiscal_year, :fiscal_period,
                            :period_end_date, :publication_date, :metric_name, :metric_value, :source_id
                        )
                        ON CONFLICT (symbol, statement_type, fiscal_year, fiscal_period, metric_name) DO NOTHING;
                    """)
                else:
                    stmt = text("""
                        INSERT OR IGNORE INTO company_financials (
                            symbol, statement_type, fiscal_year, fiscal_period,
                            period_end_date, publication_date, metric_name, metric_value, source_id
                        )
                        VALUES (
                            :symbol, :statement_type, :fiscal_year, :fiscal_period,
                            :period_end_date, :publication_date, :metric_name, :metric_value, :source_id
                        );
                    """)

                for i in range(num_batches):
                    b_chunk = records[i * batch_size:(i + 1) * batch_size]
                    conn.execute(stmt, b_chunk)

        with self.engine.connect() as conn:
            final_count = conn.execute(text("SELECT COUNT(*) FROM company_financials")).scalar()

        new_financials = final_count - initial_count
        print(f"\nCompany Financials Merge Summary:")
        print(f"  Initial DB count: {initial_count:,}")
        print(f"  Final DB count:   {final_count:,}")
        print(f"  NEW metrics added: {new_financials:,}")
        return new_financials

    def run_all(self, fundamentals_only: bool = False):
        print("=" * 70)
        print("PSXPERT - MERGING EXTERNAL REPOSITORY DATA (Immad-Baber/PSX-Data-)")
        print("=" * 70)
        start_time = time.time()

        source_id = self.register_data_source()
        new_companies = 0
        new_prices = 0

        if not fundamentals_only:
            new_companies = self.merge_companies()
            new_prices = self.merge_stock_prices(source_id)

        new_financials = self.merge_fundamentals(source_id)

        elapsed = time.time() - start_time
        print("\n" + "=" * 70)
        print(f"MERGE PIPELINE COMPLETED IN {elapsed:.2f}s")
        if not fundamentals_only:
            print(f"  New Companies Added:    {new_companies:,}")
            print(f"  New Stock Prices Added: {new_prices:,}")
        print(f"  New Financials Added:   {new_financials:,}")
        print("=" * 70)


if __name__ == "__main__":
    repo_path = r"C:\Users\HP\.gemini\antigravity-ide\brain\b5290a13-c586-4e0f-ba99-dd263f4c8fe4\scratch\PSX-Data"
    fund_only = "--fundamentals-only" in sys.argv
    merger = ExternalRepoMerger(repo_path)
    merger.run_all(fundamentals_only=fund_only)
