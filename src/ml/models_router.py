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


class NewsImpactRequest(BaseModel):
    headline: str = Field(..., description="News headline text")
    summary: Optional[str] = Field(default="", description="News article body or summary snippet")
    published_at: Optional[str] = Field(default="", description="Publication timestamp or date")
    base_sentiment_score: Optional[float] = Field(default=0.0, description="FinBERT or base continuous sentiment in [-1.0, 1.0]")
    base_sentiment_label: Optional[str] = Field(default="Neutral", description="Sentiment label (Bullish, Bearish, Neutral)")
    base_confidence: Optional[float] = Field(default=0.5, description="Model confidence score in [0.0, 1.0]")


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


@router.post("/news/evaluate-impact")
def evaluate_stock_news_impact(payload: NewsImpactRequest):
    """
    Evaluates asymmetric multi-stock transmission of financial & macroeconomic news across PSX equities.
    Accounts for transmission sensitivities (e.g. oil up -> OGDC positive, PSO negative) and anti-leakage time alignment.
    """
    svc = _get_ml_service()
    return _run_safe(
        svc.evaluate_news_impact,
        headline=payload.headline,
        summary=payload.summary,
        published_at=payload.published_at,
        base_sentiment_score=payload.base_sentiment_score,
        base_sentiment_label=payload.base_sentiment_label,
        base_confidence=payload.base_confidence,
    )


@router.get("/ablation-matrix")
def get_multimodal_ablation_matrix():
    """
    Returns empirical out-of-sample benchmark comparison across 7 model configurations:
    Technical, Fundamental, News, and all combinations evaluated on identical test data.
    """
    svc = _get_ml_service()
    return _run_safe(svc.get_ablation_matrix)

