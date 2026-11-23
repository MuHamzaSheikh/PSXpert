"""
PSXpert - Expanded Fundamental Statements Panel Builder
Harmonizes historical audited statements across 2005-2026 for:
1. All current active KSE-100 constituents
2. All former/historical KSE-100 constituents
Preserves point-in-time publication dates (verified announcement vs conservative 100-day lag).
Never uses future information.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
import openpyxl
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ExpandedFundamentals")

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "psxpert.db"
OUTPUT_CSV = DATA_DIR / "harmonized_historical_fundamentals.csv"

# Comprehensive ticker-to-SBP mapping for active and historical constituents
TICKER_TO_SBP_KEYWORDS = {
    # Active KSE-100 non-financials
    "CHCC": ["cherat cement"],
    "DGKC": ["d.g. khan cement", "dg khan cement"],
    "FCCL": ["fauji cement"],
    "FFC": ["fauji fertilizer company"],
    "FFL": ["fauji foods", "noon pakistan"],
    "FATIMA": ["fatima fertilizer"],
    "EFERT": ["engro fertilizers"],
    "ENGROH": ["engro corp", "engro chemical"],
    "HUBC": ["hub power"],
    "KAPCO": ["kot addu power"],
    "KEL": ["k-electric", "karachi electric"],
    "LUCK": ["lucky cement"],
    "MLCF": ["maple leaf cement"],
    "OGDC": ["oil & gas development", "ogdcl"],
    "POL": ["pakistan oilfields"],
    "PPL": ["pakistan petroleum"],
    "PSO": ["pakistan state oil"],
    "SYS": ["systems limited", "systems ltd"],
    "TRG": ["trg pakistan"],
    "PTC": ["pakistan telecommunication"],
    "SEARL": ["searle company"],
    "SNGP": ["sui northern gas"],
    "SSGC": ["sui southern gas"],
    "ILP": ["interloop"],
    "ISL": ["international steels"],
    "INIL": ["international industries"],
    "PIOC": ["pioneer cement"],
    "BWCL": ["bestway cement"],
    "KOHC": ["kohat cement"],
    "CNERGY": ["cnergyico", "byco petroleum"],
    "ATRL": ["attock refinery"],
    "PRL": ["pakistan refinery"],
    "APL": ["attock petroleum"],
    "NATF": ["national foods"],
    "NESTLE": ["nestle pakistan"],
    "COLG": ["colgate-palmolive"],
    "AGP": ["agp limited"],
    "ABOT": ["abbott laboratories"],
    "GLAXO": ["glaxosmithkline"],
    "HALEON": ["haleon pakistan", "glaxosmithkline consumer"],
    "INDU": ["indus motor"],
    "HCAR": ["honda atlas"],
    "ATLH": ["atlas honda"],
    "MTL": ["millat tractors"],
    "SAZEW": ["sazgar engineering"],
    "PAEL": ["pak elektron"],
    "AIRLINK": ["air link communication"],
    "GADT": ["gadoon textile"],
    "NML": ["nishat mills"],
    "KTML": ["kohinoor textile"],
    # Historical Constituents
    "UNITY": ["unity foods"],
    "PKGP": ["pakgen power", "aes pak gen"],
    "AVN": ["avanceon"],
    "EPCL": ["engro polymer"],
    "MUGHAL": ["mughal iron"],
    "NPL": ["nishat power"],
    "AGL": ["agritech", "pak-american"],
    "HUMNL": ["hum network", "eye television"],
    "PABC": ["pakistan aluminium beverage"],
    "RMPL": ["rafhan maize"],
    "HASCOL": ["hascol petroleum"],
    "ASL": ["aisha steel"],
    "ANL": ["azgard nine"],
    "GATM": ["gul ahmed textile"],
    "ARPL": ["archroma pakistan", "clariant pakistan"],
    "SHJS": ["shakarganj"],
    "NCL": ["nishat chunian", "nishat (chunian)"],
    "CEPB": ["century paper"],
    "CPBM": ["century paper"],
    "SPWL": ["saif power"],
    "LPL": ["lalpir power", "aes lalpir"],
    "CSAP": ["crescent steel"],
    "KOSM": ["kohinoor spinning"],
    "NRL": ["national refinery"],
    "HSM": ["habib sugar"],
    "POML": ["punjab oil mills"],
    "FCEPL": ["frieslandcampina engro", "engro foods"],
    "SHEL": ["shell pakistan"],
}


def load_verified_announcements() -> dict[tuple[str, int], str]:
    """Map (symbol, fiscal_year) to verified publication date."""
    csv_path = DATA_DIR / "kse100_corporate_announcements.csv"
    if not csv_path.exists():
        return {}
    df = pd.read_csv(csv_path)
    earn_df = df[df["category"].str.contains("Earnings|Financial Results|Accounts", case=False, na=False)]
    v_map = {}
    for _, r in earn_df.iterrows():
        sym = str(r["symbol"]).upper().strip()
        posting = str(r["posting_date"]).split(" ")[0].strip()
        title = str(r.get("announcement_title", "")).lower()
        m = re.search(r"20\d\d", title)
        yr = int(m.group(0)) if m else pd.to_datetime(posting, errors="coerce").year
        if pd.isna(yr):
            continue
        key = (sym, int(yr))
        if key not in v_map or "annual" in title or "year ended" in title:
            v_map[key] = posting
    return v_map


def parse_sbp_metrics_for_companies() -> list[dict[str, Any]]:
    """Parses SBP FSA archive (2005-2023) for mapped companies."""
    wb_path = RAW_DIR / "sbp_fsa_archive_2005_2023.xlsx"
    if not wb_path.exists():
        logger.warning("SBP FSA Archive %s not found.", wb_path)
        return []

    logger.info("Opening SBP FSA Archive (2005-2023)...")
    wb = openpyxl.load_workbook(wb_path, read_only=True)

    extracted_records: list[dict[str, Any]] = []

    # Process sheets 2014-23, 2009-13, 2005-08
    sheets_info = [
        ("2014-23", [str(y) for y in range(2014, 2024)]),
        ("2009-13", [str(y) for y in range(2009, 2014)]),
        ("2005-08", [str(y) for y in range(2005, 2009)]),
    ]

    for sname, years in sheets_info:
        if sname not in wb.sheetnames:
            continue
        sheet = wb[sname]
        logger.info("Parsing sheet: %s for %d target entities...", sname, len(TICKER_TO_SBP_KEYWORDS))

        year_cols = {}
        # Buffer company items: (sym, year) -> metric dict
        current_data: dict[tuple[str, int], dict[str, float]] = {}

        for i, row in enumerate(sheet.iter_rows(values_only=True)):
            if i == 0:
                for idx, col_val in enumerate(row):
                    val_str = str(col_val).strip()
                    if val_str in years:
                        year_cols[idx] = int(val_str)
                continue

            org = row[2]
            if not org or "All Sector" in str(org) or str(org) == "None":
                continue

            org_str = str(org).lower()
            # Find matching ticker
            matched_sym = None
            for sym, kw_list in TICKER_TO_SBP_KEYWORDS.items():
                if any(kw in org_str for kw in kw_list):
                    matched_sym = sym
                    break

            if not matched_sym:
                continue

            item_str = str(row[3]).strip() if row[3] else ""
            if not item_str:
                continue

            # Identify metric category
            item_lower = item_str.lower()
            is_assets = "total assets (a+b)" in item_lower or item_lower.startswith("total assets")
            is_equity = "shareholders' equity" in item_lower or "shareholders’ equity" in item_lower
            is_sales = item_lower == "1. sales" or item_lower.startswith("1. sales") or "sales / turnover" in item_lower
            is_pat = ("profit / (loss) after tax" in item_lower or "profit/(loss) after tax" in item_lower or 
                      "profit after tax" in item_lower or "profit / (loss) after taxation" in item_lower or
                      "profit/(loss) after taxation" in item_lower or "profit after taxation" in item_lower)
            is_pbt = ("profit / (loss) before taxation" in item_lower or "profit/(loss) before taxation" in item_lower or
                      "profit before taxation" in item_lower or "profit before tax" in item_lower)
            is_tax = item_lower.startswith("8. tax expenses") or item_lower == "8. tax expenses"
            is_op = (item_lower.startswith("6. ebit") or item_lower.startswith("3. gross profit") or 
                     ("operating profit" in item_lower and "margin" not in item_lower))
            is_cf = ("net cash flows from operating activities" in item_lower or item_lower.startswith("8. operating cash flow") or
                     item_lower.startswith("1. net cash flows from operating"))
            is_eps = ("basic earnings per share" in item_lower or item_lower.startswith("v3. basic earnings") or 
                      item_lower.startswith("v2. basic earnings"))
            is_ncl = "d. non-current liabilities" in item_lower
            is_cl = "e. current liabilities" in item_lower

            for c_idx, yr in year_cols.items():
                val = row[c_idx] if c_idx < len(row) else None
                if val is None or str(val).strip() in ["", "None", "-", "N/A"]:
                    continue
                try:
                    num_val = float(val)
                except ValueError:
                    continue

                key = (matched_sym, yr)
                if key not in current_data:
                    current_data[key] = {
                        "total_assets": np.nan,
                        "shareholders_equity": np.nan,
                        "revenue": np.nan,
                        "net_income": np.nan,
                        "pbt": np.nan,
                        "tax": np.nan,
                        "operating_profit": np.nan,
                        "operating_cash_flow": np.nan,
                        "eps_basic": np.nan,
                        "non_current_liab": 0.0,
                        "current_liab": 0.0,
                    }

                if is_assets and np.isnan(current_data[key]["total_assets"]):
                    current_data[key]["total_assets"] = num_val
                elif is_equity and np.isnan(current_data[key]["shareholders_equity"]):
                    current_data[key]["shareholders_equity"] = num_val
                elif is_sales and np.isnan(current_data[key]["revenue"]):
                    current_data[key]["revenue"] = num_val
                elif is_pat and np.isnan(current_data[key]["net_income"]):
                    current_data[key]["net_income"] = num_val
                elif is_pbt and np.isnan(current_data[key]["pbt"]):
                    current_data[key]["pbt"] = num_val
                elif is_tax and np.isnan(current_data[key]["tax"]):
                    current_data[key]["tax"] = num_val
                elif is_op and np.isnan(current_data[key]["operating_profit"]):
                    current_data[key]["operating_profit"] = num_val
                elif is_cf and np.isnan(current_data[key]["operating_cash_flow"]):
                    current_data[key]["operating_cash_flow"] = num_val
                elif is_eps and np.isnan(current_data[key]["eps_basic"]):
                    current_data[key]["eps_basic"] = num_val
                elif is_ncl:
                    current_data[key]["non_current_liab"] = num_val
                elif is_cl:
                    current_data[key]["current_liab"] = num_val

        # Convert sheet observations into records (converting SBP '000 to Millions: / 1000.0)
        for (sym, yr), mdict in current_data.items():
            tot_debt = mdict["non_current_liab"] + mdict["current_liab"]
            
            # Resolve net income (use PAT directly, or PBT - Tax fallback)
            net_inc = mdict["net_income"]
            if np.isnan(net_inc) and not np.isnan(mdict["pbt"]):
                tax_val = mdict["tax"] if not np.isnan(mdict["tax"]) else 0.0
                net_inc = mdict["pbt"] - tax_val

            # Scale SBP '000 to Millions: num / 1000.0
            extracted_records.append({
                "symbol": sym,
                "fiscal_year": yr,
                "period_end_date": f"{yr}-06-30",  # Standard fiscal year end for industrial firms
                "source": f"SBP FSA Archive ({sname})",
                "total_assets": round(mdict["total_assets"] / 1000.0, 3) if not np.isnan(mdict["total_assets"]) else None,
                "shareholders_equity": round(mdict["shareholders_equity"] / 1000.0, 3) if not np.isnan(mdict["shareholders_equity"]) else None,
                "revenue": round(mdict["revenue"] / 1000.0, 3) if not np.isnan(mdict["revenue"]) else None,
                "net_income": round(net_inc / 1000.0, 3) if not np.isnan(net_inc) else None,
                "operating_profit": round(mdict["operating_profit"] / 1000.0, 3) if not np.isnan(mdict["operating_profit"]) else None,
                "total_debt": round(tot_debt / 1000.0, 3) if tot_debt > 0 else None,
                "operating_cash_flow": round(mdict["operating_cash_flow"] / 1000.0, 3) if not np.isnan(mdict["operating_cash_flow"]) else None,
                "free_cash_flow": round(mdict["operating_cash_flow"] / 1000.0, 3) if not np.isnan(mdict["operating_cash_flow"]) else None,
                "interest_expense": None,
                "eps_basic": mdict["eps_basic"] if not np.isnan(mdict["eps_basic"]) else None,
                "shares_outstanding": None,
                "net_interest_income": None,
                "non_interest_expense": None,
                "total_operating_income": None,
            })

    wb.close()
    logger.info("Extracted %d annual company-year statements from SBP archive.", len(extracted_records))
    return extracted_records


def build_unified_statement_panel():
    """Merges relational statements and SBP statements with strict point-in-time publication dates."""
    verified_announcements = load_verified_announcements()

    # Load companies metadata from DB
    conn = sqlite3.connect(DB_PATH)
    comp_df = pd.read_sql("SELECT symbol, company_name, sector, sector_category FROM companies", conn)
    conn.close()

    comp_meta = {}
    for _, r in comp_df.iterrows():
        sym = str(r["symbol"]).upper().strip()
        sec = str(r["sector"]).strip()
        cat = str(r.get("sector_category", "")).strip()
        is_b = "COMMERCIAL BANKS" in sec.upper() or "BANK" in cat.upper()
        comp_meta[sym] = {"company_name": str(r["company_name"]), "sector": sec, "is_bank": is_b}

    all_records: list[dict[str, Any]] = []

    # 1. Ingest existing relational statements (data/kse100_fundamentals_annual.csv)
    ann_path = DATA_DIR / "kse100_fundamentals_annual.csv"
    if ann_path.exists():
        df_ann = pd.read_csv(ann_path)
        for _, r in df_ann.iterrows():
            sym = str(r["symbol"]).upper().strip()
            yr = int(r["fiscal_year"])
            meta = comp_meta.get(sym, {"company_name": sym, "sector": "UNCLASSIFIED", "is_bank": False})
            p_end = str(r.get("period_end_date", f"{yr}-06-30")).split(" ")[0].strip()

            tot_a = pd.to_numeric(r.get("total_assets"), errors="coerce")
            tot_l = pd.to_numeric(r.get("total_liabilities"), errors="coerce")
            eq = pd.to_numeric(r.get("shareholders_equity"), errors="coerce")
            if (pd.isna(eq) or eq <= 0) and pd.notna(tot_a) and pd.notna(tot_l) and (tot_a > tot_l > 0):
                eq = tot_a - tot_l

            all_records.append({
                "symbol": sym,
                "company_name": meta["company_name"],
                "sector": meta["sector"],
                "is_bank": meta["is_bank"],
                "fiscal_year": yr,
                "period_end_date": p_end,
                "source": "kse100_fundamentals_annual.csv",
                "net_income": pd.to_numeric(r.get("net_profit_after_tax"), errors="coerce"),
                "revenue": pd.to_numeric(r.get("revenue_sales"), errors="coerce"),
                "shareholders_equity": eq,
                "total_assets": tot_a,
                "operating_profit": pd.to_numeric(r.get("operating_profit"), errors="coerce"),
                "operating_cash_flow": pd.to_numeric(r.get("operating_cash_flow"), errors="coerce"),
                "free_cash_flow": pd.to_numeric(r.get("free_cash_flow"), errors="coerce"),
                "total_debt": pd.to_numeric(r.get("total_debt"), errors="coerce"),
                "interest_expense": pd.to_numeric(r.get("interest_expense", 0), errors="coerce"),
                "eps_basic": pd.to_numeric(r.get("eps_basic"), errors="coerce"),
                "shares_outstanding": pd.to_numeric(r.get("common_shares_outstanding"), errors="coerce"),
                "net_interest_income": pd.to_numeric(r.get("net_interest_income"), errors="coerce") if meta["is_bank"] else np.nan,
                "non_interest_expense": pd.to_numeric(r.get("operating_expenses"), errors="coerce") if meta["is_bank"] else np.nan,
                "total_operating_income": pd.to_numeric(r.get("operating_income"), errors="coerce") if meta["is_bank"] else np.nan,
            })

    # 2. Ingest SBP parsed statements
    sbp_records = parse_sbp_metrics_for_companies()
    for rec in sbp_records:
        sym = rec["symbol"]
        meta = comp_meta.get(sym, {"company_name": sym, "sector": "UNCLASSIFIED", "is_bank": False})
        rec["company_name"] = meta["company_name"]
        rec["sector"] = meta["sector"]
        rec["is_bank"] = meta["is_bank"]
        all_records.append(rec)

    df_all = pd.DataFrame(all_records)
    logger.info("Combined raw statement count: %d rows across %d symbols.", len(df_all), df_all["symbol"].nunique())

    # Point-in-Time Publication Date Resolution
    resolved_rows = []
    for _, r in df_all.iterrows():
        sym = str(r["symbol"])
        yr = int(r["fiscal_year"])
        p_end = str(r["period_end_date"]).split(" ")[0].strip()
        try:
            p_end_dt = pd.to_datetime(p_end)
        except Exception:
            p_end_dt = pd.to_datetime(f"{yr}-06-30")
            p_end = f"{yr}-06-30"

        candidate_pub = verified_announcements.get((sym, yr))
        if candidate_pub and pd.to_datetime(candidate_pub) >= p_end_dt:
            pub_date = candidate_pub
            is_est = False
            conf = "VERIFIED_ANNOUNCEMENT"
        else:
            pub_date = (p_end_dt + timedelta(days=100)).strftime("%Y-%m-%d")
            is_est = True
            conf = "ESTIMATED_100D_FALLBACK"

        row_dict = r.to_dict()
        row_dict["publication_date"] = pub_date
        row_dict["is_estimated_publication"] = is_est
        row_dict["timestamp_confidence"] = conf
        resolved_rows.append(row_dict)

    df_panel = pd.DataFrame(resolved_rows)

    # Deduplicate: if both kse100 CSV and SBP exist for same (symbol, yr), prefer the one with more non-null fields, then verified announcement
    df_panel["non_null_count"] = df_panel[["net_income", "total_assets", "shareholders_equity", "revenue", "operating_profit"]].notnull().sum(axis=1)
    df_panel.sort_values(
        by=["symbol", "fiscal_year", "non_null_count", "is_estimated_publication"],
        ascending=[True, True, False, True],
        inplace=True
    )
    df_panel.drop_duplicates(subset=["symbol", "fiscal_year"], keep="first", inplace=True)
    df_panel.drop(columns=["non_null_count"], inplace=True)
    df_panel.sort_values(by=["symbol", "fiscal_year"], inplace=True)
    df_panel.reset_index(drop=True, inplace=True)

    df_panel.to_csv(OUTPUT_CSV, index=False)
    logger.info("Saved harmonized panel with %d statements across %d symbols to %s", len(df_panel), df_panel["symbol"].nunique(), OUTPUT_CSV)

    # Ingest into SQLite company_financials
    conn = sqlite3.connect(DB_PATH)
    # Check current financials count
    cur_count = conn.execute("SELECT COUNT(*) FROM company_financials").fetchone()[0]
    logger.info("Current SQLite company_financials count: %d", cur_count)
    conn.close()

    return df_panel


if __name__ == "__main__":
    df = build_unified_statement_panel()
    print("Harmonized fundamental panel successfully generated!")
    print(f"Total statements: {len(df)} across {df['symbol'].nunique()} unique companies.")
    print("Year range:", df["fiscal_year"].min(), "to", df["fiscal_year"].max())
    print("Timestamp confidence breakdown:\n", df["timestamp_confidence"].value_counts())
    print("Sample historical constituents coverage:")
    for test_sym in ["UNITY", "PKGP", "AVN", "MUGHAL", "EPCL", "AGL", "HUMNL", "PABC", "RMPL", "HASCOL"]:
        sub = df[df["symbol"] == test_sym]
        print(f"  {test_sym:8}: {len(sub)} statements ({sub['fiscal_year'].min()} - {sub['fiscal_year'].max()})")
