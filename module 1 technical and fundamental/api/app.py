"""Standalone FastAPI application and mountable Module 1 router."""

import os
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.exc import SQLAlchemyError

from m1.predict import predict_stock
from m1.settings import CLASSES
from m1.sources import DataUnavailable

Direction = Literal["BEARISH", "SIDEWAYS", "BULLISH"]
router = APIRouter(prefix="/api/module1", tags=["PSXpert Module 1"])


class Freshness(BaseModel):
    price_date: date
    price_age_calendar_days: int
    price_source: str
    price_origin: str | None
    period_end_date: date
    publication_date: date
    publication_timestamp: datetime | None
    available_from_timestamp: datetime
    fundamental_source: str
    filing_source: str
    missing_features: list[str]


class Contribution(BaseModel):
    feature: str
    group: Literal["technical", "fundamental"]
    contribution: float


class LocalExplanation(BaseModel):
    base_value: float
    output: float
    group_totals: dict[str, float]
    features: list[Contribution]


class Explanations(BaseModel):
    direction_output_scale: str
    return_output_scale: str
    direction_by_class: dict[Direction, LocalExplanation]
    expected_return: LocalExplanation


class Prediction(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    ticker: str
    prediction_horizon_trading_days: Literal[20]
    prediction_timestamp: datetime
    requested_as_of_timestamp: datetime
    model_training_cutoff: datetime
    predicted_direction: Direction
    direction_probabilities: dict[Direction, float]
    expected_return_pct: float
    technical_score: float | None = Field(ge=-100, le=100)
    fundamental_score: float | None
    model_version: str
    probabilities_calibrated: bool
    price_basis: str
    feature_freshness: Freshness
    feature_explanations: Explanations
    pypsx_crosscheck: dict | None
    data_limitations: list[str]
    disclaimer: str

    @model_validator(mode="after")
    def validate_predictions(self):
        values = self.direction_probabilities
        if (set(values) != set(CLASSES) or any(not 0 <= p <= 1 for p in values.values())
                or abs(sum(values.values()) - 1) > 1e-5):
            raise ValueError("Direction probabilities must form a three-class distribution")
        return self


@router.get("/predict/{ticker}", response_model=Prediction)
def predict(ticker: str, as_of_timestamp: datetime | None = None):
    try:
        result = predict_stock(
            ticker, as_of_timestamp,
            version=os.getenv("MODULE1_MODEL_VERSION", "combined_v1"),
            check_pypsx=os.getenv("MODULE1_CHECK_PYPSX") == "1",
        )
    except KeyError:
        raise HTTPException(404, "Unknown PSX ticker") from None
    except (ValueError, OverflowError) as exc:
        raise HTTPException(422, str(exc)) from None
    except DataUnavailable as exc:
        raise HTTPException(503, str(exc)) from None
    except SQLAlchemyError:
        raise HTTPException(503, "Read-only data source query failed") from None
    try:
        return Prediction.model_validate(result)
    except ValidationError:
        raise HTTPException(503, "Model output failed response validation") from None


app = FastAPI(title="PSXpert Module 1")
app.include_router(router)
