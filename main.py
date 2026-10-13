import os
import sys
import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.scraper import SarmayaPSXScraper

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
STOCKS_DIR = os.path.join(DATA_DIR, "stocks_historical")


def main():
    print("=" * 70)
    print("PSXpert: Pakistan Stock Exchange (PSX) & KSE-100 Data Scraper")
    print("Source: Sarmaaya (https://sarmaaya.pk)")
    print("=" * 70)

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(STOCKS_DIR, exist_ok=True)

    scraper = SarmayaPSXScraper()

    # -------------------------------------------------------------
    # 1. Scrape KSE-100 Index Historical Data (2002 - 2026)
    # -------------------------------------------------------------
    print("\n[Step 1/5] Scraping KSE-100 Index Historical Data...")
    df_index = scraper.get_kse100_index_history(days=15000)
    if not df_index.empty:
        index_csv_path = os.path.join(DATA_DIR, "kse100_index_history_2002_2026.csv")
        # Format columns cleanly
        export_df = df_index[["date_formatted", "symbol", "close"]].copy()
        export_df.rename(columns={"date_formatted": "date"}, inplace=True)
        # Calculate daily change and change percentage
        export_df["change"] = export_df["close"].diff().round(2)
        export_df["change_pct"] = (
            (export_df["change"] / export_df["close"].shift(1)) * 100
        ).round(2)
        export_df.to_csv(index_csv_path, index=False)
        print(
            f"-> KSE-100 Index: {len(export_df)} records saved to {index_csv_path}"
        )
        print(
            f"   Date range: {export_df['date'].iloc[0]} to {export_df['date'].iloc[-1]}"
        )
        print(f"   Latest Index Close: {export_df['close'].iloc[-1]:,.2f}")
    else:
        print("-> Warning: KSE-100 Index data could not be retrieved.")

    # -------------------------------------------------------------
    # 2. Scrape KSE-100 Constituents
    # -------------------------------------------------------------
    print("\n[Step 2/5] Scraping KSE-100 Constituent Stocks...")
    df_constituents = scraper.get_kse100_constituents()
    constituents_csv_path = os.path.join(DATA_DIR, "kse100_constituents.csv")
    df_constituents.to_csv(constituents_csv_path, index=False)
    kse100_symbols = df_constituents["symbol"].tolist()
    print(
        f"-> KSE-100 Constituents: {len(kse100_symbols)} stocks saved to {constituents_csv_path}"
    )

    # -------------------------------------------------------------
    # 3. Scrape All PSX Stocks Snapshot & Directory (with Sectors)
    # -------------------------------------------------------------
    print("\n[Step 3/5] Scraping PSX Stocks Snapshot & Company Sectors...")
    df_snapshot = scraper.get_all_stocks_snapshot()
    snapshot_csv_path = os.path.join(DATA_DIR, "psx_market_snapshot_ohlcv.csv")
    df_snapshot.to_csv(snapshot_csv_path, index=False)
    print(
        f"-> Market Snapshot: {len(df_snapshot)} listed stocks saved to {snapshot_csv_path}"
    )

    # Fetch sector details for KSE-100 stocks
    print("\n[Step 3b/5] Enriching KSE-100 companies with Sector and Profile Info...")
    company_profiles = []

    def fetch_profile(sym):
        prof = scraper.get_stock_profile(sym)
        return sym, prof

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_profile, s) for s in kse100_symbols]
        for f in as_completed(futures):
            sym, prof = f.result()
            if prof:
                company_profiles.append(
                    {
                        "symbol": sym,
                        "name": prof.get("name", ""),
                        "isin": prof.get("isin", ""),
                        "sectorName": prof.get("sectorName", ""),
                        "sectorCategory": prof.get("sectorCategory", ""),
                        "exchange": prof.get("exchangeid", "PSX"),
                        "isShariah": prof.get("isshariah", False),
                        "high52": prof.get("high52", None),
                        "low52": prof.get("low52", None),
                    }
                )

    df_profiles = pd.DataFrame(company_profiles)
    profiles_csv_path = os.path.join(DATA_DIR, "psx_companies_directory.csv")
    df_profiles.sort_values(by="symbol", inplace=True)
    df_profiles.to_csv(profiles_csv_path, index=False)
    print(
        f"-> Company Directory: {len(df_profiles)} company profiles saved to {profiles_csv_path}"
    )

    # Sector mapping dictionary for quick lookup
    sector_map = (
        df_profiles.set_index("symbol")["sectorName"].to_dict()
        if not df_profiles.empty
        else {}
    )

    # -------------------------------------------------------------
    # 4. Scrape Historical EOD Data for all KSE-100 Stocks (2002-2026)
    # -------------------------------------------------------------
    print("\n[Step 4/5] Scraping Historical OHLCV/EOD Data for all KSE-100 Stocks...")
    histories = scraper.fetch_all_kse100_histories(
        kse100_symbols, max_workers=6, delay=0.1
    )

    master_records = []
    saved_stock_count = 0

    for sym, df_stock in histories.items():
        if not df_stock.empty:
            clean_stock = df_stock.copy()
            clean_stock["date"] = clean_stock["date_formatted"]
            clean_stock["sector"] = sector_map.get(sym, "")

            # Select and order columns
            cols = [
                c
                for c in ["date", "symbol", "close", "volume", "marketCap", "sector"]
                if c in clean_stock.columns
            ]
            clean_stock = clean_stock[cols]

            # Save individual stock CSV
            stock_path = os.path.join(STOCKS_DIR, f"{sym}.csv")
            clean_stock.to_csv(stock_path, index=False)
            saved_stock_count += 1

            master_records.append(clean_stock)

    # -------------------------------------------------------------
    # 5. Compile Master Dataset
    # -------------------------------------------------------------
    print("\n[Step 5/5] Compiling Master Dataset...")
    if master_records:
        df_master = pd.concat(master_records, ignore_index=True)
        df_master.sort_values(by=["symbol", "date"], inplace=True)
        master_csv_path = os.path.join(
            DATA_DIR, "kse100_stocks_historical_2002_2026.csv"
        )
        df_master.to_csv(master_csv_path, index=False)
        print(
            f"-> Master Dataset: {len(df_master):,} total daily stock records compiled!"
        )
        print(f"-> Saved master file to: {master_csv_path}")
    else:
        print("-> Warning: No stock history records to compile.")

    print("\n" + "=" * 70)
    print("SUCCESS: All datasets successfully downloaded and exported to CSV!")
    print(f"Data location: {os.path.abspath(DATA_DIR)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
