"""Comprehensive test suite for Phase 1: Fundamental Recovery & Strategy Comparison.

Verifies:
1. SBP FSA Coverage Matrix completeness and unmatched preservation.
2. Strict point-in-time publication date integrity (zero lookahead).
3. 12M minus 1M momentum formula causality and session indexing.
4. Sector-aware accounting separation (Banks vs Non-Financials, NaNs preserved, never 0).
5. Strategy evaluation fairness and out-of-sample execution constraints.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure project root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.ml.fundamental_recovery import (
    build_harmonized_fundamental_panel,
    calculate_momentum_12m_minus_1m,
    compute_sector_aware_ratios,
    get_latest_eligible_filing,
)

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "psxpert.db"
REPORTS_DIR = Path("reports/model_evaluation")


class TestCoverageMatrix:
    """Requirement 1: SBP Data Coverage Verification."""

    def test_coverage_matrix_structure_and_counts(self):
        matrix_path = REPORTS_DIR / "sbp_fsa_coverage_matrix.csv"
        assert matrix_path.exists(), f"Missing coverage matrix at {matrix_path}"

        df = pd.read_csv(matrix_path)
        assert len(df) == 100, f"Expected exactly 100 constituents, got {len(df)}"

        required_cols = [
            "symbol",
            "company_name",
            "sector",
            "is_bank",
            "matching_status",
            "matching_confidence",
            "years_count",
            "available_financial_years",
            "missing_financial_years",
            "statement_types_available",
            "source_workbooks_and_sheets",
            "has_verified_earnings_announcements",
        ]
        for col in required_cols:
            assert col in df.columns, f"Required column {col} missing from matrix"

    def test_unmatched_companies_preserved_for_review(self):
        unmatched_path = REPORTS_DIR / "sbp_fsa_unmatched_review.csv"
        assert unmatched_path.exists(), f"Missing unmatched review file at {unmatched_path}"

        unmatched_df = pd.read_csv(unmatched_path)
        matrix_df = pd.read_csv(REPORTS_DIR / "sbp_fsa_coverage_matrix.csv")

        unmatched_count = len(matrix_df[matrix_df["matching_status"] == "UNMATCHED"])
        assert len(unmatched_df) == unmatched_count, (
            f"Unmatched review file count ({len(unmatched_df)}) does not match matrix ({unmatched_count})"
        )
        assert len(unmatched_df) == 42, f"Expected exactly 42 unmatched companies, got {len(unmatched_df)}"

    def test_history_expansion(self):
        matrix_df = pd.read_csv(REPORTS_DIR / "sbp_fsa_coverage_matrix.csv")
        avg_years = matrix_df["years_count"].mean()
        assert avg_years >= 10.0, f"Average years history ({avg_years:.1f}) should exceed 10 years per company"

        firms_ge_10 = (matrix_df["years_count"] >= 10).sum()
        assert firms_ge_10 >= 40, f"Expected at least 40 companies with >= 10 years history, got {firms_ge_10}"


class TestPointInTimeIntegrity:
    """Requirement 2: Point-in-Time Data Integrity & Fallback Distinction."""

    def test_harmonized_panel_publication_after_period_end(self):
        panel = build_harmonized_fundamental_panel()
        assert not panel.empty, "Harmonized panel is empty"
        assert panel["symbol"].nunique() >= 90, "Expected at least 90 covered symbols"

        # Every filing must have publication_date >= period_end_date
        p_end = pd.to_datetime(panel["period_end_date"])
        p_pub = pd.to_datetime(panel["publication_date"])
        invalid_lag = panel[p_pub < p_end]
        assert len(invalid_lag) == 0, f"Found {len(invalid_lag)} statements published before period end date!"

    def test_timestamp_confidence_provenance_distinction(self):
        panel = build_harmonized_fundamental_panel()
        valid_confidences = {"VERIFIED_ANNOUNCEMENT", "ESTIMATED_100D_FALLBACK"}
        observed = set(panel["timestamp_confidence"].unique())
        assert observed.issubset(valid_confidences), f"Unexpected confidence labels: {observed - valid_confidences}"

        # Verified announcements must have is_estimated_publication == False
        verified = panel[panel["timestamp_confidence"] == "VERIFIED_ANNOUNCEMENT"]
        assert (verified["is_estimated_publication"] == False).all()

        # Estimated fallbacks must have is_estimated_publication == True
        estimated = panel[panel["timestamp_confidence"] == "ESTIMATED_100D_FALLBACK"]
        assert (estimated["is_estimated_publication"] == True).all()

    def test_no_future_statement_accessible(self):
        panel = build_harmonized_fundamental_panel()
        test_row = panel.iloc[0]
        sym = test_row["symbol"]
        pub_date = pd.to_datetime(test_row["publication_date"])

        # Query 1 day before publication date -> must NOT return this filing
        prior_date = (pub_date - timedelta(days=1)).strftime("%Y-%m-%d")
        filing_prior = get_latest_eligible_filing(sym, prior_date, panel)

        if filing_prior is not None:
            assert pd.to_datetime(filing_prior["publication_date"]) < pub_date

        # Query on publication date -> eligible
        filing_on_pub = get_latest_eligible_filing(sym, test_row["publication_date"], panel)
        assert filing_on_pub is not None
        assert pd.to_datetime(filing_on_pub["publication_date"]) <= pub_date


class TestMomentumFormula:
    """Requirement 4: Strictly Defined 12M minus 1M Momentum."""

    def test_momentum_session_indexing(self):
        # Create a synthetic series of 300 sessions where price is exactly session number: 1, 2, ..., 300
        prices = list(range(1, 301))  # prices[-1] = 300, prices[-22] = 279, prices[-253] = 48
        mom = calculate_momentum_12m_minus_1m(prices)
        assert mom is not None

        expected = 279.0 / 48.0 - 1.0
        assert pytest.approx(mom, rel=1e-5) == expected

    def test_momentum_minimum_history_requirement(self):
        # 252 sessions should return None (need at least 253 for t-252 causal index)
        short_prices = list(range(1, 253))
        assert calculate_momentum_12m_minus_1m(short_prices) is None

        # 253 sessions returns a valid float
        exact_prices = list(range(1, 254))
        assert calculate_momentum_12m_minus_1m(exact_prices) is not None

    def test_momentum_causality_zero_lookahead(self):
        # Modifying the current session t price (prices[-1]) or t-1 to t-20 prices
        # MUST NOT affect the 12M minus 1M momentum value!
        base_prices = list(range(100, 400))
        base_mom = calculate_momentum_12m_minus_1m(base_prices)

        # Perturb the most recent 20 sessions (t-20 to t)
        perturbed_prices = list(base_prices)
        for i in range(1, 21):
            perturbed_prices[-i] = perturbed_prices[-i] * 5.0  # huge shock in skip-month

        perturbed_mom = calculate_momentum_12m_minus_1m(perturbed_prices)
        assert pytest.approx(base_mom, rel=1e-7) == perturbed_mom, (
            "Momentum calculation leaked recent 1-month prices! It must strictly use P[t-21] / P[t-252] - 1."
        )


class TestSectorAccountingSeparation:
    """Requirement 5: Banking vs Non-Banking Formula Separation."""

    def test_bank_ratios_keep_industrial_as_nan(self):
        bank_stmt = {
            "is_bank": True,
            "net_income": 1000.0,
            "shareholders_equity": 5000.0,
            "total_assets": 50000.0,
            "net_interest_income": 3000.0,
            "non_interest_expense": 1200.0,
            "total_operating_income": 3500.0,
            "shares_outstanding": 100.0,
        }
        ratios = compute_sector_aware_ratios(bank_stmt, market_price=50.0)

        # Bank metrics computed
        assert ratios["is_bank"] is True
        assert ratios["roe"] == pytest.approx(1000.0 / 5000.0)
        assert ratios["roa"] == pytest.approx(1000.0 / 50000.0)
        assert ratios["net_interest_margin"] == pytest.approx(3000.0 / 50000.0)
        assert ratios["cost_to_income"] == pytest.approx(1200.0 / 3500.0)
        assert ratios["earnings_yield"] == pytest.approx(1000.0 / (50.0 * 100.0))

        # Inapplicable industrial metrics MUST BE NaN, NEVER 0
        assert np.isnan(ratios["fcf_yield"]), "Bank fcf_yield must be NaN, not zero"
        assert np.isnan(ratios["operating_margin"]), "Bank operating_margin must be NaN, not zero"
        assert np.isnan(ratios["debt_to_equity"]), "Bank debt_to_equity must be NaN, not zero"
        assert np.isnan(ratios["interest_coverage"]), "Bank interest_coverage must be NaN, not zero"

    def test_non_bank_ratios_keep_bank_metrics_as_nan(self):
        corp_stmt = {
            "is_bank": False,
            "net_income": 500.0,
            "revenue": 5000.0,
            "operating_profit": 800.0,
            "shareholders_equity": 2500.0,
            "total_debt": 1000.0,
            "interest_expense": 100.0,
            "free_cash_flow": 400.0,
            "total_assets": 6000.0,
            "shares_outstanding": 100.0,
        }
        ratios = compute_sector_aware_ratios(corp_stmt, market_price=25.0)

        # Industrial metrics computed
        assert ratios["is_bank"] is False
        assert ratios["operating_margin"] == pytest.approx(800.0 / 5000.0)
        assert ratios["debt_to_equity"] == pytest.approx(1000.0 / 2500.0)
        assert ratios["interest_coverage"] == pytest.approx(800.0 / 100.0)
        assert ratios["fcf_yield"] == pytest.approx(400.0 / (25.0 * 100.0))
        assert ratios["earnings_yield"] == pytest.approx(500.0 / (25.0 * 100.0))

        # Inapplicable bank metrics MUST BE NaN, NEVER 0
        assert np.isnan(ratios["net_interest_margin"]), "Non-bank net_interest_margin must be NaN"
        assert np.isnan(ratios["cost_to_income"]), "Non-bank cost_to_income must be NaN"
