"""
Step 1: Automated Database, CSV & Codebase Audit Engine.

Inspects all PostgreSQL tables, local CSV archives, existing feature modules
(`technical_indicators`, `candlestick_patterns`, `regime_hmm`, `genetic_algorithm`,
`walk_forward`, `sentiment`) and produces quantitative data-quality & leakage metrics.
"""

from pathlib import Path
from typing import Dict, Any
import pandas as pd
from sqlalchemy import text, inspect

from src.predictive_data.intraday_builder import audit_intraday_availability


def run_comprehensive_audit(engine, project_root: Path) -> Dict[str, Any]:
    """Runs live SQL and file inspections across the entire PSXpert warehouse."""
    insp = inspect(engine)
    table_names = sorted(insp.get_table_names())
    table_counts = {}

    with engine.connect() as conn:
        for t in table_names:
            table_counts[t] = int(conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar())

        # Companies breakdown
        comp_audit = pd.read_sql(
            text("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE is_kse100) AS kse100_true,
                    COUNT(*) FILTER (WHERE is_active) AS active_true,
                    COUNT(*) FILTER (WHERE sector IN ('OTHER / UNCLASSIFIED', 'OTHER / PSX HISTORICAL') OR sector IS NULL) AS unclassified_sector,
                    COUNT(*) FILTER (WHERE symbol ~ '^P[0-9]{2}') AS debt_sukuk_tickers,
                    COUNT(*) FILTER (WHERE symbol LIKE '%ETF%' OR symbol LIKE '%CPS%' OR symbol LIKE '%PREF%') AS etf_pref_tickers
                FROM companies
            """),
            conn,
        ).iloc[0].to_dict()

        # Stock prices quality
        sp_audit = pd.read_sql(
            text("""
                SELECT
                    COUNT(*) AS total_rows,
                    COUNT(DISTINCT symbol) AS distinct_symbols,
                    MIN(trading_date)::text AS min_date,
                    MAX(trading_date)::text AS max_date,
                    COUNT(*) FILTER (WHERE close <= 0) AS nonpos_close,
                    COUNT(*) FILTER (WHERE high < low) AS bad_hl,
                    COUNT(*) FILTER (WHERE high = low) AS flat_hl,
                    COUNT(*) FILTER (WHERE open = close) AS flat_oc,
                    COUNT(*) FILTER (WHERE volume = 0 OR volume IS NULL) AS zero_vol,
                    COUNT(*) FILTER (WHERE high < GREATEST(open, close) OR low > LEAST(open, close)) AS ohlc_envelope_violations,
                    COUNT(*) FILTER (WHERE EXTRACT(DOW FROM trading_date) IN (0, 6)) AS weekend_phantom_rows,
                    COUNT(*) FILTER (WHERE market_cap IS NOT NULL) AS market_cap_populated
                FROM stock_prices
            """),
            conn,
        ).iloc[0].to_dict()

        # Non-KSE100-calendar extra rows in stock_prices (from 2002-01-01 onward)
        sp_non_cal = int(conn.execute(text("""
            SELECT COUNT(*)
            FROM stock_prices s
            LEFT JOIN market_indices m ON s.trading_date = m.trading_date AND m.index_symbol = 'KSE100'
            WHERE s.trading_date >= '2002-01-01' AND m.trading_date IS NULL
        """)).scalar())

        # Market indices
        mi_audit = pd.read_sql(
            text("""
                SELECT
                    COUNT(*) AS total_rows,
                    MIN(trading_date)::text AS min_date,
                    MAX(trading_date)::text AS max_date,
                    COUNT(*) FILTER (WHERE volume = 0) AS zero_vol_rows,
                    COUNT(*) FILTER (WHERE EXTRACT(DOW FROM trading_date) IN (0, 6)) AS weekend_rows
                FROM market_indices
            """),
            conn,
        ).iloc[0].to_dict()

        # Technical indicators
        ti_audit = pd.read_sql(
            text("""
                SELECT COUNT(*) AS total_rows, COUNT(DISTINCT symbol) AS distinct_symbols,
                       MIN(trading_date)::text AS min_date, MAX(trading_date)::text AS max_date
                FROM technical_indicators
            """),
            conn,
        ).iloc[0].to_dict()

        # Company financials
        cf_audit = pd.read_sql(
            text("""
                SELECT statement_type,
                       COUNT(*) AS rows,
                       COUNT(DISTINCT symbol) AS syms,
                       MIN(period_end_date)::text AS min_end,
                       MAX(period_end_date)::text AS max_end,
                       COUNT(*) FILTER (WHERE publication_date = period_end_date) AS pub_eq_end,
                       COUNT(*) FILTER (WHERE publication_date < period_end_date) AS pub_lt_end,
                       COUNT(*) FILTER (WHERE period_end_date > '2026-10-13') AS future_period_end,
                       COUNT(*) FILTER (WHERE metric_value = 12121) AS sentinel_12121_rows
                FROM company_financials
                GROUP BY statement_type
                ORDER BY statement_type
            """),
            conn,
        ).to_dict(orient="records")

        # News articles
        news_audit = pd.read_sql(
            text("""
                SELECT
                    COUNT(*) AS total_articles,
                    COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM published_at AT TIME ZONE 'Asia/Karachi') = 2026) AS articles_2026,
                    COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM published_at AT TIME ZONE 'Asia/Karachi') <= 2024) AS articles_archive,
                    COUNT(*) FILTER (WHERE published_at AT TIME ZONE 'Asia/Karachi' > TIMESTAMP '2026-10-13 15:30:00') AS post_price_cutoff_articles,
                    MIN(published_at)::text AS min_pub,
                    MAX(published_at)::text AS max_pub
                FROM news_articles
            """),
            conn,
        ).iloc[0].to_dict()

        # Corporate payouts placeholder audit
        payout_audit = pd.read_sql(
            text("SELECT payout_type, COUNT(*) AS cnt FROM corporate_payouts GROUP BY payout_type ORDER BY cnt DESC"),
            conn,
        ).to_dict(orient="records")

    # CSV coverage summary
    csv_files = []
    for sub in [project_root / "data" / "raw", project_root / "data" / "processed"]:
        if sub.exists():
            for f in sorted(sub.glob("*.csv")):
                csv_files.append({
                    "path": str(f.relative_to(project_root)).replace("\\", "/"),
                    "size_kb": round(f.stat().st_size / 1024.0, 1),
                })

    intraday_audit = audit_intraday_availability(engine, project_root)

    return {
        "database_dialect": engine.dialect.name,
        "table_counts": {k: int(v) for k, v in table_counts.items()},
        "companies": {k: int(v) for k, v in comp_audit.items()},
        "stock_prices": {**{k: (int(v) if isinstance(v, (int, float)) else v) for k, v in sp_audit.items()}, "non_kse100_calendar_rows_since_2002": sp_non_cal},
        "market_indices": {k: (int(v) if isinstance(v, (int, float)) else v) for k, v in mi_audit.items()},
        "technical_indicators": {k: (int(v) if isinstance(v, (int, float)) else v) for k, v in ti_audit.items()},
        "company_financials": cf_audit,
        "news_articles": {k: (int(v) if isinstance(v, (int, float)) else v) for k, v in news_audit.items()},
        "corporate_payouts": payout_audit,
        "csv_inventory": csv_files,
        "intraday_availability": intraday_audit,
    }

