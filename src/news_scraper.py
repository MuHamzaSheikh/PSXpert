import re
import os
import time
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SECTOR_KEYWORDS = {
    "COMMERCIAL BANKS": [
        r"\bbanks?\b",
        r"\bcommercial banks?\b",
        r"\bsbp\b",
        r"\bstate bank\b",
        r"\binterest rates?\b",
        r"\bpolicy rate\b",
        r"\bmonetary policy\b",
        r"\bbanking\b",
        r"\blending\b",
        r"\bdeposits\b",
    ],
    "OIL & GAS / ENERGY": [
        r"\bpetrol\b",
        r"\bdiesel\b",
        r"\bcrude\b",
        r"\boil\b",
        r"\bgas\b",
        r"\blng\b",
        r"\brefinery\b",
        r"\bexploration\b",
        r"\bogdc\b",
        r"\bpso\b",
        r"\bppl\b",
        r"\bfuel\b",
        r"\benergy\b",
        r"\bpower tariff\b",
    ],
    "CEMENT": [
        r"\bcement\b",
        r"\bclinker\b",
        r"\bconstruction\b",
        r"\bluck\b",
        r"\bdgkc\b",
        r"\bmaple leaf\b",
    ],
    "FERTILIZER & AGRICULTURE": [
        r"\bfertilizers?\b",
        r"\burea\b",
        r"\bdap\b",
        r"\bagriculture\b",
        r"\bwheat\b",
        r"\bsugar\b",
        r"\bcrops?\b",
        r"\bfarmer\b",
    ],
    "AUTOMOBILE": [
        r"\bcar sales\b",
        r"\bautomobiles?\b",
        r"\bvehicles?\b",
        r"\bpama\b",
        r"\btractors?\b",
        r"\bauto\b",
    ],
    "TEXTILE": [
        r"\btextiles?\b",
        r"\byarn\b",
        r"\bfabrics?\b",
        r"\bgarments?\b",
        r"\bspinning\b",
        r"\bcotton\b",
    ],
    "TECHNOLOGY & TELECOM": [
        r"\btechnolog(?:y|ies)\b",
        r"\bit exports\b",
        r"\btelecom\b",
        r"\bsoftware\b",
        r"\bdigital\b",
        r"\bai\b",
    ],
    "PSX / EQUITIES": [
        r"\bpsx\b",
        r"\bkse-?100\b",
        r"\bkse100\b",
        r"\bstock exchange\b",
        r"\bshares?\b",
        r"\bbourse\b",
        r"\bequities\b",
        r"\bbullish\b",
        r"\bbearish\b",
        r"\bbenchmark\b",
        r"\btrading\b",
    ],
    "ECONOMY & MACRO": [
        r"\bimf\b",
        r"\binflation\b",
        r"\bcpi\b",
        r"\brupee\b",
        r"\bpkr\b",
        r"\bfiscal\b",
        r"\bgdp\b",
        r"\bfbr\b",
        r"\btax\b",
        r"\bcurrent account\b",
        r"\bdebt\b",
        r"\bremittances\b",
        r"\bpoverty\b",
        r"\bexport\b",
        r"\bimport\b",
    ],
}


class FinancialNewsScraper:
    def __init__(self, headers: Optional[Dict[str, str]] = None, timeout: int = 15):
        self.session = requests.Session()
        self.headers = headers or DEFAULT_HEADERS
        self.session.headers.update(self.headers)
        self.timeout = timeout
        self.symbol_lookup = {}
        self._load_symbol_lookup()

    def _load_symbol_lookup(self):
        """Loads available company symbols and names from Dataset A if present."""
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
            except Exception as e:
                pass

    def tag_article(self, headline: str, text: str) -> Dict[str, Any]:
        """Detects mentioned symbols and assigns relevant market/sector."""
        combined = f"{headline} {text}"
        found_symbols = set()
        detected_sectors = set()

        # Check for KSE100 / PSX
        if re.search(r"\b(?:kse-?100|kse100|psx|stock market|karachi stock exchange)\b", combined, re.I):
            found_symbols.add("KSE100")
            detected_sectors.add("PSX / EQUITIES")

        # Check known symbols & company names
        for sym, meta in self.symbol_lookup.items():
            # Check exact ticker word
            if len(sym) >= 3 and re.search(rf"\b{re.escape(sym)}\b", combined):
                found_symbols.add(sym)
                if meta["sector"]:
                    detected_sectors.add(meta["sector"])

            # Check company name distinctive keywords
            c_name = meta["name"]
            clean_name = re.sub(
                r"\b(limited|ltd|pakistan|bank|company|corp|corporation)\b",
                "",
                c_name,
                flags=re.I,
            ).strip()
            if len(clean_name) >= 5 and re.search(
                rf"\b{re.escape(clean_name)}\b", combined, re.I
            ):
                found_symbols.add(sym)
                if meta["sector"]:
                    detected_sectors.add(meta["sector"])

        # Detect general sector from keywords
        for sector, patterns in SECTOR_KEYWORDS.items():
            for p in patterns:
                if re.search(p, combined, re.I):
                    detected_sectors.add(sector)
                    break

        sector_str = " | ".join(sorted(detected_sectors)) if detected_sectors else "GENERAL MARKET"
        symbols_str = ", ".join(sorted(found_symbols)) if found_symbols else "MARKET_WIDE"

        return {
            "symbols_mentioned": symbols_str,
            "relevant_sector_or_market": sector_str,
        }

    def fetch_article_body(self, url: str, publisher: str) -> str:
        """Fetches the full text of an article given its URL."""
        try:
            r = self.session.get(url, timeout=10)
            if r.status_code != 200:
                return ""
            soup = BeautifulSoup(r.text, "html.parser")

            if publisher == "Dawn Business":
                story_div = soup.find("div", class_="story__content") or soup.find("article")
                if story_div:
                    paras = [
                        p.get_text(strip=True)
                        for p in story_div.find_all("p")
                        if p.get_text(strip=True) and not p.find_parent("aside")
                    ]
                    return "\n\n".join(paras)

            elif "Business Recorder" in publisher:
                paras = [
                    p.get_text(strip=True)
                    for p in soup.find_all("p")
                    if len(p.get_text(strip=True)) > 35
                    and not p.find_parent("footer")
                    and not p.find_parent("header")
                    and "subscribing is the best way" not in p.get_text(strip=True).lower()
                ]
                return "\n\n".join(paras)
        except Exception:
            pass
        return ""

    def fetch_dawn_business(self, limit: int = 35) -> List[Dict[str, Any]]:
        """Scrapes Dawn Business RSS feed and extracts full articles."""
        url = "https://www.dawn.com/feeds/business"
        articles = []
        try:
            r = self.session.get(url, timeout=self.timeout)
            if r.status_code != 200:
                return articles
            root = ET.fromstring(r.content)
            channel = root.find("channel")
            items = channel.findall("item") if channel is not None else []

            for item in items[:limit]:
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub_date_raw = item.findtext("pubDate", "").strip()
                desc_raw = item.findtext("description", "").strip()

                summary = (
                    BeautifulSoup(desc_raw, "html.parser").get_text(strip=True)
                    if desc_raw
                    else ""
                )

                try:
                    dt = pd.to_datetime(pub_date_raw)
                    pub_date = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pub_date = pub_date_raw

                body = self.fetch_article_body(link, "Dawn Business")
                article_text = body if body else summary
                tags = self.tag_article(title, article_text)

                articles.append(
                    {
                        "headline": title,
                        "summary": summary,
                        "published_at": pub_date,
                        "publisher": "Dawn Business",
                        "url": link,
                        "symbols_mentioned": tags["symbols_mentioned"],
                        "relevant_sector_or_market": tags["relevant_sector_or_market"],
                        "article_text": article_text,
                    }
                )
        except Exception as e:
            print(f"Error scraping Dawn Business: {e}")
        return articles

    def fetch_business_recorder_feed(self, limit: int = 35) -> List[Dict[str, Any]]:
        """Scrapes Business Recorder latest-news RSS feed."""
        url = "https://www.brecorder.com/feeds/latest-news"
        articles = []
        try:
            r = self.session.get(url, timeout=self.timeout)
            if r.status_code != 200:
                return articles
            root = ET.fromstring(r.content)
            channel = root.find("channel")
            items = channel.findall("item") if channel is not None else []

            for item in items[:limit]:
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub_date_raw = item.findtext("pubDate", "").strip()
                desc_raw = item.findtext("description", "").strip()

                summary = (
                    BeautifulSoup(desc_raw, "html.parser").get_text(strip=True)
                    if desc_raw
                    else ""
                )

                try:
                    dt = pd.to_datetime(pub_date_raw)
                    pub_date = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pub_date = pub_date_raw

                body = self.fetch_article_body(link, "Business Recorder")
                article_text = body if body else summary
                tags = self.tag_article(title, article_text)

                articles.append(
                    {
                        "headline": title,
                        "summary": summary,
                        "published_at": pub_date,
                        "publisher": "Business Recorder",
                        "url": link,
                        "symbols_mentioned": tags["symbols_mentioned"],
                        "relevant_sector_or_market": tags["relevant_sector_or_market"],
                        "article_text": article_text,
                    }
                )
        except Exception as e:
            print(f"Error scraping Business Recorder feed: {e}")
        return articles

    def fetch_business_recorder_sections(self, section_urls: List[str], max_per_section: int = 40) -> List[Dict[str, Any]]:
        """Scrapes specific Business Recorder market sections (e.g. markets/stocks, business-finance)."""
        articles = []
        seen = set()

        for sec_url in section_urls:
            try:
                r = self.session.get(sec_url, timeout=self.timeout)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")

                count = 0
                for art in soup.find_all("article"):
                    h_el = art.find(["h2", "h3", "h4"])
                    a_el = art.find("a")
                    t_el = art.find("time") or art.find("span", class_=re.compile(r"time|date", re.I))
                    p_el = art.find("p")

                    if h_el and a_el:
                        title = h_el.get_text(strip=True)
                        link = a_el.get("href", "")
                        if not link.startswith("http"):
                            link = "https://www.brecorder.com" + link

                        if link in seen or not title or len(title) < 15:
                            continue
                        seen.add(link)

                        date_raw = t_el.get_text(strip=True) if t_el else ""
                        clean_date = re.sub(r"Published", "", date_raw, flags=re.I).strip()
                        summary = p_el.get_text(strip=True) if p_el else ""

                        body = self.fetch_article_body(link, "Business Recorder")
                        article_text = body if body else summary
                        tags = self.tag_article(title, article_text)

                        articles.append(
                            {
                                "headline": title,
                                "summary": summary if summary else (article_text[:200] + "..."),
                                "published_at": clean_date,
                                "publisher": "Business Recorder",
                                "url": link,
                                "symbols_mentioned": tags["symbols_mentioned"],
                                "relevant_sector_or_market": tags["relevant_sector_or_market"],
                                "article_text": article_text,
                            }
                        )
                        count += 1
                        if count >= max_per_section:
                            break
            except Exception as e:
                print(f"Error scraping BR section {sec_url}: {e}")

        return articles

    def scrape_all_financial_news(self) -> pd.DataFrame:
        """Runs the complete financial news scraping pipeline."""
        print("1. Scraping Dawn Business...")
        dawn_articles = self.fetch_dawn_business(limit=35)
        print(f"   -> {len(dawn_articles)} articles retrieved.")

        print("2. Scraping Business Recorder (Feed)...")
        br_feed_articles = self.fetch_business_recorder_feed(limit=35)
        print(f"   -> {len(br_feed_articles)} articles retrieved.")

        print("3. Scraping Business Recorder (Stocks & Markets sections)...")
        section_urls = [
            "https://www.brecorder.com/markets/stocks",
            "https://www.brecorder.com/business-finance",
        ]
        br_section_articles = self.fetch_business_recorder_sections(section_urls, max_per_section=40)
        print(f"   -> {len(br_section_articles)} articles retrieved.")

        all_articles = dawn_articles + br_feed_articles + br_section_articles
        if not all_articles:
            return pd.DataFrame()

        df = pd.DataFrame(all_articles)
        # Deduplicate on URL
        df.drop_duplicates(subset=["url"], inplace=True)
        # Deduplicate on Headline
        df.drop_duplicates(subset=["headline"], inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df
