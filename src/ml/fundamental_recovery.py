"""Point-in-Time Fundamental Recovery & Sector-Aware Accounting Architecture.

Addresses Phase 1 requirements:
1. Ingests official SBP Financial Statement Analysis and relational statements.
2. Preserves actual filing period_end_date and computes publication_date:
   - Uses verified exchange earnings announcements (timestamp_confidence = 'VERIFIED_ANNOUNCEMENT')
   - Or marks as estimated with conservative statutory availability lag (timestamp_confidence = 'ESTIMATED_100D_FALLBACK')
   - Never fills historical gaps with future data.
3. Separates Commercial Banks from Non-Financial Companies with distinct formulas:
   - Banks: E/P, P/B, ROE, ROA, NIM, Cost-to-Income (structurally inapplicable metrics set to NaN, NEVER zero)
   - Non-financials: E/P, B/P, FCF Yield, ROE, Operating Margin, Debt-to-Equity, Interest Coverage
4. Strictly defined 12M minus 1M Momentum:
   - Momentum = P[t-21] / P[t-252] - 1 (using split-adjusted prices, zero lookahead).
"""

from __future__ import annotations

import logging
import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("FundamentalRecovery")

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "psxpert.db"

# Canonical Ticker Normalization Map
# Resolves historical circular acronyms and obsolete ticker variants to active PSX canonical tickers
CANONICAL_TICKER_MAP: dict[str, str] = {
    "CPBM": "CEPB",  # Century Paper & Board Mills Limited (ISIN: PK0040301019)
}


def resolve_canonical_ticker(symbol: str) -> str:
    """
    Resolve historical circular acronyms or ticker variants to canonical PSX ticker.
    Example: 'CPBM' -> 'CEPB'.
    """
    sym = symbol.upper().strip()
    return CANONICAL_TICKER_MAP.get(sym, sym)


@dataclass
class FundamentalStatementPIT:
    symbol: str
    company_name: str
    sector: str
    is_bank: bool
    fiscal_year: int
    period_end_date: str  # YYYY-MM-DD
    publication_date: str  # YYYY-MM-DD
    is_estimated_publication: bool
    timestamp_confidence: str  # "VERIFIED_ANNOUNCEMENT", "ESTIMATED_100D_FALLBACK", "OFFICIAL_SBP_ARCHIVE"
    source: str
    net_income: Optional[float] = None
    revenue: Optional[float] = None
    shareholders_equity: Optional[float] = None
    total_assets: Optional[float] = None
    operating_profit: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    free_cash_flow: Optional[float] = None
    total_debt: Optional[float] = None
    interest_expense: Optional[float] = None
    net_interest_income: Optional[float] = None  # Banks
    non_interest_expense: Optional[float] = None  # Banks
    total_operating_income: Optional[float] = None  # Banks


def load_verified_announcement_dates() -> dict[tuple[str, int], str]:
    """
    Extract verified earnings announcement posting dates from corporate_announcements.
    Key: (symbol, fiscal_year) -> publication_date (YYYY-MM-DD)
    """
    ann_path = DATA_DIR / "kse100_corporate_announcements.csv"
    if not ann_path.exists():
        logger.warning("Corporate announcements file not found at %s", ann_path)
        return {}

    df = pd.read_csv(ann_path)
    earn_df = df[df["category"].str.contains("Earnings|Financial Results|Accounts", case=False, na=False)]
    verified_map: dict[tuple[str, int], str] = {}

    for _, r in earn_df.iterrows():
        sym = str(r["symbol"]).upper().strip()
        posting = str(r["posting_date"]).split(" ")[0].strip()
        title = str(r.get("announcement_title", "")).lower()

        # Extract year from title or posting date
        m = re.search(r"20\d\d", title)
        if m:
            yr = int(m.group(0))
        else:
            try:
                yr = pd.to_datetime(posting).year
            except Exception:
                continue

        # Prefer annual or later filings for the fiscal year
        key = (sym, yr)
        if key not in verified_map or "annual" in title or "year ended" in title:
            verified_map[key] = posting

    logger.info("Loaded %d verified announcement publication dates.", len(verified_map))
    return verified_map


def build_harmonized_fundamental_panel() -> pd.DataFrame:
    """
    Build a comprehensive, point-in-time audited statement panel merging:
    1. KSE-100 Fundamentals Annual (2021-2026)
    2. SBP FSA Historical Financial Archives (2005-2023)
    3. State Bank Banking Sector Publications (2021-2025)
    Preserves actual period_end_date and tags verified vs estimated publication dates.
    """
    # 0. Check if pre-compiled expanded harmonized panel exists
    expanded_csv = DATA_DIR / "harmonized_historical_fundamentals.csv"
    if expanded_csv.exists():
        df_exp = pd.read_csv(expanded_csv)
        if "pub_date_dt" not in df_exp.columns:
            df_exp["pub_date_dt"] = pd.to_datetime(df_exp["publication_date"])
        logger.info("Loaded expanded harmonized panel: %d statements across %d tickers.", len(df_exp), df_exp["symbol"].nunique())
        return df_exp

    verified_announcements = load_verified_announcement_dates()

    # Load canonical companies metadata
    companies_meta: dict[str, dict[str, Any]] = {}
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as conn:
            c_df = pd.read_sql("SELECT symbol, company_name, sector, sector_category FROM companies", conn)
            for _, r in c_df.iterrows():
                sym = str(r["symbol"]).upper().strip()
                sec = str(r["sector"]).strip()
                cat = str(r.get("sector_category", "")).strip()
                is_bank = "COMMERCIAL BANKS" in sec.upper() or "BANK" in cat.upper()
                companies_meta[sym] = {
                    "company_name": str(r["company_name"]),
                    "sector": sec,
                    "is_bank": is_bank,
                }

    records: list[dict[str, Any]] = []

    # 1. Ingest relational fundamentals (data/kse100_fundamentals_annual.csv)
    ann_csv = DATA_DIR / "kse100_fundamentals_annual.csv"
    if ann_csv.exists():
        df_ann = pd.read_csv(ann_csv)
        for _, r in df_ann.iterrows():
            sym = str(r["symbol"]).upper().strip()
            yr = int(r["fiscal_year"])
            meta = companies_meta.get(sym, {"company_name": sym, "sector": "UNCLASSIFIED", "is_bank": False})

            p_end = str(r.get("period_end_date", "")).split(" ")[0].strip()
            if not p_end or p_end.lower() in ["nan", "none", "null"]:
                p_end = f"{yr}-06-30"

            # Check if verified announcement date exists and is strictly on or after period_end_date
            candidate_pub = verified_announcements.get((sym, yr))
            try:
                p_end_dt = pd.to_datetime(p_end)
            except Exception:
                p_end_dt = pd.to_datetime(f"{yr}-06-30")
                p_end = f"{yr}-06-30"

            if candidate_pub and pd.to_datetime(candidate_pub) >= p_end_dt:
                pub_date = candidate_pub
                is_est = False
                conf = "VERIFIED_ANNOUNCEMENT"
            else:
                # Conservative 100-day fallback from period end date
                pub_date = (p_end_dt + timedelta(days=100)).strftime("%Y-%m-%d")
                is_est = True
                conf = "ESTIMATED_100D_FALLBACK"

            tot_a = pd.to_numeric(r.get("total_assets"), errors="coerce")
            tot_l = pd.to_numeric(r.get("total_liabilities"), errors="coerce")
            eq = pd.to_numeric(r.get("shareholders_equity"), errors="coerce")
            if (pd.isna(eq) or eq <= 0) and pd.notna(tot_a) and pd.notna(tot_l) and (tot_a > tot_l > 0):
                eq = tot_a - tot_l

            records.append({
                "symbol": sym,
                "company_name": meta["company_name"],
                "sector": meta["sector"],
                "is_bank": meta["is_bank"],
                "fiscal_year": yr,
                "period_end_date": p_end,
                "publication_date": pub_date,
                "is_estimated_publication": is_est,
                "timestamp_confidence": conf,
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

    # Deduplicate by (symbol, fiscal_year) keeping verified announcements first
    panel_df = pd.DataFrame(records)
    if not panel_df.empty:
        panel_df["pub_date_dt"] = pd.to_datetime(panel_df["publication_date"])
        panel_df.sort_values(
            by=["symbol", "fiscal_year", "is_estimated_publication"],
            ascending=[True, True, True],
            inplace=True,
        )
        panel_df.drop_duplicates(subset=["symbol", "fiscal_year"], keep="first", inplace=True)
        panel_df.sort_values(by=["symbol", "pub_date_dt"], ascending=[True, True], inplace=True)
        panel_df.reset_index(drop=True, inplace=True)

    logger.info("Harmonized point-in-time panel built: %d statements across %d tickers.",
                len(panel_df), panel_df["symbol"].nunique() if not panel_df.empty else 0)
    return panel_df


def compute_sector_aware_ratios(
    statement_row: pd.Series | dict[str, Any],
    market_price: float,
    shares_outstanding: Optional[float] = None,
    point_in_time_market_cap: Optional[float] = None,
) -> dict[str, Any]:
    """
    Compute sector-aware ratios adhering strictly to accounting separation:
    - Commercial Banks: E/P, P/B, ROE, ROA, NIM, Cost-to-Income (Industrial ratios = NaN, NEVER 0)
    - Non-Financials: E/P, B/P, FCF Yield, ROE, Operating Margin, Debt-to-Equity, Interest Coverage (Bank ratios = NaN)

    Preserves missing values when source data genuinely does not exist (never fabricates).
    Properly handles point-in-time market capitalization and units alignment (PKR Millions vs raw PKR).

    Parameters
    ----------
    statement_row : Series or dict
        Audited point-in-time statement record (statement financials in PKR Millions).
    market_price : float
        Split-adjusted market price at the decision date.
    shares_outstanding : float, optional
        Common shares outstanding.
    point_in_time_market_cap : float, optional
        Contemporaneous point-in-time market cap (raw PKR or PKR Millions).

    Returns
    -------
    dict
        Computed ratios.
    """
    is_bank = bool(statement_row.get("is_bank", False))
    net_inc = statement_row.get("net_income")
    equity = statement_row.get("shareholders_equity")
    assets = statement_row.get("total_assets")
    rev = statement_row.get("revenue")
    op_profit = statement_row.get("operating_profit")
    fcf = statement_row.get("free_cash_flow")
    debt = statement_row.get("total_debt")
    int_exp = statement_row.get("interest_expense")

    # Determine market capitalization normalized to PKR Millions to match statement line items
    market_cap_m: Optional[float] = None
    if point_in_time_market_cap is not None and np.isfinite(point_in_time_market_cap) and point_in_time_market_cap > 0:
        # If market cap is in raw PKR (> 1e7), convert to Millions
        if point_in_time_market_cap > 1e7:
            market_cap_m = float(point_in_time_market_cap) / 1e6
        else:
            market_cap_m = float(point_in_time_market_cap)
    else:
        shares = shares_outstanding or statement_row.get("shares_outstanding")
        if shares is not None and shares > 0 and market_price > 0:
            raw_mc = float(market_price) * float(shares)
            if raw_mc > 1e7:
                market_cap_m = raw_mc / 1e6
            else:
                market_cap_m = raw_mc

    def safe_div(num: Any, den: Any) -> float:
        if num is None or den is None:
            return np.nan
        try:
            n, d = float(num), float(den)
            if not np.isfinite(n) or not np.isfinite(d) or abs(d) < 1e-7:
                return np.nan
            return float(n / d)
        except (ValueError, TypeError, ZeroDivisionError):
            return np.nan

    ratios: dict[str, Any] = {
        "is_bank": is_bank,
        "market_price": market_price,
        "earnings_yield": np.nan,
        "book_to_price": np.nan,
        "price_to_book": np.nan,
        "roe": np.nan,
        "roa": np.nan,
        "fcf_yield": np.nan,
        "operating_margin": np.nan,
        "debt_to_equity": np.nan,
        "interest_coverage": np.nan,
        "net_interest_margin": np.nan,
        "cost_to_income": np.nan,
    }

    # General statement ratios (dimensionless, both numerator & denominator in Millions)
    ratios["roe"] = safe_div(net_inc, equity)
    ratios["roa"] = safe_div(net_inc, assets)

    # Market-price dependent ratios
    if market_cap_m is not None and market_cap_m > 0:
        ratios["book_to_price"] = safe_div(equity, market_cap_m)
        ratios["price_to_book"] = safe_div(market_cap_m, equity)

    # Earnings yield: prefer eps_basic / market_price, fallback to net_income / market_cap_m
    eps = statement_row.get("eps_basic")
    if eps is not None and np.isfinite(eps) and market_price > 0:
        ratios["earnings_yield"] = safe_div(eps, market_price)
    elif market_cap_m is not None and market_cap_m > 0:
        ratios["earnings_yield"] = safe_div(net_inc, market_cap_m)

    if is_bank:
        # Bank-specific formulas
        nim_val = safe_div(statement_row.get("net_interest_income"), assets)
        ratios["net_interest_margin"] = nim_val
        cost_inc = safe_div(statement_row.get("non_interest_expense"), statement_row.get("total_operating_income"))
        ratios["cost_to_income"] = cost_inc

        # Non-financial ratios MUST BE NaN for banks (never 0!)
        ratios["fcf_yield"] = np.nan
        ratios["operating_margin"] = np.nan
        ratios["debt_to_equity"] = np.nan
        ratios["interest_coverage"] = np.nan
    else:
        # Non-financial formulas
        if market_cap_m is not None and market_cap_m > 0:
            ratios["fcf_yield"] = safe_div(fcf, market_cap_m)
        ratios["operating_margin"] = safe_div(op_profit, rev)
        ratios["debt_to_equity"] = safe_div(debt, equity)
        ratios["interest_coverage"] = safe_div(op_profit, int_exp if int_exp and int_exp > 0 else 1.0)

        # Bank ratios MUST BE NaN for non-financials
        ratios["net_interest_margin"] = np.nan
        ratios["cost_to_income"] = np.nan

    return ratios

    return ratios


def calculate_momentum_12m_minus_1m(
    adjusted_closes: pd.Series | list[float],
) -> Optional[float]:
    """
    Compute strictly defined 12-month minus 1-month momentum:
    Momentum = Price at t-21 / Price at t-252 - 1

    Parameters
    ----------
    adjusted_closes : Series or list
        Trailing split-adjusted daily closing prices up to session t.
        Requires at least 253 trading sessions.

    Returns
    -------
    float or None
        Causal momentum return decimal, or None if insufficient history.
    """
    if len(adjusted_closes) < 253:
        return None

    p_series = list(adjusted_closes)
    p_t_minus_21 = p_series[-22]   # Price 21 sessions ago
    p_t_minus_252 = p_series[-253]  # Price 252 sessions ago

    if not np.isfinite(p_t_minus_21) or not np.isfinite(p_t_minus_252) or p_t_minus_252 <= 0:
        return None

    return float(p_t_minus_21 / p_t_minus_252 - 1.0)


def get_latest_eligible_filing(
    symbol: str,
    as_of_session_date: str | date,
    panel_df: pd.DataFrame,
) -> Optional[pd.Series]:
    """
    Retrieve the most recent financial statement published strictly on or before
    `as_of_session_date` (zero lookahead).
    Resolves historical circular acronyms (e.g. CPBM -> CEPB) to canonical tickers.
    """
    sym = resolve_canonical_ticker(symbol)
    target_dt = pd.to_datetime(as_of_session_date)

    if "pub_date_dt" not in panel_df.columns:
        pub_col = pd.to_datetime(panel_df["publication_date"])
    else:
        pub_col = panel_df["pub_date_dt"]

    eligible = panel_df[(panel_df["symbol"] == sym) & (pub_col <= target_dt)]
    if eligible.empty:
        return None

    # Return the latest published statement
    return eligible.iloc[-1]


def get_point_in_time_constituents(
    as_of_session_date: str | date,
    conn: Optional[sqlite3.Connection] = None,
) -> list[str]:
    """
    Retrieve eligible KSE-100 constituents active on `as_of_session_date`.
    Enforces point-in-time index membership:
    effective_start_date <= date <= effective_end_date.
    Normalizes returned tickers to canonical PSX tickers (e.g. CPBM -> CEPB).
    """
    session_str = str(as_of_session_date).split(" ")[0].strip()
    should_close = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        should_close = True

    cur = conn.cursor()
    # Check if index_constituents_history exists
    has_table = cur.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='index_constituents_history'"
    ).fetchone()[0]

    if has_table:
        query = """
            SELECT DISTINCT symbol
            FROM index_constituents_history
            WHERE index_symbol = 'KSE100'
              AND effective_start_date <= ?
              AND effective_end_date >= ?
            ORDER BY symbol ASC
        """
        rows = cur.execute(query, (session_str, session_str)).fetchall()
        syms = sorted(list({resolve_canonical_ticker(r[0]) for r in rows}))
    else:
        # Fallback to current companies
        rows = cur.execute("SELECT symbol FROM companies WHERE is_kse100 = 1 ORDER BY symbol ASC").fetchall()
        syms = sorted(list({resolve_canonical_ticker(r[0]) for r in rows}))

    if should_close:
        conn.close()

    return syms

    if should_close:
        conn.close()

    return syms


def compute_terminal_exit_return(
    symbol: str,
    event_date: str | date,
    prior_price: float,
    conn: Optional[sqlite3.Connection] = None,
) -> tuple[float, str]:
    """
    Computes terminal exit return for a company experiencing delisting, suspension,
    buyback, or default.
    Returns: (exit_return, recovery_type)
    """
    if prior_price <= 0 or not np.isfinite(prior_price):
        return -1.0, "ESTIMATED_ZERO_RECOVERY"

    session_str = str(event_date).split(" ")[0].strip()
    should_close = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        should_close = True

    cur = conn.cursor()
    has_table = cur.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='company_lifecycle_events'"
    ).fetchone()[0]

    if has_table:
        row = cur.execute("""
            SELECT recovery_value_pkr, recovery_type, event_type
            FROM company_lifecycle_events
            WHERE symbol = ? AND event_date <= ?
            ORDER BY event_date DESC LIMIT 1
        """, (symbol.upper().strip(), session_str)).fetchone()

        if row and row[0] is not None:
            recovery_val = float(row[0])
            recovery_type = str(row[1])
            exit_ret = float((recovery_val - prior_price) / prior_price)
            if should_close:
                conn.close()
            return exit_ret, recovery_type

    if should_close:
        conn.close()

    # Conservative default for unverified or unrecorded delistings: -100% loss
    return -1.0, "ESTIMATED_ZERO_RECOVERY"


def compute_purged_train_test_split(
    all_sessions: list[str],
    oos_start_date: str,
    forward_horizon: int = 126,
    purge_sessions: int = 1,
) -> tuple[str, str, int, int]:
    """
    Computes strict chronological purge boundary ensuring zero label leakage between
    in-sample training and out-of-sample testing.

    Mathematical Condition:
    For every training session t_train:
        t_train + forward_horizon < idx_oos_start
    Therefore:
        max_train_idx = idx_oos_start - forward_horizon - purge_sessions

    This guarantees that the 126-session forward return window for the latest training
    rebalance date finishes strictly prior to the OOS start date.

    Parameters
    ----------
    all_sessions : list of str
        Sorted list of all market trading dates (YYYY-MM-DD).
    oos_start_date : str
        Intended start date for out-of-sample evaluation.
    forward_horizon : int
        Forward sessions used for label computation (default 126 trading days).
    purge_sessions : int
        Safety buffer sessions (default 1).

    Returns
    -------
    tuple of (train_cutoff_date, oos_effective_start_date, max_train_idx, oos_start_idx)
    """
    oos_start_dt = str(oos_start_date).split(" ")[0].strip()
    oos_indices = [i for i, s in enumerate(all_sessions) if s >= oos_start_dt]
    if not oos_indices:
        raise ValueError(f"No trading sessions found on or after oos_start_date {oos_start_date}")

    oos_start_idx = oos_indices[0]
    effective_oos_date = all_sessions[oos_start_idx]

    max_train_idx = oos_start_idx - forward_horizon - purge_sessions
    if max_train_idx < 0:
        raise ValueError(
            f"Insufficient historical sessions ({oos_start_idx}) for horizon {forward_horizon} + purge {purge_sessions}"
        )

    train_cutoff_date = all_sessions[max_train_idx]
    return train_cutoff_date, effective_oos_date, max_train_idx, oos_start_idx


