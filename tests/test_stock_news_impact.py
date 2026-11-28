"""
Unit Tests for PSXpert Stock-Specific News Impact Engine
Uses standard library unittest for 100% dependency-free verification.

Verifies:
1. Asymmetric macro transmission (Oil up -> OGDC positive, PSO/LUCK negative).
2. Interest rate transmission (Rate up -> HBL positive, DGKC negative).
3. Currency depreciation transmission (PKR down -> SYS positive, INDU negative).
4. Anti-leakage time alignment (after 16:00 PKT or weekend aligns to next trading session).
5. Direct corporate mention overrides/blends with macro themes.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.sentiment.stock_news_impact import StockNewsImpactEngine, SECTOR_TRANSMISSION_MATRIX


class TestStockNewsImpactEngine(unittest.TestCase):
    def setUp(self):
        self.calendar = [
            "2026-11-13",  # Friday
            "2026-11-16",  # Monday
            "2026-11-17",  # Tuesday
            "2026-11-18",  # Wednesday
            "2026-11-19",  # Thursday
            "2026-11-20",  # Friday
        ]
        self.engine = StockNewsImpactEngine(trading_calendar=self.calendar)

    def test_oil_price_surge_asymmetric_impact(self):
        """
        Crude oil price surge must positively affect upstream E&P (OGDC, PPL)
        and negatively affect OMCs (PSO) and energy-intensive manufacturing (LUCK).
        """
        article = {
            "headline": "Crude oil surges 6% as Middle East conflict escalates supply fears",
            "summary": "Brent crude climbed past $87 per barrel in international trading.",
            "published_at": "2026-11-16 08:00:00",
            "base_sentiment_score": 0.80,
            "base_sentiment_label": "Bullish",
            "base_confidence": 0.85
        }
        res = self.engine.evaluate_article_impact(**article)
        impacts = res["stock_impacts"]

        self.assertIn("OGDC", impacts, "OGDC must be impacted by oil surge")
        self.assertIn("PSO", impacts, "PSO must be impacted by oil surge")
        self.assertIn("LUCK", impacts, "LUCK must be impacted by oil surge")

        # Upstream must be positive
        self.assertGreater(impacts["OGDC"]["impact_score"], 0, "OGDC impact must be positive")
        self.assertEqual(impacts["OGDC"]["impact_type"], "BULLISH_TAILWIND")

        # OMC and Cement must be negative
        self.assertLess(impacts["PSO"]["impact_score"], 0, "PSO impact must be negative on oil surge")
        self.assertEqual(impacts["PSO"]["impact_type"], "BEARISH_HEADWIND")

        self.assertLess(impacts["LUCK"]["impact_score"], 0, "LUCK impact must be negative on oil surge")
        self.assertEqual(impacts["LUCK"]["impact_type"], "BEARISH_HEADWIND")

    def test_interest_rate_hike_asymmetric_impact(self):
        """
        Monetary tightening / rate hike must expand bank NIMs (HBL, MCB positive)
        and increase borrowing finance costs for leveraged cyclicals (DGKC negative).
        """
        article = {
            "headline": "State Bank hikes policy rate by 150 bps to 22 percent",
            "summary": "Monetary Policy Committee moves decisively against headline inflation.",
            "published_at": "2026-11-16 08:30:00",
            "base_sentiment_score": -0.65,
            "base_sentiment_label": "Bearish",
            "base_confidence": 0.90
        }
        res = self.engine.evaluate_article_impact(**article)
        impacts = res["stock_impacts"]

        self.assertIn("HBL", impacts, "HBL must be impacted by rate hike")
        self.assertIn("DGKC", impacts, "DGKC must be impacted by rate hike")

        # Bank must benefit from asset yield expansion
        self.assertGreater(impacts["HBL"]["impact_score"], 0, "HBL impact must be positive on rate hike")
        self.assertEqual(impacts["HBL"]["impact_type"], "BULLISH_TAILWIND")

        # Highly leveraged industrial must suffer from finance costs
        self.assertLess(impacts["DGKC"]["impact_score"], 0, "DGKC impact must be negative on rate hike")
        self.assertEqual(impacts["DGKC"]["impact_type"], "BEARISH_HEADWIND")

    def test_pkr_depreciation_asymmetric_impact(self):
        """
        PKR currency depreciation must benefit export software houses (SYS positive)
        and hurt import-dependent auto assemblers (INDU negative).
        """
        article = {
            "headline": "Pakistani rupee plunges to historic low against US dollar in interbank",
            "summary": "Persistent trade deficit drives heavy rupee devaluation.",
            "published_at": "2026-11-16 08:45:00",
            "base_sentiment_score": -0.75,
            "base_sentiment_label": "Bearish",
            "base_confidence": 0.88
        }
        res = self.engine.evaluate_article_impact(**article)
        impacts = res["stock_impacts"]

        self.assertIn("SYS", impacts, "SYS must be impacted by PKR devaluation")
        self.assertIn("INDU", impacts, "INDU must be impacted by PKR devaluation")

        # Exporter earns USD -> positive
        self.assertGreater(impacts["SYS"]["impact_score"], 0, "SYS impact must be positive on PKR drop")
        self.assertEqual(impacts["SYS"]["impact_type"], "BULLISH_TAILWIND")

        # Auto assembler imports CKD kits -> negative
        self.assertLess(impacts["INDU"]["impact_score"], 0, "INDU impact must be negative on PKR drop")
        self.assertEqual(impacts["INDU"]["impact_type"], "BEARISH_HEADWIND")

    def test_anti_leakage_timestamp_alignment(self):
        """
        Verifies that news published after market close (16:00 PKT) or on weekends
        is strictly mapped to the subsequent valid exchange trading session.
        """
        # 1. Friday after market close (17:30 PKT) -> must map to Monday (2026-11-16)
        align_fri_night = self.engine.align_timestamp_to_session("2026-11-13 17:30:00")
        self.assertEqual(align_fri_night, "2026-11-16", f"Expected 2026-11-16 but got {align_fri_night}")

        # 2. Sunday afternoon (14:00 PKT) -> must map to Monday (2026-11-16)
        align_sun = self.engine.align_timestamp_to_session("2026-11-15 14:00:00")
        self.assertEqual(align_sun, "2026-11-16", f"Expected 2026-11-16 but got {align_sun}")

        # 3. Monday pre-market (08:00 PKT) -> valid for Monday (2026-11-16)
        align_mon_early = self.engine.align_timestamp_to_session("2026-11-16 08:00:00")
        self.assertEqual(align_mon_early, "2026-11-16", f"Expected 2026-11-16 but got {align_mon_early}")

        # 4. Monday intraday (11:30 PKT) -> must map to Tuesday (2026-11-17) to prevent forward leakage
        align_mon_intraday = self.engine.align_timestamp_to_session("2026-11-16 11:30:00")
        self.assertEqual(align_mon_intraday, "2026-11-17", f"Expected 2026-11-17 but got {align_mon_intraday}")

    def test_direct_company_mention_priority(self):
        """
        When an article directly names a company, it receives high direct sentiment weight.
        """
        article = {
            "headline": "Systems Limited wins $50 million global digital transformation contract",
            "summary": "IT giant reports record pipeline expansion across GCC markets.",
            "published_at": "2026-11-16 08:15:00",
            "base_sentiment_score": 0.90,
            "base_sentiment_label": "Bullish",
            "base_confidence": 0.95
        }
        res = self.engine.evaluate_article_impact(**article)
        impacts = res["stock_impacts"]

        self.assertIn("SYS", impacts)
        sys_imp = impacts["SYS"]
        self.assertTrue(sys_imp["is_direct_mention"])
        self.assertGreaterEqual(sys_imp["impact_score"], 0.85)
        self.assertEqual(sys_imp["impact_type"], "BULLISH_TAILWIND")


if __name__ == "__main__":
    unittest.main()
