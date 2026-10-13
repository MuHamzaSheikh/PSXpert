"""
PSXpert - Pakistan Stock Exchange Fundamentals Scraper
Fetches comprehensive financial statement data (Income Statement, Balance Sheet, Cash Flow, Ratios)
for PSX listed companies across both Annual (ANN) and Quarterly (QTR) reporting periods.

Sources:
1. Direct PSX Data Portal (DPS) - Official exchange financial statements & quarterly results
2. Sarmaaya REST API - Detailed balance sheets, cash flow metrics, and valuation ratios
"""

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PSXFundamentals")


class PSXFundamentalsScraper:
    SARMAAYA_BASE = "https://beta-restapi.sarmaaya.pk/api/stocks/fundamentals"
    DPS_BASE = "https://dps.psx.com.pk/company"
    
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
    def _clean_numeric(val: Any) -> Optional[float]:
        """Convert financial string (e.g. '449,190,752', '(18.71)', '45.2%') to float."""
        if val is None or pd.isna(val):
            return None
        if isinstance(val, (int, float)):
            return float(val)
        val_str = str(val).strip().replace(",", "").replace("%", "")
        if not val_str or val_str in ["-", "--", "N/A", "null", "None"]:
            return None
        # Handle accounting parentheses for negative numbers (e.g. (18.71))
        if val_str.startswith("(") and val_str.endswith(")"):
            val_str = "-" + val_str[1:-1]
        try:
            return float(val_str)
        except ValueError:
            return None

    def fetch_dps_financials(self, symbol: str) -> Dict[str, Any]:
        """
        Scrapes official PSX DPS company page for audited Annual and Quarterly
        Sales, Net Profit after Tax, EPS, and Margins.
        """
        url = f"{self.DPS_BASE}/{symbol}"
        res = {"annual": [], "quarterly": [], "ratios": []}
        try:
            r = cffi_requests.get(url, impersonate="chrome120", timeout=10)
            if r.status_code != 200:
                return res
            
            soup = BeautifulSoup(r.text, "html.parser")
            tables = soup.find_all("table")
            
            for t in tables:
                rows = t.find_all("tr")
                if not rows or len(rows) < 2:
                    continue
                header = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
                if not header:
                    continue
                
                # Check for Annual Results Table (years like 2026, 2025, 2024...)
                years_match = [col for col in header[1:] if re.match(r"^20\d\d$", col)]
                if years_match and any("sales" in r.get_text(strip=True).lower() or "profit" in r.get_text(strip=True).lower() or "mark-up" in r.get_text(strip=True).lower() for r in rows):
                    for col_idx, yr in enumerate(years_match, start=1):
                        yr_int = int(yr)
                        row_data = {"symbol": symbol, "fiscal_year": yr_int}
                        for row in rows[1:]:
                            cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                            if len(cells) > col_idx:
                                metric_name = cells[0].strip()
                                metric_val = self._clean_numeric(cells[col_idx])
                                row_data[metric_name] = metric_val
                        res["annual"].append(row_data)

                # Check for Quarterly Results Table (quarters like Q3 2026, Q2 2026, Q1 2026...)
                quarters_match = [col for col in header[1:] if re.match(r"^Q[1-4]\s+20\d\d$", col, re.IGNORECASE)]
                if quarters_match and any("sales" in r.get_text(strip=True).lower() or "profit" in r.get_text(strip=True).lower() or "mark-up" in r.get_text(strip=True).lower() for r in rows):
                    for col_idx, q_label in enumerate(quarters_match, start=1):
                        parts = q_label.split()
                        q_name = parts[0].upper()
                        yr_int = int(parts[1])
                        row_data = {"symbol": symbol, "fiscal_year": yr_int, "fiscal_quarter": q_name}
                        for row in rows[1:]:
                            cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                            if len(cells) > col_idx:
                                metric_name = cells[0].strip()
                                metric_val = self._clean_numeric(cells[col_idx])
                                row_data[metric_name] = metric_val
                        res["quarterly"].append(row_data)

                # Check for Ratios Table
                if years_match and any("margin" in r.get_text(strip=True).lower() or "peg" in r.get_text(strip=True).lower() for r in rows):
                    for col_idx, yr in enumerate(years_match, start=1):
                        yr_int = int(yr)
                        row_data = {"symbol": symbol, "fiscal_year": yr_int}
                        for row in rows[1:]:
                            cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                            if len(cells) > col_idx:
                                metric_name = cells[0].strip()
                                metric_val = self._clean_numeric(cells[col_idx])
                                row_data[metric_name] = metric_val
                        res["ratios"].append(row_data)

        except Exception as e:
            logger.debug(f"DPS fetch error for {symbol}: {e}")
        return res

    def fetch_sarmaaya_statement(self, isin: str, endpoint: str, periodicity: str) -> List[Dict[str, Any]]:
        """
        Fetches fundamentals statement (income-statement, balance-sheet, cashflow, ratios)
        from Sarmaaya REST API for a given ISIN and periodicity.
        """
        url = f"{self.SARMAAYA_BASE}/{endpoint}?isin={isin}&periodicity={periodicity}"
        try:
            r = requests.get(url, headers=self.DEFAULT_HEADERS, timeout=12)
            if r.status_code != 200:
                return []
            data = r.json()
            resp = data.get("response", {})
            if not isinstance(resp, dict):
                return []

            period_map: Dict[Tuple[int, int, str], Dict[str, Any]] = {}
            for metric_name, metric_info in resp.items():
                if not isinstance(metric_info, dict):
                    continue
                entries = metric_info.get("data", [])
                for entry in entries:
                    year = entry.get("year")
                    fp = entry.get("fiscalPeriod")
                    dt_raw = entry.get("date")
                    val = self._clean_numeric(entry.get("value"))
                    
                    dt_str = dt_raw[:10] if dt_raw else ""
                    key = (year, fp, dt_str)
                    if key not in period_map:
                        period_map[key] = {}
                    period_map[key][metric_name] = val

            rows = []
            for (year, fp, dt_str), metrics in period_map.items():
                row = {
                    "year": year,
                    "fiscal_period": fp,
                    "period_end_date": dt_str,
                    **metrics
                }
                rows.append(row)
            return rows
        except Exception as e:
            logger.debug(f"Sarmaaya fetch error for {isin} {endpoint}: {e}")
            return []

    def get_company_fundamentals(self, row: pd.Series) -> Dict[str, Any]:
        """
        Aggregates DPS and Sarmaaya fundamentals for a single company across ANN and QTR.
        """
        sym = row["symbol"]
        isin = row["isin"]
        company_name = row.get("name", "")
        sector = row.get("sectorName", "")

        # 1. Fetch DPS Official Exchange Data
        dps_data = self.fetch_dps_financials(sym)

        # 2. Fetch Sarmaaya Statements for ANN and QTR
        inc_ann = self.fetch_sarmaaya_statement(isin, "income-statement", "ANN")
        bs_ann = self.fetch_sarmaaya_statement(isin, "balance-sheet", "ANN")
        cf_ann = self.fetch_sarmaaya_statement(isin, "cashflow", "ANN")
        ratios_ann = self.fetch_sarmaaya_statement(isin, "ratios", "ANN")

        inc_qtr = self.fetch_sarmaaya_statement(isin, "income-statement", "QTR")
        bs_qtr = self.fetch_sarmaaya_statement(isin, "balance-sheet", "QTR")
        cf_qtr = self.fetch_sarmaaya_statement(isin, "cashflow", "QTR")
        ratios_qtr = self.fetch_sarmaaya_statement(isin, "ratios", "QTR")

        return {
            "symbol": sym,
            "isin": isin,
            "company_name": company_name,
            "sector": sector,
            "dps": dps_data,
            "sarmaaya_ann": {
                "income": inc_ann,
                "balance": bs_ann,
                "cashflow": cf_ann,
                "ratios": ratios_ann
            },
            "sarmaaya_qtr": {
                "income": inc_qtr,
                "balance": bs_qtr,
                "cashflow": cf_qtr,
                "ratios": ratios_qtr
            }
        }

    def process_all_companies(self, max_workers: int = 10, limit: Optional[int] = None) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Scrapes and compiles master annual, quarterly, and ratios datasets for all companies.
        """
        target_df = self.companies_df.head(limit) if limit else self.companies_df
        total = len(target_df)
        logger.info(f"Starting fundamentals extraction for {total} companies...")

        annual_rows = []
        quarterly_rows = []
        ratios_rows = []

        start_time = time.time()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_sym = {
                executor.submit(self.get_company_fundamentals, row): row["symbol"]
                for _, row in target_df.iterrows()
            }
            completed = 0
            for future in as_completed(future_to_sym):
                completed += 1
                sym = future_to_sym[future]
                try:
                    res = future.result()
                    parsed_ann, parsed_qtr, parsed_rat = self._harmonize_company_data(res)
                    annual_rows.extend(parsed_ann)
                    quarterly_rows.extend(parsed_qtr)
                    ratios_rows.extend(parsed_rat)
                    if completed % 10 == 0 or completed == total:
                        logger.info(f"Progress: [{completed}/{total}] companies processed ({sym})")
                except Exception as e:
                    logger.error(f"Error processing {sym}: {e}")

        logger.info(f"Extraction completed in {time.time() - start_time:.2f}s")
        
        df_ann = pd.DataFrame(annual_rows)
        df_qtr = pd.DataFrame(quarterly_rows)
        df_rat = pd.DataFrame(ratios_rows)

        if not df_ann.empty:
            df_ann = df_ann.sort_values(by=["symbol", "fiscal_year"], ascending=[True, False]).reset_index(drop=True)
        if not df_qtr.empty:
            df_qtr = df_qtr.sort_values(by=["symbol", "fiscal_year", "fiscal_quarter"], ascending=[True, False, False]).reset_index(drop=True)
        if not df_rat.empty:
            df_rat = df_rat.sort_values(by=["symbol", "fiscal_year"], ascending=[True, False]).reset_index(drop=True)

        return df_ann, df_qtr, df_rat

    def _harmonize_company_data(self, data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Merges DPS and Sarmaaya reports into standardized annual and quarterly records.
        """
        sym = data["symbol"]
        name = data["company_name"]
        sector = data["sector"]
        dps = data["dps"]
        s_ann = data["sarmaaya_ann"]
        s_qtr = data["sarmaaya_qtr"]

        # Index DPS annual results by year
        dps_ann_by_year = {r["fiscal_year"]: r for r in dps.get("annual", [])}
        dps_qtr_by_yq = {(r["fiscal_year"], r.get("fiscal_quarter", "")): r for r in dps.get("quarterly", [])}
        dps_rat_by_year = {r["fiscal_year"]: r for r in dps.get("ratios", [])}

        # Index Sarmaaya annual statements by year
        s_inc_ann_by_year = {r["year"]: r for r in s_ann["income"]}
        s_bs_ann_by_year = {r["year"]: r for r in s_ann["balance"]}
        s_cf_ann_by_year = {r["year"]: r for r in s_ann["cashflow"]}
        s_rat_ann_by_year = {r["year"]: r for r in s_ann["ratios"]}

        # All available annual years
        all_ann_years = sorted(
            set(list(dps_ann_by_year.keys()) + list(s_inc_ann_by_year.keys()) + list(s_bs_ann_by_year.keys())),
            reverse=True
        )

        annual_records = []
        for yr in all_ann_years:
            d_ann = dps_ann_by_year.get(yr, {})
            inc = s_inc_ann_by_year.get(yr, {})
            bs = s_bs_ann_by_year.get(yr, {})
            cf = s_cf_ann_by_year.get(yr, {})

            # Revenue priority: DPS verified official sales / mark-up, else Sarmaaya
            revenue = d_ann.get("Sales") or d_ann.get("Mark-up Earned") or d_ann.get("Total Income") or inc.get("Revenue") or inc.get("Interest Income")
            gross_profit = inc.get("Gross Profit")
            operating_profit = inc.get("Operating Profit(EBIT)") or inc.get("Operating Profit")
            
            # Profit after tax: DPS verified else Sarmaaya
            net_profit = d_ann.get("Profit after Taxation") or inc.get("Net Income")
            eps = d_ann.get("EPS") or inc.get("Basic EPS")
            eps_diluted = inc.get("Diluted EPS")

            # Balance sheet items
            tot_assets = bs.get("Total Assets")
            cur_assets = bs.get("Total Current Assets")
            cash_eq = bs.get("Cash & Equivalents") or bs.get("Cash & Due from Banks")
            net_ppe = bs.get("Net PPE")
            tot_liab = bs.get("Total Liabilities")
            cur_liab = bs.get("Current Liabilities")
            tot_debt = bs.get("Total Debt")
            equity = bs.get("Shareholders Equity") or bs.get("Shareholders' Equity") or bs.get("Total Equity")
            retained_earnings = bs.get("Retained Earnings")
            shares_out = bs.get("Common Shares Outstanding")

            # Cash flow items
            cfo = cf.get("Cashflow from Operations")
            capex = cf.get("Capital Expenditures")
            cfi = cf.get("Cashflow from Investing")
            cff = cf.get("Cashflow from Financing")
            dividends_paid = cf.get("Dividends Paid")
            fcf = cf.get("Free Cash Flow")

            period_end_date = inc.get("period_end_date") or bs.get("period_end_date") or f"{yr}-06-30"

            annual_records.append({
                "symbol": sym,
                "company_name": name,
                "sector": sector,
                "periodicity": "ANN",
                "fiscal_year": yr,
                "period_end_date": period_end_date,
                "revenue_sales": revenue,
                "gross_profit": gross_profit,
                "operating_profit": operating_profit,
                "net_profit_after_tax": net_profit,
                "eps_basic": eps,
                "eps_diluted": eps_diluted,
                "total_assets": tot_assets,
                "current_assets": cur_assets,
                "cash_and_equivalents": cash_eq,
                "net_ppe": net_ppe,
                "total_liabilities": tot_liab,
                "current_liabilities": cur_liab,
                "total_debt": tot_debt,
                "shareholders_equity": equity,
                "retained_earnings": retained_earnings,
                "common_shares_outstanding": shares_out,
                "operating_cash_flow": cfo,
                "capital_expenditures": capex,
                "investing_cash_flow": cfi,
                "financing_cash_flow": cff,
                "dividends_paid": dividends_paid,
                "free_cash_flow": fcf
            })

        # Process Quarterly records
        quarterly_records = []
        # Index Sarmaaya quarterly statements by (year, fiscal_period)
        s_inc_qtr_by_yfp = {(r["year"], r["fiscal_period"]): r for r in s_qtr["income"]}
        s_bs_qtr_by_yfp = {(r["year"], r["fiscal_period"]): r for r in s_qtr["balance"]}
        s_cf_qtr_by_yfp = {(r["year"], r["fiscal_period"]): r for r in s_qtr["cashflow"]}

        # Map DPS quarters (Q1, Q2, Q3, Q4)
        for (yr, q_label), d_qtr in dps_qtr_by_yq.items():
            q_num = int(q_label[1]) if len(q_label) > 1 and q_label[1].isdigit() else 0
            inc = s_inc_qtr_by_yfp.get((yr, q_num), {})
            bs = s_bs_qtr_by_yfp.get((yr, q_num), {})
            cf = s_cf_qtr_by_yfp.get((yr, q_num), {})

            revenue = d_qtr.get("Sales") or d_qtr.get("Mark-up Earned") or d_qtr.get("Total Income") or inc.get("Revenue")
            net_profit = d_qtr.get("Profit after Taxation") or inc.get("Net Income")
            eps = d_qtr.get("EPS") or inc.get("Basic EPS")

            tot_assets = bs.get("Total Assets")
            tot_liab = bs.get("Total Liabilities")
            tot_debt = bs.get("Total Debt")
            equity = bs.get("Shareholders Equity") or bs.get("Shareholders' Equity") or bs.get("Total Equity")
            cfo = cf.get("Cashflow from Operations")
            fcf = cf.get("Free Cash Flow")

            period_end_date = inc.get("period_end_date") or bs.get("period_end_date") or ""

            quarterly_records.append({
                "symbol": sym,
                "company_name": name,
                "sector": sector,
                "periodicity": "QTR",
                "fiscal_year": yr,
                "fiscal_quarter": q_label,
                "period_end_date": period_end_date,
                "revenue_sales": revenue,
                "gross_profit": inc.get("Gross Profit"),
                "operating_profit": inc.get("Operating Profit(EBIT)") or inc.get("Operating Profit"),
                "net_profit_after_tax": net_profit,
                "eps": eps,
                "total_assets": tot_assets,
                "total_liabilities": tot_liab,
                "total_debt": tot_debt,
                "shareholders_equity": equity,
                "operating_cash_flow": cfo,
                "free_cash_flow": fcf
            })

        # Process Ratios records
        ratios_records = []
        for yr in all_ann_years:
            d_rat = dps_rat_by_year.get(yr, {})
            s_rat = s_rat_ann_by_year.get(yr, {})
            if not d_rat and not s_rat:
                continue

            ratios_records.append({
                "symbol": sym,
                "company_name": name,
                "sector": sector,
                "fiscal_year": yr,
                "pe_ratio": s_rat.get("Price to Earnings"),
                "pb_ratio": s_rat.get("Price to Book Value"),
                "ps_ratio": s_rat.get("Price to Sales"),
                "enterprise_value": s_rat.get("Enterprise Value"),
                "ev_to_ebitda": s_rat.get("Enterprise Value to EBITDA (x)"),
                "debt_to_equity_pct": s_rat.get("Debt to Equity (%)"),
                "debt_to_asset_pct": s_rat.get("Debt to Asset (%)"),
                "current_ratio": s_rat.get("Current Ratio (x)"),
                "quick_ratio": s_rat.get("Quick Ratio (x)"),
                "return_on_equity_pct": s_rat.get("Return on Common Equity (%)") or s_rat.get("Return on Average Total Equity (%)"),
                "return_on_assets_pct": s_rat.get("Return on Average Assets (%)"),
                "gross_profit_margin_pct": d_rat.get("Gross Profit Margin (%)") or s_rat.get("Gross Income Margin (x)"),
                "net_profit_margin_pct": d_rat.get("Net Profit Margin (%)") or s_rat.get("Net Income Margin (%)"),
                "operating_margin_pct": s_rat.get("Operating Margin (x)"),
                "dividend_yield_pct": s_rat.get("Dividend Yield (%)"),
                "dividend_per_share": s_rat.get("Dividends Per Share"),
                "book_value_per_share": s_rat.get("Book Value Per Share"),
                "free_cash_flow_per_share": s_rat.get("Free Cash Flow Per Share"),
                "eps_growth_pct": d_rat.get("EPS Growth (%)"),
                "peg_ratio": d_rat.get("PEG")
            })

        return annual_records, quarterly_records, ratios_records
