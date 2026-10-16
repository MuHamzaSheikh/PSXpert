# PSXpert: Pakistan Stock Exchange (PSX) & KSE-100 Dataset (2002–2026)

High-accuracy historical market data, company fundamentals, financial news, and corporate announcements engine for the **Pakistan Stock Exchange (PSX)**, sourced directly from **Direct PSX Data Portal (DPS)** and **Sarmaaya Financials** (`sarmaaya.pk`).

---

## 📊 Dataset Overview

### Dataset A — PSX Stock Market & Index Data
| File Name | Description | Rows | Date Range | Size |
|---|---|---|---|---|
| [`data/kse100_index_history_2002_2026.csv`](file:///c:/Users/HP/psxpert/data/kse100_index_history_2002_2026.csv) | Full historical daily points for KSE-100 index | **6,127** | `2002-01-01` to `2026-10-13` | ~240 KB |
| [`data/kse100_stocks_historical_2002_2026.csv`](file:///c:/Users/HP/psxpert/data/kse100_stocks_historical_2002_2026.csv) | Master daily EOD records for all 100 KSE-100 stocks | **475,244** | `2002-01-01` to `2026-10-13` | ~29.3 MB |
| [`data/psx_companies_directory.csv`](file:///c:/Users/HP/psxpert/data/psx_companies_directory.csv) | Complete profiles with Sector, ISIN, and 52W High/Low | **100** | Active Listing | ~12 KB |
| [`data/kse100_constituents.csv`](file:///c:/Users/HP/psxpert/data/kse100_constituents.csv) | All 100 active constituent stocks of the KSE-100 | **100** | Snapshot | ~4.6 KB |
| [`data/psx_market_snapshot_ohlcv.csv`](file:///c:/Users/HP/psxpert/data/psx_market_snapshot_ohlcv.csv) | Full market OHLCV, 52W High/Low for all PSX stocks | **506** | Snapshot | ~95 KB |
| [`data/stocks_historical/`](file:///c:/Users/HP/psxpert/data/stocks_historical) | Directory of 100 individual stock historical CSV files | **100 files** | Inception to 2026 | ~30 MB |

### Dataset B — Financial News
| File Name | Description | Rows | Date Range | Size |
|---|---|---|---|---|
| [`data/financial_news.csv`](file:///c:/Users/HP/psxpert/data/financial_news.csv) | Financial news, symbols tagged, sectors, full body | **184** | Live / Multi-Year | ~615 KB |
| [`data/financial_news_historical_2002_2026.csv`](file:///c:/Users/HP/psxpert/data/financial_news_historical_2002_2026.csv) | Archive financial news spanning 2002 to 2026 | **64** | `2002-06-15` to `2026-10-13` | ~196 KB |

### Dataset C — Company Fundamentals
| File Name | Description | Rows | Periodicity | Size |
|---|---|---|---|---|
| [`data/kse100_fundamentals_annual.csv`](file:///c:/Users/HP/psxpert/data/kse100_fundamentals_annual.csv) | Master Annual Financial Statements & Balance Sheets | **543** | Annual (`ANN`) 2021–2026 | ~128 KB |
| [`data/kse100_fundamentals_quarterly.csv`](file:///c:/Users/HP/psxpert/data/kse100_fundamentals_quarterly.csv) | Master Quarterly Financial Statements & Performance | **399** | Quarterly (`QTR`) Q1–Q4 | ~60 KB |
| [`data/kse100_financial_ratios.csv`](file:///c:/Users/HP/psxpert/data/kse100_financial_ratios.csv) | Master Valuation, Solvency & Profitability Ratios | **543** | Annual Multi-Year | ~63 KB |
| [`data/fundamentals_company/`](file:///c:/Users/HP/psxpert/data/fundamentals_company) | Per-company breakdown CSV files (annual & quarterly) | **198 files** | Annual & Quarterly | ~200 KB |

### Dataset D — Corporate Announcements & Payouts
| File Name | Description | Rows | Category Breakdown | Size |
|---|---|---|---|---|
| [`data/kse100_corporate_announcements.csv`](file:///c:/Users/HP/psxpert/data/kse100_corporate_announcements.csv) | Master Corporate Announcements & Disclosures with official PSX PDFs | **20,884** | 5.4k Earnings, 1.6k Dividends, 1.5k Material, 12.3k Events | ~4.8 MB |
| [`data/kse100_corporate_payouts_2001_2026.csv`](file:///c:/Users/HP/psxpert/data/kse100_corporate_payouts_2001_2026.csv) | Master Historical Corporate Payouts (Dividends, Splits, Bonus Shares) | **2,336** | 2001 to 2026 (25 Years) | ~193 KB |
| [`data/announcements_company/`](file:///c:/Users/HP/psxpert/data/announcements_company) | Per-company announcements & payouts CSV files | **193 files** | All Constituent Companies | ~5.2 MB |

---

## 📁 Repository Structure

```
psxpert/
├── data/
│   ├── kse100_corporate_announcements.csv      # Dataset D: Master announcements (20,884 rows)
│   ├── kse100_corporate_payouts_2001_2026.csv  # Dataset D: Master payouts 2001-2026 (2,336 rows)
│   ├── announcements_company/                  # Dataset D: Per-company announcement & payout CSVs (193 files)
│   ├── kse100_fundamentals_annual.csv          # Dataset C: Master annual fundamentals (543 rows)
│   ├── kse100_fundamentals_quarterly.csv       # Dataset C: Master quarterly fundamentals (399 rows)
│   ├── kse100_financial_ratios.csv             # Dataset C: Valuation & solvency ratios (543 rows)
│   ├── fundamentals_company/                   # Dataset C: 198 individual company statement files
│   ├── financial_news.csv                      # Dataset B: 184 Financial news articles
│   ├── financial_news_historical_2002_2026.csv # Dataset B: 2002-2026 historical news archive
│   ├── kse100_index_history_2002_2026.csv      # Dataset A: KSE-100 Index historical daily closes
│   ├── kse100_stocks_historical_2002_2026.csv  # Dataset A: Combined master dataset (475,244 rows)
│   ├── psx_companies_directory.csv             # Dataset A: Sector and company metadata
│   ├── kse100_constituents.csv                 # Dataset A: 100 KSE-100 constituent tickers
│   ├── psx_market_snapshot_ohlcv.csv           # Dataset A: Full market OHLCV snapshot (506 stocks)
│   └── stocks_historical/                      # Dataset A: Individual CSV per stock (100 files)
├── src/
│   ├── __init__.py
│   ├── scraper.py                              # Dataset A: Core Sarmaaya PSX API scraper module
│   ├── news_scraper.py                         # Dataset B: Live financial news scraper & symbol tagger
│   ├── historical_news_scraper.py              # Dataset B: 2002-2026 archive news scraper
│   ├── fundamentals_scraper.py                 # Dataset C: DPS & Sarmaaya fundamentals scraper
│   └── announcements_scraper.py                # Dataset D: Corporate announcements & payouts scraper
├── main.py                                     # Orchestrator for Dataset A (Prices & Index)
├── scrape_news.py                              # Orchestrator for Dataset B (Live News)
├── scrape_historical_news.py                   # Orchestrator for Dataset B (Historical News)
├── scrape_fundamentals.py                      # Orchestrator for Dataset C (Company Fundamentals)
├── scrape_announcements.py                     # Orchestrator for Dataset D (Corporate Announcements)
├── verify_data.py                              # Dataset integrity and validation runner
├── requirements.txt                            # Python dependencies
└── README.md
```

---

## 📈 Data Fields & Schema

### 1. `kse100_corporate_announcements.csv` (Dataset D — Announcements)
* `symbol`: PSX ticker symbol (e.g. `OGDC`, `LUCK`, `MEBL`, `SYS`).
* `company_name`: Official corporate name.
* `sector`: PSX industry sector classification.
* `posting_date`: Announcement publication date (`YYYY-MM-DD`).
* `category`: Classified announcement category:
  - `Earnings Announcements`: Annual/interim financial results, financial statements, and reports.
  - `Dividends & Bonus Shares`: Book closure notices, dividend declarations, stock splits, entitlement letters.
  - `Material Disclosures`: Discoveries, well production, commercial operational updates, plant shutdowns/expansions, mergers/acquisitions.
  - `Corporate Events`: Board meetings, AGMs/EGMs, appointment/election of directors, resolutions.
* `announcement_title`: Full text headline/subject of the announcement.
* `announcement_id`: Unique PSX disclosure tracking identifier (e.g. `WAS-249475`).
* `document_url`: Direct download URL to official PSX exchange document / PDF.
* `attachment_url`: Scan or image attachment URL where applicable.

### 2. `kse100_corporate_payouts_2001_2026.csv` (Dataset D — Payouts)
* `symbol`: PSX ticker symbol.
* `company_name`: Official corporate name.
* `sector`: Industry sector.
* `announcement_date`: Date the corporate action was announced (`YYYY-MM-DD`).
* `fiscal_year`: Fiscal accounting year.
* `payout_type`: Action type (`dividend`, `split`, `bonus`).
* `dividend_per_share_pkr`: Dividend per share in PKR.
* `payout_percentage`: Percentage on face value (e.g. `60.0%`, `145.0%`).
* `face_value_pkr`: Nominal face value per share (e.g. `10.0`, `2.0`).

### 3. `kse100_fundamentals_annual.csv` (Dataset C — Annual Statements)
* `symbol`: PSX ticker symbol.
* `company_name`: Official corporate name.
* `sector`: Industry sector classification.
* `periodicity`: `ANN` (Annual fiscal reporting period).
* `fiscal_year`: Fiscal year (e.g. `2026`, `2025`, `2024`, `2023`, `2022`, `2021`).
* `period_end_date`: End date of the fiscal year (`YYYY-MM-DD`).
* `revenue_sales`: Gross Revenue / Sales / Mark-up earned (in thousand PKR).
* `gross_profit`: Gross Profit after Cost of Goods Sold.
* `operating_profit`: Operating Profit (EBIT).
* `net_profit_after_tax`: Net Profit After Tax / Profit after taxation.
* `eps_basic`: Basic Earnings Per Share (PKR).
* `eps_diluted`: Diluted Earnings Per Share (PKR).
* `total_assets`: Total Assets on the Balance Sheet.
* `current_assets`: Total Current Assets.
* `cash_and_equivalents`: Cash & short-term liquid equivalents.
* `net_ppe`: Property, Plant & Equipment (Net PPE).
* `total_liabilities`: Total Liabilities.
* `current_liabilities`: Total Current Liabilities.
* `total_debt`: Total borrowings & debt obligations (Short-term + Long-term).
* `shareholders_equity`: Total Stockholders' Equity.
* `retained_earnings`: Cumulative Retained Earnings.
* `common_shares_outstanding`: Total common shares issued (thousands).
* `operating_cash_flow`: Net Cash Flow from Operating Activities (CFO).
* `capital_expenditures`: Capital Expenditures (Capex).
* `investing_cash_flow`: Net Cash Flow from Investing Activities (CFI).
* `financing_cash_flow`: Net Cash Flow from Financing Activities (CFF).
* `dividends_paid`: Total dividends paid to shareholders.
* `free_cash_flow`: Free Cash Flow (FCF = CFO - Capex).

### 4. `kse100_fundamentals_quarterly.csv` (Dataset C — Quarterly Statements)
* `symbol`, `company_name`, `sector`, `periodicity` (`QTR`), `fiscal_year`, `fiscal_quarter` (`Q1` to `Q4`), `period_end_date`, `revenue_sales`, `gross_profit`, `operating_profit`, `net_profit_after_tax`, `eps`, `total_assets`, `total_liabilities`, `total_debt`, `shareholders_equity`, `operating_cash_flow`, `free_cash_flow`.

### 5. `kse100_financial_ratios.csv` (Dataset C — Ratios & Metrics)
* `symbol`, `company_name`, `sector`, `fiscal_year`, `pe_ratio`, `pb_ratio`, `ps_ratio`, `enterprise_value`, `ev_to_ebitda`, `debt_to_equity_pct`, `debt_to_asset_pct`, `current_ratio`, `quick_ratio`, `return_on_equity_pct` (ROE), `return_on_assets_pct` (ROA), `gross_profit_margin_pct`, `net_profit_margin_pct`, `operating_margin_pct`, `dividend_yield_pct`, `dividend_per_share`, `book_value_per_share`, `free_cash_flow_per_share`, `eps_growth_pct`, `peg_ratio`.

---

## 🚀 How to Run or Update All Datasets

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Dataset A (PSX & KSE-100 Daily Prices 2002–2026)
```bash
python main.py
```

### 3. Run Dataset B (Financial News & Historical Archives)
```bash
python scrape_news.py
python scrape_historical_news.py
```

### 4. Run Dataset C (Company Fundamentals: Annual & Quarterly)
```bash
python scrape_fundamentals.py
```

### 5. Run Dataset D (Corporate Announcements & Payouts)
```bash
python scrape_announcements.py
```

### 6. Verify All Datasets Integrity
```bash
python verify_data.py
```

---

## 🏛️ Phase 2: Database & Data Engineering Layer

The raw PSXpert datasets are cleaned, typed, and structured into a relational data layer designed for AI backtesting, predictive modeling, and quantitative analysis.

### Dual Engine Architecture
* **PostgreSQL (Production)**: Connects automatically via `.env` (`DATABASE_URL` or standard PG credentials).
* **SQLite (Zero-Configuration Fallback)**: Automatically active if PostgreSQL is offline or unconfigured, storing local data in `data/psxpert.db`.

### Database Schema & Tables
| Table | Primary / Unique Key | Description | Records |
|---|---|---|---|
| `data_sources` | `id` (PK), `source_name` (Unique) | Data provenance tracking, retrieval timestamps, API endpoints | 4 |
| `companies` | `symbol` (PK) | PSX symbols, corporate names, sectors, ISINs, Shariah/KSE-100 flags | 100 |
| `stock_prices` | `(symbol, trading_date)` (Unique) | Daily OHLCV, market cap (2002–2026). Strictly 0 duplicates | 475,244 |
| `market_indices` | `(index_symbol, trading_date)` (Unique) | Historical index points, volume, and percentage changes | 6,127 |
| `news_articles` | `(publisher, url)` (Unique) | Headlines, publishers, ISO-8601 timestamps, full article text | 184 |
| `news_entities` | `(article_id, entity_type, entity_value)` (Unique) | Article-to-company and article-to-sector tag mappings | 708 |
| `news_sentiment` | `(article_id, model_name)` (Unique) | Sentiment labels (POSITIVE/NEGATIVE/NEUTRAL) & polarity scores | 184 |
| `company_financials` | `(symbol, fiscal_year, fiscal_period, metric_name)` (Unique) | Financial line items with **both accounting period & official publication filing dates** | 14,489 |
| `corporate_announcements`| `(symbol, announcement_id)` (Unique) | Official regulatory disclosures & direct exchange PDF links | 20,884 |
| `corporate_payouts` | `(symbol, announcement_date, payout_type)` (Unique) | Dividends, splits, bonus shares with payout rates | 1,727 |

### Core Data Engineering Rules
1. **Unique Key Enforcement**: Daily stock prices use composite key `(symbol, trading_date)` with zero duplicates.
2. **Timezone Preservation**: Timestamps are normalized to ISO-8601 preserving Pakistan Standard Time (`+05:00`).
3. **Zero Lookahead Bias in Backtesting**:
   - `company_financials` explicitly stores `publication_date` alongside `period_end_date`.
   - AI backtesting models must query:
     ```sql
     WHERE publication_date <= :prediction_timestamp
     ```
   - Verified across 13,371+ financial records where `publication_date >= period_end_date`.
4. **Strict Data Separation**:
   - `data/raw/`: Untouched, immutable scrapings.
   - `data/processed/`: Standardized, deduplicated, and typed CSVs.
5. **Idempotent Ingestion**: Safe to retry at any time (`ON CONFLICT DO UPDATE` in PostgreSQL; `INSERT OR REPLACE` in SQLite).

### Running Phase 2 Commands
```bash
# 1. Clean raw data and bulk-ingest into database
python ingest_all.py

# 2. Run verification suite (counts, unique constraints, and joins)
python verify_db.py
```

---

## 🧠 Phase 3 — News Sentiment Analysis & FinBERT Benchmark

Phase 3 transforms unstructured Pakistani financial news into clean, quantitative sentiment signals, distinguishing overall article tone from target-specific impact on individual PSX equities.

### 1. Sentiment Processing Pipeline Architecture
The end-to-end pipeline (`src/sentiment/pipeline.py`) operates in five deterministic stages:
1. **Text Preprocessing & Deduplication (`cleaner.py`)**:
   - Strips publisher bylines, HTML boilerplate, boilerplate disclaimers, and wire stamps.
   - SHA-256 fingerprinting for near-duplicate and exact-duplicate deduplication.
   - ISO-639-1 language detection (`langdetect`) ensuring non-English articles are flagged.
2. **Entity & Sector Mapping (`entity_matcher.py`)**:
   - Maps company names and ticker aliases across 800+ PSX stocks (`OGDC`, `LUCK`, `MEBL`, `SYS`, `HUBC`, `HBL`, etc.).
   - Resolves 11 PSX industry sectors (`Commercial Banks`, `Cement`, `Oil & Gas Exploration`, `Power Generation`, `Technology`, etc.).
   - Extracts target-specific sentence contexts for aspect-based sentiment analysis.
3. **Sentiment Model Scoring**:
   - **Baseline Model (`lexicon_baseline.py`)**: Enhanced VADER + Loughran-McDonald financial dictionary augmented with 50+ Pakistani market idioms (`circular debt`, `bourse rally`, `policy rate cut`, `IMF tranche`, `gas tariff hike`, `selling pressure`).
   - **Transformer Model (`finbert_analyzer.py`)**: Pretrained `ProsusAI/finbert` model evaluating probabilities across `POSITIVE`, `NEGATIVE`, and `NEUTRAL`, outputting continuous scores in `[-1.0, +1.0]`.
4. **Target-Specific vs. Article-Level Sentiment**:
   - When an article discusses multiple companies (e.g., *Lucky Cement expands exports while DG Khan Cement faces plant closure*), FinBERT calculates individual target sentiment per company symbol rather than applying a single uniform label.
5. **Database Persistence**:
   - Upserts sentiment scores, class probabilities, and target-specific metadata into `news_sentiment`.
   - Links entities with confidence weights into `news_entities`, preserving publication timestamps for backtesting.

### 2. Benchmark Evaluation (50 Gold-Standard Pakistani News Samples)
A representative benchmark was curated and manually labelled across major PSX sectors. FinBERT demonstrated significant superiority over the lexicon baseline (+22.0% accuracy improvement):

| Metric | Lexicon Baseline | FinBERT Transformer | Delta |
|---|---|---|---|
| **Overall Accuracy** | 64.00% | **86.00%** | **+22.0%** |
| **Macro F1-Score** | 0.6405 | **0.8550** | **+0.2145** |
| **Weighted F1-Score** | 0.6421 | **0.8594** | **+0.2173** |
| **Positive Class F1** | 0.6341 | **0.9444** | **+0.3103** |
| **Negative Class F1** | 0.6667 | **0.8205** | **+0.1538** |
| **Neutral Class F1** | 0.6207 | **0.8000** | **+0.1793** |

#### Confusion Matrices (Rows: Ground Truth, Columns: Predicted)

**Lexicon Baseline Confusion Matrix**:
```
True \ Pred    |   POSITIVE |   NEGATIVE |    NEUTRAL
POSITIVE       |         13 |          2 |          3
NEGATIVE       |          5 |         10 |          3
NEUTRAL        |          5 |          0 |          9
```

**FinBERT Transformer Confusion Matrix**:
```
True \ Pred    |   POSITIVE |   NEGATIVE |    NEUTRAL
POSITIVE       |         17 |          1 |          0
NEGATIVE       |          1 |         16 |          1
NEUTRAL        |          0 |          4 |         10
```

### 3. Pakistani Domain Nuances & Error Analysis
- **Contextual Semantics**: FinBERT successfully disambiguates negative regulatory events (e.g. *"NEPRA slashes return on equity for IPPs"*) where lexicon tools falsely triggered positive scores due to words like *"return"* and *"equity"*.
- **SBP Policy Rate Dynamics**: In Pakistani equity markets, State Bank rate cuts reliably trigger strong rallies (positive for equities due to reduced financial leverage costs), whereas international models can mistakenly view rate cuts as signals of banking margin contraction.
- **Regulatory Disclosures**: FinBERT cleanly categorizes administrative board meetings, AGM notices, and book closures as `NEUTRAL`, avoiding false trading signals.

### 4. Running Phase 3 Commands
```bash
# 1. Run the full benchmark evaluation suite
python evaluate_sentiment.py

# 2. Run the end-to-end production sentiment pipeline on PostgreSQL database
python run_sentiment_pipeline.py
```

---

## 💻 Phase 4 — Interactive Web Trading Terminal & Pattern Suite

PSXpert features a TradingView / Bloomberg Terminal-grade web application powered by **FastAPI** and **PostgreSQL 18**, offering real-time candlestick charting, mathematical pattern recognition, and FinBERT sentiment intelligence.

### 1. Terminal Features
- **TradingView Lightweight Charts Integration**: Smooth 60fps rendering of daily OHLCV candlesticks with custom emerald green (`#00f59b`) and crimson red (`#ff3366`) candles.
- **Mathematical Candlestick Pattern Recognition**: 20+ classical patterns detected in real-time (*Morning Star*, *Evening Star*, *Hammer*, *Inverted Hammer*, *Bullish/Bearish Engulfing*, *Piercing Line*, *Three White Soldiers*, *Three Black Crows*, *Doji*).
- **Interactive Visual Pattern Markers**: Clickable markers plotted directly onto candlestick bars showing pattern classification, trading signals, and technical rationale.
- **Technical Indicators**: One-click toggles for EMA 20 (Cyan), EMA 50 (Gold), EMA 200 (Purple), and Volume Subplots.
- **PSX Watchlist & Sector Filters**: Live directory of 800+ listed equities with sector filtering, top gainers, top losers, and highest-volume tickers.
- **FinBERT Market Catalyst News Feed**: Phase 3 sentiment-tagged headlines with confidence ratings linked to active stocks.
- **Live Ticker Tape**: Marquee header streaming real-time prices for KSE-100 and constituent equities.

### 2. Launching the Web Terminal
```bash
# Start the FastAPI server daemon
python -m uvicorn app:app --host 127.0.0.1 --port 8000

# Open in browser
# http://127.0.0.1:8000/
```

---

## 🔍 Provenance & Methodology
- **Prices & Indices**: Daily settlement records from Sarmaaya API and PSX Data Portal covering 2002–2026 (6,127 trading sessions).
- **News**: Multi-source financial articles from Dawn Business and Business Recorder with automated NLP ticker detection and sector mapping.
- **Fundamentals**: Harmonized financial statements merging official audited PSX exchange reports (DPS) with balance sheets, cash flow statements, and valuation ratios from Sarmaaya REST API. Both non-financial corporates and commercial banking models are standardized.
- **Announcements & Payouts**: Verified PSX regulatory disclosures mapped to direct PSX exchange PDF documents, covering 25 years of dividends, bonus distributions, and stock splits alongside 20,800+ categorised corporate disclosures.

