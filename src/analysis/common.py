"""Shared point-in-time data loaders, sanitization utilities, and helpers for PSX analysis engines."""

from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional, Tuple

import numpy as np

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from sqlalchemy import text
    from sqlalchemy.engine import Connection
except ImportError:
    text = None
    Connection = Any

try:
    from src.predictive_data.point_in_time import (
        adjust_splits_and_flag_glitches,
        load_clean_corporate_actions,
    )
except ImportError:
    adjust_splits_and_flag_glitches = None
    load_clean_corporate_actions = None

EXCLUDED_UNCLASSIFIED_SECTORS = {
    "",
    "OTHER / UNCLASSIFIED",
    "OTHER / PSX HISTORICAL",
    "UNCLASSIFIED",
    "N/A",
    "NONE",
}


def safe_float(val: Any, digits: Optional[int] = None) -> Optional[float]:
    """Convert numeric values to finite Python float or None."""
    if val is None or (pd is not None and val is pd.NA):
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return round(f, digits) if digits is not None else f


def safe_div(
    num: Any,
    den: Any,
    *,
    require_positive_den: bool = False,
    digits: Optional[int] = None,
) -> Optional[float]:
    """Safely divide two numbers, returning None for missing, non-finite, or zero denominator."""
    n = safe_float(num)
    d = safe_float(den)
    if n is None or d is None or d == 0.0:
        return None
    if require_positive_den and d <= 0.0:
        return None
    res = n / d
    if not math.isfinite(res):
        return None
    return round(res, digits) if digits is not None else res


def sanitize_for_json(obj: Any) -> Any:
    """Recursively convert numpy/pandas/date objects to strict JSON-safe Python primitives."""
    if obj is None or (pd is not None and obj is pd.NA):
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating, Decimal)):
        f = float(obj)
        return f if math.isfinite(f) else None
    if (pd is not None and isinstance(obj, pd.Timestamp)) or isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    if pd is not None and pd.isna(obj):
        return None
    return obj


def parse_as_of_date(as_of_date: Optional[date | datetime | str]) -> Optional[date]:
    """Parse optional evaluation date into a Python date object."""
    if as_of_date is None or as_of_date == "":
        return None
    if pd is not None and isinstance(as_of_date, pd.Timestamp):
        return as_of_date.date()
    if isinstance(as_of_date, datetime):
        return as_of_date.date()
    if isinstance(as_of_date, date):
        return as_of_date
    if pd is not None:
        try:
            return pd.to_datetime(str(as_of_date), format="ISO8601").date()
        except Exception:
            try:
                return pd.to_datetime(str(as_of_date)).date()
            except Exception as exc:
                raise ValueError(f"Invalid as_of_date format '{as_of_date}'. Expected YYYY-MM-DD.") from exc
    # Standard library fallback
    s = str(as_of_date).strip()[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Invalid as_of_date format '{as_of_date}'. Expected YYYY-MM-DD.") from exc


def get_company_metadata(conn: Connection, symbol: str) -> dict[str, Any]:
    """Fetch company classification metadata from PostgreSQL or verify existence in stock_prices."""
    sym = symbol.strip().upper()
    row = conn.execute(
        text(
            """
            SELECT symbol, company_name, sector, sector_category, isin, is_shariah, is_kse100, is_active
            FROM companies
            WHERE UPPER(symbol) = :sym
            LIMIT 1
            """
        ),
        {"sym": sym},
    ).mappings().first()

    if row:
        meta = dict(row)
        sector = (meta.get("sector") or "").strip()
        meta["has_classified_sector"] = sector.upper() not in EXCLUDED_UNCLASSIFIED_SECTORS
        return meta

    has_px = conn.execute(
        text("SELECT 1 FROM stock_prices WHERE UPPER(symbol) = :sym LIMIT 1"),
        {"sym": sym},
    ).first()
    if has_px:
        return {
            "symbol": sym,
            "company_name": sym,
            "sector": "OTHER / UNCLASSIFIED",
            "sector_category": "EQUITY",
            "isin": None,
            "is_shariah": False,
            "is_kse100": False,
            "is_active": True,
            "has_classified_sector": False,
        }

    raise ValueError(f"PSX symbol '{sym}' was not found in companies or stock_prices.")


def load_trading_calendar(conn: Connection, max_date: Optional[date] = None) -> pd.DataFrame:
    """Load KSE-100 trading days from market_indices up to max_date."""
    if max_date is not None:
        q = text(
            """
            SELECT trading_date, open, high, low, close, volume
            FROM market_indices
            WHERE index_symbol = 'KSE100' AND trading_date <= :max_d
            ORDER BY trading_date ASC
            """
        )
        df = pd.read_sql(q, conn, params={"max_d": max_date})
    else:
        q = text(
            """
            SELECT trading_date, open, high, low, close, volume
            FROM market_indices
            WHERE index_symbol = 'KSE100'
            ORDER BY trading_date ASC
            """
        )
        df = pd.read_sql(q, conn)

    df = df.drop_duplicates(subset=["trading_date"]).sort_values("trading_date").reset_index(drop=True)
    df["cal_idx"] = np.arange(len(df), dtype=int)
    return df


def resolve_effective_as_of_date(
    conn: Connection,
    symbol: str,
    as_of_date: Optional[date | datetime | str] = None,
) -> Tuple[date, date]:
    """Resolve requested cutoff date and the latest KSE-100 market trading date <= cutoff."""
    parsed = parse_as_of_date(as_of_date)
    latest_mkt = conn.execute(
        text("SELECT MAX(trading_date) FROM market_indices WHERE index_symbol = 'KSE100'")
    ).scalar()
    if latest_mkt is None:
        raise RuntimeError("market_indices contains no KSE100 calendar rows.")

    if isinstance(latest_mkt, datetime):
        latest_mkt = latest_mkt.date()

    requested = min(parsed, latest_mkt) if parsed is not None else latest_mkt

    resolved_mkt = conn.execute(
        text(
            """
            SELECT MAX(trading_date)
            FROM market_indices
            WHERE index_symbol = 'KSE100' AND trading_date <= :req_d
            """
        ),
        {"req_d": requested},
    ).scalar()
    if resolved_mkt is None:
        raise ValueError(f"Requested as_of_date {requested} precedes earliest KSE100 date.")
    if isinstance(resolved_mkt, datetime):
        resolved_mkt = resolved_mkt.date()

    return requested, resolved_mkt


def load_clean_symbol_prices(
    conn: Connection,
    symbol: str,
    max_date: date,
    cal_df: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """
    Load KSE-100 calendar-aligned OHLCV history for `symbol` up to `max_date`,
    stripping weekend phantom duplicates and zero/negative closes, and applying
    causal split adjustments strictly known on or before `max_date`.
    """
    sym = symbol.strip().upper()
    if cal_df is None:
        cal_df = load_trading_calendar(conn, max_date=max_date)
    else:
        cal_df = cal_df[pd.to_datetime(cal_df["trading_date"]).dt.date <= max_date].copy()
        cal_df["cal_idx"] = np.arange(len(cal_df), dtype=int)

    raw_counts = conn.execute(
        text(
            """
            SELECT
                COUNT(*) AS total_raw_rows,
                COUNT(*) FILTER (WHERE EXTRACT(DOW FROM trading_date) IN (0, 6)) AS weekend_rows,
                COUNT(*) FILTER (WHERE close <= 0 OR close IS NULL) AS nonpositive_close_rows
            FROM stock_prices
            WHERE UPPER(symbol) = :sym AND trading_date <= :max_d
            """
        ),
        {"sym": sym, "max_d": max_date},
    ).mappings().first()

    q_px = text(
        """
        SELECT sp.symbol, sp.trading_date, sp.open, sp.high, sp.low, sp.close,
               sp.volume, sp.market_cap, sp.source_id
        FROM stock_prices sp
        JOIN (
            SELECT DISTINCT trading_date
            FROM market_indices
            WHERE index_symbol = 'KSE100' AND trading_date <= :max_d
        ) mi ON mi.trading_date = sp.trading_date
        WHERE UPPER(sp.symbol) = :sym
          AND sp.close > 0
        ORDER BY sp.trading_date ASC, sp.source_id ASC
        """
    )
    px_df = pd.read_sql(q_px, conn, params={"sym": sym, "max_d": max_date})
    if px_df.empty:
        return px_df, cal_df, {
            "raw_rows_le_cutoff": int(raw_counts["total_raw_rows"]) if raw_counts else 0,
            "weekend_phantom_rows_excluded": int(raw_counts["weekend_rows"]) if raw_counts else 0,
            "nonpositive_close_rows_excluded": int(raw_counts["nonpositive_close_rows"]) if raw_counts else 0,
            "clean_aligned_rows": 0,
            "splits_applied": 0,
        }

    px_df["symbol"] = sym
    px_df = (
        px_df.sort_values(["trading_date", "source_id"])
        .drop_duplicates(subset=["symbol", "trading_date"], keep="last")
        .reset_index(drop=True)
    )

    payouts_df, ann_actions_df = load_clean_corporate_actions(conn)
    payouts_pit = payouts_df[
        (payouts_df["symbol"].str.upper() == sym)
        & (pd.to_datetime(payouts_df["announcement_date"]).dt.date <= max_date)
    ].copy()
    ann_pit = ann_actions_df[
        (ann_actions_df["symbol"].str.upper() == sym)
        & (pd.to_datetime(ann_actions_df["posting_date"]).dt.date <= max_date)
    ].copy()

    adj_df = adjust_splits_and_flag_glitches(px_df, cal_df, payouts_pit, ann_pit)
    adj_df = adj_df.sort_values("trading_date").reset_index(drop=True)

    # Identify flat EOD bars where High == Low so candlestick & range checks avoid false Dojis
    highs = pd.to_numeric(adj_df["adj_high"], errors="coerce")
    lows = pd.to_numeric(adj_df["adj_low"], errors="coerce")
    closes = pd.to_numeric(adj_df["adj_close"], errors="coerce")
    adj_df["is_flat_ohlc_bar"] = (highs - lows).abs() <= (closes.abs() * 1e-6).clip(lower=1e-6)

    audit = {
        "raw_rows_le_cutoff": int(raw_counts["total_raw_rows"]) if raw_counts else len(px_df),
        "weekend_phantom_rows_excluded": int(raw_counts["weekend_rows"]) if raw_counts else 0,
        "nonpositive_close_rows_excluded": int(raw_counts["nonpositive_close_rows"]) if raw_counts else 0,
        "clean_aligned_rows": int(len(adj_df)),
        "splits_applied": int(adj_df["is_corp_action_exdate"].sum()) if "is_corp_action_exdate" in adj_df.columns else 0,
        "flat_ohlc_bars_count": int(adj_df["is_flat_ohlc_bar"].sum()),
        "glitch_bars_flagged": int(adj_df["has_price_glitch_flag"].sum()) if "has_price_glitch_flag" in adj_df.columns else 0,
    }
    return adj_df, cal_df, audit

