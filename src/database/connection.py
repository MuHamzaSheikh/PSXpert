"""
PSXpert - Database Connection Management
Provides resilient SQLAlchemy database engine supporting PostgreSQL and SQLite fallback.
Reads settings from .env file or environment variables.
"""

import logging
import os
from pathlib import Path
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PSXpertDB")

Base = declarative_base()


def get_database_url() -> str:
    """
    Resolves the Database URL from environment variables.
    Defaults to PostgreSQL if credentials exist, else SQLite fallback.
    """
    explicit_url = os.getenv("DATABASE_URL")
    if explicit_url:
        return explicit_url

    pg_user = os.getenv("POSTGRES_USER", "postgres")
    pg_pass = os.getenv("POSTGRES_PASSWORD", "")
    pg_host = os.getenv("POSTGRES_HOST", "localhost")
    pg_port = os.getenv("POSTGRES_PORT", "5432")
    pg_db = os.getenv("POSTGRES_DB", "psxpert")

    if pg_pass:
        return f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"

    # Default fallback to SQLite in data directory
    data_dir = Path(__file__).resolve().parent.parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = data_dir / "psxpert.db"
    return f"sqlite:///{sqlite_path.as_posix()}"


_engine: Engine = None
_SessionFactory = None


def get_engine() -> Engine:
    """Returns or creates the singleton SQLAlchemy engine with failover handling."""
    global _engine, _SessionFactory
    if _engine is not None:
        return _engine

    db_url = get_database_url()
    try:
        if db_url.startswith("postgresql"):
            logger.info(f"Connecting to PostgreSQL at {db_url.split('@')[-1]}...")
            engine = create_engine(
                db_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True
            )
            # Test connectivity
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Successfully established connection to PostgreSQL.")
            _engine = engine
            _SessionFactory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
            return _engine
    except Exception as e:
        logger.warning(f"Could not connect to PostgreSQL ({e}). Falling back to embedded SQLite...")

    # Fallback to SQLite
    data_dir = Path(__file__).resolve().parent.parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = data_dir / "psxpert.db"
    fallback_url = f"sqlite:///{sqlite_path.as_posix()}"
    logger.info(f"Using SQLite database -> {sqlite_path}")
    _engine = create_engine(
        fallback_url,
        connect_args={"check_same_thread": False}
    )
    # Enable WAL mode and foreign keys for SQLite
    with _engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        conn.execute(text("PRAGMA foreign_keys=ON;"))
    _SessionFactory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _engine


def get_session() -> Session:
    """Returns a new SQLAlchemy session."""
    global _SessionFactory
    if _SessionFactory is None:
        get_engine()
    return _SessionFactory()


def is_postgres() -> bool:
    """Returns True if the active database is PostgreSQL."""
    return get_engine().dialect.name == "postgresql"
