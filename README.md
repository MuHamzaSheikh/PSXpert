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

## 🔍 Provenance & Methodology
- **Prices & Indices**: Daily settlement records from Sarmaaya API and PSX Data Portal covering 2002–2026 (6,127 trading sessions).
- **News**: Multi-source financial articles from Dawn Business and Business Recorder with automated NLP ticker detection and sector mapping.
- **Fundamentals**: Harmonized financial statements merging official audited PSX exchange reports (DPS) with balance sheets, cash flow statements, and valuation ratios from Sarmaaya REST API. Both non-financial corporates and commercial banking models are standardized.
- **Announcements & Payouts**: Verified PSX regulatory disclosures mapped to direct PSX exchange PDF documents, covering 25 years of dividends, bonus distributions, and stock splits alongside 20,800+ categorised corporate disclosures.
