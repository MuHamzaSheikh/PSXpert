"""FastAPI router exposing trained ML Technical & Fundamental Analysis endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.ml.service import MLAnalysisService, ModelUnavailableError

router = APIRouter(prefix="/api/analysis/ml", tags=["ML Analysis Models"])

_ml_service: Optional[MLAnalysisService] = None


def preload_ml_service_on_startup() -> MLAnalysisService:
    """Initialize global MLAnalysisService and load `.pkl` artifacts once at FastAPI startup."""
    global _ml_service
    if _ml_service is None:
        _ml_service = MLAnalysisService()
    _ml_service.preload_models()
    return _ml_service


def _get_ml_service() -> MLAnalysisService:
    global _ml_service
    if _ml_service is None:
        _ml_service = MLAnalysisService()
        _ml_service.preload_models()
    return _ml_service


def _run_safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except (FileNotFoundError, ModelUnavailableError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        msg = str(exc)
        status = 404 if "not found" in msg.lower() else 400
        raise HTTPException(status_code=status, detail=msg) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ML analysis error: {exc}") from exc


@router.get("/models/status")
def get_ml_models_status():
    """Return stored ML model artifact metadata, benchmark metrics, feature importances, and readiness report."""
    svc = _get_ml_service()
    return _run_safe(svc.get_models_status)


@router.get("/technical/{symbol}")
def get_ml_technical_analysis(
    symbol: str,
    as_of_date: Optional[str] = Query(default=None, description="Point-in-time cutoff date (YYYY-MM-DD)"),
    force_refresh: bool = Query(default=False, description="Force refresh rule-based DB cache"),
):
    """Return separate Rule-Based and ML-Based Technical assessments for `symbol`."""
    svc = _get_ml_service()
    return _run_safe(
        svc.get_technical_comparison,
        symbol,
        as_of_date=as_of_date,
        force_refresh=force_refresh,
    )


@router.get("/fundamental/{symbol}")
def get_ml_fundamental_analysis(
    symbol: str,
    as_of_date: Optional[str] = Query(default=None, description="Point-in-time cutoff date (YYYY-MM-DD)"),
    force_refresh: bool = Query(default=False, description="Force refresh rule-based DB cache"),
):
    """Return Rule-Based Fundamental assessment alongside Fundamental ML readiness/blocker report."""
    svc = _get_ml_service()
    return _run_safe(
        svc.get_fundamental_comparison,
        symbol,
        as_of_date=as_of_date,
        force_refresh=force_refresh,
    )


@router.get("/combined/{symbol}")
def get_ml_combined_analysis(
    symbol: str,
    as_of_date: Optional[str] = Query(default=None, description="Point-in-time cutoff date (YYYY-MM-DD)"),
    force_refresh: bool = Query(default=False, description="Force refresh rule-based DB cache"),
):
    """Return combined view keeping Rule-Based and ML-Based assessments clearly distinguished."""
    svc = _get_ml_service()
    return _run_safe(
        svc.get_combined_ml_analysis,
        symbol,
        as_of_date=as_of_date,
        force_refresh=force_refresh,
    )

