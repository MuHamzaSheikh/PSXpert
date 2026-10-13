"""
PSXpert - Corporate Announcements & Payouts Scraper (Dataset D)
Scrapes comprehensive corporate actions and announcements for PSX/KSE-100 listed companies:
- Earnings announcements (Financial results, interim & annual reporting releases)
- Dividends and bonus shares (Payout history, cash dividends, stock splits, bonus shares)
- Material company disclosures (Material information, operations, discoveries, regulatory notices)
- Other relevant corporate events (AGMs/EGMs, board meetings, executive changes, resolutions)

Source: Sarmaaya Financials API & Direct PSX Exchange Disclosures
"""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PSXAnnouncements")


class PSXAnnouncementsScraper:
    SARMAAYA_DIVIDENDS_BASE = "https://beta-restapi.sarmaaya.pk/api/stocks/dividends"
    SARMAAYA_ANNOUNCEMENTS_BASE = "https://beta-restapi.sarmaaya.pk/api/stocks/announcements"
    
    DEFAULT_HEADERS = {
        "Origin": "https://sarmaaya.pk",
        "Referer": "https://sarmaaya.pk/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    def __init__(self, directory_path: str = "data/psx_companies_directory.csv"):
        self.directory_path = Path(directory_path)
        self.companies_df = self._load_directory()

    def _load_directory(self) -> pd.DataFrame:
        if self.directory_path.exists():
            return pd.read_csv(self.directory_path)
        raise FileNotFoundError(f"Companies directory not found at {self.directory_path}")

    @staticmethod
    def classify_announcement(title: str) -> str:
        """
        Classifies corporate announcement titles into the required categories:
        1. Earnings Announcements
        2. Dividends & Bonus Shares
        3. Material Disclosures
        4. Corporate Events
        """
        title_lower = title.lower()

        # 1. Earnings Announcements
        if any(k in title_lower for k in [
            "financial result", "financial statement", "quarterly report", "annual report",
            "half yearly report", "transmission of quarterly", "transmission of annual",
            "transmission of half", "interim financial", "condensed interim", "profit / (loss)",
            "audited accounts", "financial accounts", "un-audited financial", "half-yearly"
        ]):
            return "Earnings Announcements"

        # 2. Dividends and Bonus Shares
        elif any(k in title_lower for k in [
            "dividend", "bonus", "book closure", "sub-division of shares", "split",
            "right shares", "right issue", "payout", "credit of interim", "unclaimed dividend",
            "fractional shares", "interim cash", "final cash", "entitlement"
        ]):
            return "Dividends & Bonus Shares"

        # 3. Material Company Disclosures
        elif any(k in title_lower for k in [
            "material information", "disclosure of material", "discovery", "condensate",
            "oil well", "gas discovery", "well", "production", "plant shut", "expansion",
            "contract", "commercial production", "joint venture", "merger", "acquisition",
            "takeover", "mou", "court order", "restructuring", "besos", "exploration"
        ]):
            return "Material Disclosures"

        # 4. Other Relevant Corporate Events (AGMs, Board Meetings, Director changes)
        else:
            return "Corporate Events"

    def fetch_company_payouts(self, symbol: str, name: str, sector: str) -> List[Dict[str, Any]]:
        """
        Fetches full historical payouts (Dividends, Splits, Bonus shares) for a company.
        """
        url = f"{self.SARMAAYA_DIVIDENDS_BASE}/{symbol}"
        rows = []
        try:
            r = requests.get(url, headers=self.DEFAULT_HEADERS, timeout=12)
            if r.status_code != 200:
                return rows
            data = r.json()
            history = data.get("response", {}).get("payoutHistory", [])
            for item in history:
                ann_date = item.get("announcementDate", "")
                if ann_date == "0000-00-00":
                    ann_date = f"{item.get('year', '')}-01-01" if item.get('year') else ""
                
                rows.append({
                    "symbol": symbol,
                    "company_name": name,
                    "sector": sector,
                    "announcement_date": ann_date,
                    "fiscal_year": item.get("year"),
                    "payout_type": item.get("payoutType", "dividend"),
                    "dividend_per_share_pkr": item.get("dividendPerShare"),
                    "payout_percentage": item.get("percentage"),
                    "face_value_pkr": item.get("faceValue")
                })
        except Exception as e:
            logger.debug(f"Error fetching payouts for {symbol}: {e}")
        return rows

    def fetch_company_announcements(self, symbol: str, name: str, sector: str, start_date: str = "2000-01-01", end_date: str = "2026-10-14") -> List[Dict[str, Any]]:
        """
        Fetches official corporate announcements for a company.
        """
        url = f"{self.SARMAAYA_ANNOUNCEMENTS_BASE}/{symbol}?startDate={start_date}&endDate={end_date}"
        rows = []
        try:
            r = requests.get(url, headers=self.DEFAULT_HEADERS, timeout=12)
            if r.status_code != 200:
                return rows
            data = r.json()
            ann_list = data.get("response", [])
            for item in ann_list:
                title = item.get("announcementTitle", "").strip()
                if not title:
                    continue

                category = self.classify_announcement(title)
                attachments = item.get("attachments", [])
                
                # Separate PDF document link from image scan link
                doc_url = next((a for a in attachments if a.endswith(".pdf")), "")
                img_url = next((a for a in attachments if not a.endswith(".pdf")), "")
                if not doc_url and attachments:
                    doc_url = attachments[0]

                rows.append({
                    "symbol": symbol,
                    "company_name": name,
                    "sector": sector,
                    "posting_date": item.get("postingDate", ""),
                    "category": category,
                    "announcement_title": title,
                    "announcement_id": item.get("sysAnnouncementId", ""),
                    "document_url": doc_url,
                    "attachment_url": img_url
                })
        except Exception as e:
            logger.debug(f"Error fetching announcements for {symbol}: {e}")
        return rows

    def process_all_companies(self, max_workers: int = 12, limit: Optional[int] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Processes all companies in parallel, returning master announcements and payouts DataFrames.
        """
        target_df = self.companies_df.head(limit) if limit else self.companies_df
        total = len(target_df)
        logger.info(f"Starting Corporate Announcements & Payouts extraction for {total} companies...")

        all_payouts: List[Dict[str, Any]] = []
        all_announcements: List[Dict[str, Any]] = []

        def worker(row):
            sym = row["symbol"]
            name = row.get("name", "")
            sector = row.get("sectorName", "")
            payouts = self.fetch_company_payouts(sym, name, sector)
            announcements = self.fetch_company_announcements(sym, name, sector)
            return sym, payouts, announcements

        start_time = time.time()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_sym = {
                executor.submit(worker, row): row["symbol"]
                for _, row in target_df.iterrows()
            }
            completed = 0
            for future in as_completed(future_to_sym):
                completed += 1
                sym = future_to_sym[future]
                try:
                    _, p_list, a_list = future.result()
                    all_payouts.extend(p_list)
                    all_announcements.extend(a_list)
                    if completed % 20 == 0 or completed == total:
                        logger.info(f"Progress: [{completed}/{total}] companies processed ({sym} -> {len(a_list)} ann, {len(p_list)} payouts)")
                except Exception as e:
                    logger.error(f"Error processing {sym}: {e}")

        logger.info(f"Extraction completed in {time.time() - start_time:.2f}s")
        
        df_payouts = pd.DataFrame(all_payouts)
        df_announcements = pd.DataFrame(all_announcements)

        if not df_payouts.empty:
            df_payouts = df_payouts.sort_values(
                by=["symbol", "announcement_date"],
                ascending=[True, False]
            ).reset_index(drop=True)

        if not df_announcements.empty:
            df_announcements = df_announcements.sort_values(
                by=["posting_date", "symbol"],
                ascending=[False, True]
            ).reset_index(drop=True)

        return df_announcements, df_payouts
