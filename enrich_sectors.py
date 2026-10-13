import os
import time
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
constituents_path = os.path.join(DATA_DIR, "kse100_constituents.csv")
df_const = pd.read_csv(constituents_path)
symbols = df_const["symbol"].tolist()

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Origin': 'https://sarmaaya.pk',
    'Referer': 'https://sarmaaya.pk/',
}

profiles = []

def fetch_with_retry(sym, max_retries=3):
    url = f'https://beta-restapi.sarmaaya.pk/api/stocks/{sym}'
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers=headers, timeout=12)
            if r.status_code == 200:
                data = r.json().get('response', {})
                return {
                    "symbol": sym,
                    "name": data.get("name", ""),
                    "isin": data.get("isin", ""),
                    "sectorName": data.get("sectorName", ""),
                    "sectorCategory": data.get("sectorCategory", ""),
                    "exchange": data.get("exchangeid", "PSX"),
                    "isShariah": data.get("isshariah", False),
                    "close": data.get("close", None),
                    "high": data.get("high", None),
                    "low": data.get("low", None),
                    "volume": data.get("volume", None),
                    "high52": data.get("high52", None),
                    "low52": data.get("low52", None),
                }
            time.sleep(0.5)
        except Exception:
            time.sleep(1.0)
    return {"symbol": sym, "name": "", "isin": "", "sectorName": "", "sectorCategory": "", "exchange": "PSX"}

print(f"Fetching complete sector & profile info for all {len(symbols)} KSE-100 stocks...")
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(fetch_with_retry, s) for s in symbols]
    for f in as_completed(futures):
        profiles.append(f.result())

df_profiles = pd.DataFrame(profiles)
df_profiles.sort_values(by="symbol", inplace=True)
profiles_csv = os.path.join(DATA_DIR, "psx_companies_directory.csv")
df_profiles.to_csv(profiles_csv, index=False)
print(f"Saved {len(df_profiles)} profiles to {profiles_csv}")
print("Sample:\n", df_profiles[["symbol", "name", "sectorName"]].head(10))

# Update master dataset with complete sector information
master_csv = os.path.join(DATA_DIR, "kse100_stocks_historical_2002_2026.csv")
if os.path.exists(master_csv):
    print("\nUpdating sector information in master historical dataset...")
    df_master = pd.read_csv(master_csv)
    sector_map = df_profiles.set_index("symbol")["sectorName"].to_dict()
    df_master["sector"] = df_master["symbol"].map(sector_map).fillna("")
    df_master.to_csv(master_csv, index=False)
    print("Master dataset sector updated successfully!")

# Also update individual files
stocks_dir = os.path.join(DATA_DIR, "stocks_historical")
for sym, sector in sector_map.items():
    stock_file = os.path.join(stocks_dir, f"{sym}.csv")
    if os.path.exists(stock_file):
        df_s = pd.read_csv(stock_file)
        df_s["sector"] = sector
        df_s.to_csv(stock_file, index=False)
print("Individual stock CSVs updated with sector information!")
