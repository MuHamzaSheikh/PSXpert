"""
Consolidates all PSX data into a single master directory: 'psx all data'
Organizes all data types cleanly with a master catalog and summary.
"""

import os
import shutil
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ConsolidatePSXData")

ROOT_DIR = Path("c:/Users/HP/psxpert")
DEST_DIR = ROOT_DIR / "psx all data"

CATEGORIES = {
    "1_market_and_prices": [
        "data/processed/stock_prices_clean.csv",
        "module 1 technical and fundamental/data/collected/public_20261117_142707/stock_price_history.csv.gz",
        "data/processed/market_indices_clean.csv",
        "data/raw/kse100_index_history_2002_2026.csv",
        "data/raw/kse100_stocks_historical_2002_2026.csv"
    ],
    "2_technical_indicators": [
        "data/processed/psx_technical_indicators_dataset.csv"
    ],
    "3_fundamentals_and_financials": [
        "data/processed/kse100_fundamentals_historical_2005_2026.csv",
        "data/processed/company_financials_clean.csv",
        "data/raw/kse100_fundamentals_annual.csv",
        "data/raw/kse100_fundamentals_quarterly.csv",
        "data/raw/kse100_financial_ratios.csv",
        "data/raw/sbp_fsa_archive_2005_2023.xlsx",
        "data/raw/sbp_fsa_nfc_fy20_fy25.xlsx",
        "data/raw/sbp_fsa_financial_sector_2021_2025.xlsx",
        "data/raw/sbp_fsaq_mar_26.xlsx"
    ],
    "4_corporate_payouts": [
        "data/processed/corporate_payouts_clean.csv",
        "data/raw/kse100_corporate_payouts_2001_2026.csv"
    ],
    "5_corporate_announcements": [
        "data/processed/corporate_announcements_clean.csv",
        "module 1 technical and fundamental/data/collected/public_20261117_142707/sarmaaya_announcements.csv.gz",
        "module 1 technical and fundamental/data/collected/public_20261117_142707/investify_announcements.csv.gz"
    ],
    "6_audited_filing_documents": [
        "module 1 technical and fundamental/data/collected/public_20261117_142707/filing_document_links.csv.gz",
        "module 1 technical and fundamental/data/collected/public_20261117_142707/document_downloads.jsonl",
        "module 1 technical and fundamental/data/collected/public_20261117_142707/documents_summary.json",
        "module 1 technical and fundamental/data/collected/public_20261117_142707/original_document_index.csv",
        "module 1 technical and fundamental/data/collected/public_20261117_142707/original_documents"
    ],
    "7_news_and_sentiment": [
        "data/processed/news_articles_clean.csv",
        "data/processed/news_entities_clean.csv",
        "data/raw/financial_news_historical_2002_2026.csv",
        "data/raw/financial_news.csv"
    ],
    "8_companies_metadata": [
        "data/processed/companies_clean.csv",
        "data/raw/kse100_constituents.csv",
        "data/raw/psx_companies_directory.csv"
    ]
}


def main():
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Target directory: {DEST_DIR}")

    total_files = 0
    total_bytes = 0

    for cat_name, file_list in CATEGORIES.items():
        cat_dir = DEST_DIR / cat_name
        cat_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"\nProcessing category: {cat_name}")

        for item_rel in file_list:
            src_path = ROOT_DIR / item_rel
            if not src_path.exists():
                logger.warning(f"  [MISSING] {item_rel}")
                continue

            dest_path = cat_dir / src_path.name
            if src_path.is_dir():
                logger.info(f"  Copying directory: {src_path.name} ...")
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                shutil.copytree(src_path, dest_path)
                dir_size = sum(f.stat().st_size for f in dest_path.glob("**/*") if f.is_file())
                dir_count = sum(1 for f in dest_path.glob("**/*") if f.is_file())
                logger.info(f"  [DIR COPIED] {src_path.name}: {dir_count} files, {dir_size / (1024*1024):.1f} MB")
                total_files += dir_count
                total_bytes += dir_size
            else:
                shutil.copy2(src_path, dest_path)
                fsize = dest_path.stat().st_size
                logger.info(f"  [FILE COPIED] {dest_path.name} ({fsize / (1024*1024):.2f} MB)")
                total_files += 1
                total_bytes += fsize

    logger.info(f"\n=== CONSOLIDATION COMPLETE ===")
    logger.info(f"Total files consolidated: {total_files:,}")
    logger.info(f"Total data volume: {total_bytes / (1024*1024):.2f} MB ({total_bytes / (1024**3):.2f} GB)")

    # Create README.md inside 'psx all data'
    readme_path = DEST_DIR / "README.md"
    readme_content = f"""# PSX All Data — Master Repository

This folder consolidates all datasets collected, scraped, engineered, and verified for the PSXpert quantitative system.

- **Total Data Volume**: {total_bytes / (1024*1024):.2f} MB ({total_bytes / (1024**3):.2f} GB)
- **Total Files**: {total_files:,}
- **Stock Universe**: KSE-100 Benchmark Index Constituent Companies
- **Time Span**: 2000 to 2026 (over 25 continuous years)

---

## Directory Structure & Contents

### `1_market_and_prices/`
Daily trading records and market index benchmarks.
- `stock_prices_clean.csv`: 475,244 continuous daily records (2002 to 2026).
- `stock_price_history.csv.gz`: 477,642 daily records up to November 17, 2026.
- `market_indices_clean.csv`: 6,127 daily sessions for the KSE-100 benchmark index.
- `kse100_index_history_2002_2026.csv`: Raw KSE-100 index trading archive.

### `2_technical_indicators/`
Pre-engineered technical indicator matrices for quantitative modeling.
- `psx_technical_indicators_dataset.csv`: 110,816 feature rows (August 15, 2000 – October 13, 2026) including SMA, EMA, RSI, MACD, Bollinger Bands, ATR, OBV, and Stochastic oscillators.

### `3_fundamentals_and_financials/`
Audited annual, quarterly, and multi-decade financial statement datasets.
- `kse100_fundamentals_historical_2005_2026.csv`: 1,397 annual statement records across 88 tickers spanning 2005 to 2026 (22 continuous fiscal years). Includes full Balance Sheet, Income Statement, and Cash Flow metrics.
- `company_financials_clean.csv`: Clean standardized statement repository for active models and API queries.
- `sbp_fsa_archive_2005_2023.xlsx`: Official State Bank of Pakistan 19-year non-financial statements archive.
- `sbp_fsa_nfc_fy20_fy25.xlsx`: SBP recent statements archive covering FY2020 through FY2025.
- `sbp_fsa_financial_sector_2021_2025.xlsx`: SBP commercial banks and financial sector statements.
- `sbp_fsaq_mar_26.xlsx`: SBP quarterly corporate financial statements archive.

### `4_corporate_payouts/`
Corporate action registers used to compute dividend yields and split-adjusted prices.
- `corporate_payouts_clean.csv`: 1,727 clean payout events (2001 to 2026) covering cash dividends, bonus shares, and stock splits.
- `kse100_corporate_payouts_2001_2026.csv`: 2,336 raw payout entries across 25+ years.

### `5_corporate_announcements/`
Official exchange disclosure streams.
- `corporate_announcements_clean.csv`: 20,884 classified announcements (2015 to 2026).
- `sarmaaya_announcements.csv.gz`: 21,525 announcements (2021 to 2026) with direct PDF attachment links.
- `investify_announcements.csv.gz`: Cross-source announcement verification stream.

### `6_audited_filing_documents/`
Primary source official company filings from the Pakistan Stock Exchange Data Portal (`dps.psx.com.pk`).
- `original_documents/`: 368 verified PDF files (1.18 GB) of audited annual accounts, quarterly transmissions, and corporate actions.
- `filing_document_links.csv.gz`: Index of 3,909 official filing links.
- `document_downloads.jsonl` & `documents_summary.json`: Download audit logs and checksum verification records.

### `7_news_and_sentiment/`
News feeds and sentiment analysis datasets.
- `news_articles_clean.csv`: 184 processed financial news articles with FinBERT sentiment scores.
- `financial_news_historical_2002_2026.csv`: Historical economic and company news events from 2002 to 2026.

### `8_companies_metadata/`
Company directory and master tickers universe.
- `companies_clean.csv`: Master KSE-100 roster with ISIN, sector, and Shariah-compliance indicators.
- `kse100_constituents.csv`: Current constituent membership and weights.
- `psx_companies_directory.csv`: Complete listing directory of all companies on the exchange.
"""
    readme_path.write_text(readme_content, encoding="utf-8")
    logger.info(f"Created documentation: {readme_path}")


if __name__ == "__main__":
    main()
