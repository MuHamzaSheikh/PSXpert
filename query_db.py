#!/usr/bin/env python3
"""
PSXpert - Interactive Database Explorer
Quickly browse tables, inspect ticker data, and run custom queries.

Usage:
  python query_db.py tables                     # List all tables and row counts
  python query_db.py companies                  # View constituent companies
  python query_db.py stock_prices OGDC [limit]  # View recent daily prices for a ticker
  python query_db.py news [limit]               # View recent financial news
  python query_db.py financials OGDC            # View financial fundamentals
  python query_db.py announcements OGDC         # View recent corporate announcements
  python query_db.py sql "SELECT ..."           # Run arbitrary SQL query
"""

import sys
import pandas as pd
from sqlalchemy import text
from src.database.connection import get_engine, is_postgres

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
pd.set_option('display.max_colwidth', 50)

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1].lower()
    engine = get_engine()
    dialect = "PostgreSQL" if is_postgres() else "SQLite"

    with engine.connect() as conn:
        if cmd == "tables":
            print(f"\n--- TABLES IN PSXPERT ({dialect}) ---")
            tables = [
                "data_sources", "companies", "stock_prices", "market_indices",
                "news_articles", "news_entities", "company_financials",
                "news_sentiment", "corporate_announcements", "corporate_payouts"
            ]
            for tbl in tables:
                cnt = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
                print(f"  {tbl:<28s}: {cnt:>10,} rows")
            print()

        elif cmd == "companies":
            sector = sys.argv[2] if len(sys.argv) > 2 else None
            sql = "SELECT symbol, company_name, sector, is_shariah, is_active FROM companies"
            if sector:
                sql += f" WHERE sector ILIKE '%{sector}%'"
            sql += " ORDER BY symbol LIMIT 30"
            df = pd.read_sql(text(sql), conn)
            print(f"\n[COMPANIES DIRECTORY] ({len(df)} rows displayed):")
            print(df.to_string(index=False))

        elif cmd in ("stock_prices", "prices"):
            symbol = sys.argv[2].upper() if len(sys.argv) > 2 else "OGDC"
            limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
            sql = text(f"""
                SELECT trading_date, symbol, open, high, low, close, volume, market_cap
                FROM stock_prices
                WHERE symbol = '{symbol}'
                ORDER BY trading_date DESC
                LIMIT {limit}
            """)
            df = pd.read_sql(sql, conn)
            print(f"\n[STOCK PRICES - {symbol}] (Latest {len(df)} sessions):")
            print(df.to_string(index=False))

        elif cmd == "news":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            sql = text(f"""
                SELECT a.published_at, e.entity_value as symbol, s.sentiment_label, a.publisher, a.headline
                FROM news_articles a
                LEFT JOIN news_entities e ON a.id = e.article_id AND e.entity_type = 'COMPANY'
                LEFT JOIN news_sentiment s ON a.id = s.article_id
                ORDER BY a.published_at DESC
                LIMIT {limit}
            """)
            df = pd.read_sql(sql, conn)
            print(f"\n[FINANCIAL NEWS & SENTIMENT] (Latest {len(df)} articles):")
            print(df.to_string(index=False))

        elif cmd == "financials":
            symbol = sys.argv[2].upper() if len(sys.argv) > 2 else "OGDC"
            sql = text(f"""
                SELECT fiscal_year, fiscal_period, period_end_date, publication_date, metric_name, metric_value
                FROM company_financials
                WHERE symbol = '{symbol}'
                ORDER BY fiscal_year DESC, fiscal_period DESC, metric_name
                LIMIT 20
            """)
            df = pd.read_sql(sql, conn)
            print(f"\n[COMPANY FINANCIALS - {symbol}]:")
            print(df.to_string(index=False))

        elif cmd in ("announcements", "ann"):
            symbol = sys.argv[2].upper() if len(sys.argv) > 2 else "OGDC"
            limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
            sql = text(f"""
                SELECT posting_date, category, announcement_title, document_url
                FROM corporate_announcements
                WHERE symbol = '{symbol}'
                ORDER BY posting_date DESC
                LIMIT {limit}
            """)
            df = pd.read_sql(sql, conn)
            print(f"\n[CORPORATE ANNOUNCEMENTS - {symbol}]:")
            print(df.to_string(index=False))

        elif cmd == "sql":
            query = " ".join(sys.argv[2:])
            if not query.strip():
                print("Error: Please provide a SQL query, e.g. python query_db.py sql 'SELECT * FROM companies LIMIT 5'")
                return
            df = pd.read_sql(text(query), conn)
            print(f"\n[QUERY RESULT] ({len(df)} rows):")
            print(df.to_string(index=False))

        else:
            print(f"Unknown command '{cmd}'. Available: tables, companies, stock_prices, news, financials, announcements, sql")

if __name__ == "__main__":
    main()
