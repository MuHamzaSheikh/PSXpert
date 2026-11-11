"""FastAPI router exposing independent and combined PSX analysis endpoints."""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query

from src.analysis.service import AnalysisService

router = APIRouter(prefix="/api/analysis", tags=["Analysis Engines"])

_service: Optional[AnalysisService] = None


def _get_service() -> AnalysisService:
    global _service
    if _service is None:
        _service = AnalysisService()
    return _service


def _run_with_error_mapping(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ValueError as exc:
        msg = str(exc)
        status = 404 if "not found" in msg.lower() else 400
        raise HTTPException(status_code=status, detail=msg) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis engine failure: {exc}") from exc


@router.get("/technical/{symbol}")
def get_technical_analysis(
    symbol: str,
    as_of_date: Optional[str] = Query(default=None, description="Point-in-time cutoff date (YYYY-MM-DD)"),
    force_refresh: bool = Query(default=False, description="Bypass DB cache and force fresh computation"),
):
    """Run or fetch cached causal Technical Analysis for a PSX stock."""
    svc = _get_service()
    return _run_with_error_mapping(
        svc.get_technical_analysis,
        symbol,
        as_of_date=as_of_date,
        force_refresh=force_refresh,
    )


@router.get("/fundamental/{symbol}")
def get_fundamental_analysis(
    symbol: str,
    as_of_date: Optional[str] = Query(default=None, description="Point-in-time cutoff date (YYYY-MM-DD)"),
    force_refresh: bool = Query(default=False, description="Bypass DB cache and force fresh computation"),
):
    """Run or fetch cached point-in-time Fundamental Analysis for a PSX stock."""
    svc = _get_service()
    return _run_with_error_mapping(
        svc.get_fundamental_analysis,
        symbol,
        as_of_date=as_of_date,
        force_refresh=force_refresh,
    )


@router.get("/combined/{symbol}")
def get_combined_analysis(
    symbol: str,
    as_of_date: Optional[str] = Query(default=None, description="Point-in-time cutoff date (YYYY-MM-DD)"),
    force_refresh: bool = Query(default=False, description="Bypass DB cache and force fresh computation"),
):
    """Run or fetch cached Technical + Fundamental analysis for a PSX stock."""
    svc = _get_service()
    return _run_with_error_mapping(
        svc.get_combined_analysis,
        symbol,
        as_of_date=as_of_date,
        force_refresh=force_refresh,
    )


@router.get("/{symbol}")
def get_selected_analysis(
    symbol: str,
    mode: Literal["technical", "fundamental", "both"] = Query(
        default="both",
        description="Select 'technical', 'fundamental', or 'both'",
    ),
    as_of_date: Optional[str] = Query(default=None, description="Point-in-time cutoff date (YYYY-MM-DD)"),
    force_refresh: bool = Query(default=False, description="Bypass DB cache and force fresh computation"),
):
    """Unified endpoint allowing selection of Technical only, Fundamental only, or Both together."""
    svc = _get_service()
    if mode == "technical":
        return _run_with_error_mapping(svc.get_technical_analysis, symbol, as_of_date=as_of_date, force_refresh=force_refresh)
    if mode == "fundamental":
        return _run_with_error_mapping(svc.get_fundamental_analysis, symbol, as_of_date=as_of_date, force_refresh=force_refresh)
    return _run_with_error_mapping(svc.get_combined_analysis, symbol, as_of_date=as_of_date, force_refresh=force_refresh)

