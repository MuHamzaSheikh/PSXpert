#!/usr/bin/env python3
"""
PSXpert - Master Fundamentals Scraper Pipeline (Dataset C)
Scrapes and exports comprehensive company fundamentals for KSE-100 listed companies:
- Revenue and profit (Income Statement)
- Earnings per share (EPS)
- Assets and liabilities (Balance Sheet)
- Debt and equity
- Cash flow statement (Operating, Investing, Financing, Free Cash Flow)
- Quarterly and annual reporting periods
- Financial & Valuation Ratios

Outputs:
- data/kse100_fundamentals_annual.csv
- data/kse100_fundamentals_quarterly.csv
- data/kse100_financial_ratios.csv
- data/fundamentals_company/{symbol}_fundamentals.csv
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.fundamentals_scraper import PSXFundamentalsScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ScrapeFundamentalsPipeline")


def run_pipeline(output_dir: str = "data", max_workers: int = 10, limit: int = None):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    comp_dir = out_path / "fundamentals_company"
    comp_dir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    logger.info("Initializing PSX Company Fundamentals Pipeline (Dataset C)...")
    scraper = PSXFundamentalsScraper(directory_path=str(out_path / "psx_companies_directory.csv"))

    target_count = limit if limit else len(scraper.companies_df)
    logger.info(f"Targeting {target_count} KSE-100 companies with {max_workers} worker threads...")

    # Execute scraping
    df_annual, df_quarterly, df_ratios = scraper.process_all_companies(
        max_workers=max_workers,
        limit=limit
    )

    # 1. Export Master Annual Fundamentals
    annual_file = out_path / "kse100_fundamentals_annual.csv"
    df_annual.to_csv(annual_file, index=False)
    logger.info(f"Saved Master Annual Fundamentals -> {annual_file} ({len(df_annual)} records)")

    # 2. Export Master Quarterly Fundamentals
    quarterly_file = out_path / "kse100_fundamentals_quarterly.csv"
    df_quarterly.to_csv(quarterly_file, index=False)
    logger.info(f"Saved Master Quarterly Fundamentals -> {quarterly_file} ({len(df_quarterly)} records)")

    # 3. Export Financial Ratios
    ratios_file = out_path / "kse100_financial_ratios.csv"
    df_ratios.to_csv(ratios_file, index=False)
    logger.info(f"Saved Financial Ratios -> {ratios_file} ({len(df_ratios)} records)")

    # 4. Export Individual Company Fundamentals
    symbols = sorted(set(df_annual["symbol"].dropna().unique()))
    logger.info(f"Exporting per-company files to {comp_dir} for {len(symbols)} companies...")
    for sym in symbols:
        sym_ann = df_annual[df_annual["symbol"] == sym]
        sym_qtr = df_quarterly[df_quarterly["symbol"] == sym]
        sym_rat = df_ratios[df_ratios["symbol"] == sym]

        # Combine annual & quarterly for individual stock sheet
        combined_sym = {
            "annual": sym_ann,
            "quarterly": sym_qtr,
            "ratios": sym_rat
        }
        sym_ann.to_csv(comp_dir / f"{sym}_annual.csv", index=False)
        if not sym_qtr.empty:
            sym_qtr.to_csv(comp_dir / f"{sym}_quarterly.csv", index=False)

    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"DATASET C FUNDAMENTALS PIPELINE COMPLETE ({elapsed:.2f}s)")
    logger.info(f"  Annual Statements:    {len(df_annual):,} records across {df_annual['symbol'].nunique()} companies")
    logger.info(f"  Quarterly Statements: {len(df_quarterly):,} records across {df_quarterly['symbol'].nunique()} companies")
    logger.info(f"  Financial Ratios:     {len(df_ratios):,} records across {df_ratios['symbol'].nunique()} companies")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PSX Fundamentals Scraper Pipeline (Dataset C)")
    parser.add_argument("--workers", type=int, default=10, help="Number of worker threads (default: 10)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of companies (for test)")
    parser.add_argument("--output-dir", type=str, default="data", help="Output directory (default: data)")
    args = parser.parse_args()

    run_pipeline(output_dir=args.output_dir, max_workers=args.workers, limit=args.limit)
