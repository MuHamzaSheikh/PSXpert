"""Extracts official Bank financial statements from SBP Financial Sector Analysis

and merges them with kse100_fundamentals_historical_2005_2026.csv.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXCEL_PATH = PROJECT_ROOT / "data" / "raw" / "sbp_fsa_financial_sector_2021_2025.xlsx"
FUNDS_PATH = PROJECT_ROOT / "psx all data" / "3_fundamentals_and_financials" / "kse100_fundamentals_historical_2005_2026.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "kse100_fundamentals_historical_2005_2026.csv"

BANK_MAPPING = {
    "ALLIED BANK LTD.": "ABL",
    "ASKARI BANK LTD.": "AKBL",
    "BANK AL-HABIB LTD.": "BAHL",
    "STANDARD CHARTERED BANK (PAKISTAN) LTD.": "SCBPL",
    "BANK ALFALAH LTD.": "BAFL",
    "HABIB BANK LTD.": "HBL",
    "FAYSAL BANK LTD.": "FABL",
    "MCB BANK LTD.": "MCB",
    "MEEZAN BANK LTD.": "MEBL",
    "Bank Makramah Limited": "BML",
    "UNITED BANK LTD.": "UBL",
    "NATIONAL BANK OF PAKISTAN": "NBP",
    "BANKISLAMI PAKISTAN LTD.": "BIPL",
    "SONERI BANK LTD.": "SNBL",
    "THE BANK OF PUNJAB": "BOP",
    "JS BANK LTD.": "JSBL",
}

def extract_banks():
    print(f"Reading {EXCEL_PATH} Sheet 1...")
    df = pd.read_excel(EXCEL_PATH, sheet_name="1", header=3)
    print("Columns:", df.columns.tolist()[:8])
    
    # Filter for known KSE-100 banks
    df_banks = df[df["Bank Name"].isin(BANK_MAPPING.keys())].copy()
    print(f"Found {df_banks['Bank Name'].nunique()} banks in Excel.")

    # Find year columns
    year_cols = [c for c in df.columns if isinstance(c, (int, float)) and 2000 <= int(c) <= 2030]
    print("Year columns:", year_cols)

    records = []
    for (bank_name, item_name), group in df_banks.groupby(["Bank Name", "Item Name"]):
        sym = BANK_MAPPING[bank_name]
        for yr in year_cols:
            val = group[yr].values[0]
            if pd.notna(val):
                records.append({
                    "symbol": sym,
                    "sbp_organization": bank_name,
                    "fiscal_year": int(yr),
                    "item_name": str(item_name).strip(),
                    "value": float(val)
                })

    df_items = pd.DataFrame(records)
    print(f"Extracted {len(df_items)} bank item-year records.")

    # Pivot items into columns per (symbol, fiscal_year)
    pivoted = df_items.pivot_table(
        index=["symbol", "sbp_organization", "fiscal_year"],
        columns="item_name",
        values="value",
        aggfunc="first"
    ).reset_index()

    print("Pivoted shape:", pivoted.shape)
    
    # Map into standard fundamentals schema
    # Note: SBP units for banks are PKR Thousands (000)
    bank_funds = pd.DataFrame()
    bank_funds["symbol"] = pivoted["symbol"]
    bank_funds["sbp_organization"] = pivoted["sbp_organization"]
    bank_funds["fiscal_year"] = pivoted["fiscal_year"]
    bank_funds["period_end_date"] = pivoted["fiscal_year"].astype(str) + "-12-31"  # Pakistan banks have Dec 31 year end
    bank_funds["periodicity"] = "ANNUAL"

    # Assets & Equity
    bank_funds["total_assets"] = pivoted.get("C. Total assets (C1 to C4 + C8 to C10)", np.nan)
    bank_funds["shareholders_equity"] = pivoted.get("A. Total equity (A1 to A4)", np.nan)
    bank_funds["common_share_capital"] = pivoted.get("1. Share capital", np.nan)
    bank_funds["reserves_and_surplus"] = pivoted.get("2. Reserves", np.nan)
    bank_funds["current_assets"] = pivoted.get("1. Cash and balances with treasury banks", np.nan) + pivoted.get("2. Balances with other banks", 0)
    bank_funds["current_liabilities"] = pivoted.get("1. Bills payable", np.nan) + pivoted.get("3. Deposits and other accounts", 0)
    bank_funds["cash_and_equivalents"] = pivoted.get("1. Cash and balances with treasury banks", np.nan)

    # Profitability & Revenue
    # Markup earned + Non-markup income = Total Bank Revenue
    markup_earned = pivoted.get("1. Markup/interest earned", 0)
    non_markup = pivoted.get("6. Non-markup/interest income", 0)
    bank_funds["revenue_sales"] = markup_earned + non_markup
    bank_funds["net_profit_after_tax"] = pivoted.get("10. Profit/(loss) after taxation", np.nan)
    bank_funds["profit_before_tax"] = pivoted.get("9. Profit/(loss) before taxation", np.nan)
    bank_funds["operating_profit"] = pivoted.get("5. Net markup/interest income after provisions", np.nan)
    bank_funds["interest_expense"] = pivoted.get("2. Markup/interest expenses", np.nan)
    bank_funds["operating_cash_flow"] = pivoted.get("4. Cash generated from operating activities", np.nan)

    # Precomputed SBP ratios
    bank_funds["roe_pct"] = pivoted.get("3. Return on equity (ROE) (D10/A*)", np.nan)
    bank_funds["roa_pct"] = pivoted.get("4. Return on assets (ROA) (D10/C)", np.nan)
    bank_funds["net_profit_margin_pct"] = ((bank_funds["net_profit_after_tax"] / bank_funds["revenue_sales"].replace(0, np.nan)) * 100.0)
    bank_funds["debt_to_equity_ratio"] = (pivoted.get("B. Total liabilities (B1 to B4)", 0) / bank_funds["shareholders_equity"].replace(0, np.nan))
    bank_funds["current_ratio"] = (bank_funds["current_assets"] / bank_funds["current_liabilities"].replace(0, np.nan))

    print(f"Built {len(bank_funds)} clean annual statements for {bank_funds['symbol'].nunique()} banks.")

    # Load existing NFC fundamentals
    existing = pd.read_csv(FUNDS_PATH)
    print(f"Existing fundamentals: {len(existing)} rows, {existing['symbol'].nunique()} symbols.")

    # Remove any overlapping bank rows from existing if any
    existing_filtered = existing[~existing["symbol"].isin(bank_funds["symbol"].unique())].copy()

    # Align columns
    common_cols = [c for c in existing.columns if c in bank_funds.columns]
    combined = pd.concat([existing_filtered[common_cols], bank_funds[common_cols]], ignore_index=True)
    combined = combined.sort_values(["symbol", "fiscal_year"]).reset_index(drop=True)

    print(f"Combined fundamentals: {len(combined)} rows across {combined['symbol'].nunique()} symbols!")
    print("Symbols in combined:", combined["symbol"].nunique())

    # Save to both paths
    combined.to_csv(OUTPUT_PATH, index=False)
    combined.to_csv(FUNDS_PATH, index=False)
    print(f"Saved updated fundamentals to {OUTPUT_PATH} and {FUNDS_PATH}")

if __name__ == "__main__":
    extract_banks()
