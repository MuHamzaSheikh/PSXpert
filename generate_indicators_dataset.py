#!/usr/bin/env python3
"""
PSXpert - Master Technical Indicators Dataset Generator
Computes all 8 core technical indicators across PSX equities and the KSE-100 index:
- SMA / EMA (Price Trends)
- RSI (Momentum and Overbought/Oversold)
- MACD (Trend & Momentum Changes)
- Bollinger Bands (Volatility & Relative Position)
- ADX / DMI (Trend Strength & Direction)
- ATR (Volatility)
- OBV (Price-Volume Relationship)
- Stochastic Oscillator (Momentum relative to range)

Deliverable:
Generates enriched master dataset CSV with [symbol, date, OHLCV, indicators]
with strictly zero lookahead bias, and persists to PostgreSQL 'technical_indicators'.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from sqlalchemy import text
import psycopg2
from psycopg2.extras import execute_values

from src.database.connection import get_session, get_engine, get_database_url
from src.analysis.technical_indicators import TechnicalIndicatorCalculator

# Top representative KSE-100 constituents + overall market index
CORE_TICKERS = [
    "KSE100",  # Overall Market Index
    "OGDC",    # Oil & Gas Exploration (Top Cap)
    "PPL",     # Petroleum
    "MARI",    # Mari Petroleum
    "LUCK",    # Cement & Construction
    "DGKC",    # D.G. Khan Cement
    "MEBL",    # Islamic Commercial Banks
    "MCB",     # Commercial Banking
    "HBL",     # Habib Bank
    "UBL",     # United Bank
    "SYS",     # Technology & IT Services
    "HUBC",    # Power Generation
    "ENGRO",   # Conglomerate / Fertilizer
    "FFC",     # Fauji Fertilizer
    "EFERT",   # Engro Fertilizers
    "PRL",     # Refinery
    "NRL",     # National Refinery
    "PSO",     # Oil Marketing
    "SEARL",   # Pharmaceuticals
    "ILP"      # Textiles
]


def create_db_table_if_not_exists():
    """Ensures PostgreSQL table 'technical_indicators' exists with appropriate constraints."""
    session = get_session()
    try:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS technical_indicators (
                id BIGSERIAL PRIMARY KEY,
                symbol VARCHAR(20) NOT NULL,
                trading_date DATE NOT NULL,
                open NUMERIC(12, 4),
                high NUMERIC(12, 4),
                low NUMERIC(12, 4),
                close NUMERIC(12, 4) NOT NULL,
                volume BIGINT DEFAULT 0,
                sma_20 NUMERIC(12, 4),
                sma_50 NUMERIC(12, 4),
                sma_200 NUMERIC(12, 4),
                ema_12 NUMERIC(12, 4),
                ema_26 NUMERIC(12, 4),
                ema_20 NUMERIC(12, 4),
                ema_50 NUMERIC(12, 4),
                ema_200 NUMERIC(12, 4),
                rsi_14 NUMERIC(8, 4),
                macd_line NUMERIC(12, 4),
                macd_signal NUMERIC(12, 4),
                macd_diff NUMERIC(12, 4),
                bb_middle NUMERIC(12, 4),
                bb_upper NUMERIC(12, 4),
                bb_lower NUMERIC(12, 4),
                bb_bandwidth NUMERIC(8, 4),
                bb_percent_b NUMERIC(8, 4),
                dmi_plus_14 NUMERIC(8, 4),
                dmi_minus_14 NUMERIC(8, 4),
                adx_14 NUMERIC(8, 4),
                atr_14 NUMERIC(12, 4),
                atr_pct NUMERIC(8, 4),
                obv BIGINT,
                stoch_k NUMERIC(8, 4),
                stoch_d NUMERIC(8, 4),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                CONSTRAINT uq_tech_ind_sym_date UNIQUE(symbol, trading_date)
            );
            CREATE INDEX IF NOT EXISTS idx_tech_ind_sym_date ON technical_indicators(symbol, trading_date DESC);
        """))
        session.commit()
    finally:
        session.close()


def fetch_symbol_ohlcv(symbol: str) -> pd.DataFrame:
    """Fetches full historical OHLCV data for symbol from PostgreSQL."""
    sym = symbol.strip().upper()
    session = get_session()
    try:
        if sym in ["KSE100", "KSE-100", "INDEX"]:
            query = text("""
                SELECT 'KSE100' as symbol, trading_date, open, high, low, close, volume
                FROM market_indices
                WHERE index_symbol = 'KSE100'
                ORDER BY trading_date ASC;
            """)
        else:
            query = text("""
                SELECT symbol, trading_date, open, high, low, close, volume
                FROM stock_prices
                WHERE symbol = :symbol
                ORDER BY trading_date ASC;
            """)
        rows = session.execute(query, {"symbol": sym}).fetchall()
        cols = ["symbol", "trading_date", "open", "high", "low", "close", "volume"]
        return pd.DataFrame(rows, columns=cols)
    finally:
        session.close()


def bulk_upsert_indicators_to_db(df: pd.DataFrame):
    """Fast batch upsert of calculated indicators into PostgreSQL."""
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "hamza1234")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    dbname = os.getenv("POSTGRES_DB", "psxpert")

    conn = psycopg2.connect(
        dbname=dbname, user=user, password=password, host=host, port=port
    )
    conn.autocommit = False
    cur = conn.cursor()

    insert_cols = [
        "symbol", "trading_date", "open", "high", "low", "close", "volume",
        "sma_20", "sma_50", "sma_200", "ema_12", "ema_26", "ema_20", "ema_50", "ema_200",
        "rsi_14", "macd_line", "macd_signal", "macd_diff",
        "bb_middle", "bb_upper", "bb_lower", "bb_bandwidth", "bb_percent_b",
        "dmi_plus_14", "dmi_minus_14", "adx_14", "atr_14", "atr_pct", "obv", "stoch_k", "stoch_d"
    ]

    # Clean records, replace NaN with None for SQL NULL
    sub_df = df[insert_cols].copy()
    sub_df = sub_df.where(pd.notnull(sub_df), None)
    records = list(sub_df.itertuples(index=False, name=None))

    sql = f"""
        INSERT INTO technical_indicators ({', '.join(insert_cols)})
        VALUES %s
        ON CONFLICT (symbol, trading_date) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            sma_20 = EXCLUDED.sma_20,
            sma_50 = EXCLUDED.sma_50,
            sma_200 = EXCLUDED.sma_200,
            ema_12 = EXCLUDED.ema_12,
            ema_26 = EXCLUDED.ema_26,
            ema_20 = EXCLUDED.ema_20,
            ema_50 = EXCLUDED.ema_50,
            ema_200 = EXCLUDED.ema_200,
            rsi_14 = EXCLUDED.rsi_14,
            macd_line = EXCLUDED.macd_line,
            macd_signal = EXCLUDED.macd_signal,
            macd_diff = EXCLUDED.macd_diff,
            bb_middle = EXCLUDED.bb_middle,
            bb_upper = EXCLUDED.bb_upper,
            bb_lower = EXCLUDED.bb_lower,
            bb_bandwidth = EXCLUDED.bb_bandwidth,
            bb_percent_b = EXCLUDED.bb_percent_b,
            dmi_plus_14 = EXCLUDED.dmi_plus_14,
            dmi_minus_14 = EXCLUDED.dmi_minus_14,
            adx_14 = EXCLUDED.adx_14,
            atr_14 = EXCLUDED.atr_14,
            atr_pct = EXCLUDED.atr_pct,
            obv = EXCLUDED.obv,
            stoch_k = EXCLUDED.stoch_k,
            stoch_d = EXCLUDED.stoch_d;
    """

    try:
        execute_values(cur, sql, records, page_size=10000)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="PSXpert Technical Indicators Dataset Generator")
    parser.add_argument("--symbols", type=str, default=None, help="Comma-separated list of symbols (e.g. KSE100,OGDC,LUCK)")
    parser.add_argument("--all-constituents", action="store_true", help="Process all KSE-100 constituents + index")
    parser.add_argument("--out-csv", type=str, default="data/processed/psx_technical_indicators_dataset.csv", help="Path to save output CSV")
    parser.add_argument("--save-db", action="store_true", default=True, help="Save to PostgreSQL table technical_indicators")
    args = parser.parse_args()

    start_time = time.time()
    print("=" * 80)
    print("PSXPERT PHASE 4 - TECHNICAL INDICATORS DATASET GENERATOR")
    print("=" * 80)

    # Resolve target symbols
    if args.symbols:
        targets = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    elif args.all_constituents:
        session = get_session()
        try:
            constituents = session.execute(text("SELECT symbol FROM companies WHERE is_kse100 = True ORDER BY symbol;")).fetchall()
            targets = ["KSE100"] + [r[0] for r in constituents]
        finally:
            session.close()
    else:
        targets = CORE_TICKERS

    print(f"Target Symbols ({len(targets)} total): {', '.join(targets[:10])}{' ...' if len(targets) > 10 else ''}")
    print("Ensuring PostgreSQL table 'technical_indicators' exists...")
    create_db_table_if_not_exists()

    calculator = TechnicalIndicatorCalculator()
    all_frames = []
    total_processed_rows = 0

    for idx, sym in enumerate(targets, 1):
        try:
            raw_df = fetch_symbol_ohlcv(sym)
            if raw_df.empty:
                print(f"  [{idx:>2}/{len(targets)}] {sym:<8} -> 0 rows (Skipped)")
                continue

            # Compute all indicators strictly with data available up to each date
            enriched = calculator.compute_all_indicators(raw_df)
            all_frames.append(enriched)
            total_processed_rows += len(enriched)

            if args.save_db:
                bulk_upsert_indicators_to_db(enriched)

            latest_close = enriched["close"].iloc[-1]
            latest_rsi = enriched["rsi_14"].iloc[-1]
            latest_macd = enriched["macd_diff"].iloc[-1]
            print(f"  [{idx:>2}/{len(targets)}] {sym:<8} -> {len(enriched):>5,} rows | Close: PKR {latest_close:>8.2f} | RSI: {latest_rsi:>5.1f} | MACD Hist: {latest_macd:>+6.2f}")

        except Exception as e:
            print(f"  [{idx:>2}/{len(targets)}] {sym:<8} -> ERROR: {e}")

    if all_frames:
        master_df = pd.concat(all_frames, ignore_index=True)
        # Ensure output directory exists
        out_path = Path(args.out_csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        master_df.to_csv(out_path, index=False)
        print("\n" + "=" * 80)
        print("DELIVERABLE DATASET GENERATED SUCCESSFULLY")
        print("=" * 80)
        print(f"File Output       : {out_path.resolve()}")
        print(f"Total Rows        : {len(master_df):,} records")
        print(f"Total Columns     : {len(master_df.columns)} columns")
        print(f"Symbols Included  : {master_df['symbol'].nunique()} equities + KSE-100 index")
        print(f"Date Range        : {master_df['trading_date'].min()} to {master_df['trading_date'].max()}")
        print(f"Execution Time    : {time.time() - start_time:.2f} seconds")
        print("=" * 80)

        # Show sample row to verify format
        sample_row = master_df.iloc[-1]
        print("\nSample Row Deliverable (Latest Entry):")
        for col in ["symbol", "trading_date", "open", "high", "low", "close", "volume",
                    "sma_20", "ema_20", "rsi_14", "macd_diff", "bb_middle", "bb_upper",
                    "bb_lower", "adx_14", "atr_14", "obv", "stoch_k", "stoch_d"]:
            if col in sample_row:
                print(f"  {col:<15}: {sample_row[col]}")
        print("=" * 80)


if __name__ == "__main__":
    main()
