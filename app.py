"""
PSXpert - Web Application Backend (FastAPI)
Serves live market indices, stock OHLCV prices, candlestick pattern recognitions,
and FinBERT news sentiment from PostgreSQL.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
import pandas as pd
import numpy as np

from src.database.connection import get_session
from src.analysis.candlestick_patterns import CandlestickPatternDetector

app = FastAPI(title="PSXpert Terminal API", version="1.0.0")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pattern_detector = CandlestickPatternDetector()
STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/api/market-summary")
def get_market_summary() -> Dict[str, Any]:
    """Returns KSE-100 latest points, point change, 52W range, and market breadth."""
    session = get_session()
    try:
        # 1. Latest KSE-100 index record
        idx_row = session.execute(text("""
            SELECT trading_date, open, high, low, close, point_change, pct_change
            FROM market_indices
            WHERE index_symbol = 'KSE100'
            ORDER BY trading_date DESC
            LIMIT 1;
        """)).fetchone()

        if not idx_row:
            raise HTTPException(status_code=404, detail="KSE-100 index data not found.")

        # 2. 52-Week High and Low for KSE-100
        stats_52w = session.execute(text("""
            SELECT MAX(high) as high_52w, MIN(low) as low_52w
            FROM market_indices
            WHERE index_symbol = 'KSE100'
              AND trading_date >= (CURRENT_DATE - INTERVAL '365 days');
        """)).fetchone()

        # 3. Market Breadth from latest stock sessions (fast indexed join)
        breadth = session.execute(text("""
            WITH latest_date AS (
                SELECT MAX(trading_date) as max_d FROM stock_prices
            )
            SELECT
                COUNT(CASE WHEN s.close > s.open THEN 1 END) as advances,
                COUNT(CASE WHEN s.close < s.open THEN 1 END) as declines,
                COUNT(CASE WHEN s.close = s.open THEN 1 END) as unchanged,
                COUNT(*) as total_active
            FROM stock_prices s
            JOIN latest_date ld ON s.trading_date = ld.max_d;
        """)).fetchone()

        # 4. Top Gainers & Losers
        movers = session.execute(text("""
            WITH latest_date AS (
                SELECT MAX(trading_date) as max_d FROM stock_prices
            )
            SELECT s.symbol, c.company_name, c.sector, s.close, s.open,
                   ROUND(((s.close - s.open) / NULLIF(s.open, 0)) * 100, 2) as pct_change,
                   s.volume
            FROM stock_prices s
            JOIN latest_date ld ON s.trading_date = ld.max_d
            JOIN companies c ON s.symbol = c.symbol
            WHERE s.open > 0
            ORDER BY pct_change DESC;
        """)).fetchall()

        gainers = []
        losers = []
        for r in movers:
            item = {
                "symbol": r[0],
                "company_name": r[1],
                "sector": r[2],
                "close": float(r[3]),
                "pct_change": float(r[4]) if r[4] is not None else 0.0,
                "volume": int(r[5]) if r[5] else 0
            }
            if len(gainers) < 5 and item["pct_change"] > 0:
                gainers.append(item)
            if item["pct_change"] < 0:
                losers.append(item)
        losers = sorted(losers, key=lambda x: x["pct_change"])[:5]

        # 5. FinBERT sentiment overview
        sent_counts = session.execute(text("""
            SELECT sentiment_label, COUNT(*)
            FROM news_sentiment
            WHERE model_name = 'finbert'
            GROUP BY sentiment_label;
        """)).fetchall()
        sent_dict = {r[0]: r[1] for r in sent_counts}

        return {
            "index_symbol": "KSE100",
            "name": "KSE-100 Index (Pakistan Stock Exchange)",
            "trading_date": str(idx_row[0]),
            "open": float(idx_row[1]),
            "high": float(idx_row[2]),
            "low": float(idx_row[3]),
            "close": float(idx_row[4]),
            "point_change": float(idx_row[5]) if idx_row[5] is not None else 0.0,
            "pct_change": float(idx_row[6]) if idx_row[6] is not None else 0.0,
            "high_52w": float(stats_52w[0]) if stats_52w and stats_52w[0] else float(idx_row[2]),
            "low_52w": float(stats_52w[1]) if stats_52w and stats_52w[1] else float(idx_row[3]),
            "breadth": {
                "advances": int(breadth[0]) if breadth else 0,
                "declines": int(breadth[1]) if breadth else 0,
                "unchanged": int(breadth[2]) if breadth else 0,
                "total": int(breadth[3]) if breadth else 0
            },
            "top_gainers": gainers,
            "top_losers": losers,
            "sentiment_summary": {
                "positive": sent_dict.get("POSITIVE", 0),
                "negative": sent_dict.get("NEGATIVE", 0),
                "neutral": sent_dict.get("NEUTRAL", 0)
            }
        }
    finally:
        session.close()


@app.get("/api/stocks")
def list_stocks(
    search: Optional[str] = None,
    sector: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Returns list of listed PSX stocks with latest price and sector info."""
    session = get_session()
    try:
        where_clauses = ["1=1"]
        params = {"limit": limit}

        if search:
            where_clauses.append("(UPPER(c.symbol) LIKE :search OR UPPER(c.company_name) LIKE :search)")
            params["search"] = f"%{search.strip().upper()}%"
        if sector and sector != "ALL":
            where_clauses.append("c.sector = :sector")
            params["sector"] = sector

        where_sql = " AND ".join(where_clauses)

        query = text(f"""
            WITH latest_date AS (
                SELECT MAX(trading_date) as max_d FROM stock_prices
            )
            SELECT c.symbol, c.company_name, c.sector, c.is_kse100, c.is_shariah,
                   s.close, s.open, s.high, s.low, s.volume,
                   ROUND(((s.close - s.open) / NULLIF(s.open, 0)) * 100, 2) as pct_change,
                   s.trading_date
            FROM companies c
            LEFT JOIN stock_prices s ON c.symbol = s.symbol AND s.trading_date = (SELECT max_d FROM latest_date)
            WHERE {where_sql}
            ORDER BY c.is_kse100 DESC, s.volume DESC NULLS LAST
            LIMIT :limit;
        """)

        rows = session.execute(query, params).fetchall()
        result = []
        for r in rows:
            result.append({
                "symbol": r[0],
                "company_name": r[1],
                "sector": r[2],
                "is_kse100": bool(r[3]),
                "is_shariah": bool(r[4]),
                "close": float(r[5]) if r[5] is not None else 0.0,
                "open": float(r[6]) if r[6] is not None else 0.0,
                "high": float(r[7]) if r[7] is not None else 0.0,
                "low": float(r[8]) if r[8] is not None else 0.0,
                "volume": int(r[9]) if r[9] is not None else 0,
                "pct_change": float(r[10]) if r[10] is not None else 0.0,
                "latest_date": str(r[11]) if r[11] else None
            })
        return result
    finally:
        session.close()


@app.get("/api/sectors")
def list_sectors() -> List[str]:
    """Returns distinct sectors in PSX."""
    session = get_session()
    try:
        rows = session.execute(text("SELECT DISTINCT sector FROM companies WHERE sector IS NOT NULL ORDER BY sector;")).fetchall()
        return [r[0] for r in rows if r[0]]
    finally:
        session.close()


@app.get("/api/ohlcv/{symbol}")
def get_ohlcv(
    symbol: str,
    days: int = Query(default=180, ge=10, le=5000)
) -> Dict[str, Any]:
    """
    Returns authentic OHLCV candlestick records and technical indicators (EMAs)
    for any stock or KSE-100 from PostgreSQL.
    """
    sym = symbol.strip().upper()
    session = get_session()
    try:
        company_info = None
        if sym in ["KSE100", "KSE-100", "INDEX", "MARKET"]:
            query = text("""
                SELECT trading_date, open, high, low, close, volume, point_change, pct_change
                FROM market_indices
                WHERE index_symbol = 'KSE100'
                ORDER BY trading_date DESC
                LIMIT :limit;
            """)
            rows = session.execute(query, {"limit": days}).fetchall()
            cols = ["trading_date", "open", "high", "low", "close", "volume", "point_change", "pct_change"]
            company_info = {
                "symbol": "KSE100",
                "name": "KSE-100 Index (Pakistan Stock Exchange)",
                "sector": "Overall Market Index",
                "is_kse100": True
            }
        else:
            c_row = session.execute(text("SELECT company_name, sector, is_kse100, is_shariah FROM companies WHERE symbol = :s"), {"s": sym}).fetchone()
            if c_row:
                company_info = {
                    "symbol": sym,
                    "name": c_row[0],
                    "sector": c_row[1],
                    "is_kse100": bool(c_row[2]),
                    "is_shariah": bool(c_row[3])
                }

            query = text("""
                SELECT trading_date, open, high, low, close, volume
                FROM stock_prices
                WHERE symbol = :symbol
                ORDER BY trading_date DESC
                LIMIT :limit;
            """)
            rows = session.execute(query, {"symbol": sym, "limit": days}).fetchall()
            cols = ["trading_date", "open", "high", "low", "close", "volume"]

        if not rows:
            raise HTTPException(status_code=404, detail=f"No price records found for symbol '{sym}'.")

        df = pd.DataFrame(rows, columns=cols)
        df["symbol"] = sym
        df = df.sort_values(by="trading_date").reset_index(drop=True)

        # Calculate candlestick indicators and detect patterns
        df_annotated, patterns = pattern_detector.detect_patterns(df)

        candles = []
        for _, row in df_annotated.iterrows():
            candles.append({
                "time": str(row["trading_date"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
                "ema20": float(row["ema20"]) if pd.notna(row.get("ema20")) else None,
                "ema50": float(row["ema50"]) if pd.notna(row.get("ema50")) else None,
                "ema200": float(row["ema200"]) if pd.notna(row.get("ema200")) else None,
                "pattern": row.get("pattern_name"),
                "pattern_type": row.get("pattern_type"),
                "pattern_signal": row.get("pattern_signal")
            })

        return {
            "symbol": sym,
            "company": company_info or {"symbol": sym, "name": sym, "sector": "PSX Listed"},
            "total_bars": len(candles),
            "candles": candles,
            "patterns": patterns,
            "stats": {
                "latest_close": candles[-1]["close"],
                "period_high": max(c["high"] for c in candles),
                "period_low": min(c["low"] for c in candles),
                "total_volume": sum(c["volume"] for c in candles),
                "bullish_patterns_count": sum(1 for p in patterns if p["type"] == "BULLISH"),
                "bearish_patterns_count": sum(1 for p in patterns if p["type"] == "BEARISH"),
                "neutral_patterns_count": sum(1 for p in patterns if p["type"] == "NEUTRAL")
            }
        }
    finally:
        session.close()


@app.get("/api/patterns/{symbol}")
def get_patterns(
    symbol: str,
    days: int = Query(default=180, ge=10, le=1000)
) -> List[Dict[str, Any]]:
    """Returns structured list of detected candlestick patterns for a symbol."""
    ohlcv_data = get_ohlcv(symbol, days=days)
    return ohlcv_data.get("patterns", [])


@app.get("/api/indicators/{symbol}")
def get_indicators(
    symbol: str,
    days: int = Query(default=180, ge=10, le=1000)
) -> Dict[str, Any]:
    """
    Returns precomputed or on-demand calculated technical indicators
    (SMA, EMA, RSI, MACD, Bollinger Bands, ATR, ADX, OBV, Stochastic)
    along with diagnostic analytical interpretations explaining the conditions.
    """
    sym = symbol.strip().upper()
    session = get_session()
    try:
        # Check if precomputed in technical_indicators table
        rows = session.execute(text("""
            SELECT trading_date, open, high, low, close, volume,
                   sma_20, sma_50, sma_200, ema_12, ema_26, ema_20, ema_50, ema_200,
                   rsi_14, macd_line, macd_signal, macd_diff,
                   bb_middle, bb_upper, bb_lower, bb_bandwidth, bb_percent_b,
                   dmi_plus_14, dmi_minus_14, adx_14, atr_14, atr_pct,
                   obv, stoch_k, stoch_d
            FROM technical_indicators
            WHERE symbol = :symbol
            ORDER BY trading_date DESC
            LIMIT :limit;
        """), {"symbol": sym, "limit": days}).fetchall()

        if rows:
            cols = [
                "trading_date", "open", "high", "low", "close", "volume",
                "sma_20", "sma_50", "sma_200", "ema_12", "ema_26", "ema_20", "ema_50", "ema_200",
                "rsi_14", "macd_line", "macd_signal", "macd_diff",
                "bb_middle", "bb_upper", "bb_lower", "bb_bandwidth", "bb_percent_b",
                "dmi_plus_14", "dmi_minus_14", "adx_14", "atr_14", "atr_pct",
                "obv", "stoch_k", "stoch_d"
            ]
            df = pd.DataFrame(rows, columns=cols).sort_values(by="trading_date").reset_index(drop=True)
        else:
            # Calculate on-demand using TechnicalIndicatorCalculator
            raw_ohlcv = get_ohlcv(sym, days=days)
            raw_df = pd.DataFrame(raw_ohlcv["candles"])
            raw_df["symbol"] = sym
            raw_df = raw_df.rename(columns={"time": "trading_date"})
            from src.analysis.technical_indicators import TechnicalIndicatorCalculator
            calc = TechnicalIndicatorCalculator()
            df = calc.compute_all_indicators(raw_df)

        from src.analysis.technical_indicators import TechnicalIndicatorCalculator
        calc = TechnicalIndicatorCalculator()
        interpretation = calc.generate_analytical_interpretation(df.iloc[-1])

        records = []
        for _, r in df.iterrows():
            record = {}
            for col in df.columns:
                val = r[col]
                if pd.isna(val):
                    record[col] = None
                elif isinstance(val, (int, np.integer)):
                    record[col] = int(val)
                elif isinstance(val, (float, np.floating)):
                    record[col] = float(val)
                else:
                    record[col] = str(val)
            records.append(record)

        return {
            "symbol": sym,
            "total_bars": len(records),
            "indicators": records,
            "latest_diagnostics": interpretation
        }
    finally:
        session.close()


@app.get("/api/sentiment/latest")
def get_latest_sentiment(limit: int = 20) -> List[Dict[str, Any]]:
    """Returns recent financial news articles with FinBERT sentiment scores."""
    session = get_session()
    try:
        query = text("""
            SELECT a.id, a.headline, a.publisher, a.url, a.published_at,
                   s.sentiment_label, s.sentiment_score, s.confidence, s.evaluation_metadata
            FROM news_articles a
            JOIN news_sentiment s ON a.id = s.article_id
            WHERE s.model_name = 'finbert'
            ORDER BY a.published_at DESC
            LIMIT :limit;
        """)
        rows = session.execute(query, {"limit": limit}).fetchall()
        news_list = []
        for r in rows:
            meta = r[8]
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            elif not isinstance(meta, dict):
                meta = {}

            news_list.append({
                "article_id": r[0],
                "headline": r[1],
                "publisher": r[2],
                "url": r[3],
                "published_at": str(r[4]),
                "sentiment_label": r[5],
                "sentiment_score": float(r[6]) if r[6] is not None else 0.0,
                "confidence": float(r[7]) if r[7] is not None else 0.0,
                "symbols_mentioned": meta.get("symbols_mentioned", []),
                "target_sentiments": meta.get("target_specific_sentiments", {})
            })
        return news_list
    finally:
        session.close()


# Mount static directory for frontend files
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>PSXpert Terminal - Building Frontend...</h1>")
