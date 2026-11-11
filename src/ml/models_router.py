"""FastAPI endpoints serving startup-loaded ML `.pkl` artifacts under /api/models/*."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.ml.router import _get_ml_service, _run_safe

router = APIRouter(prefix="/api/models", tags=["ML Prediction Models"])


class TechnicalPredictRequest(BaseModel):
    symbol: Optional[str] = Field(default=None, description="PSX stock symbol (e.g. OGDC) to score from live DB features")
    as_of_date: Optional[str] = Field(default=None, description="Point-in-time cutoff date (YYYY-MM-DD)")
    features: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional direct 74-feature vector dictionary for raw observation inference",
    )


class FundamentalPredictRequest(BaseModel):
    symbol: Optional[str] = Field(default=None, description="PSX stock symbol (e.g. MEBL)")
    as_of_date: Optional[str] = Field(default=None, description="Point-in-time cutoff date (YYYY-MM-DD)")
    features: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional 29-feature financial disclosure dictionary",
    )


@router.get("/status")
def get_models_deployment_status():
    """Report artifact existence, startup load state, model types, versions, training dates, and inference readiness."""
    svc = _get_ml_service()
    return _run_safe(svc.get_models_deployment_status)


@router.post("/technical/predict")
def predict_technical_condition(payload: TechnicalPredictRequest):
    """Run Technical ML inference using the startup-loaded `.pkl` pipeline without reloading per request."""
    svc = _get_ml_service()
    return _run_safe(
        svc.predict_technical_request,
        symbol=payload.symbol,
        as_of_date=payload.as_of_date,
        features=payload.features,
    )


@router.post("/fundamental/predict")
def predict_fundamental_health(payload: FundamentalPredictRequest):
    """Serve Fundamental ML prediction if valid `.pkl` is available, or return HTTP 503 with documented label blockers."""
    svc = _get_ml_service()
    return _run_safe(
        svc.predict_fundamental_request,
        symbol=payload.symbol,
        as_of_date=payload.as_of_date,
        features=payload.features,
    )

