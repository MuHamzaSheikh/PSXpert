"""Unit, integration, point-in-time leakage, and regression tests for PSX analysis engines."""

from __future__ import annotations

import os
import sys
from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from src.analysis.candlestick_patterns import CandlestickPatternDetector
from src.analysis.common import load_clean_symbol_prices, load_trading_calendar
from src.analysis.fundamental_engine import FundamentalAnalysisEngine
from src.analysis.service import AnalysisService
from src.analysis.technical_engine import TechnicalAnalysisEngine
from src.analysis.technical_indicators import TechnicalIndicatorCalculator
from src.database.connection import get_engine


@pytest.fixture(scope="module")
def db_engine():
    return get_engine()


@pytest.fixture(scope="module")
def service(db_engine):
    return AnalysisService(engine=db_engine)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_technical_indicator_parity_and_weekend_exclusion(db_engine):
    """TechnicalAnalysisEngine must match TechnicalIndicatorCalculator on clean calendar-aligned split-adjusted series."""
    tech_eng = TechnicalAnalysisEngine()
    calc = TechnicalIndicatorCalculator()

    with db_engine.connect() as conn:
        result = tech_eng.analyze(conn, "OGDC", as_of_date="2026-10-13")
        cal_df = load_trading_calendar(conn, max_date=date(2026, 10, 13))
        adj_df, _, audit = load_clean_symbol_prices(conn, "OGDC", max_date=date(2026, 10, 13), cal_df=cal_df)

    # Confirm 0 weekend dates exist in cleaned series
    tdates = pd.to_datetime(adj_df["trading_date"])
    assert (tdates.dt.dayofweek >= 5).sum() == 0
    assert audit["weekend_phantom_rows_excluded"] >= 0

    raw_calc_input = pd.DataFrame(
        {
            "trading_date": tdates,
            "open": adj_df["adj_open"].astype(float),
            "high": adj_df["adj_high"].astype(float),
            "low": adj_df["adj_low"].astype(float),
            "close": adj_df["adj_close"].astype(float),
            "volume": adj_df["volume"].astype(float),
        }
    )
    expected = calc.compute_all_indicators(raw_calc_input).iloc[-1]

    t_ind = result["trend_analysis"]["indicators"]
    m_ind = result["momentum_analysis"]["indicators"]
    v_ind = result["volatility_analysis"]["indicators"]

    assert t_ind["sma_20"] == pytest.approx(float(expected["sma_20"]), abs=1e-3)
    assert t_ind["sma_50"] == pytest.approx(float(expected["sma_50"]), abs=1e-3)
    assert t_ind["sma_200"] == pytest.approx(float(expected["sma_200"]), abs=1e-3)
    assert t_ind["ema_20"] == pytest.approx(float(expected["ema_20"]), abs=1e-3)
    assert t_ind["adx_14"] == pytest.approx(float(expected["adx_14"]), abs=1e-2)
    assert m_ind["rsi_14"] == pytest.approx(float(expected["rsi_14"]), abs=1e-2)
    assert m_ind["macd_line"] == pytest.approx(float(expected["macd_line"]), abs=1e-3)
    assert m_ind["macd_signal"] == pytest.approx(float(expected["macd_signal"]), abs=1e-3)
    assert m_ind["stoch_k"] == pytest.approx(float(expected["stoch_k"]), abs=1e-2)
    assert v_ind["atr_14"] == pytest.approx(float(expected["atr_14"]), abs=1e-3)
    assert v_ind["bb_upper"] == pytest.approx(float(expected["bb_upper"]), abs=1e-3)

    # Verify pre-listing behavior -> explicit NO_PRICE_DATA without crash
    with db_engine.connect() as conn:
        pre_ipo = tech_eng.analyze(conn, "OGDC", as_of_date="2002-05-31")
    assert pre_ipo.get("status") == "NO_PRICE_DATA"
    assert pre_ipo["technical_score"] is None

    # Verify short-history warmup masking (< 50 sessions => sma_50/200 None; < 200 => sma_200 None)
    thirtieth_day = tdates.iloc[29].date().isoformat()
    with db_engine.connect() as conn:
        tiny_res = tech_eng.analyze(conn, "OGDC", as_of_date=thirtieth_day)
    assert tiny_res["data_freshness"]["total_trading_sessions"] == 30
    assert tiny_res["trend_analysis"]["indicators"]["sma_50"] is None
    assert tiny_res["trend_analysis"]["indicators"]["sma_200"] is None
    assert tiny_res["trend_analysis"]["long_term_trend"] == "INSUFFICIENT_HISTORY"

    eightieth_day = tdates.iloc[79].date().isoformat()
    with db_engine.connect() as conn:
        short_res = tech_eng.analyze(conn, "OGDC", as_of_date=eightieth_day)
    assert short_res["data_freshness"]["total_trading_sessions"] == 80
    assert short_res["trend_analysis"]["indicators"]["sma_50"] is not None
    assert short_res["trend_analysis"]["indicators"]["sma_200"] is None


def test_flat_bar_doji_suppression():
    """Candlestick analyzer must filter out artificial Dojis caused by High == Low EOD bars."""
    eng = TechnicalAnalysisEngine()
    n = 35
    df = pd.DataFrame(
        {
            "trading_date": pd.date_range("2026-01-01", periods=n, freq="B"),
            "open": [100.0 + i * 0.2 for i in range(n)],
            "high": [101.0 + i * 0.2 for i in range(n)],
            "low": [99.0 + i * 0.2 for i in range(n)],
            "close": [100.5 + i * 0.2 for i in range(n)],
            "volume": [100000.0] * n,
        }
    )
    # Force last 3 bars to be completely flat EOD quotes (O == H == L == C)
    for idx in (n - 3, n - 2, n - 1):
        df.loc[idx, ["open", "high", "low", "close"]] = 107.0
    flat_mask = (df["high"] - df["low"]).abs() <= 1e-6

    # Raw detector flags flat bars as Doji, engine must suppress them
    _, raw_pats = CandlestickPatternDetector().detect_patterns(df)
    assert any(p["index"] >= n - 3 and "Doji" in p["pattern"] for p in raw_pats)

    c_out = eng._analyze_candlesticks(df, "TEST", flat_mask)
    assert c_out["suppressed_flat_bar_patterns"] >= 1
    assert all(p["bars_ago"] >= 3 for p in c_out["patterns"])


def test_technical_causal_cutoff_and_hmm_no_leakage(db_engine):
    """Historical technical analysis as_of_date must never contain post-cutoff levels or regimes."""
    tech_eng = TechnicalAnalysisEngine()
    cutoff = "2024-06-28"
    with db_engine.connect() as conn:
        hist_res = tech_eng.analyze(conn, "LUCK", as_of_date=cutoff)

    assert hist_res["data_cutoff_timestamp"] <= cutoff
    assert hist_res["hmm_market_context"]["regime_date"] <= cutoff
    # Every pivot source date inside S/R zones must be <= cutoff
    for lvl_group in ("support_levels", "resistance_levels"):
        for zone in hist_res["support_resistance"][lvl_group]:
            for src in zone["sources"]:
                if "(" in src and ")" in src:
                    inner = src.split("(")[-1].rstrip(")")
                    if len(inner) == 10 and inner[4] == "-":
                        assert inner <= cutoff


def test_fundamental_ratios_derived_eps_and_pit_cutoffs(db_engine):
    """Verify exact IFRS ratios, derived EPS for OGDC FY26, skipped-year YoY protection, and pre-disclosure barrier."""
    fund_eng = FundamentalAnalysisEngine()
    with db_engine.connect() as conn:
        # 1. OGDC latest (2026-10-13): 2026-06-30 disclosed 2026-09-04 (missing basic_eps -> derived ~56.35)
        ogdc_now = fund_eng.analyze(conn, "OGDC", as_of_date="2026-10-13")
        assert ogdc_now["status"] == "OK"
        assert ogdc_now["reporting_period_context"]["latest_complete_period_end"] == "2026-06-30"
        assert ogdc_now["profitability"]["eps_source"] == "derived_net_income_over_shares"
        assert ogdc_now["profitability"]["eps_pkr"] == pytest.approx(242371919000.0 / 4300928400.0, abs=0.05)
        assert ogdc_now["financial_health"]["interest_coverage_ratio"] > 20.0
        # OGDC 2025-06-30 lacked revenue, so strict 1Y revenue YoY must be None while 1Y NI YoY uses 2025->2026
        assert ogdc_now["growth"]["revenue_growth_yoy_pct"] is None
        assert ogdc_now["growth"]["net_income_growth_yoy_pct"] == pytest.approx(42.65, abs=0.2)

        # 2. Strict PIT cutoff: before OGDC FY26 disclosure (2026-09-04), FY26 must NOT appear
        ogdc_pre = fund_eng.analyze(conn, "OGDC", as_of_date="2026-08-01")
        assert ogdc_pre["reporting_period_context"]["latest_complete_period_end"] == "2024-06-30"
        assert ogdc_pre["reporting_period_context"]["latest_disclosed_period_end"] == "2025-06-30"

        # 3. Exploration sector on 2024-11-01 when MARI, POL, PPL, OGDC all had FY24 published
        ogdc_2024 = fund_eng.analyze(conn, "OGDC", as_of_date="2024-11-01")
        assert ogdc_2024["sector_comparison"]["status"] == "OK"
        assert ogdc_2024["sector_comparison"]["comparable_peers_count"] == 3


def test_fundamental_split_invariance_and_dividend_repair(db_engine):
    """Pre-split LUCK valuation must be split-invariant and corporate_payouts face-value bugs repaired."""
    fund_eng = FundamentalAnalysisEngine()
    with db_engine.connect() as conn:
        # LUCK pre-split (2024-10-15, raw_close ~844, market_cap 247B, FY24 NI ~65.56B -> P/E ~3.77x)
        luck_pre = fund_eng.analyze(conn, "LUCK", as_of_date="2024-10-15")
        assert luck_pre["valuation"]["pe_ratio"] is not None
        assert 2.5 <= luck_pre["valuation"]["pe_ratio"] <= 6.0

        # LUCK 2025-11-01: 2025-09-17 dividend row had scraper raw=100.0 with payout_pct=200%, fv=2.0 -> repaired to 4.0
        luck_div = fund_eng.analyze(conn, "LUCK", as_of_date="2025-11-01")
        ev = next(e for e in luck_div["dividend_analysis"]["recent_announcements"] if e["announcement_date"] == "2025-09-17")
        assert ev["dps_corrected_for_face_value"] is True
        assert ev["validated_dps_pkr"] == pytest.approx(4.0, abs=1e-4)
        assert luck_div["valuation"]["pe_ratio"] is not None


def test_fundamental_bank_guards_and_missing_data(db_engine):
    """Commercial banks must mark non-applicable industrial ratios None; missing firms never fabricate ratios."""
    fund_eng = FundamentalAnalysisEngine()
    with db_engine.connect() as conn:
        mebl = fund_eng.analyze(conn, "MEBL", as_of_date="2026-10-13")
        assert mebl["status"] == "OK"
        assert mebl["profitability"]["operating_margin_pct"] is None
        assert mebl["financial_health"]["current_ratio"] is None
        assert mebl["financial_health"]["interest_coverage_ratio"] is None
        assert mebl["sector_comparison"]["status"] == "OK"
        assert mebl["sector_comparison"]["comparable_peers_count"] >= 5

        tele = fund_eng.analyze(conn, "TELE", as_of_date="2026-10-13")
        assert tele["status"] == "NO_FINANCIAL_STATEMENTS"
        assert tele["fundamental_score"] is None
        assert tele["profitability"]["status"] == "UNAVAILABLE"
        assert tele["sector_comparison"]["status"] == "INSUFFICIENT_SECTOR_DATA"

        aicl = fund_eng.analyze(conn, "AICL", as_of_date="2026-10-13")
        assert aicl["status"] == "OK"
        assert aicl["sector_comparison"]["status"] == "INSUFFICIENT_SECTOR_DATA"


def test_db_persistence_and_cache_invalidation(service, db_engine):
    """Repeated requests for unchanged data must hit analysis_results cache without recalculation."""
    first = service.get_technical_analysis("FFC", as_of_date="2026-10-13", force_refresh=True)
    second = service.get_technical_analysis("FFC", as_of_date="2026-10-13", force_refresh=False)
    diff_cutoff = service.get_technical_analysis("FFC", as_of_date="2025-10-15", force_refresh=False)

    assert first["cache"]["hit"] is False
    assert second["cache"]["hit"] is True
    assert first["cache"]["source_fingerprint"] == second["cache"]["source_fingerprint"]
    assert first["technical_score"] == second["technical_score"]
    assert diff_cutoff["cache"]["source_fingerprint"] != second["cache"]["source_fingerprint"]

    with db_engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT symbol, analysis_type, data_cutoff_timestamp, source_fingerprint
                FROM analysis_results
                WHERE id = :rid
                """
            ),
            {"rid": second["cache"]["analysis_id"]},
        ).mappings().first()
        assert row is not None
        assert row["symbol"] == "FFC"
        assert row["analysis_type"] == "TECHNICAL"


def test_fastapi_endpoints_and_legacy_regression(client):
    """New analysis endpoints and existing dashboard endpoints must work cleanly together."""
    r_tech = client.get("/api/analysis/technical/OGDC")
    assert r_tech.status_code == 200
    assert r_tech.json()["analysis_type"] == "TECHNICAL"

    r_fund = client.get("/api/analysis/fundamental/MEBL")
    assert r_fund.status_code == 200
    assert r_fund.json()["analysis_type"] == "FUNDAMENTAL"

    r_comb = client.get("/api/analysis/combined/LUCK")
    assert r_comb.status_code == 200
    body = r_comb.json()
    assert "technical_analysis" in body and "fundamental_analysis" in body

    r_sel = client.get("/api/analysis/SYS?mode=both&as_of_date=2025-10-15")
    assert r_sel.status_code == 200
    assert r_sel.json()["as_of_date"] <= "2025-10-15"

    assert client.get("/api/analysis/technical/INVALID_TICKER_XYZ").status_code == 404
    assert client.get("/api/analysis/technical/OGDC?as_of_date=not-a-date").status_code == 400

    # Regression checks on existing endpoints
    assert client.get("/api/market-summary").status_code == 200
    assert client.get("/api/stocks").status_code == 200
    assert client.get("/api/indicators/OGDC").status_code == 200
    assert client.get("/api/quantitative/hmm").status_code == 200


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

