"""Service coordinating rule-based engines and trained ML analysis models cleanly side-by-side."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy.engine import Engine

from src.analysis.common import resolve_effective_as_of_date, sanitize_for_json
from src.analysis.service import AnalysisService
from src.database.connection import get_engine
from src.ml.fundamental_ml import FundamentalMLAdvisor
from src.ml.technical_ml import TechnicalMLPredictor


class ModelUnavailableError(RuntimeError):
    """Raised when a model artifact is missing, corrupted, or blocked from inference."""


class MLAnalysisService:
    """
    Combines independent rule-based engines (TechnicalAnalysisEngine, FundamentalAnalysisEngine)
    with ML model outputs without silently overwriting rule-based scores.
    """

    def __init__(self, engine: Optional[Engine] = None) -> None:
        self.engine = engine or get_engine()
        self.rule_service = AnalysisService(engine=self.engine)
        self.tech_predictor = TechnicalMLPredictor()
        self.fund_advisor = FundamentalMLAdvisor()
        self._startup_loaded: bool = False

    def preload_models(self) -> dict[str, Any]:
        """Load persisted model artifacts once during FastAPI application startup."""
        tech_ok = self.tech_predictor.preload(verify_checksum=True)
        fund_ok = self.fund_advisor.preload()
        self._startup_loaded = True
        return {"technical": tech_ok, "fundamental": fund_ok}

    def get_models_status(self) -> dict[str, Any]:
        """Return model artifact inventory, training metadata, benchmarks, and blocker audit."""
        return sanitize_for_json(
            {
                "technical_ml_model": self.tech_predictor.get_status_summary(),
                "fundamental_ml_model": self.fund_advisor.get_readiness_report(),
            }
        )

    def get_models_deployment_status(self) -> dict[str, Any]:
        """Return Section 6 deployment readiness summary for GET /api/models/status."""
        tech_st = self.tech_predictor.get_status_summary()
        fund_st = self.fund_advisor.get_status_summary()
        return sanitize_for_json(
            {
                "status": "PARTIAL" if tech_st.get("ready_for_inference") and not fund_st.get("ready_for_inference") else (
                    "READY" if tech_st.get("ready_for_inference") and fund_st.get("ready_for_inference") else "DEGRADED"
                ),
                "loaded_on_startup": self._startup_loaded,
                "technical": {
                    "artifact_exists": bool(tech_st.get("artifact_exists")),
                    "loaded_successfully": bool(tech_st.get("loaded_successfully")),
                    "model_type": tech_st.get("model_type"),
                    "version": tech_st.get("version"),
                    "training_date": tech_st.get("trained_at"),
                    "ready_for_inference": bool(tech_st.get("ready_for_inference")),
                    "feature_count": tech_st.get("feature_count"),
                    "classes": tech_st.get("classes"),
                    "status": tech_st.get("status"),
                    "error": tech_st.get("error"),
                },
                "fundamental": {
                    "artifact_exists": bool(fund_st.get("artifact_exists")),
                    "loaded_successfully": bool(fund_st.get("loaded_successfully")),
                    "model_type": fund_st.get("model_type"),
                    "version": fund_st.get("version"),
                    "training_date": fund_st.get("trained_at"),
                    "ready_for_inference": bool(fund_st.get("ready_for_inference")),
                    "feature_count": fund_st.get("feature_count"),
                    "classes": fund_st.get("classes"),
                    "status": fund_st.get("status"),
                    "blocking_reasons": fund_st.get("blocking_reasons", []),
                    "error": fund_st.get("error"),
                },
            }
        )

    def predict_technical_request(
        self,
        *,
        symbol: Optional[str] = None,
        as_of_date: Optional[date | datetime | str] = None,
        features: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Run Technical ML inference reusing startup-loaded `.pkl` artifacts."""
        if not self.tech_predictor.is_available():
            raise ModelUnavailableError(
                self.tech_predictor._load_error or "Technical ML artifact (.pkl) is missing."
            )
        if self.tech_predictor._bundle is None:
            ok = self.tech_predictor.preload(verify_checksum=True)
            if not ok:
                raise ModelUnavailableError(
                    self.tech_predictor._load_error or "Technical ML artifact failed loading."
                )

        if features is not None:
            out = self.tech_predictor.predict_from_features(features)
        elif symbol and symbol.strip():
            with self.engine.connect() as conn:
                out = self.tech_predictor.predict_for_symbol(conn, symbol, as_of_date=as_of_date)
        else:
            raise ValueError("Provide either 'symbol' or a complete 'features' dictionary.")

        out["loaded_from_startup_cache"] = bool(self._startup_loaded)
        out["artifact_load_count"] = int(self.tech_predictor._load_count)
        return sanitize_for_json(out)

    def predict_fundamental_request(
        self,
        *,
        symbol: Optional[str] = None,
        as_of_date: Optional[date | datetime | str] = None,
        features: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Serve Fundamental ML prediction if valid `.pkl` is exported, or raise 503 with honest blocker details."""
        if not self.fund_advisor.is_model_artifact_present():
            rep = self.fund_advisor.get_readiness_report()
            raise ModelUnavailableError(
                "Fundamental ML model (.pkl) is NOT deployed ("
                + str(rep.get("training_status", "BLOCKED_INSUFFICIENT_RELIABLE_LABELS"))
                + "): "
                + "; ".join(rep.get("blocking_reasons", [])[:3])
            )
        if self.fund_advisor._model is None:
            if not self.fund_advisor.preload():
                raise ModelUnavailableError(
                    f"Fundamental ML model artifact exists but failed to load safely: {self.fund_advisor._load_error}"
                )
        raise ModelUnavailableError("Fundamental ML prediction requires an approved trained model schema.")

    def get_technical_comparison(
        self,
        symbol: str,
        *,
        as_of_date: Optional[date | datetime | str] = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Return separate rule-based Technical assessment and ML-based Technical prediction."""
        sym = symbol.strip().upper()
        rule_tech = self.rule_service.get_technical_analysis(
            sym, as_of_date=as_of_date, force_refresh=force_refresh
        )
        if self.tech_predictor._bundle is None:
            if not self.tech_predictor.preload(verify_checksum=True):
                raise ModelUnavailableError(
                    self.tech_predictor._load_error or "Technical ML model artifact unavailable."
                )
        with self.engine.connect() as conn:
            ml_tech = self.tech_predictor.predict_for_symbol(conn, sym, as_of_date=as_of_date)

        agreement = self._compare_technical(rule_tech, ml_tech)
        return sanitize_for_json(
            {
                "symbol": sym,
                "company_name": rule_tech.get("company_name"),
                "sector": rule_tech.get("sector"),
                "as_of_date": rule_tech.get("as_of_date"),
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                "rule_vs_ml_comparison": agreement,
                "rule_based_technical_assessment": rule_tech,
                "ml_based_technical_assessment": ml_tech,
            }
        )

    def get_fundamental_comparison(
        self,
        symbol: str,
        *,
        as_of_date: Optional[date | datetime | str] = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Return rule-based Fundamental assessment alongside Fundamental ML readiness/blocker report."""
        sym = symbol.strip().upper()
        rule_fund = self.rule_service.get_fundamental_analysis(
            sym, as_of_date=as_of_date, force_refresh=force_refresh
        )
        ml_fund = self.fund_advisor.assess_symbol(rule_fund)
        return sanitize_for_json(
            {
                "symbol": sym,
                "company_name": rule_fund.get("company_name"),
                "sector": rule_fund.get("sector"),
                "as_of_date": rule_fund.get("as_of_date"),
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                "rule_based_fundamental_assessment": rule_fund,
                "ml_based_fundamental_assessment": ml_fund,
            }
        )

    def get_combined_ml_analysis(
        self,
        symbol: str,
        *,
        as_of_date: Optional[date | datetime | str] = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Return combined view keeping rule-based and ML assessments strictly separated."""
        sym = symbol.strip().upper()
        rule_combined = self.rule_service.get_combined_analysis(
            sym, as_of_date=as_of_date, force_refresh=force_refresh
        )
        rule_tech = rule_combined["technical_analysis"]
        rule_fund = rule_combined["fundamental_analysis"]

        with self.engine.connect() as conn:
            _, mkt_cutoff = resolve_effective_as_of_date(conn, sym, as_of_date)
            ml_tech = self.tech_predictor.predict_for_symbol(conn, sym, as_of_date=mkt_cutoff)
        ml_fund = self.fund_advisor.assess_symbol(rule_fund)

        return sanitize_for_json(
            {
                "symbol": sym,
                "company_name": rule_combined.get("company_name"),
                "sector": rule_combined.get("sector"),
                "sector_category": rule_combined.get("sector_category"),
                "as_of_date": rule_combined.get("as_of_date"),
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                "rule_based_combined_alignment": rule_combined.get("cross_engine_alignment"),
                "rule_vs_ml_technical_comparison": self._compare_technical(rule_tech, ml_tech),
                "rule_based_technical_assessment": rule_tech,
                "ml_based_technical_assessment": ml_tech,
                "rule_based_fundamental_assessment": rule_fund,
                "ml_based_fundamental_assessment": ml_fund,
            }
        )

    @staticmethod
    def _compare_technical(rule_tech: dict[str, Any], ml_tech: dict[str, Any]) -> dict[str, Any]:
        r_raw = str(rule_tech.get("overall_assessment", "INSUFFICIENT_DATA")).upper()
        m_cls = ml_tech.get("predicted_condition")
        if m_cls is None:
            return {
                "status": "ML_UNAVAILABLE",
                "rule_direction": r_raw,
                "ml_direction": None,
                "agree": None,
                "note": ml_tech.get("note", "ML prediction unavailable."),
            }

        if "BULLISH" in r_raw:
            r_bucket = "Bullish"
        elif "BEARISH" in r_raw:
            r_bucket = "Bearish"
        else:
            r_bucket = "Neutral"

        agree = r_bucket == m_cls
        note = (
            f"Rule engine ({r_raw} -> {r_bucket}) and ML classifier ({m_cls}, conf {ml_tech.get('confidence')}) AGREE."
            if agree
            else f"Divergence: Rule engine signals {r_raw} ({rule_tech.get('technical_score')}), whereas ML classifies trailing structural condition as {m_cls} (conf {ml_tech.get('confidence')})."
        )
        return {
            "status": "COMPARED",
            "rule_direction": r_bucket,
            "rule_raw_assessment": r_raw,
            "rule_score": rule_tech.get("technical_score"),
            "ml_direction": m_cls,
            "ml_confidence": ml_tech.get("confidence"),
            "ml_conviction_tier": ml_tech.get("conviction_tier"),
            "ml_is_actionable": ml_tech.get("is_actionable"),
            "ml_selective_action": ml_tech.get("selective_action"),
            "ml_expected_win_rate_pct": ml_tech.get("historical_expected_win_rate_pct"),
            "agree": agree,
            "note": note,
        }

