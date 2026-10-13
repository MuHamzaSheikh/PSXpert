# PSXpert: Pakistan Stock Exchange (PSX) & KSE-100 Dataset (2002–2026)

High-accuracy historical market data and analytics engine for the **Pakistan Stock Exchange (PSX)**, sourced directly from **Sarmaaya Financials** (`sarmaaya.pk`).

---

## 📊 Dataset Overview

| File Name | Description | Rows | Date Range | Size |
|---|---|---|---|---|
| [`data/kse100_index_history_2002_2026.csv`](file:///c:/Users/HP/psxpert/data/kse100_index_history_2002_2026.csv) | Full historical daily points for KSE-100 index | **6,127** | `2002-01-01` to `2026-10-13` | ~240 KB |
| [`data/kse100_stocks_historical_2002_2026.csv`](file:///c:/Users/HP/psxpert/data/kse100_stocks_historical_2002_2026.csv) | Master daily EOD records for all 100 KSE-100 stocks | **475,244** | `2002-01-01` to `2026-10-13` | ~29.3 MB |
| [`data/psx_companies_directory.csv`](file:///c:/Users/HP/psxpert/data/psx_companies_directory.csv) | Complete profiles with Sector, ISIN, and 52W High/Low | **100** | Active Listing | ~12 KB |
| [`data/kse100_constituents.csv`](file:///c:/Users/HP/psxpert/data/kse100_constituents.csv) | All 100 active constituent stocks of the KSE-100 | **100** | Snapshot | ~4.6 KB |
| [`data/psx_market_snapshot_ohlcv.csv`](file:///c:/Users/HP/psxpert/data/psx_market_snapshot_ohlcv.csv) | Full market OHLCV, 52W High/Low for all PSX stocks | **506** | Snapshot | ~95 KB |
| [`data/stocks_historical/`](file:///c:/Users/HP/psxpert/data/stocks_historical) | Directory of 100 individual stock historical CSV files | **100 files** | Inception to 2026 | ~30 MB |

---

## 📁 Repository Structure

```
psxpert/
├── data/
│   ├── kse100_index_history_2002_2026.csv      # KSE-100 Index historical daily closes
│   ├── kse100_stocks_historical_2002_2026.csv   # Combined master dataset (475,244 rows)
│   ├── psx_companies_directory.csv             # Sector and company metadata
│   ├── kse100_constituents.csv                 # 100 KSE-100 constituent tickers
│   ├── psx_market_snapshot_ohlcv.csv           # Full market OHLCV snapshot (506 stocks)
│   └── stocks_historical/                      # Individual CSV per stock
│       ├── ABL.csv
│       ├── ABOT.csv
│       ├── OGDC.csv
│       ├── LUCK.csv
│       ├── MCB.csv
│       └── ... (100 constituent stock files)
├── src/
│   ├── __init__.py
│   └── scraper.py                              # Core Sarmaaya PSX API scraper module
├── main.py                                     # Orchestrator to fetch all datasets
├── enrich_sectors.py                           # Sector enrichment script
├── verify_data.py                              # Dataset integrity and validation runner
├── requirements.txt                            # Python dependencies
└── README.md
```

---

## 📈 Data Fields & Schema

### 1. `kse100_index_history_2002_2026.csv`
* `date`: Trading date (`YYYY-MM-DD`).
* `symbol`: Index ticker (`KSE100`).
* `close`: Closing index value points (e.g. `164,776.44`).
* `change`: Daily point change (`+/-`).
* `change_pct`: Daily percentage change (`%`).

### 2. `kse100_stocks_historical_2002_2026.csv`
* `date`: Trading date (`YYYY-MM-DD`).
* `symbol`: PSX ticker symbol (e.g., `OGDC`, `LUCK`, `SYS`).
* `close`: Daily closing share price in PKR.
* `volume`: Daily traded volume in shares.
* `marketCap`: Total company market capitalization in PKR.
* `sector`: PSX industry sector classification (e.g., `OIL & GAS EXPLORATION COMPANIES`, `COMMERCIAL BANKS`, `FERTILIZER`, `CEMENT`).

### 3. `psx_market_snapshot_ohlcv.csv`
* `isin`: International Securities Identification Number.
* `name`: Registered corporate entity name.
* `symbol`: Stock ticker.
* `open`: Opening trading price.
* `high`: Day's high price.
* `low`: Day's low price.
* `close`: Closing price.
* `change`: Price change in PKR.
* `changepercentage`: Percentage price change.
* `date`: Market date.

---

## 🚀 How to Re-Run or Update Data

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Full Scraper Pipeline
```bash
python main.py
```

### 3. Verify Dataset Integrity
```bash
python verify_data.py
```

---

## 🔍 Note on Date Range
The earliest computerized daily record in Sarmaaya's database begins on **January 1, 2002** (`2002-01-01`), providing **24+ continuous years** (6,127 trading sessions) of verified Pakistan Stock Exchange daily data up to **October 2026**.
