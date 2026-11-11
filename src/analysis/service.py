"""Unified Analysis Service coordinating Technical, Fundamental, and Combined analysis with DB caching."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy.engine import Engine

from src.analysis.common import resolve_effective_as_of_date, safe_float, sanitize_for_json
from src.analysis.fundamental_engine import FundamentalAnalysisEngine
from src.analysis.persistence import (
    compute_source_fingerprint,
    get_cached_analysis,
    save_analysis_result,
)
from src.analysis.technical_engine import TechnicalAnalysisEngine
from src.database.connection import get_engine


class AnalysisService:
    """
    Facade coordinating independent Technical and Fundamental engines with
    deterministic source-fingerprint caching inside PostgreSQL `analysis_results`.
    """

    def __init__(self, engine: Optional[Engine] = None) -> None:
        self.engine = engine or get_engine()
        self.technical_engine = TechnicalAnalysisEngine()
        self.fundamental_engine = FundamentalAnalysisEngine()

    def get_technical_analysis(
        self,
        symbol: str,
        *,
        as_of_date: Optional[date | datetime | str] = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Run or serve cached point-in-time Technical Analysis for `symbol`."""
        sym = symbol.strip().upper()
        with self.engine.begin() as conn:
            _, mkt_cutoff = resolve_effective_as_of_date(conn, sym, as_of_date)
            fp = compute_source_fingerprint(conn, sym, "TECHNICAL", mkt_cutoff)

            if not force_refresh:
                cached = get_cached_analysis(conn, sym, "TECHNICAL", mkt_cutoff, fp)
                if cached is not None:
                    return cached

            result = self.technical_engine.analyze(conn, sym, as_of_date=mkt_cutoff)
            return save_analysis_result(
                conn=conn,
                symbol=sym,
                analysis_type="TECHNICAL",
                as_of_date=mkt_cutoff,
                data_cutoff_timestamp=result["data_cutoff_timestamp"],
                source_fingerprint=fp,
                overall_assessment=result.get("overall_assessment"),
                score=safe_float(result.get("technical_score")),
                payload=result,
                data_source_references=result.get("data_source_references") or {},
            )

    def get_fundamental_analysis(
        self,
        symbol: str,
        *,
        as_of_date: Optional[date | datetime | str] = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Run or serve cached point-in-time Fundamental Analysis for `symbol`."""
        sym = symbol.strip().upper()
        with self.engine.begin() as conn:
            _, mkt_cutoff = resolve_effective_as_of_date(conn, sym, as_of_date)
            fp = compute_source_fingerprint(conn, sym, "FUNDAMENTAL", mkt_cutoff)

            if not force_refresh:
                cached = get_cached_analysis(conn, sym, "FUNDAMENTAL", mkt_cutoff, fp)
                if cached is not None:
                    return cached

            result = self.fundamental_engine.analyze(conn, sym, as_of_date=mkt_cutoff)
            return save_analysis_result(
                conn=conn,
                symbol=sym,
                analysis_type="FUNDAMENTAL",
                as_of_date=mkt_cutoff,
                data_cutoff_timestamp=result["data_cutoff_timestamp"],
                source_fingerprint=fp,
                overall_assessment=result.get("overall_assessment"),
                score=safe_float(result.get("fundamental_score")),
                payload=result,
                data_source_references=result.get("data_source_references") or {},
            )

    def get_combined_analysis(
        self,
        symbol: str,
        *,
        as_of_date: Optional[date | datetime | str] = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Run or serve cached Combined (Technical + Fundamental) analysis keeping pillars independent."""
        sym = symbol.strip().upper()
        with self.engine.begin() as conn:
            _, mkt_cutoff = resolve_effective_as_of_date(conn, sym, as_of_date)
            fp = compute_source_fingerprint(conn, sym, "COMBINED", mkt_cutoff)

            if not force_refresh:
                cached = get_cached_analysis(conn, sym, "COMBINED", mkt_cutoff, fp)
                if cached is not None:
                    return cached

        # Reuse cached/computed sub-engines cleanly
        tech = self.get_technical_analysis(sym, as_of_date=mkt_cutoff, force_refresh=force_refresh)
        fund = self.get_fundamental_analysis(sym, as_of_date=mkt_cutoff, force_refresh=force_refresh)

        tech_clean = {k: v for k, v in tech.items() if k != "cache"}
        fund_clean = {k: v for k, v in fund.items() if k != "cache"}

        cross_alignment = self._summarize_cross_alignment(tech_clean, fund_clean)
        combined_payload = sanitize_for_json(
            {
                "symbol": sym,
                "company_name": tech_clean.get("company_name") or fund_clean.get("company_name"),
                "sector": tech_clean.get("sector") or fund_clean.get("sector"),
                "sector_category": tech_clean.get("sector_category") or fund_clean.get("sector_category"),
                "analysis_type": "COMBINED",
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                "as_of_date": mkt_cutoff.isoformat(),
                "data_cutoff_timestamp": max(
                    str(tech_clean.get("data_cutoff_timestamp", "")),
                    str(fund_clean.get("data_cutoff_timestamp", "")),
                ),
                "cross_engine_alignment": cross_alignment,
                "technical_analysis": tech_clean,
                "fundamental_analysis": fund_clean,
                "data_source_references": {
                    "technical": tech_clean.get("data_source_references"),
                    "fundamental": fund_clean.get("data_source_references"),
                },
            }
        )

        with self.engine.begin() as conn:
            return save_analysis_result(
                conn=conn,
                symbol=sym,
                analysis_type="COMBINED",
                as_of_date=mkt_cutoff,
                data_cutoff_timestamp=combined_payload["data_cutoff_timestamp"],
                source_fingerprint=fp,
                overall_assessment=cross_alignment.get("alignment_label"),
                score=safe_float(tech_clean.get("technical_score")),
                payload=combined_payload,
                data_source_references=combined_payload.get("data_source_references") or {},
            )

    @staticmethod
    def _summarize_cross_alignment(tech: dict[str, Any], fund: dict[str, Any]) -> dict[str, Any]:
        t_assess = tech.get("overall_assessment", "INSUFFICIENT_DATA")
        f_assess = fund.get("overall_assessment", "INSUFFICIENT_FUNDAMENTAL_DATA")
        t_score = tech.get("technical_score")
        f_score = fund.get("fundamental_score")

        t_pos = t_assess in ("BULLISH", "STRONG_BULLISH")
        t_neg = t_assess in ("BEARISH", "STRONG_BEARISH")
        f_pos = f_assess in ("STRONG", "CONSTRUCTIVE")
        f_neg = f_assess in ("WEAK",)

        if f_score is None or t_score is None:
            label = "PARTIAL_COVERAGE"
            note = "One engine lacked sufficient underlying disclosures or price history; evaluate available pillar independently."
        elif t_pos and f_pos:
            label = "BULLISH_ALIGNED"
            note = f"Both technical ({t_assess}, {t_score:+.1f}/100) and fundamental ({f_assess}, {f_score:.1f}/100) assessments are constructive."
        elif t_neg and f_neg:
            label = "BEARISH_ALIGNED"
            note = f"Both technical ({t_assess}, {t_score:+.1f}/100) and fundamental ({f_assess}, {f_score:.1f}/100) pillars indicate weakness."
        elif t_pos and f_neg:
            label = "DIVERGENT_TECH_OVER_FUND"
            note = "Price technicals are bullish despite weaker underlying IFRS fundamentals."
        elif t_neg and f_pos:
            label = "DIVERGENT_FUND_OVER_TECH"
            note = "Constructive fundamental profile contrasts with bearish technical momentum."
        else:
            label = "MIXED_OR_NEUTRAL"
            note = f"Mixed/neutral signal combination: Technical={t_assess}, Fundamental={f_assess}."

        return {
            "alignment_label": label,
            "technical_assessment": t_assess,
            "technical_score": t_score,
            "fundamental_assessment": f_assess,
            "fundamental_score": f_score,
            "note": note,
        }

