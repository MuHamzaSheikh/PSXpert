#!/usr/bin/env python3
"""
PSXpert - Master Data Engineering & Ingestion Runner
Orchestrates Phase 2 data pipeline:
1. Backs up and isolates raw data in data/raw/
2. Cleans, validates, and normalizes datasets in data/processed/
3. Initializes database tables and indexes
4. Ingests all tables with safe, idempotent conflict resolution
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.database.cleaner import PSXDataCleaner
from src.database.ingest import PSXDataIngestor
from init_db import init_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("IngestAll")


def run_pipeline(clean_only: bool = False, skip_clean: bool = False):
    start_total = time.time()
    logger.info("=" * 65)
    logger.info("PSXPERT PHASE 2 - DATA ENGINEERING & INGESTION PIPELINE")
    logger.info("=" * 65)

    cleaner = PSXDataCleaner()

    if not skip_clean:
        logger.info("\n--- STEP 1: DATA CLEANING & RAW/PROCESSED SEPARATION ---")
        cleaner.run_all()
        if clean_only:
            logger.info("Completed cleaning as requested (--clean-only). Exiting.")
            return

    logger.info("\n--- STEP 2: DATABASE SCHEMA INITIALIZATION ---")
    init_database(drop_existing=False)

    logger.info("\n--- STEP 3: HIGH-THROUGHPUT BULK INGESTION ---")
    ingestor = PSXDataIngestor()
    ingestor.run_all()

    elapsed = time.time() - start_total
    logger.info("\n" + "=" * 65)
    logger.info(f"PHASE 2 PIPELINE FULLY COMPLETED IN {elapsed:.2f}s")
    logger.info("Run 'python verify_db.py' to run integrity verification and join checks.")
    logger.info("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PSXpert Master Ingestion Pipeline")
    parser.add_argument("--clean-only", action="store_true", help="Run only the cleaning and separation step")
    parser.add_argument("--skip-clean", action="store_true", help="Skip cleaning and ingest existing processed data")
    args = parser.parse_args()

    run_pipeline(clean_only=args.clean_only, skip_clean=args.skip_clean)
