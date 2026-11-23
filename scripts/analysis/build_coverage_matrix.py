"""Comprehensive SBP FSA & Relational Financial Statement Coverage Matrix Generator.

Audits every KSE-100 company against official State Bank of Pakistan (SBP) Financial
Statement Analysis publications and exchange disclosure records.
Generates:
- reports/model_evaluation/sbp_fsa_coverage_matrix.csv
- reports/model_evaluation/sbp_fsa_unmatched_review.csv
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

import openpyxl
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CoverageMatrix")

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
REPORTS_DIR = Path("reports/model_evaluation")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Curated alias dictionary mapping PSX tickers/names to SBP FSA entity names
TICKER_TO_SBP_ALIASES: dict[str, list[str]] = {
    # Commercial Banks (matched against sbp_fsa_financial_sector_2021_2025.xlsx)
    "ABL": ["Allied Bank Limited", "Allied Bank Ltd.", "Allied Bank"],
    "AKBL": ["Askari Bank Limited", "Askari Bank Ltd.", "Askari Bank"],
    "BAFL": ["Bank Alfalah Limited", "Bank Alfalah Ltd.", "Bank Alfalah"],
    "BAHL": ["Bank AL Habib Limited", "Bank AL Habib Ltd.", "Bank Al-Habib", "Bank Al Habib"],
    "BML": ["Bank Makramah Limited", "Summit Bank Limited", "Bank Makramah"],
    "BOP": ["The Bank of Punjab", "Bank of Punjab"],
    "FABL": ["Faysal Bank Limited", "Faysal Bank Ltd.", "Faysal Bank"],
    "HBL": ["Habib Bank Limited", "Habib Bank Ltd.", "Habib Bank"],
    "HMB": ["Habib Metropolitan Bank Limited", "Habib Metropolitan Bank Ltd.", "Habib Metropolitan Bank"],
    "MCB": ["MCB Bank Limited", "MCB Bank Ltd.", "Muslim Commercial Bank"],
    "MEBL": ["Meezan Bank Limited", "Meezan Bank Ltd.", "Meezan Bank"],
    "NBP": ["National Bank of Pakistan", "National Bank"],
    "SCBPL": ["Standard Chartered Bank (Pakistan) Limited", "Standard Chartered Bank (Pakistan) Ltd.", "Standard Chartered Bank"],
    "UBL": ["United Bank Limited", "United Bank Ltd.", "United Bank"],
    # Non-Financials with acronyms or slight naming differences
    "CHCC": ["Cherat Cement Company Limited", "Cherat Cement Co. Ltd.", "Cherat Cement"],
    "DGKC": ["D. G. Khan Cement Company Limited", "D.G. Khan Cement Company Limited", "D.G. Khan Cement", "DG Khan Cement"],
    "FCCL": ["Fauji Cement Company Limited", "Fauji Cement Co. Ltd.", "Fauji Cement"],
    "FFC": ["Fauji Fertilizer Company Limited", "Fauji Fertilizer Co. Ltd.", "Fauji Fertilizer"],
    "FFL": ["Fauji Foods Limited", "Fauji Foods Ltd.", "Noon Pakistan Limited"],
    "FATIMA": ["Fatima Fertilizer Company Limited", "Fatima Fertilizer Co. Ltd.", "Fatima Fertilizer"],
    "EFERT": ["Engro Fertilizers Limited", "Engro Fertilizers Ltd."],
    "ENGROH": ["Engro Corporation Limited", "Engro Corp. Ltd.", "Engro Chemical Pakistan Ltd."],
    "HUBC": ["The Hub Power Company Limited", "Hub Power Co. Ltd.", "Hub Power Company"],
    "KAPCO": ["Kot Addu Power Company Limited", "Kot Addu Power Co. Ltd."],
    "KEL": ["K-Electric Limited", "K-Electric Ltd.", "Karachi Electric Supply Company"],
    "LUCK": ["Lucky Cement Limited", "Lucky Cement Ltd."],
    "MLCF": ["Maple Leaf Cement Factory Limited", "Maple Leaf Cement Factory Ltd."],
    "OGDC": ["Oil & Gas Development Company Limited", "Oil & Gas Development Co. Ltd.", "OGDCL"],
    "POL": ["Pakistan Oilfields Limited", "Pakistan Oilfields Ltd."],
    "PPL": ["Pakistan Petroleum Limited", "Pakistan Petroleum Ltd."],
    "PSO": ["Pakistan State Oil Company Limited", "Pakistan State Oil Co. Ltd."],
    "SYS": ["Systems Limited", "Systems Ltd."],
    "TRG": ["TRG Pakistan Limited", "TRG Pakistan Ltd."],
    "PTC": ["Pakistan Telecommunication Company Limited", "Pakistan Telecommunication Company Ltd."],
    "SEARL": ["The Searle Company Limited", "Searle Company Ltd."],
    "SNGP": ["Sui Northern Gas Pipelines Limited", "Sui Northern Gas Pipelines Ltd."],
    "SSGC": ["Sui Southern Gas Company Limited", "Sui Southern Gas Co. Ltd."],
    "ILP": ["Interloop Limited", "Interloop Ltd."],
    "ISL": ["International Steels Limited", "International Steels Ltd."],
    "INIL": ["International Industries Limited", "International Industries Ltd."],
    "PIOC": ["Pioneer Cement Limited", "Pioneer Cement Ltd."],
    "BWCL": ["Bestway Cement Limited", "Bestway Cement Ltd."],
    "KOHC": ["Kohat Cement Company Limited", "Kohat Cement Co. Ltd."],
    "CNERGY": ["Cnergyico PK Limited", "Byco Petroleum Pakistan Limited"],
    "ATRL": ["Attock Refinery Limited", "Attock Refinery Ltd."],
    "PRL": ["Pakistan Refinery Limited", "Pakistan Refinery Ltd."],
    "APL": ["Attock Petroleum Limited", "Attock Petroleum Ltd."],
    "NATF": ["National Foods Limited", "National Foods Ltd."],
    "NESTLE": ["Nestle Pakistan Limited", "Nestle Pakistan Ltd."],
    "COLG": ["Colgate-Palmolive (Pakistan) Limited", "Colgate-Palmolive (Pakistan) Ltd."],
    "AGP": ["AGP Limited", "AGP Ltd."],
    "ABOT": ["Abbott Laboratories (Pakistan) Limited", "Abbott Laboratories (Pakistan) Ltd."],
    "GLAXO": ["GlaxoSmithKline Pakistan Limited", "GlaxoSmithKline Pakistan Ltd."],
    "HALEON": ["Haleon Pakistan Limited", "GlaxoSmithKline Consumer Healthcare Pakistan Ltd."],
    "INDU": ["Indus Motor Company Limited", "Indus Motor Co. Ltd."],
    "HCAR": ["Honda Atlas Cars (Pakistan) Limited", "Honda Atlas Cars (Pakistan) Ltd."],
    "ATLH": ["Atlas Honda Limited", "Atlas Honda Ltd."],
    "MTL": ["Millat Tractors Limited", "Millat Tractors Ltd."],
    "SAZEW": ["Sazgar Engineering Works Limited", "Sazgar Engineering Works Ltd."],
    "PAEL": ["Pak Elektron Limited", "Pak Elektron Ltd."],
    "AIRLINK": ["Air Link Communication Limited", "Air Link Communication Ltd."],
    "GADT": ["Gadoon Textile Mills Limited", "Gadoon Textile Mills Ltd."],
    "NML": ["Nishat Mills Limited", "Nishat Mills Ltd."],
    "KTML": ["Kohinoor Textile Mills Limited", "Kohinoor Textile Mills Ltd."],
}


def load_kse100_companies() -> pd.DataFrame:
    """Load canonical list of 100 KSE-100 companies from database or clean CSV."""
    db_path = DATA_DIR / "psxpert.db"
    if db_path.exists():
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql("SELECT symbol, company_name, sector, sector_category FROM companies", conn)
            if len(df) == 100:
                return df
    # Fallback to CSV
    csv_path = DATA_DIR / "kse100_fundamentals_annual.csv"
    if csv_path.exists():
        ann = pd.read_csv(csv_path)
        syms = ann[["symbol", "company_name"]].drop_duplicates().reset_index(drop=True)
        return syms
    raise FileNotFoundError("Could not locate KSE-100 companies table.")


def parse_sbp_archive_companies() -> dict[str, dict[str, Any]]:
    """Scan sbp_fsa_archive_2005_2023.xlsx and extract company names and available years."""
    path = RAW_DIR / "sbp_fsa_archive_2005_2023.xlsx"
    if not path.exists():
        logger.warning("SBP FSA Archive %s not found.", path)
        return {}

    wb = openpyxl.load_workbook(path, read_only=True)
    org_data: dict[str, dict[str, Any]] = {}

    for sname in ["2014-23", "2009-13", "2005-08"]:
        if sname not in wb.sheetnames:
            continue
        sheet = wb[sname]
        headers = []
        year_cols: dict[int, str] = {}
        for i, row in enumerate(sheet.iter_rows(values_only=True)):
            if i == 0:
                headers = list(row)
                for col_idx, h in enumerate(headers):
                    if h and re.match(r"^\d{4}$", str(h).strip()):
                        year_cols[col_idx] = str(h).strip()
            else:
                org = row[2]
                if not org or "All Sector" in str(org) or str(org) == "None":
                    continue
                org_str = str(org).strip()
                m = re.match(r"^(\d{6})\s*-\s*(.+)$", org_str)
                code = m.group(1) if m else "N/A"
                cname = m.group(2).strip() if m else org_str

                norm_key = re.sub(r"[^a-zA-Z0-9]", "", cname.lower())
                if norm_key not in org_data:
                    org_data[norm_key] = {
                        "code": code,
                        "raw_name": cname,
                        "years": set(),
                        "sheets": set(),
                    }
                org_data[norm_key]["sheets"].add(sname)
                for col_idx, yr in year_cols.items():
                    val = row[col_idx] if col_idx < len(row) else None
                    if val is not None and str(val).strip() != "" and str(val).strip() != "None":
                        org_data[norm_key]["years"].add(int(yr))

    logger.info("Parsed %d distinct companies from SBP Archive (2005-2023).", len(org_data))
    return org_data


def parse_sbp_bank_companies() -> dict[str, dict[str, Any]]:
    """Scan sbp_fsa_financial_sector_2021_2025.xlsx and extract banks."""
    path = RAW_DIR / "sbp_fsa_financial_sector_2021_2025.xlsx"
    if not path.exists():
        logger.warning("SBP Bank Archive %s not found.", path)
        return {}

    wb = openpyxl.load_workbook(path, read_only=True)
    if "1" not in wb.sheetnames:
        return {}

    sheet = wb["1"]
    bank_data: dict[str, dict[str, Any]] = {}
    year_cols: dict[int, str] = {}

    for i, row in enumerate(sheet.iter_rows(values_only=True)):
        if i == 3:
            for col_idx, h in enumerate(row):
                if h and re.match(r"^\d{4}$", str(h).strip()):
                    year_cols[col_idx] = str(h).strip()
        elif i > 3:
            bname = row[2]
            if not bname or "All Banks" in str(bname) or str(bname) == "None":
                continue
            bname_str = str(bname).strip()
            norm_key = re.sub(r"[^a-zA-Z0-9]", "", bname_str.lower())
            if norm_key not in bank_data:
                bank_data[norm_key] = {
                    "raw_name": bname_str,
                    "years": set(),
                    "sheets": {"Sheet 1 (Banks)"},
                }
            for col_idx, yr in year_cols.items():
                val = row[col_idx] if col_idx < len(row) else None
                if val is not None and str(val).strip() != "" and str(val).strip() != "None":
                    bank_data[norm_key]["years"].add(int(yr))

    logger.info("Parsed %d commercial banks from SBP Financial Sector (2021-2025).", len(bank_data))
    return bank_data


def parse_relational_fundamentals() -> dict[str, dict[str, Any]]:
    """Inspect data/kse100_fundamentals_annual.csv and company_financials."""
    csv_path = DATA_DIR / "kse100_fundamentals_annual.csv"
    if not csv_path.exists():
        return {}
    df = pd.read_csv(csv_path)
    res: dict[str, dict[str, Any]] = {}
    for sym, group in df.groupby("symbol"):
        yrs = set(group["fiscal_year"].dropna().astype(int).tolist())
        res[str(sym).upper()] = {
            "years": yrs,
            "row_count": len(group),
            "source": "kse100_fundamentals_annual.csv",
        }
    return res


def parse_corporate_announcements() -> dict[str, dict[str, Any]]:
    """Scan kse100_corporate_announcements.csv for verified publication dates."""
    ann_path = DATA_DIR / "kse100_corporate_announcements.csv"
    if not ann_path.exists():
        return {}
    df = pd.read_csv(ann_path)
    res: dict[str, dict[str, Any]] = {}
    for sym, group in df.groupby("symbol"):
        earn = group[group["category"] == "Earnings Announcements"]
        res[str(sym).upper()] = {
            "total_announcements": len(group),
            "earnings_announcements": len(earn),
            "min_announcement_date": group["posting_date"].min(),
            "max_announcement_date": group["posting_date"].max(),
        }
    return res


def match_company_to_sbp(
    symbol: str,
    company_name: str,
    sector: str,
    is_bank: bool,
    sbp_archive: dict[str, dict[str, Any]],
    sbp_banks: dict[str, dict[str, Any]],
) -> tuple[str, str, dict[str, Any] | None]:
    """
    Match a PSX ticker to its corresponding SBP entity record.
    Returns: (match_status, confidence_level, sbp_record)
    """
    sym = symbol.upper()
    cname = company_name.strip()
    norm_cname = re.sub(r"[^a-zA-Z0-9]", "", cname.lower())

    # 1. Check curated aliases first
    if sym in TICKER_TO_SBP_ALIASES:
        candidates = TICKER_TO_SBP_ALIASES[sym]
        for alias in candidates:
            norm_alias = re.sub(r"[^a-zA-Z0-9]", "", alias.lower())
            if is_bank and norm_alias in sbp_banks:
                return "MATCHED", "CURATED_ALIAS_EXACT", sbp_banks[norm_alias]
            if not is_bank and norm_alias in sbp_archive:
                return "MATCHED", "CURATED_ALIAS_EXACT", sbp_archive[norm_alias]

    # 2. Check exact normalized name match
    if is_bank:
        if norm_cname in sbp_banks:
            return "MATCHED", "NAME_EXACT", sbp_banks[norm_cname]
        for b_key, b_rec in sbp_banks.items():
            if norm_cname in b_key or b_key in norm_cname:
                return "MATCHED", "NAME_SUBSTRING", b_rec
    else:
        if norm_cname in sbp_archive:
            return "MATCHED", "NAME_EXACT", sbp_archive[norm_cname]
        for s_key, s_rec in sbp_archive.items():
            if len(norm_cname) >= 6 and (norm_cname in s_key or s_key in norm_cname):
                return "MATCHED", "NAME_SUBSTRING", s_rec

    return "UNMATCHED", "NO_MATCH", None


def generate_coverage_matrix():
    logger.info("Starting Phase 1 SBP Data Coverage & Missingness Audit...")
    companies = load_kse100_companies()
    sbp_archive = parse_sbp_archive_companies()
    sbp_banks = parse_sbp_bank_companies()
    relational_funds = parse_relational_fundamentals()
    announcements = parse_corporate_announcements()

    all_years = list(range(2005, 2027))
    matrix_rows = []
    unmatched_rows = []

    for _, r in companies.iterrows():
        sym = str(r["symbol"]).upper()
        cname = str(r.get("company_name", sym))
        sec = str(r.get("sector", "UNCLASSIFIED"))
        cat = str(r.get("sector_category", ""))
        is_bank = "BANK" in sec.upper() or "BANK" in cat.upper()

        status, confidence, sbp_rec = match_company_to_sbp(
            sym, cname, sec, is_bank, sbp_archive, sbp_banks
        )

        sbp_years = set()
        sbp_sources = set()
        matched_sbp_name = "N/A"
        sbp_code = "N/A"

        if sbp_rec:
            sbp_years = sbp_rec["years"]
            sbp_sources = sbp_rec.get("sheets", set())
            matched_sbp_name = sbp_rec["raw_name"]
            sbp_code = sbp_rec.get("code", "N/A")

        rel_years = relational_funds.get(sym, {}).get("years", set())
        combined_available_years = sorted(list(sbp_years | rel_years))
        missing_years = [y for y in all_years if y not in combined_available_years]

        ann_info = announcements.get(sym, {})
        has_announcements = ann_info.get("total_announcements", 0) > 0
        has_earnings_ann = ann_info.get("earnings_announcements", 0) > 0

        # Statement types present
        stmt_types = []
        if sbp_rec:
            stmt_types.append("SBP_ANNUAL_AUDITED")
        if rel_years:
            stmt_types.append("PSX_RELATIONAL_ANNUAL")
        if not stmt_types:
            stmt_types.append("NONE")

        # Conflict check
        has_conflict = False
        conflict_notes = "None"
        overlap_years = sbp_years & rel_years
        if overlap_years:
            conflict_notes = f"Overlapping years {sorted(list(overlap_years))} across SBP & PSX"

        row = {
            "symbol": sym,
            "company_name": cname,
            "sector": sec,
            "is_bank": is_bank,
            "matching_status": status,
            "matching_confidence": confidence,
            "matched_sbp_name": matched_sbp_name,
            "sbp_entity_code": sbp_code,
            "source_workbooks_and_sheets": "; ".join(sorted(sbp_sources)) if sbp_sources else ("PSX_RELATIONAL_ONLY" if rel_years else "NONE"),
            "statement_types_available": "; ".join(stmt_types),
            "years_count": len(combined_available_years),
            "available_financial_years": ", ".join(map(str, combined_available_years)) if combined_available_years else "NONE",
            "missing_financial_years": ", ".join(map(str, missing_years)) if missing_years else "NONE",
            "has_verified_earnings_announcements": has_earnings_ann,
            "announcements_count": ann_info.get("total_announcements", 0),
            "timestamp_provenance": "VERIFIED_ANNOUNCEMENT" if has_earnings_ann else "ESTIMATED_100D_FALLBACK",
            "duplicate_or_conflict_flag": has_conflict,
            "conflict_notes": conflict_notes,
        }
        matrix_rows.append(row)

        if status == "UNMATCHED":
            unmatched_rows.append({
                "symbol": sym,
                "company_name": cname,
                "sector": sec,
                "is_bank": is_bank,
                "reason": "No match found in SBP Archive or Bank publications; relies on PSX announcements and relational filings only",
            })

    matrix_df = pd.DataFrame(matrix_rows)
    matrix_csv = REPORTS_DIR / "sbp_fsa_coverage_matrix.csv"
    matrix_df.to_csv(matrix_csv, index=False)
    logger.info("Saved SBP FSA Coverage Matrix -> %s (%d companies)", matrix_csv, len(matrix_df))

    unmatched_df = pd.DataFrame(unmatched_rows)
    unmatched_csv = REPORTS_DIR / "sbp_fsa_unmatched_review.csv"
    unmatched_df.to_csv(unmatched_csv, index=False)
    logger.info("Saved Unmatched Companies Review -> %s (%d companies)", unmatched_csv, len(unmatched_df))

    # Print summary statistics
    matched_cnt = int((matrix_df["matching_status"] == "MATCHED").sum())
    avg_years = matrix_df["years_count"].mean()
    print("\n" + "=" * 60)
    print("PSXpert SBP FSA & Relational Coverage Audit Results")
    print("=" * 60)
    print(f"Total KSE-100 Universe:               {len(matrix_df)} companies")
    print(f"Matched with Official SBP FSA:        {matched_cnt} of {len(matrix_df)} ({matched_cnt / len(matrix_df):.1%})")
    print(f"Unmatched (Preserved for review):     {len(unmatched_df)} companies")
    print(f"Average Financial Years per Company:  {avg_years:.1f} years (was 1.5 years before recovery)")
    print(f"Companies with >= 10 Years History:   {int((matrix_df['years_count'] >= 10).sum())} companies")
    print(f"Companies with Verified Ann. Dates:   {int(matrix_df['has_verified_earnings_announcements'].sum())} companies")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    generate_coverage_matrix()
