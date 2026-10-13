import re
import os
import time
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from curl_cffi import requests
from typing import List, Dict, Any, Optional

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SECTOR_KEYWORDS = {
    "COMMERCIAL BANKS": [
        r"\bbanks?\b", r"\bcommercial banks?\b", r"\bsbp\b", r"\bstate bank\b",
        r"\binterest rates?\b", r"\bpolicy rate\b", r"\bmonetary policy\b",
        r"\bbanking\b", r"\blending\b", r"\bdeposits\b",
    ],
    "OIL & GAS / ENERGY": [
        r"\bpetrol\b", r"\bdiesel\b", r"\bcrude\b", r"\boil\b", r"\bgas\b",
        r"\blng\b", r"\brefinery\b", r"\bexploration\b", r"\bogdc\b", r"\bpso\b",
        r"\bppl\b", r"\bfuel\b", r"\benergy\b", r"\bpower tariff\b",
    ],
    "CEMENT": [
        r"\bcement\b", r"\bclinker\b", r"\bconstruction\b", r"\bluck\b", r"\bdgkc\b",
    ],
    "FERTILIZER & AGRICULTURE": [
        r"\bfertilizers?\b", r"\burea\b", r"\bdap\b", r"\bagriculture\b",
        r"\bwheat\b", r"\bsugar\b", r"\bcrops?\b", r"\bfarmer\b",
    ],
    "AUTOMOBILE": [
        r"\bcar sales\b", r"\bautomobiles?\b", r"\bvehicles?\b", r"\bpama\b", r"\btractors?\b",
    ],
    "TEXTILE": [
        r"\btextiles?\b", r"\byarn\b", r"\bfabrics?\b", r"\bgarments?\b", r"\bcotton\b",
    ],
    "TECHNOLOGY & TELECOM": [
        r"\btechnolog(?:y|ies)\b", r"\bit exports\b", r"\btelecom\b", r"\bsoftware\b", r"\bdigital\b",
    ],
    "PSX / EQUITIES": [
        r"\bpsx\b", r"\bkse-?100\b", r"\bkse100\b", r"\bstock exchange\b",
        r"\bshares?\b", r"\bbourse\b", r"\bequities\b", r"\bbullish\b", r"\bbearish\b",
    ],
    "ECONOMY & MACRO": [
        r"\bimf\b", r"\binflation\b", r"\bcpi\b", r"\brupee\b", r"\bpkr\b",
        r"\bfiscal\b", r"\bgdp\b", r"\bfbr\b", r"\btax\b", r"\bcurrent account\b",
        r"\bdebt\b", r"\bremittances\b", r"\btrade deficit\b",
    ],
}


class HistoricalNewsScraper:
    def __init__(self):
        self.session = requests.Session(impersonate="chrome120")
        self.symbol_lookup = {}
        self._load_symbol_lookup()

    def _load_symbol_lookup(self):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        profiles_path = os.path.join(data_dir, "psx_companies_directory.csv")
        if os.path.exists(profiles_path):
            try:
                df = pd.read_csv(profiles_path)
                for _, row in df.iterrows():
                    sym = str(row["symbol"]).strip().upper()
                    name = str(row["name"]).strip()
                    sector = str(row.get("sectorName", "")).strip()
                    self.symbol_lookup[sym] = {"name": name, "sector": sector}
            except Exception:
                pass

    def tag_article(self, headline: str, text: str) -> Dict[str, Any]:
        combined = f"{headline} {text}"
        found_symbols = set()
        detected_sectors = set()

        if re.search(r"\b(?:kse-?100|kse100|psx|stock market|karachi stock exchange)\b", combined, re.I):
            found_symbols.add("KSE100")
            detected_sectors.add("PSX / EQUITIES")

        for sym, meta in self.symbol_lookup.items():
            if len(sym) >= 3 and re.search(rf"\b{re.escape(sym)}\b", combined):
                found_symbols.add(sym)
                if meta["sector"]:
                    detected_sectors.add(meta["sector"])

            clean_name = re.sub(
                r"\b(limited|ltd|pakistan|bank|company|corp|corporation)\b",
                "",
                meta["name"],
                flags=re.I,
            ).strip()
            if len(clean_name) >= 5 and re.search(
                rf"\b{re.escape(clean_name)}\b", combined, re.I
            ):
                found_symbols.add(sym)
                if meta["sector"]:
                    detected_sectors.add(meta["sector"])

        for sector, patterns in SECTOR_KEYWORDS.items():
            for p in patterns:
                if re.search(p, combined, re.I):
                    detected_sectors.add(sector)
                    break

        sector_str = " | ".join(sorted(detected_sectors)) if detected_sectors else "ECONOMY & GENERAL"
        symbols_str = ", ".join(sorted(found_symbols)) if found_symbols else "MARKET_WIDE"

        return {
            "symbols_mentioned": symbols_str,
            "relevant_sector_or_market": sector_str,
        }

    def fetch_articles_for_date(self, date_str: str, max_articles: int = 15) -> List[Dict[str, Any]]:
        """Scrapes business articles from Dawn newspaper for a specific date (YYYY-MM-DD)."""
        url = f"https://www.dawn.com/newspaper/business/{date_str}"
        records = []

        try:
            r = self.session.get(url, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            
            # Find news article links
            links = []
            for a in soup.find_all("a"):
                href = a.get("href")
                if href and "/news/" in href:
                    if href not in links:
                        links.append(href)

            # If no business newspaper links found, fallback to general archive
            if not links:
                url_archive = f"https://www.dawn.com/archive/{date_str}"
                r_arc = self.session.get(url_archive, timeout=10)
                if r_arc.status_code == 200:
                    soup_arc = BeautifulSoup(r_arc.text, "html.parser")
                    for a in soup_arc.find_all("a"):
                        href = a.get("href")
                        if href and "/news/" in href and href not in links:
                            # Filter for business or market related keywords in link
                            if any(k in href.lower() for k in ["business", "economy", "trade", "market", "stock", "rupee", "bank", "imf", "oil", "price"]):
                                links.append(href)

            for link in links[:max_articles]:
                try:
                    time.sleep(0.1)
                    art_res = self.session.get(link, timeout=10)
                    if art_res.status_code != 200:
                        continue
                    art_soup = BeautifulSoup(art_res.text, "html.parser")

                    # Extract headline
                    h1 = art_soup.find("h1") or art_soup.find(["h2", "h3"])
                    headline = h1.get_text(strip=True) if h1 else ""
                    if not headline or len(headline) < 10:
                        title_tag = art_soup.title.string if art_soup.title else ""
                        headline = re.sub(r"- (Newspaper - )?DAWN\.COM", "", title_tag).strip()

                    if not headline or len(headline) < 10:
                        continue

                    # Extract article body
                    story_div = art_soup.find("div", class_="story__content") or art_soup.find("article")
                    if story_div:
                        paras = [
                            p.get_text(strip=True)
                            for p in story_div.find_all("p")
                            if p.get_text(strip=True) and not p.find_parent("aside")
                        ]
                        article_text = "\n\n".join(paras)
                    else:
                        paras = [p.get_text(strip=True) for p in art_soup.find_all("p") if len(p.get_text(strip=True)) > 30]
                        article_text = "\n\n".join(paras)

                    if not article_text:
                        continue

                    summary = paras[0] if paras else headline
                    tags = self.tag_article(headline, article_text)

                    records.append({
                        "headline": headline,
                        "summary": summary,
                        "published_at": f"{date_str} 00:00:00",
                        "publisher": "Dawn",
                        "url": link,
                        "symbols_mentioned": tags["symbols_mentioned"],
                        "relevant_sector_or_market": tags["relevant_sector_or_market"],
                        "article_text": article_text,
                    })
                except Exception:
                    pass

        except Exception as e:
            print(f"Error fetching date {date_str}: {e}")

        return records
