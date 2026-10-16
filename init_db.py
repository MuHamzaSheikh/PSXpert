#!/usr/bin/env python3
"""
PSXpert - Database Schema Initializer
Creates all tables, constraints, indexes, and views.
Supports PostgreSQL (using native DDL or SQLAlchemy metadata) and SQLite.
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from src.database.connection import get_engine, is_postgres, Base
import src.database.models  # Ensure all models are registered

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("InitDB")


def init_database(drop_existing: bool = False):
    engine = get_engine()
    is_pg = is_postgres()
    logger.info(f"Initializing database tables (Target dialect: {'PostgreSQL' if is_pg else 'SQLite'})...")

    if drop_existing:
        logger.warning("Dropping existing tables as requested (--drop)...")
        Base.metadata.drop_all(bind=engine)

    # If PostgreSQL and schema.sql exists, we can apply schema.sql
    schema_sql_path = Path(__file__).parent / "src" / "database" / "schema.sql"
    if is_pg and schema_sql_path.exists():
        logger.info(f"Applying native PostgreSQL schema DDL from {schema_sql_path}...")
        with open(schema_sql_path, "r", encoding="utf-8") as f:
            ddl_content = f.read()
        with engine.begin() as conn:
            # Execute DDL statements
            conn.execute(text(ddl_content))
    else:
        logger.info("Creating tables via SQLAlchemy Metadata...")
        Base.metadata.create_all(bind=engine)

    logger.info("Database tables, constraints, and indexes successfully initialized!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize PSXpert Database")
    parser.add_argument("--drop", action="store_true", help="Drop existing tables before recreating")
    args = parser.parse_args()

    init_database(drop_existing=args.drop)
