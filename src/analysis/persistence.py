"""PostgreSQL persistence and fingerprint-based cache for PSX analysis engines."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.analysis.common import sanitize_for_json

ENGINE_VERSION = "psxpert_analysis_v1.1"

_DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS analysis_results (
        id SERIAL PRIMARY KEY,
        symbol VARCHAR(32) NOT NULL,
        analysis_type VARCHAR(24) NOT NULL,
        as_of_date DATE NOT NULL,
        analysis_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        data_cutoff_timestamp VARCHAR(64) NOT NULL,
        source_fingerprint VARCHAR(128) NOT NULL,
        overall_assessment VARCHAR(64),
        score DOUBLE PRECISION,
        metrics_and_findings JSONB NOT NULL,
        data_source_references JSONB NOT NULL,
        CONSTRAINT uq_analysis_cache UNIQUE (symbol, analysis_type, as_of_date, source_fingerprint)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_analysis_results_lookup
    ON analysis_results (symbol, analysis_type, as_of_date, analysis_timestamp DESC)
    """,
]


def ensure_analysis_results_table(conn: Connection) -> None:
    """Create analysis_results table and index idempotently."""
    for ddl in _DDL_STATEMENTS:
        conn.execute(text(ddl))


def compute_source_fingerprint(
    conn: Connection,
    symbol: str,
    analysis_type: str,
    as_of_date: date,
) -> str:
    """
    Compute a deterministic fingerprint over all underlying database state
    visible on or before `as_of_date` so unchanged data serves cached results.
    """
    sym = symbol.strip().upper()
    atype = analysis_type.strip().upper()

    parts: dict[str, Any] = {
        "engine_version": ENGINE_VERSION,
        "symbol": sym,
        "analysis_type": atype,
        "as_of_date": as_of_date.isoformat(),
    }

    # Price & calendar state (needed by Technical for charts/indicators AND by Fundamental for P/E, P/B, Yield)
    px_row = conn.execute(
        text(
            """
            SELECT COUNT(*) AS cnt, MAX(trading_date)::text AS max_d
            FROM stock_prices
            WHERE UPPER(symbol) = :sym AND trading_date <= :cutoff AND close > 0
            """
        ),
        {"sym": sym, "cutoff": as_of_date},
    ).mappings().first()

    latest_px = conn.execute(
        text(
            """
            SELECT sp.trading_date::text AS d, sp.close, sp.volume, sp.market_cap
            FROM stock_prices sp
            JOIN market_indices mi ON mi.trading_date = sp.trading_date AND mi.index_symbol = 'KSE100'
            WHERE UPPER(sp.symbol) = :sym AND sp.trading_date <= :cutoff AND sp.close > 0
            ORDER BY sp.trading_date DESC, sp.source_id DESC
            LIMIT 1
            """
        ),
        {"sym": sym, "cutoff": as_of_date},
    ).mappings().first()

    idx_row = conn.execute(
        text(
            """
            SELECT COUNT(*) AS cnt, MAX(trading_date)::text AS max_d
            FROM market_indices
            WHERE index_symbol = 'KSE100' AND trading_date <= :cutoff
            """
        ),
        {"cutoff": as_of_date},
    ).mappings().first()

    pay_row = conn.execute(
        text(
            """
            SELECT COUNT(*) AS cnt, MAX(announcement_date)::text AS max_d
            FROM corporate_payouts
            WHERE UPPER(symbol) = :sym AND announcement_date <= :cutoff AND payout_type != 'type'
            """
        ),
        {"sym": sym, "cutoff": as_of_date},
    ).mappings().first()

    ann_row = conn.execute(
        text(
            """
            SELECT COUNT(*) AS cnt, MAX(posting_date)::text AS max_d
            FROM corporate_announcements
            WHERE UPPER(symbol) = :sym AND posting_date <= :cutoff
            """
        ),
        {"sym": sym, "cutoff": as_of_date},
    ).mappings().first()

    parts["market_indices"] = dict(idx_row) if idx_row else {}
    parts["stock_prices"] = dict(px_row) if px_row else {}
    parts["latest_price"] = dict(latest_px) if latest_px else {}
    parts["corporate_payouts"] = dict(pay_row) if pay_row else {}
    parts["corporate_announcements"] = dict(ann_row) if ann_row else {}

    if atype in ("FUNDAMENTAL", "COMBINED"):
        comp_row = conn.execute(
            text(
                """
                SELECT sector, sector_category, is_kse100
                FROM companies
                WHERE UPPER(symbol) = :sym
                LIMIT 1
                """
            ),
            {"sym": sym},
        ).mappings().first()
        sector_val = (comp_row["sector"] if comp_row else None) or "OTHER / UNCLASSIFIED"

        fin_sym_row = conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt, MAX(period_end_date)::text AS max_pe
                FROM company_financials
                WHERE UPPER(symbol) = :sym
                  AND statement_type IN ('INCOME_STATEMENT', 'BALANCE_SHEET', 'CASH_FLOW')
                """
            ),
            {"sym": sym},
        ).mappings().first()

        sector_peer_row = conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt, COUNT(DISTINCT cf.symbol) AS syms, MAX(cf.period_end_date)::text AS max_pe
                FROM company_financials cf
                JOIN companies c ON c.symbol = cf.symbol
                WHERE c.sector = :sector
                  AND cf.statement_type IN ('INCOME_STATEMENT', 'BALANCE_SHEET', 'CASH_FLOW')
                """
            ),
            {"sector": sector_val},
        ).mappings().first()

        # Also track sector peer payout & price updates up to cutoff
        sector_px_row = conn.execute(
            text(
                """
                SELECT COUNT(*) AS cnt, MAX(sp.trading_date)::text AS max_d
                FROM stock_prices sp
                JOIN companies c ON c.symbol = sp.symbol
                WHERE c.sector = :sector AND sp.trading_date <= :cutoff
                """
            ),
            {"sector": sector_val, "cutoff": as_of_date},
        ).mappings().first()

        parts["company"] = dict(comp_row) if comp_row else {}
        parts["financials_symbol"] = dict(fin_sym_row) if fin_sym_row else {}
        parts["financials_sector"] = dict(sector_peer_row) if sector_peer_row else {}
        parts["sector_prices"] = dict(sector_px_row) if sector_px_row else {}

    canonical = json.dumps(sanitize_for_json(parts), sort_keys=True, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def get_cached_analysis(
    conn: Connection,
    symbol: str,
    analysis_type: str,
    as_of_date: date,
    source_fingerprint: str,
) -> Optional[dict[str, Any]]:
    """Retrieve a matching cached analysis payload from PostgreSQL if present."""
    ensure_analysis_results_table(conn)
    row = conn.execute(
        text(
            """
            SELECT id, analysis_timestamp, data_cutoff_timestamp,
                   source_fingerprint, metrics_and_findings
            FROM analysis_results
            WHERE symbol = :sym
              AND analysis_type = :atype
              AND as_of_date = :as_of
              AND source_fingerprint = :fp
            ORDER BY analysis_timestamp DESC
            LIMIT 1
            """
        ),
        {
            "sym": symbol.strip().upper(),
            "atype": analysis_type.strip().upper(),
            "as_of": as_of_date,
            "fp": source_fingerprint,
        },
    ).mappings().first()

    if not row:
        return None

    payload = row["metrics_and_findings"]
    if isinstance(payload, str):
        payload = json.loads(payload)

    cached_at = row["analysis_timestamp"]
    cached_iso = cached_at.isoformat() if isinstance(cached_at, datetime) else str(cached_at)

    out = dict(payload)
    out["cache"] = {
        "hit": True,
        "analysis_id": int(row["id"]),
        "cached_at": cached_iso,
        "source_fingerprint": row["source_fingerprint"],
    }
    return out


def save_analysis_result(
    conn: Connection,
    symbol: str,
    analysis_type: str,
    as_of_date: date,
    data_cutoff_timestamp: str,
    source_fingerprint: str,
    overall_assessment: Optional[str],
    score: Optional[float],
    payload: dict[str, Any],
    data_source_references: dict[str, Any],
) -> dict[str, Any]:
    """Persist structured analysis output into PostgreSQL analysis_results table."""
    ensure_analysis_results_table(conn)
    clean_payload = sanitize_for_json(payload)
    # Remove any transient cache wrapper inside persisted body before saving
    clean_payload.pop("cache", None)
    clean_sources = sanitize_for_json(data_source_references)
    now_utc = datetime.now(timezone.utc)

    row = conn.execute(
        text(
            """
            INSERT INTO analysis_results (
                symbol, analysis_type, as_of_date, analysis_timestamp,
                data_cutoff_timestamp, source_fingerprint, overall_assessment,
                score, metrics_and_findings, data_source_references
            )
            VALUES (
                :sym, :atype, :as_of, :ats,
                :cutoff, :fp, :assess,
                :score, CAST(:payload AS jsonb), CAST(:sources AS jsonb)
            )
            ON CONFLICT ON CONSTRAINT uq_analysis_cache DO UPDATE SET
                analysis_timestamp = EXCLUDED.analysis_timestamp,
                data_cutoff_timestamp = EXCLUDED.data_cutoff_timestamp,
                overall_assessment = EXCLUDED.overall_assessment,
                score = EXCLUDED.score,
                metrics_and_findings = EXCLUDED.metrics_and_findings,
                data_source_references = EXCLUDED.data_source_references
            RETURNING id, analysis_timestamp
            """
        ),
        {
            "sym": symbol.strip().upper(),
            "atype": analysis_type.strip().upper(),
            "as_of": as_of_date,
            "ats": now_utc,
            "cutoff": data_cutoff_timestamp,
            "fp": source_fingerprint,
            "assess": overall_assessment,
            "score": score,
            "payload": json.dumps(clean_payload, allow_nan=False),
            "sources": json.dumps(clean_sources, allow_nan=False),
        },
    ).mappings().first()

    saved_ts = row["analysis_timestamp"]
    out = dict(clean_payload)
    out["cache"] = {
        "hit": False,
        "analysis_id": int(row["id"]),
        "cached_at": saved_ts.isoformat() if isinstance(saved_ts, datetime) else str(saved_ts),
        "source_fingerprint": source_fingerprint,
    }
    return out

