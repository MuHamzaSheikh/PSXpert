"""
Inspect database connection, table counts, and companies data sources.
"""
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from src.database.connection import get_session, is_postgres, get_engine
from sqlalchemy import text

print(f"Connecting to DB. is_postgres: {is_postgres()}")
session = get_session()

tables = [
    "companies",
    "stock_prices",
    "market_indices",
    "technical_indicators",
    "news_articles",
    "news_entities",
    "news_sentiment"
]

for tbl in tables:
    try:
        res = session.execute(text(f"SELECT count(*) FROM {tbl}")).fetchone()
        print(f"Table '{tbl}': {res[0]} rows")
    except Exception as e:
        print(f"Table '{tbl}' error: {e}")

try:
    c_res = session.execute(text("SELECT count(DISTINCT symbol) FROM companies")).fetchone()
    print(f"Distinct symbols in companies table: {c_res[0]}")
    sp_res = session.execute(text("SELECT count(DISTINCT symbol) FROM stock_prices")).fetchone()
    print(f"Distinct symbols in stock_prices table: {sp_res[0]}")
except Exception as e:
    print("Distinct query error:", e)

session.close()
