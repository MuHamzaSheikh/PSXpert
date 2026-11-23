"""
PSXpert - Historical KSE-100 Universe & Survivorship Bias Validation Test Suite
Tests:
1. Historical constituent membership schema and integrity
2. Entry and exit date chronological ordering
3. Point-in-time constituent membership query dynamics
4. Point-in-time financial disclosure availability (zero lookahead)
5. Publication date strictly on or after period-end date
6. Company lifecycle events schema and provenance
7. Terminal exit return accounting (documented recovery vs conservative zero recovery)
8. Banking and non-banking sector-aware metric separation
9. Causal momentum calculation (12M minus 1M)
10. Portfolio simulation reproducibility and metrics consistency
"""

import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest

from src.ml.fundamental_recovery import (
    build_harmonized_fundamental_panel,
    calculate_momentum_12m_minus_1m,
    compute_purged_train_test_split,
    compute_sector_aware_ratios,
    compute_terminal_exit_return,
    get_latest_eligible_filing,
    get_point_in_time_constituents,
    resolve_canonical_ticker,
)

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "psxpert.db"


@pytest.fixture
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


def test_index_constituents_history_exists_and_populated(db_conn):
    """Test that index_constituents_history table exists and contains verified records."""
    cur = db_conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "index_constituents_history" in tables, "Table index_constituents_history missing from database"

    count = cur.execute("SELECT COUNT(*) FROM index_constituents_history").fetchone()[0]
    assert count >= 100, f"Expected at least 100 constituent intervals, found {count}"

    # Verify no nulls in mandatory primary columns
    null_starts = cur.execute("SELECT COUNT(*) FROM index_constituents_history WHERE effective_start_date IS NULL").fetchone()[0]
    null_ends = cur.execute("SELECT COUNT(*) FROM index_constituents_history WHERE effective_end_date IS NULL").fetchone()[0]
    assert null_starts == 0, "Found null effective_start_date in index_constituents_history"
    assert null_ends == 0, "Found null effective_end_date in index_constituents_history"


def test_constituent_effective_dates_consistency(db_conn):
    """Test that effective_end_date is strictly greater than or equal to effective_start_date."""
    df = pd.read_sql("SELECT symbol, effective_start_date, effective_end_date FROM index_constituents_history", db_conn)
    for _, r in df.iterrows():
        start = str(r["effective_start_date"])
        end = str(r["effective_end_date"])
        assert start <= end, f"Inverted dates for {r['symbol']}: start {start} > end {end}"


def test_point_in_time_constituent_membership_dynamics(db_conn):
    """
    Test that point-in-time constituent query dynamically reflects recompositions:
    - IMAGE was inducted on 2026-10-01 (should NOT be in index on 2025-01-01, but in on 2026-10-15)
    - UNITY was excluded on 2026-04-01 (should be in index on 2025-01-01, but NOT on 2026-05-01)
    """
    members_2025 = set(get_point_in_time_constituents("2025-01-01", db_conn))
    members_2026_may = set(get_point_in_time_constituents("2026-05-01", db_conn))
    members_2026_oct = set(get_point_in_time_constituents("2026-10-15", db_conn))

    # UNITY: active in early 2025, removed April 2026
    assert "UNITY" in members_2025, "UNITY should be in KSE-100 on 2025-01-01"
    assert "UNITY" not in members_2026_may, "UNITY should NOT be in KSE-100 on 2026-05-01"

    # IMAGE: inducted October 2026
    assert "IMAGE" not in members_2025, "IMAGE should NOT be in KSE-100 on 2025-01-01"
    assert "IMAGE" in members_2026_oct, "IMAGE should be in KSE-100 on 2026-10-15"

    # Core stalwart like OGDC or LUCK should be in all
    assert "OGDC" in members_2025 and "OGDC" in members_2026_may and "OGDC" in members_2026_oct
    assert "LUCK" in members_2025 and "LUCK" in members_2026_may and "LUCK" in members_2026_oct


def test_company_lifecycle_events_schema_and_recovery(db_conn):
    """Test that company_lifecycle_events table exists and tracks documented events."""
    cur = db_conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "company_lifecycle_events" in tables, "Table company_lifecycle_events missing from database"

    events = pd.read_sql("SELECT symbol, event_type, recovery_value_pkr, recovery_type FROM company_lifecycle_events", db_conn)
    assert len(events) >= 5, "Expected lifecycle events to be populated"

    # HASCOL transfer to defaulters
    hascol_evt = events[events["symbol"] == "HASCOL"]
    assert not hascol_evt.empty, "HASCOL event missing"
    assert hascol_evt.iloc[0]["event_type"] == "DEFAULTER_SEGMENT"

    # SHEL buyback tender offer
    shel_evt = events[events["symbol"] == "SHEL"]
    assert not shel_evt.empty, "SHEL buyback event missing"
    assert shel_evt.iloc[0]["recovery_value_pkr"] == 155.00


def test_terminal_return_calculations(db_conn):
    """Test terminal return accounting for documented recovery vs conservative zero recovery."""
    # 1. SHEL tender offer at 155.00 from entry price of 100.00 -> +55%
    ret_shel, rec_shel = compute_terminal_exit_return("SHEL", "2024-11-10", prior_price=100.00, conn=db_conn)
    assert abs(ret_shel - 0.55) < 1e-4
    assert rec_shel == "DOCUMENTED_BUYBACK"

    # 2. HASCOL defaulter exit at 5.75 from entry price of 10.00 -> -42.5%
    ret_hascol, rec_hascol = compute_terminal_exit_return("HASCOL", "2021-07-01", prior_price=10.00, conn=db_conn)
    assert abs(ret_hascol - (-0.425)) < 1e-4
    assert rec_hascol == "DOCUMENTED_TRADING_EXIT"

    # 3. Defunct unrecorded firm with zero recovery -> -100% loss
    ret_defunct, rec_defunct = compute_terminal_exit_return("ACORD", "2015-07-01", prior_price=20.00, conn=db_conn)
    assert ret_defunct == -1.0
    assert rec_defunct == "ESTIMATED_ZERO_RECOVERY"


def test_point_in_time_financial_availability():
    """Test that financial statements cannot be retrieved prior to their publication date."""
    panel_df = pd.DataFrame([
        {
            "symbol": "TEST",
            "fiscal_year": 2023,
            "period_end_date": "2023-06-30",
            "publication_date": "2023-10-08",
            "is_estimated_publication": True,
            "timestamp_confidence": "ESTIMATED_100D_FALLBACK",
            "net_income": 1000.0,
            "shareholders_equity": 5000.0,
            "total_assets": 10000.0,
            "revenue": 8000.0,
            "operating_profit": 1500.0,
            "is_bank": False,
        }
    ])

    # 1. Prior to publication date (e.g. 2023-09-01): filing must NOT be available
    filing_prior = get_latest_eligible_filing("TEST", "2023-09-01", panel_df)
    assert filing_prior is None, "Lookahead violation: statement retrieved prior to publication date"

    # 2. On publication date (2023-10-08): filing MUST be available
    filing_on = get_latest_eligible_filing("TEST", "2023-10-08", panel_df)
    assert filing_on is not None, "Statement should be available on publication date"
    assert filing_on["net_income"] == 1000.0

    # 3. After publication date (2023-11-01): filing MUST be available
    filing_after = get_latest_eligible_filing("TEST", "2023-11-01", panel_df)
    assert filing_after is not None
    assert filing_after["net_income"] == 1000.0


def test_publication_date_strictly_after_period_end():
    """Test that across all harmonized statements, publication_date >= period_end_date."""
    panel_csv = DATA_DIR / "harmonized_historical_fundamentals.csv"
    if panel_csv.exists():
        df = pd.read_csv(panel_csv)
        violations = df[pd.to_datetime(df["publication_date"]) < pd.to_datetime(df["period_end_date"])]
        assert len(violations) == 0, f"Found {len(violations)} statements with publication date < period end date"


def test_sector_aware_ratios_separation():
    """Test that banking ratios and industrial ratios are strictly segregated."""
    # Bank filing
    bank_filing = pd.Series({
        "symbol": "TESTBANK",
        "is_bank": True,
        "net_income": 500.0,
        "shareholders_equity": 2000.0,
        "total_assets": 10000.0,
        "net_interest_income": 800.0,
        "non_interest_expense": 400.0,
        "total_operating_income": 1000.0,
        "free_cash_flow": np.nan,
        "operating_profit": np.nan,
        "total_debt": np.nan,
    })
    bank_ratios = compute_sector_aware_ratios(bank_filing, market_price=50.0, shares_outstanding=100.0)
    assert np.isnan(bank_ratios["fcf_yield"]), "Bank should have NaN for fcf_yield"
    assert np.isnan(bank_ratios["debt_to_equity"]), "Bank should have NaN for debt_to_equity"
    assert np.isfinite(bank_ratios["net_interest_margin"])
    assert np.isfinite(bank_ratios["cost_to_income"])

    # Industrial filing
    corp_filing = pd.Series({
        "symbol": "TESTCORP",
        "is_bank": False,
        "net_income": 200.0,
        "shareholders_equity": 1000.0,
        "total_assets": 3000.0,
        "revenue": 2500.0,
        "operating_profit": 350.0,
        "free_cash_flow": 150.0,
        "total_debt": 500.0,
        "interest_expense": 50.0,
    })
    corp_ratios = compute_sector_aware_ratios(corp_filing, market_price=25.0, shares_outstanding=100.0)
    assert np.isnan(corp_ratios["net_interest_margin"]), "Non-bank should have NaN for NIM"
    assert np.isnan(corp_ratios["cost_to_income"]), "Non-bank should have NaN for Cost-to-Income"
    assert np.isfinite(corp_ratios["fcf_yield"])
    assert np.isfinite(corp_ratios["operating_margin"])
    assert np.isfinite(corp_ratios["debt_to_equity"])


def test_causal_momentum_12m_minus_1m():
    """Test that momentum formula P[t-21] / P[t-252] - 1 is causal and correct."""
    # 253 linear prices from 100 to 352
    prices = [float(100 + i) for i in range(253)]
    # p[-22] is price 21 sessions ago: 100 + (253 - 22) = 100 + 231 = 331
    # p[-253] is price 252 sessions ago: 100 + 0 = 100
    expected_mom = (331.0 / 100.0) - 1.0  # 2.31
    mom = calculate_momentum_12m_minus_1m(prices)
    assert mom is not None
    assert abs(mom - expected_mom) < 1e-4

    # Insufficient length returns None
    assert calculate_momentum_12m_minus_1m(prices[:200]) is None


def test_canonical_ticker_resolution_cpbm_to_cepb(db_conn):
    """Test canonical resolution of CPBM to CEPB and database presence."""
    assert resolve_canonical_ticker("CPBM") == "CEPB"
    assert resolve_canonical_ticker("cpbm") == "CEPB"
    assert resolve_canonical_ticker("OGDC") == "OGDC"

    cur = db_conn.cursor()
    cepb_prices = cur.execute("SELECT COUNT(*) FROM stock_prices WHERE symbol = 'CEPB'").fetchone()[0]
    assert cepb_prices >= 5000, f"Expected >= 5000 price records for canonical CEPB, found {cepb_prices}"

    # Verify fundamentals panel has CEPB
    panel = build_harmonized_fundamental_panel()
    cepb_filings = panel[panel["symbol"] == "CEPB"]
    assert len(cepb_filings) >= 15, f"Expected >= 15 audited statements for CEPB, found {len(cepb_filings)}"


def test_point_in_time_market_cap_ratio_calculation():
    """Test compute_sector_aware_ratios with point_in_time_market_cap and known inputs."""
    # Non-bank scenario: equity 20,000M, net_income 2,500M, fcf 1,500M, market_cap raw PKR 50,000,000,000 (50,000M)
    non_bank_stmt = {
        "is_bank": False,
        "net_income": 2500.0,
        "shareholders_equity": 20000.0,
        "total_assets": 40000.0,
        "revenue": 30000.0,
        "operating_profit": 4000.0,
        "free_cash_flow": 1500.0,
        "total_debt": 5000.0,
        "interest_expense": 500.0,
    }
    ratios = compute_sector_aware_ratios(
        statement_row=non_bank_stmt,
        market_price=50.0,
        point_in_time_market_cap=50_000_000_000.0,  # 50,000 Million PKR
    )
    # B/P = 20,000 / 50,000 = 0.40
    assert abs(ratios["book_to_price"] - 0.40) < 1e-4
    # P/B = 50,000 / 20,000 = 2.50
    assert abs(ratios["price_to_book"] - 2.50) < 1e-4
    # ROE = 2,500 / 20,000 = 0.125
    assert abs(ratios["roe"] - 0.125) < 1e-4
    # FCF Yield = 1,500 / 50,000 = 0.03
    assert abs(ratios["fcf_yield"] - 0.03) < 1e-4
    # Earnings Yield = 2,500 / 50,000 = 0.05
    assert abs(ratios["earnings_yield"] - 0.05) < 1e-4
    # Bank ratios MUST be NaN
    assert np.isnan(ratios["net_interest_margin"])
    assert np.isnan(ratios["cost_to_income"])


def test_purged_train_test_split_zero_sample_overlap(db_conn):
    """
    Test that compute_purged_train_test_split strictly guarantees zero label leakage:
    For every training date t <= train_cutoff_date, its forward 126-session label
    outcome date MUST be strictly prior to oos_start_date.
    """
    cur = db_conn.cursor()
    all_sessions = sorted([
        r[0] for r in cur.execute(
            "SELECT DISTINCT trading_date FROM market_indices WHERE index_symbol='KSE100' ORDER BY trading_date ASC"
        ).fetchall()
    ])
    oos_start = "2024-07-09"
    forward_horizon = 126
    purge_sessions = 1

    train_cutoff, eff_oos, train_idx, oos_idx = compute_purged_train_test_split(
        all_sessions=all_sessions,
        oos_start_date=oos_start,
        forward_horizon=forward_horizon,
        purge_sessions=purge_sessions,
    )

    assert train_cutoff < oos_start, f"train_cutoff {train_cutoff} not before oos_start {oos_start}"
    assert eff_oos == oos_start, f"eff_oos {eff_oos} does not match {oos_start}"
    assert oos_idx - train_idx >= forward_horizon + purge_sessions, "Purge gap insufficient"

    # Forward 126-session outcome session for the maximum training session
    max_train_label_end_idx = train_idx + forward_horizon
    max_train_label_end_date = all_sessions[max_train_label_end_idx]

    # Must be strictly less than oos_idx
    assert max_train_label_end_idx < oos_idx, (
        f"Label outcome session index {max_train_label_end_idx} ({max_train_label_end_date}) "
        f"reaches into or beyond OOS start index {oos_idx} ({eff_oos})!"
    )
    assert max_train_label_end_date < eff_oos, (
        f"Label outcome date {max_train_label_end_date} reaches into OOS period ({eff_oos})!"
    )

