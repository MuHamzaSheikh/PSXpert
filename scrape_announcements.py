#!/usr/bin/env python3
"""
PSXpert - Master Corporate Announcements & Payouts Pipeline (Dataset D)
Scrapes, categorizes, and exports comprehensive corporate announcements for all KSE-100 listed companies:
- Earnings announcements
- Dividends and bonus shares (payouts 2001-2026)
- Material company disclosures
- Other relevant corporate events (AGMs, board meetings, director changes)

Outputs:
- data/kse100_corporate_announcements.csv
- data/kse100_corporate_payouts_2001_2026.csv
- data/announcements_company/{symbol}_announcements.csv
- data/announcements_company/{symbol}_payouts.csv
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.announcements_scraper import PSXAnnouncementsScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ScrapeAnnouncementsPipeline")


def run_pipeline(output_dir: str = "data", max_workers: int = 12, limit: int = None):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    comp_dir = out_path / "announcements_company"
    comp_dir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    logger.info("Initializing PSX Corporate Announcements Pipeline (Dataset D)...")
    scraper = PSXAnnouncementsScraper(directory_path=str(out_path / "psx_companies_directory.csv"))

    target_count = limit if limit else len(scraper.companies_df)
    logger.info(f"Targeting {target_count} KSE-100 companies with {max_workers} worker threads...")

    # Execute scraping
    df_announcements, df_payouts = scraper.process_all_companies(
        max_workers=max_workers,
        limit=limit
    )

    # 1. Export Master Corporate Announcements
    announcements_file = out_path / "kse100_corporate_announcements.csv"
    df_announcements.to_csv(announcements_file, index=False)
    logger.info(f"Saved Master Announcements -> {announcements_file} ({len(df_announcements):,} records)")

    # 2. Export Master Corporate Payouts (2001-2026)
    payouts_file = out_path / "kse100_corporate_payouts_2001_2026.csv"
    df_payouts.to_csv(payouts_file, index=False)
    logger.info(f"Saved Master Payouts -> {payouts_file} ({len(df_payouts):,} records)")

    # 3. Export Per-Company Files
    symbols = sorted(set(list(df_announcements["symbol"].unique()) + list(df_payouts["symbol"].unique())))
    logger.info(f"Exporting per-company files to {comp_dir} for {len(symbols)} companies...")
    for sym in symbols:
        sym_ann = df_announcements[df_announcements["symbol"] == sym]
        sym_pay = df_payouts[df_payouts["symbol"] == sym]

        if not sym_ann.empty:
            sym_ann.to_csv(comp_dir / f"{sym}_announcements.csv", index=False)
        if not sym_pay.empty:
            sym_pay.to_csv(comp_dir / f"{sym}_payouts.csv", index=False)

    elapsed = time.time() - start_time
    logger.info("=" * 65)
    logger.info(f"DATASET D CORPORATE ANNOUNCEMENTS PIPELINE COMPLETE ({elapsed:.2f}s)")
    logger.info(f"  Total Announcements:   {len(df_announcements):,} records across {df_announcements['symbol'].nunique()} companies")
    if not df_announcements.empty and "category" in df_announcements.columns:
        cat_counts = df_announcements["category"].value_counts().to_dict()
        for cat, cnt in cat_counts.items():
            logger.info(f"    - {cat:<26s}: {cnt:>5,} records")
    logger.info(f"  Total Payouts:         {len(df_payouts):,} records across {df_payouts['symbol'].nunique()} companies")
    if not df_payouts.empty and "payout_type" in df_payouts.columns:
        p_counts = df_payouts["payout_type"].value_counts().to_dict()
        for pt, cnt in p_counts.items():
            logger.info(f"    - {pt:<26s}: {cnt:>5,} records")
    logger.info("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PSX Corporate Announcements Pipeline (Dataset D)")
    parser.add_argument("--workers", type=int, default=12, help="Number of worker threads (default: 12)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of companies (for test)")
    parser.add_argument("--output-dir", type=str, default="data", help="Output directory (default: data)")
    args = parser.parse_args()

    run_pipeline(output_dir=args.output_dir, max_workers=args.workers, limit=args.limit)
