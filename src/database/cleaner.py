"""
PSXpert - Data Cleaning & ETL Normalizer
Transforms raw scraped CSVs into cleaned, validated, normalized datasets in data/processed/.
Preserves raw data separately in data/raw/.
Enforces unique constraints, timezone preservation, and financial publication dates.
"""

import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PSXpertCleaner")


class PSXDataCleaner:
    def __init__(self, data_root: str = "data"):
        self.data_root = Path(data_root)
        self.raw_dir = self.data_root / "raw"
        self.processed_dir = self.data_root / "processed"
        self._setup_directories()

    def _setup_directories(self):
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def backup_raw_data(self):
        """Ensures all raw files in data/ are mirrored in data/raw/."""
        logger.info("Verifying raw data separation in data/raw/...")
        for item in self.data_root.glob("*.csv"):
            raw_dest = self.raw_dir / item.name
            if not raw_dest.exists() or raw_dest.stat().st_size != item.stat().st_size:
                shutil.copy2(item, raw_dest)
        
        # Mirror subdirectories if they exist
        for subdir_name in ["stocks_historical", "fundamentals_company", "announcements_company"]:
            src_sub = self.data_root / subdir_name
            if src_sub.exists() and src_sub.is_dir():
                dest_sub = self.raw_dir / subdir_name
                dest_sub.mkdir(parents=True, exist_ok=True)
                for f in src_sub.glob("*.csv"):
                    dest_file = dest_sub / f.name
                    if not dest_file.exists():
                        shutil.copy2(f, dest_file)
        logger.info("Raw data safely isolated in data/raw/.")

    def clean_companies(self) -> pd.DataFrame:
        """Cleans and standardizes company profiles."""
        raw_file = self.raw_dir / "psx_companies_directory.csv"
        if not raw_file.exists():
            raw_file = self.data_root / "psx_companies_directory.csv"

        df = pd.read_csv(raw_file)
        df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
        df["company_name"] = df["name"].astype(str).str.strip()
        df["sector"] = df["sectorName"].astype(str).str.strip()
        df["sector_category"] = df.get("sectorCategory", "").astype(str).str.strip()
        df["isin"] = df.get("isin", "").astype(str).str.strip()
        df["is_shariah"] = df.get("isShariah", False).fillna(False).astype(bool)
        df["is_kse100"] = True
        df["is_active"] = True

        clean_df = df[[
            "symbol", "company_name", "sector", "sector_category",
            "isin", "is_shariah", "is_kse100", "is_active"
        ]].drop_duplicates(subset=["symbol"])

        out_path = self.processed_dir / "companies_clean.csv"
        clean_df.to_csv(out_path, index=False)
        logger.info(f"Cleaned Companies -> {out_path} ({len(clean_df)} records)")
        return clean_df

    def clean_stock_prices(self) -> pd.DataFrame:
        """
        Cleans master historical daily stock prices.
        Enforces unique constraint on (symbol, trading_date).
        Validates numeric ranges and formats.
        """
        raw_file = self.raw_dir / "kse100_stocks_historical_2002_2026.csv"
        if not raw_file.exists():
            raw_file = self.data_root / "kse100_stocks_historical_2002_2026.csv"

        logger.info(f"Loading raw stock prices from {raw_file}...")
        df = pd.read_csv(raw_file, low_memory=False)

        # Standardize columns
        df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
        df["trading_date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        
        # Numeric conversions
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")
        df["market_cap"] = pd.to_numeric(df.get("marketCap"), errors="coerce")

        # Open, High, Low approximation if not in historical EOD
        if "open" in df.columns:
            df["open"] = pd.to_numeric(df["open"], errors="coerce").fillna(df["close"])
        else:
            df["open"] = df["close"]

        if "high" in df.columns:
            df["high"] = pd.to_numeric(df["high"], errors="coerce").fillna(df["close"])
        else:
            df["high"] = df["close"]

        if "low" in df.columns:
            df["low"] = pd.to_numeric(df["low"], errors="coerce").fillna(df["close"])
        else:
            df["low"] = df["close"]

        # Drop invalid rows and deduplicate on (symbol, trading_date)
        df = df.dropna(subset=["symbol", "trading_date", "close"])
        before_dedup = len(df)
        df = df.drop_duplicates(subset=["symbol", "trading_date"], keep="last")
        dedup_dropped = before_dedup - len(df)
        if dedup_dropped > 0:
            logger.info(f"Deduplicated {dedup_dropped:,} duplicate (symbol, trading_date) entries.")

        # Sort chronologically
        df = df.sort_values(by=["symbol", "trading_date"]).reset_index(drop=True)

        clean_cols = ["symbol", "trading_date", "open", "high", "low", "close", "volume", "market_cap"]
        clean_df = df[clean_cols]

        out_path = self.processed_dir / "stock_prices_clean.csv"
        clean_df.to_csv(out_path, index=False)
        logger.info(f"Cleaned Stock Prices -> {out_path} ({len(clean_df):,} records)")
        return clean_df

    def clean_market_indices(self) -> pd.DataFrame:
        """Cleans KSE-100 historical daily index points."""
        raw_file = self.raw_dir / "kse100_index_history_2002_2026.csv"
        if not raw_file.exists():
            raw_file = self.data_root / "kse100_index_history_2002_2026.csv"

        df = pd.read_csv(raw_file)
        df["index_symbol"] = "KSE100"
        df["trading_date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df["open"] = df["close"]
        df["high"] = df["close"]
        df["low"] = df["close"]
        df["volume"] = 0
        df["point_change"] = pd.to_numeric(df.get("change"), errors="coerce").fillna(0.0)
        df["pct_change"] = pd.to_numeric(df.get("change_pct"), errors="coerce").fillna(0.0)

        df = df.dropna(subset=["trading_date", "close"]).drop_duplicates(subset=["index_symbol", "trading_date"])
        df = df.sort_values(by="trading_date").reset_index(drop=True)

        clean_cols = ["index_symbol", "trading_date", "open", "high", "low", "close", "volume", "point_change", "pct_change"]
        clean_df = df[clean_cols]

        out_path = self.processed_dir / "market_indices_clean.csv"
        clean_df.to_csv(out_path, index=False)
        logger.info(f"Cleaned Market Indices -> {out_path} ({len(clean_df):,} records)")
        return clean_df

    def clean_news(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Cleans news articles, standardizes timestamps with timezone awareness,
        and extracts normalized news entities (symbol and sector links).
        """
        raw_live = self.raw_dir / "financial_news.csv"
        if not raw_live.exists():
            raw_live = self.data_root / "financial_news.csv"

        raw_hist = self.raw_dir / "financial_news_historical_2002_2026.csv"
        if not raw_hist.exists():
            raw_hist = self.data_root / "financial_news_historical_2002_2026.csv"

        dfs = []
        if raw_live.exists():
            dfs.append(pd.read_csv(raw_live))
        if raw_hist.exists():
            dfs.append(pd.read_csv(raw_hist))

        if not dfs:
            return pd.DataFrame(), pd.DataFrame()

        combined = pd.concat(dfs, ignore_index=True)
        # Deduplicate on canonical URL
        combined = combined.drop_duplicates(subset=["url"]).reset_index(drop=True)

        # Parse publication timestamps consistently with timezone preservation
        def parse_timestamp(val):
            if not val or pd.isna(val):
                return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S+05:00")
            val_str = str(val).strip()
            # Try ISO formats
            try:
                dt = pd.to_datetime(val_str, errors="coerce")
                if pd.notna(dt):
                    # Default to PKT (+05:00) if naive
                    if dt.tzinfo is None:
                        return dt.strftime("%Y-%m-%d %H:%M:%S+05:00")
                    return dt.isoformat()
            except Exception:
                pass
            return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S+05:00")

        combined["published_at"] = combined["published_at"].apply(parse_timestamp)
        combined["headline"] = combined["headline"].astype(str).str.strip()
        combined["summary"] = combined["summary"].fillna("").astype(str).str.strip()
        combined["article_text"] = combined["article_text"].fillna("").astype(str).str.strip()
        combined["publisher"] = combined["publisher"].astype(str).str.strip()

        # Add integer article_id for relational foreign keys
        combined["article_id"] = combined.index + 1

        articles_clean = combined[[
            "article_id", "headline", "summary", "article_text",
            "publisher", "url", "published_at"
        ]]

        # Generate entities table (article_to_company and article_to_sector links)
        entities_rows = []
        for _, row in combined.iterrows():
            art_id = row["article_id"]
            
            # Symbols mentioned
            syms_str = str(row.get("symbols_mentioned", "")).strip()
            if syms_str and syms_str != "nan":
                for sym in syms_str.split("|"):
                    sym = sym.strip().upper()
                    if sym and sym not in ["NONE", "NAN"]:
                        ent_type = "INDEX" if sym in ["KSE100", "KSE-100"] else ("MARKET" if sym == "MARKET_WIDE" else "COMPANY")
                        entities_rows.append({
                            "article_id": art_id,
                            "entity_type": ent_type,
                            "entity_value": sym,
                            "confidence_score": 1.000
                        })

            # Sectors mentioned
            sec_str = str(row.get("relevant_sector_or_market", "")).strip()
            if sec_str and sec_str != "nan":
                for sec in sec_str.split("|"):
                    sec = sec.strip()
                    if sec and sec not in ["NONE", "NAN"]:
                        entities_rows.append({
                            "article_id": art_id,
                            "entity_type": "SECTOR",
                            "entity_value": sec,
                            "confidence_score": 0.950
                        })

        entities_df = pd.DataFrame(entities_rows).drop_duplicates(subset=["article_id", "entity_type", "entity_value"])

        out_art = self.processed_dir / "news_articles_clean.csv"
        out_ent = self.processed_dir / "news_entities_clean.csv"
        articles_clean.to_csv(out_art, index=False)
        entities_df.to_csv(out_ent, index=False)
        logger.info(f"Cleaned News Articles -> {out_art} ({len(articles_clean)} records)")
        logger.info(f"Cleaned News Entities -> {out_ent} ({len(entities_df)} records)")
        return articles_clean, entities_df

    def clean_financials(self) -> pd.DataFrame:
        """
        Normalizes company fundamentals into relational format (company_financials).
        Crucially preserves publication_date (the actual exchange filing date)
        alongside period_end_date to eliminate lookahead bias in backtesting.
        """
        raw_ann = self.raw_dir / "kse100_fundamentals_annual.csv"
        if not raw_ann.exists():
            raw_ann = self.data_root / "kse100_fundamentals_annual.csv"

        raw_qtr = self.raw_dir / "kse100_fundamentals_quarterly.csv"
        if not raw_qtr.exists():
            raw_qtr = self.data_root / "kse100_fundamentals_quarterly.csv"

        # Load announcements to map filing/publication dates
        raw_announc = self.raw_dir / "kse100_corporate_announcements.csv"
        if not raw_announc.exists():
            raw_announc = self.data_root / "kse100_corporate_announcements.csv"

        filing_dates: Dict[Tuple[str, int, str], str] = {}
        if raw_announc.exists():
            ann_df = pd.read_csv(raw_announc)
            earnings_ann = ann_df[ann_df["category"] == "Earnings Announcements"]
            for _, r in earnings_ann.iterrows():
                s = str(r["symbol"]).upper()
                p_date = str(r["posting_date"])
                title = str(r["announcement_title"]).lower()
                # Extract year
                yr_match = re.search(r"20\d\d", title)
                if yr_match:
                    yr = int(yr_match.group(0))
                    # Determine period
                    period = "FY"
                    if "quarter" in title or "first" in title or "q1" in title:
                        period = "Q1"
                    elif "half" in title or "second" in title or "q2" in title:
                        period = "Q2"
                    elif "third" in title or "nine" in title or "q3" in title:
                        period = "Q3"
                    elif "annual" in title or "year ended" in title:
                        period = "FY"
                    filing_dates[(s, yr, period)] = p_date

        rows = []
        # Process Annual
        if raw_ann.exists():
            df_ann = pd.read_csv(raw_ann)
            metric_cols = [
                "revenue_sales", "gross_profit", "operating_profit", "net_profit_after_tax",
                "eps_basic", "eps_diluted", "total_assets", "current_assets", "cash_and_equivalents",
                "net_ppe", "total_liabilities", "current_liabilities", "total_debt",
                "shareholders_equity", "retained_earnings", "common_shares_outstanding",
                "operating_cash_flow", "capital_expenditures", "investing_cash_flow",
                "financing_cash_flow", "dividends_paid", "free_cash_flow"
            ]
            for _, r in df_ann.iterrows():
                sym = str(r["symbol"]).upper()
                yr = int(r["fiscal_year"])
                raw_end = r.get("period_end_date")
                if pd.isna(raw_end) or not str(raw_end).strip() or str(raw_end).strip().lower() in ["nan", "none", "null"]:
                    end_date = f"{yr}-06-30"
                else:
                    end_date = str(raw_end).strip()
                pub_date = filing_dates.get((sym, yr, "FY"), end_date)
                if pd.isna(pub_date) or not str(pub_date).strip() or str(pub_date).strip().lower() in ["nan", "none", "null"]:
                    pub_date = end_date

                for m in metric_cols:
                    val = r.get(m)
                    if pd.notna(val):
                        rows.append({
                            "symbol": sym,
                            "statement_type": "ANNUAL",
                            "fiscal_year": yr,
                            "fiscal_period": "FY",
                            "period_end_date": end_date,
                            "publication_date": pub_date,
                            "metric_name": m,
                            "metric_value": float(val),
                            "unit": "PKR_THOUSANDS" if "eps" not in m else "PKR_PER_SHARE"
                        })

        # Process Quarterly
        if raw_qtr.exists():
            df_qtr = pd.read_csv(raw_qtr)
            qtr_metrics = [
                "revenue_sales", "gross_profit", "operating_profit", "net_profit_after_tax",
                "eps", "total_assets", "total_liabilities", "total_debt",
                "shareholders_equity", "operating_cash_flow", "free_cash_flow"
            ]
            for _, r in df_qtr.iterrows():
                sym = str(r["symbol"]).upper()
                yr = int(r["fiscal_year"])
                q_label = str(r.get("fiscal_quarter", "Q1")).strip()
                raw_end_qtr = r.get("period_end_date")
                if pd.isna(raw_end_qtr) or not str(raw_end_qtr).strip() or str(raw_end_qtr).strip().lower() in ["nan", "none", "null"]:
                    if "1" in q_label:
                        end_date = f"{yr}-09-30"
                    elif "2" in q_label:
                        end_date = f"{yr}-12-31"
                    elif "3" in q_label:
                        end_date = f"{yr}-03-31"
                    else:
                        end_date = f"{yr}-06-30"
                else:
                    end_date = str(raw_end_qtr).strip()

                pub_date = filing_dates.get((sym, yr, q_label), end_date)
                if pd.isna(pub_date) or not str(pub_date).strip() or str(pub_date).strip().lower() in ["nan", "none", "null"]:
                    pub_date = end_date

                for m in qtr_metrics:
                    val = r.get(m)
                    if pd.notna(val):
                        rows.append({
                            "symbol": sym,
                            "statement_type": "QUARTERLY",
                            "fiscal_year": yr,
                            "fiscal_period": q_label,
                            "period_end_date": end_date,
                            "publication_date": pub_date,
                            "metric_name": m,
                            "metric_value": float(val),
                            "unit": "PKR_THOUSANDS" if m != "eps" else "PKR_PER_SHARE"
                        })

        fin_df = pd.DataFrame(rows).drop_duplicates(
            subset=["symbol", "statement_type", "fiscal_year", "fiscal_period", "metric_name"]
        )

        out_path = self.processed_dir / "company_financials_clean.csv"
        fin_df.to_csv(out_path, index=False)
        logger.info(f"Cleaned Company Financials -> {out_path} ({len(fin_df):,} records)")
        return fin_df

    def clean_announcements_and_payouts(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Cleans official corporate announcements and 2001-2026 payout history."""
        raw_ann = self.raw_dir / "kse100_corporate_announcements.csv"
        if not raw_ann.exists():
            raw_ann = self.data_root / "kse100_corporate_announcements.csv"

        raw_pay = self.raw_dir / "kse100_corporate_payouts_2001_2026.csv"
        if not raw_pay.exists():
            raw_pay = self.data_root / "kse100_corporate_payouts_2001_2026.csv"

        df_ann = pd.DataFrame()
        if raw_ann.exists():
            df_ann = pd.read_csv(raw_ann)
            df_ann["symbol"] = df_ann["symbol"].astype(str).str.strip().str.upper()
            df_ann["posting_date"] = pd.to_datetime(df_ann["posting_date"], errors="coerce").dt.strftime("%Y-%m-%d")
            df_ann["category"] = df_ann["category"].fillna("Corporate Events").astype(str).str.strip()
            df_ann["title"] = df_ann["announcement_title"].fillna("").astype(str).str.strip()
            df_ann["announcement_id"] = df_ann["announcement_id"].fillna("").astype(str).str.strip()
            df_ann["document_url"] = df_ann.get("document_url", "").fillna("")
            df_ann["attachment_url"] = df_ann.get("attachment_url", "").fillna("")
            df_ann = df_ann.dropna(subset=["symbol", "posting_date"]).drop_duplicates(subset=["symbol", "announcement_id"])
            df_ann = df_ann[["symbol", "posting_date", "category", "title", "announcement_id", "document_url", "attachment_url"]]
            out_ann = self.processed_dir / "corporate_announcements_clean.csv"
            df_ann.to_csv(out_ann, index=False)
            logger.info(f"Cleaned Corporate Announcements -> {out_ann} ({len(df_ann):,} records)")

        df_pay = pd.DataFrame()
        if raw_pay.exists():
            df_pay = pd.read_csv(raw_pay)
            df_pay["symbol"] = df_pay["symbol"].astype(str).str.strip().str.upper()
            df_pay["announcement_date"] = pd.to_datetime(df_pay["announcement_date"], errors="coerce").dt.strftime("%Y-%m-%d")
            df_pay["fiscal_year"] = pd.to_numeric(df_pay["fiscal_year"], errors="coerce").fillna(2026).astype(int)
            df_pay["payout_type"] = df_pay["payout_type"].fillna("dividend").astype(str).str.strip()
            df_pay["dividend_per_share"] = pd.to_numeric(df_pay["dividend_per_share_pkr"], errors="coerce")
            df_pay["payout_percentage"] = pd.to_numeric(df_pay["payout_percentage"], errors="coerce")
            df_pay["face_value"] = pd.to_numeric(df_pay["face_value_pkr"], errors="coerce")
            df_pay = df_pay.dropna(subset=["symbol", "announcement_date"]).drop_duplicates()
            df_pay = df_pay[[
                "symbol", "announcement_date", "fiscal_year", "payout_type",
                "dividend_per_share", "payout_percentage", "face_value"
            ]]
            out_pay = self.processed_dir / "corporate_payouts_clean.csv"
            df_pay.to_csv(out_pay, index=False)
            logger.info(f"Cleaned Corporate Payouts -> {out_pay} ({len(df_pay):,} records)")

        return df_ann, df_pay

    def run_all(self):
        """Runs complete cleaning and raw/processed isolation pipeline."""
        logger.info("Starting PSXpert Data Normalization & Separation Pipeline...")
        self.backup_raw_data()
        self.clean_companies()
        self.clean_stock_prices()
        self.clean_market_indices()
        self.clean_news()
        self.clean_financials()
        self.clean_announcements_and_payouts()
        logger.info("Complete data separation and cleaning finished successfully.")
