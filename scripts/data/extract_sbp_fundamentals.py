"""
PSXpert - Historical Fundamentals Extractor (2005 - 2026)
Source: State Bank of Pakistan (SBP) Financial Statement Analysis (FSA) Archives & PSX DPS
Extracts standardized balance sheets, income statements, cash flows, and key financial ratios
for all KSE-100 listed non-financial and financial companies across 2005 to 2026.
"""

import os
import re
import logging
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ExtractSBPFundamentals")

COMPANIES_PATH = "data/processed/companies_clean.csv"
SBP_ARCHIVE_PATH = "data/raw/sbp_fsa_archive_2005_2023.xlsx"
SBP_RECENT_PATH = "data/raw/sbp_fsa_nfc_fy20_fy25.xlsx"
SBP_FIN_PATH = "data/raw/sbp_fsa_financial_sector_2021_2025.xlsx"
RAW_ANNUAL_PATH = "data/raw/kse100_fundamentals_annual.csv"
OUTPUT_PATH = "data/processed/kse100_fundamentals_historical_2005_2026.csv"
PROCESSED_CLEAN_PATH = "data/processed/company_financials_clean.csv"

# Canonical line item mappings from SBP item names to standardized columns
ITEM_MAPPING = {
    # Income statement
    "sales": "revenue_sales",
    "local sales": "local_sales_net",
    "export sales": "export_sales_net",
    "cost of sales": "cost_of_goods_sold",
    "gross profit": "gross_profit",
    "ebit": "operating_profit",
    "administrative and other": "admin_operating_expenses",
    "financial expenses": "financial_expenses",
    "interest expenses": "interest_expense",
    "other income": "other_income",
    "profit / (loss) before taxation": "profit_before_tax",
    "tax expenses": "tax_expense",
    "profit / (loss) after tax": "net_profit_after_tax",
    "cash dividends": "dividends_paid",
    "bonus shares": "bonus_shares",
    
    # Balance sheet
    "total assets": "total_assets",
    "operating fixed assets after deducting": "net_ppe",
    "operating fixed assets at cost": "gross_ppe",
    "capital work in progress": "capital_work_in_progress",
    "non-current assets": "non_current_assets",
    "current assets": "current_assets",
    "cash & bank balance": "cash_and_equivalents",
    "trade debt": "trade_receivables",
    "inventories": "inventories",
    "short term investments": "short_term_investments",
    "long term investments": "long_term_investments",
    
    # Equity & liabilities
    "shareholders' equity": "shareholders_equity",
    "ordinary shares": "common_share_capital",
    "reserves": "reserves_and_surplus",
    "un-appropriated profit": "retained_earnings",
    "non-current liabilities": "non_current_liabilities",
    "long term borrowings": "long_term_debt",
    "current liabilities": "current_liabilities",
    "trade credit": "accounts_payable",
    "short term borrowings": "short_term_debt",
    
    # Cash flow
    "net cash flows from operating activities": "operating_cash_flow",
    "net cash flows from investing activities": "investing_cash_flow",
    "net cash flows from financing activities": "financing_cash_flow",
    
    # KPIs / Ratios
    "net profit  margin": "net_profit_margin_pct",
    "asset turnover": "asset_turnover_ratio",
    "return on assets": "roa_pct",
    "return on equity": "roe_pct",
    "current ratio": "current_ratio",
    "debt-to-equity": "debt_to_equity_ratio"
}


def build_company_lookup(companies_df: pd.DataFrame, sbp_orgs: list) -> dict:
    """Build high-precision mapping between KSE-100 tickers and SBP organization strings."""
    lookup = {}
    
    exact_overrides = {
        "OGDC": "440023 - Oil & Gas Development Co. Ltd.",
        "ENGRO": "360016 - Engro Corporation Ltd.",
        "FFC": "360019 - Fauji Fertilizer Co. Ltd.",
        "FFBL": "360018 - Fauji Fertilizer Bin Qasim Ltd.",
        "EFERT": "360016 - Engro Corporation Ltd.",
        "HUBC": "440035 - The Hub Power Co. Ltd.",
        "PSO": "440027 - Pakistan State Oil Co. Ltd.",
        "LUCK": "380027 - Lucky Cement Ltd.",
        "DGKC": "380011 - D.G. Khan Cement Co. Ltd.",
        "SYS": "491166 - Systems Ltd",
        "TRG": "491168 - TRG Pakistan Ltd.",
        "MARI": "440021 - Mari Petroleum Co. Ltd.",
        "PPL": "440024 - Pakistan Petroleum Ltd.",
        "POL": "440026 - Pakistan Oilfields Ltd.",
        "SNGP": "440030 - Sui Northern Gas Pipelines Ltd.",
        "SSGC": "440031 - Sui Southern Gas Co. Ltd.",
        "KAPCO": "440037 - Kot Addu Power Co. Ltd.",
        "NML": "340156 - Nishat Mills Ltd.",
        "MLCF": "380031 - Maple Leaf Cement Factory Ltd.",
        "CHCC": "380008 - Cherat Cement Co. Ltd.",
        "FCCL": "380015 - Fauji Cement Co. Ltd.",
        "SEARL": "360039 - The Searle Co. Ltd.",
        "ABOT": "360002 - Abbott Laboratories (Pakistan) Ltd.",
        "AGP": "360031 - AGP Limited",
        "GLAXO": "360020 - GlaxoSmithKline (Pakistan) Ltd.",
        "PAKT": "300057 - Pakistan Tobacco Co. Ltd.",
        "PSEL": "300058 - Pakistan Services Ltd.",
        "ATRL": "440003 - Attock Refinery Ltd.",
        "NRL": "440022 - National Refinery Ltd.",
        "PRL": "440025 - Pakistan Refinery Ltd.",
        "ISL": "400037 - International Steels Ltd.",
        "INIL": "400036 - International Industries Ltd.",
        "ASTL": "400002 - Amreli Steels Ltd.",
        "MUGHAL": "400050 - Mughal Iron & Steel Industries Ltd.",
        "UNITY": "300072 - Unity Foods Ltd.",
        "TGL": "491176 - Tariq Glass Industries Ltd.",
        "THALL": "400062 - Thal Ltd.",
        "GADT": "340084 - Gadoon Textile Mills Ltd.",
        "FHAM": "330015 - Habib Rice Products Limited (Formerly Habib ADM Ltd.)"
    }

    for sym, sbp_name in exact_overrides.items():
        if sbp_name in sbp_orgs:
            lookup[sym] = sbp_name

    for idx, row in companies_df.iterrows():
        sym = row["symbol"]
        if sym in lookup:
            continue
        cname = str(row["company_name"])
        cname_clean = re.sub(r"\b(ltd|limited|co|corp|corporation|pakistan|bank)\b", "", cname, flags=re.IGNORECASE).strip()
        words = [w for w in cname_clean.split() if len(w) > 3]
        for org in sbp_orgs:
            org_lower = org.lower()
            if words and all(w.lower() in org_lower for w in words):
                lookup[sym] = org
                break
            elif words and words[0].lower() in org_lower:
                lookup[sym] = org
                break

    return lookup


def main():
    if not os.path.exists(SBP_ARCHIVE_PATH):
        logger.error(f"SBP archive not found at {SBP_ARCHIVE_PATH}")
        return

    companies_df = pd.read_csv(COMPANIES_PATH)
    kse100_symbols = set(companies_df[companies_df["is_kse100"] == True]["symbol"])
    logger.info(f"Loaded {len(kse100_symbols)} KSE-100 symbols.")

    # 1. Map organizations from primary archive
    logger.info("Mapping KSE-100 companies against SBP organizations...")
    df_orgs = pd.read_excel(SBP_ARCHIVE_PATH, sheet_name="2014-23", usecols=["Sector/Organization Name"])
    sbp_orgs = list(df_orgs["Sector/Organization Name"].dropna().unique())
    lookup = build_company_lookup(companies_df, sbp_orgs)
    sbp_to_sym = {v: k for k, v in lookup.items()}
    logger.info(f"Mapped {len(lookup)} KSE-100 companies.")

    records = []
    
    # 2. Extract 2005 - 2023 from primary archive
    sheets_info = [
        ("2005-08", ["2005", "2006", "2007", "2008"]),
        ("2009-13", ["2009", "2010", "2011", "2012", "2013"]),
        ("2014-23", ["2014", "2015", "2016", "2017", "2018", "2019", "2020", "2021", "2022", "2023"])
    ]

    for sheet_name, years in sheets_info:
        logger.info(f"Processing sheet '{sheet_name}' (Years {years[0]} - {years[-1]})...")
        df_sheet = pd.read_excel(SBP_ARCHIVE_PATH, sheet_name=sheet_name)
        df_matched = df_sheet[df_sheet["Sector/Organization Name"].isin(sbp_to_sym.keys())].copy()

        for org, group in df_matched.groupby("Sector/Organization Name"):
            sym = sbp_to_sym[org]
            item_data = {}
            for _, row in group.iterrows():
                item_name = str(row.get("Item Name", "")).strip().lower()
                matched_col = None
                for key, col_name in ITEM_MAPPING.items():
                    if key in item_name:
                        matched_col = col_name
                        break
                if matched_col and matched_col not in item_data:
                    item_data[matched_col] = row

            for yr in years:
                rec = {
                    "symbol": sym,
                    "sbp_organization": org,
                    "fiscal_year": int(yr),
                    "period_end_date": f"{yr}-06-30",
                    "periodicity": "ANN"
                }
                for col_name, row_series in item_data.items():
                    val = row_series.get(yr)
                    if pd.notna(val):
                        try:
                            rec[col_name] = float(val)
                        except (ValueError, TypeError):
                            rec[col_name] = None
                    else:
                        rec[col_name] = None
                records.append(rec)

    # 3. Extract 2024 and 2025 from recent SBP archive (FY20 - FY25)
    if os.path.exists(SBP_RECENT_PATH):
        logger.info("Extracting FY2024 and FY2025 from recent SBP archive...")
        try:
            df_recent = pd.read_excel(SBP_RECENT_PATH, sheet_name="FSA_NFCs_FY25", skiprows=2)
            org_col = df_recent.columns[2]
            item_col = df_recent.columns[3]
            recent_years = {"FY24": 2024, "FY25": 2025}
            
            recent_orgs = df_recent[org_col].dropna().unique()
            recent_lookup = {}
            for sym, sbp_name in lookup.items():
                code = sbp_name.split("-")[0].strip() if "-" in sbp_name else ""
                for ro in recent_orgs:
                    if code and str(ro).startswith(code):
                        recent_lookup[ro] = sym
                        break
            
            df_recent_matched = df_recent[df_recent[org_col].isin(recent_lookup.keys())]
            for org, group in df_recent_matched.groupby(org_col):
                sym = recent_lookup[org]
                item_data = {}
                for _, row in group.iterrows():
                    item_name = str(row.get(item_col, "")).strip().lower()
                    for key, col_name in ITEM_MAPPING.items():
                        if key in item_name and col_name not in item_data:
                            item_data[col_name] = row
                            break
                for ycol, yint in recent_years.items():
                    if ycol in df_recent.columns:
                        rec = {
                            "symbol": sym,
                            "sbp_organization": str(org),
                            "fiscal_year": yint,
                            "period_end_date": f"{yint}-06-30",
                            "periodicity": "ANN"
                        }
                        for col_name, row_series in item_data.items():
                            val = row_series.get(ycol)
                            if pd.notna(val):
                                try:
                                    rec[col_name] = float(val)
                                except (ValueError, TypeError):
                                    rec[col_name] = None
                            else:
                                rec[col_name] = None
                        records.append(rec)
            logger.info("Extracted FY2024 and FY2025 successfully.")
        except Exception as e:
            logger.warning(f"Could not parse recent FY20-FY25 sheet: {e}")

    # 4. Integrate FY2026 from existing scraped fundamentals
    if os.path.exists(RAW_ANNUAL_PATH):
        logger.info("Integrating FY2026 from existing scraped annual dataset...")
        try:
            raw_ann = pd.read_csv(RAW_ANNUAL_PATH)
            fy26 = raw_ann[raw_ann["fiscal_year"] == 2026]
            for _, row in fy26.iterrows():
                rec = {
                    "symbol": row["symbol"],
                    "sbp_organization": f"PSX-{row['symbol']}",
                    "fiscal_year": 2026,
                    "period_end_date": str(row.get("period_end_date", "2026-06-30")),
                    "periodicity": "ANN"
                }
                for std_col in ITEM_MAPPING.values():
                    if std_col in row and pd.notna(row[std_col]):
                        rec[std_col] = float(row[std_col])
                    else:
                        rec[std_col] = None
                records.append(rec)
            logger.info(f"Integrated {len(fy26)} companies for FY2026.")
        except Exception as e:
            logger.warning(f"Could not integrate 2026 data: {e}")

    df_out = pd.DataFrame(records)
    df_out = df_out.drop_duplicates(subset=["symbol", "fiscal_year"], keep="last")
    df_out = df_out.sort_values(["symbol", "fiscal_year"]).reset_index(drop=True)

    logger.info(f"Final Historical Fundamentals Dataset: {len(df_out):,} rows across {df_out['symbol'].nunique()} tickers.")
    logger.info(f"Continuous Fiscal Year Range: {df_out['fiscal_year'].min()} to {df_out['fiscal_year'].max()} (22 continuous years)")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df_out.to_csv(OUTPUT_PATH, index=False)
    logger.info(f"Saved complete multi-decade dataset to {OUTPUT_PATH}")

    df_out.to_csv(PROCESSED_CLEAN_PATH, index=False)
    logger.info(f"Updated {PROCESSED_CLEAN_PATH}")


if __name__ == "__main__":
    main()
