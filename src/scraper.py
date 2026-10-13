import os
import time
import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

BASE_API_URL = "https://beta-restapi.sarmaaya.pk/api"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Origin": "https://sarmaaya.pk",
    "Referer": "https://sarmaaya.pk/",
    "Accept": "application/json, text/plain, */*",
}


class SarmayaPSXScraper:
    def __init__(self, headers: Optional[Dict[str, str]] = None, timeout: int = 15):
        self.session = requests.Session()
        self.headers = headers or DEFAULT_HEADERS
        self.session.headers.update(self.headers)
        self.timeout = timeout

    def get_kse100_index_history(self, days: int = 15000) -> pd.DataFrame:
        """
        Scrapes historical daily points for the KSE-100 index from Sarmaaya.
        Covers from 2002 up to 2026.
        """
        url = f"{BASE_API_URL}/indices/price-history/KSE100?days={days}"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json().get("response", [])

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        # Rename and format columns
        df.rename(columns={"price": "close"}, inplace=True)
        df["date"] = pd.to_datetime(df["date"])
        # Format date as YYYY-MM-DD
        df["date_formatted"] = df["date"].dt.strftime("%Y-%m-%d")
        df.sort_values(by="date", ascending=True, inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    def get_kse100_constituents(self) -> pd.DataFrame:
        """
        Fetches the complete list of 100 constituent stocks currently in KSE-100.
        """
        url = f"{BASE_API_URL}/stocks/ticker?index=KSE100"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json().get("response", [])

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df.sort_values(by="symbol", inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    def get_all_stocks_snapshot(self) -> pd.DataFrame:
        """
        Fetches all PSX stocks with current OHLCV, 52W High/Low, and status.
        """
        url = f"{BASE_API_URL}/stocks"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json().get("response", [])

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        return df

    def get_stock_profile(self, symbol: str) -> Dict[str, Any]:
        """
        Fetches full company profile including sector name, category, and ISIN.
        """
        url = f"{BASE_API_URL}/stocks/{symbol.strip().upper()}"
        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json().get("response", {})
                return data if isinstance(data, dict) else {}
        except Exception as e:
            print(f"Error fetching profile for {symbol}: {e}")
        return {}

    def get_stock_price_history(self, symbol: str, days: int = 15000) -> pd.DataFrame:
        """
        Fetches full historical daily prices, volume, and marketCap for a given stock.
        """
        symbol_clean = symbol.strip().upper()
        url = f"{BASE_API_URL}/stocks/price-history/{symbol_clean}?days={days}"
        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json().get("response", [])
                if data:
                    df = pd.DataFrame(data)
                    df.rename(columns={"price": "close"}, inplace=True)
                    df["date"] = pd.to_datetime(df["date"])
                    df["date_formatted"] = df["date"].dt.strftime("%Y-%m-%d")
                    df.sort_values(by="date", ascending=True, inplace=True)
                    df.reset_index(drop=True, inplace=True)
                    return df
        except Exception as e:
            print(f"Error fetching history for {symbol}: {e}")
        return pd.DataFrame()

    def fetch_all_kse100_histories(
        self, symbols: List[str], max_workers: int = 8, delay: float = 0.05
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetches historical data for multiple stocks concurrently using a thread pool.
        """
        results = {}
        total = len(symbols)
        print(f"Starting historical data scraping for {total} stocks with {max_workers} worker threads...")

        def worker(sym):
            time.sleep(delay)
            df = self.get_stock_price_history(sym)
            return sym, df

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_sym = {executor.submit(worker, s): s for s in symbols}
            completed = 0
            for future in as_completed(future_to_sym):
                sym = future_to_sym[future]
                try:
                    s, df = future.result()
                    results[s] = df
                    completed += 1
                    earliest = df["date_formatted"].iloc[0] if not df.empty else "N/A"
                    latest = df["date_formatted"].iloc[-1] if not df.empty else "N/A"
                    print(
                        f"[{completed}/{total}] {sym}: {len(df)} records ({earliest} -> {latest})"
                    )
                except Exception as e:
                    print(f"[{completed}/{total}] {sym} failed: {e}")
                    results[sym] = pd.DataFrame()

        return results
