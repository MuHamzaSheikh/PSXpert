# PSXpert: Pakistan Stock Exchange (PSX) & KSE-100 Dataset (2002–2026)

High-accuracy historical market data, company fundamentals, and financial news engine for the **Pakistan Stock Exchange (PSX)**, sourced directly from **Direct PSX Data Portal (DPS)** and **Sarmaaya Financials** (`sarmaaya.pk`).

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

---

## 📁 Repository Structure

```
psxpert/
├── data/
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
│   └── fundamentals_scraper.py                 # Dataset C: DPS & Sarmaaya fundamentals scraper
├── main.py                                     # Orchestrator for Dataset A (Prices & Index)
├── scrape_news.py                              # Orchestrator for Dataset B (Live News)
├── scrape_historical_news.py                   # Orchestrator for Dataset B (Historical News)
├── scrape_fundamentals.py                      # Orchestrator for Dataset C (Company Fundamentals)
├── verify_data.py                              # Dataset integrity and validation runner
├── requirements.txt                            # Python dependencies
└── README.md
```

---

## 📈 Data Fields & Schema

### 1. `kse100_fundamentals_annual.csv` (Dataset C — Annual Statements)
* `symbol`: PSX ticker symbol (e.g. `OGDC`, `LUCK`, `MEBL`, `SYS`).
* `company_name`: Official registered corporate name.
* `sector`: PSX industry sector classification.
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

### 2. `kse100_fundamentals_quarterly.csv` (Dataset C — Quarterly Statements)
* `symbol`: PSX ticker symbol.
* `company_name`: Official corporate name.
* `sector`: PSX sector classification.
* `periodicity`: `QTR` (Quarterly reporting period).
* `fiscal_year`: Fiscal year.
* `fiscal_quarter`: Reporting quarter (`Q1`, `Q2`, `Q3`, `Q4`).
* `period_end_date`: Quarter-end reporting date.
* `revenue_sales`: Quarterly revenue / net sales / mark-up.
* `gross_profit`: Quarterly gross profit.
* `operating_profit`: Quarterly operating profit.
* `net_profit_after_tax`: Quarterly net profit after taxation.
* `eps`: Quarterly Earnings Per Share (PKR).
* `total_assets`: Total balance sheet assets at quarter end.
* `total_liabilities`: Total balance sheet liabilities at quarter end.
* `total_debt`: Total debt obligations at quarter end.
* `shareholders_equity`: Total equity at quarter end.
* `operating_cash_flow`: Quarterly Operating Cash Flow.
* `free_cash_flow`: Quarterly Free Cash Flow.

### 3. `kse100_financial_ratios.csv` (Dataset C — Ratios & Metrics)
* `symbol`: PSX ticker symbol.
* `company_name`: Corporate name.
* `sector`: Industry sector.
* `fiscal_year`: Fiscal year.
* `pe_ratio`: Price-to-Earnings Ratio (P/E).
* `pb_ratio`: Price-to-Book Ratio (P/B).
* `ps_ratio`: Price-to-Sales Ratio (P/S).
* `enterprise_value`: Enterprise Value (EV).
* `ev_to_ebitda`: Enterprise Value to EBITDA multiple.
* `debt_to_equity_pct`: Debt-to-Equity ratio (%).
* `debt_to_asset_pct`: Debt-to-Asset ratio (%).
* `current_ratio`: Current ratio (Liquidity).
* `quick_ratio`: Quick / Acid-test ratio.
* `return_on_equity_pct`: Return on Equity (ROE %).
* `return_on_assets_pct`: Return on Assets (ROA %).
* `gross_profit_margin_pct`: Gross Profit Margin (%).
* `net_profit_margin_pct`: Net Profit Margin (%).
* `operating_margin_pct`: Operating Margin (%).
* `dividend_yield_pct`: Dividend Yield (%).
* `dividend_per_share`: Dividends Per Share (DPS in PKR).
* `book_value_per_share`: Book Value Per Share (BVPS in PKR).
* `free_cash_flow_per_share`: Free Cash Flow Per Share (PKR).
* `eps_growth_pct`: Year-over-Year EPS Growth (%).
* `peg_ratio`: Price/Earnings to Growth Ratio (PEG).

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
# Live & recent news with full text extraction
python scrape_news.py

# Multi-year historical news archives (2002–2026)
python scrape_historical_news.py
```

### 4. Run Dataset C (Company Fundamentals: Annual & Quarterly)
```bash
python scrape_fundamentals.py
```

### 5. Verify All Datasets Integrity
```bash
python verify_data.py
```

---

## 🔍 Provenance & Methodology
- **Prices & Indices**: Daily settlement records from Sarmaaya API and PSX Data Portal covering 2002–2026 (6,127 trading sessions).
- **News**: Multi-source financial articles from Dawn Business and Business Recorder with automated NLP ticker detection and sector mapping.
- **Fundamentals**: Harmonized financial statements merging official audited PSX exchange reports (DPS) with balance sheets, cash flow statements, and valuation ratios from Sarmaaya REST API. Both non-financial corporates and commercial banking models are standardized.
