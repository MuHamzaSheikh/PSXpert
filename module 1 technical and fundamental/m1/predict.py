"""Inference from a frozen artifact and the shared point-in-time feature pipeline."""

import json
import logging

import pandas as pd
from .sources import ticker as normalize_ticker

from .explain import explain_prediction
from .features import FUNDAMENTAL, as_of, build_dataset, statement_panel
from .settings import CLASSES, PRICE_BASIS, ROOT, Settings
from .sources import DataUnavailable, compare_prices, database, fetch_pypsx, read_sources
from .training import load_models, probability, write_json

LOGGER = logging.getLogger(__name__)


def independent_scores(connection, symbol, cutoff, statements, announcements):
    from sqlalchemy.exc import SQLAlchemyError

    from src.analysis.fundamental_engine import FundamentalAnalysisEngine
    from src.analysis.technical_engine import TechnicalAnalysisEngine

    class VerifiedFundamentalEngine(FundamentalAnalysisEngine):
        def _load_pit_statements_for_symbols(self, conn, symbols, date):
            sources = read_sources(conn, cutoff=date)
            panel, _ = statement_panel(sources[3], sources[4])
            end = pd.Timestamp(date, tz=cutoff.tz) + pd.Timedelta(days=1)
            return {key: sorted((p for p in panel.get(key, []) if p["available_from_timestamp"] < end),
                                key=lambda p: p["period_end_date"])
                    for key in symbols}

    engines = {"technical_score": TechnicalAnalysisEngine(), "fundamental_score": VerifiedFundamentalEngine()}
    score, notes = {}, []
    for name, engine in engines.items():
        if name == "fundamental_score" and not statement_panel(statements, announcements)[0]:
            score[name] = None
        else:
            try:
                score[name] = engine.analyze(connection, symbol, as_of_date=cutoff.date()).get(name)
            except (SQLAlchemyError, TypeError, KeyError, IndexError, ValueError, RuntimeError, NotImplementedError) as exc:
                LOGGER.info("%s unavailable (%s)", name, type(exc).__name__)
                score[name] = None
        if score[name] is None:
            notes.append(f"The independent {name.replace('_', ' ')} is unavailable.")
    return score, notes


def score_path(symbol, signal):
    return ROOT / "artifacts" / "scores" / symbol / f"{signal['trading_date'].date()}.json"


def prepare_scores(symbol, as_of_timestamp=None):
    symbol = normalize_ticker(symbol)
    cutoff = as_of(as_of_timestamp)
    if cutoff > as_of():
        raise ValueError("as_of_timestamp must be in the past or present")
    with database() as connection:
        sources = read_sources(connection, symbol, cutoff.date())
        data, _ = build_dataset(sources, cutoff, labels=False)
        signal = data.iloc[-1]
        scores, notes = independent_scores(connection, symbol, signal["prediction_timestamp"], sources[3], sources[4])
    path = score_path(symbol, signal)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ticker": symbol, "prediction_timestamp": signal["prediction_timestamp"],
               "close": float(signal["close"]), "origin": text_value(signal["origin"]),
               "scores": scores, "notes": notes}
    write_json(path, payload)
    return payload


def stored_scores(symbol, signal):
    try:
        with score_path(symbol, signal).open(encoding="utf-8") as file:
            payload = json.load(file)
        if (payload["close"] == float(signal["close"]) and payload["origin"] == text_value(signal["origin"])
                and as_of(payload["prediction_timestamp"]) == signal["prediction_timestamp"]):
            return payload["scores"], payload["notes"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return {"technical_score": None, "fundamental_score": None}, [
        "Independent rule scores have not been prepared for this price snapshot."
    ]


def predict_stock(ticker, as_of_timestamp=None, *, version="combined_v1", check_pypsx=False):
    symbol = normalize_ticker(ticker)
    cutoff = as_of(as_of_timestamp)
    if cutoff > as_of():
        raise ValueError("as_of_timestamp must be in the past or present")
    with database() as connection:
        sources = read_sources(connection, symbol, cutoff.date())
        classifier, regressor, metadata = load_models(version)
        trained_until = as_of(metadata["model_training_cutoff"])
        settings = Settings(**metadata["training_configuration"])
        data, _ = build_dataset(sources, cutoff, settings, labels=False)
        latest = data.tail(1)
        signal = latest.iloc[0]
        if signal["prediction_timestamp"] <= trained_until:
            raise DataUnavailable("No completed prediction session after the artifact training and calibration cutoff")
        if pd.isna(signal["momentum_20_pct"]):
            raise DataUnavailable("Ticker has insufficient warmed technical history")
        if latest[FUNDAMENTAL].isna().all(axis=None):
            raise DataUnavailable("Ticker has no eligible current fundamental ratios")
        notes = [
            "Prices are unadjusted. Unverified splits or price errors can affect returns.",
            "End-of-day signals use the latest completed database price date.",
            "Date-only annual reports are eligible from the next Pakistan calendar day.",
            "Statement snapshots do not provide a complete restatement or revision history.",
        ]
        scores, score_notes = stored_scores(symbol, signal)
        notes.extend(score_notes)

    crosscheck = None
    if check_pypsx:
        start = signal["trading_date"] - pd.Timedelta(days=45)
        try:
            secondary = fetch_pypsx(symbol, start, cutoff.date())
            crosscheck, _ = compare_prices(sources[0], secondary)
            if crosscheck["conflict_rows"] or crosscheck["pypsx_duplicate_rows"]:
                notes.append("pyPSX disagreed with database prices or returned duplicate keys. Database data supplied the forecast.")
        except DataUnavailable as exc:
            notes.append(str(exc))

    features = latest[metadata["features"]]
    probabilities = probability(classifier, features, metadata["calibration"])[0]
    price_age = (cutoff.date() - signal["trading_date"].date()).days
    if price_age > 5:
        notes.append("The last completed ticker close is more than five calendar days old.")
    if metadata["calibration"] is None:
        notes.append("Validation class coverage was insufficient for probability recalibration.")
    return {
        "ticker": symbol,
        "prediction_horizon_trading_days": settings.horizon,
        "prediction_timestamp": signal["prediction_timestamp"],
        "requested_as_of_timestamp": cutoff,
        "model_training_cutoff": trained_until,
        "predicted_direction": CLASSES[int(probabilities.argmax())],
        "direction_probabilities": {name: float(probabilities[i]) for i, name in enumerate(CLASSES)},
        "expected_return_pct": float(regressor.predict(features)[0]),
        **scores,
        "model_version": version,
        "probabilities_calibrated": metadata["calibration"] is not None,
        "price_basis": PRICE_BASIS,
        "feature_freshness": {
            "price_date": signal["trading_date"].date(), "price_age_calendar_days": price_age,
            "price_source": signal["price_source"], "price_origin": text_value(signal["origin"]),
            "period_end_date": signal["period_end_date"],
            "publication_date": signal["publication_date"],
            "publication_timestamp": text_value(signal["publication_timestamp"]),
            "available_from_timestamp": signal["available_from_timestamp"],
            "fundamental_source": signal["fundamental_source"], "filing_source": signal["filing_source"],
            "missing_features": [name for name in features if features[name].isna().iat[0]],
        },
        "feature_explanations": explain_prediction(classifier, regressor, features),
        "pypsx_crosscheck": crosscheck,
        "data_limitations": notes,
        "disclaimer": "Decision-support forecast; not guaranteed financial advice.",
    }


def text_value(value):
    return None if pd.isna(value) else value
