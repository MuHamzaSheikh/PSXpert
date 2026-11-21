from contextlib import contextmanager

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api import app as api_module
from m1 import predict
from m1.backtest import simulate
from m1.evaluation import temporal_splits
from m1.explain import contribution_arrays
from m1.features import research_rows
from m1.settings import Settings
from m1.sources import DataUnavailable
from m1.training import load_models, probability, train_all


def test_purging_is_market_wide_and_final_test_is_held_out(fixtures):
    _, _, data, _ = fixtures
    eligible = research_rows(data)
    folds, test = temporal_splits(eligible, 5)
    for train, valid in folds:
        assert train["target_timestamp"].max() < valid["prediction_timestamp"].min()
        assert valid["target_timestamp"].max() < test["prediction_timestamp"].min()
        assert train["session"].max() < valid["session"].min() - 20
    assert folds[-1][0]["session"].min() < folds[-1][0]["session"].max()


def test_no_real_training_without_fundamentals(fixtures, tmp_path):
    _, _, data, metadata = fixtures
    from m1.features import FUNDAMENTAL

    unavailable = data.copy()
    unavailable[FUNDAMENTAL] = np.nan
    with pytest.raises(DataUnavailable, match="No common rows"):
        train_all(unavailable, metadata, "blocked", Settings(), tmp_path)
    assert not list(tmp_path.iterdir())


def test_model_artifacts_shap_inference_and_api(fixtures, tmp_path, monkeypatch):
    sources, cutoff, data, metadata = fixtures
    import m1.training as training

    monkeypatch.setitem(training.MODEL_PARAMETERS, "n_estimators", 8)
    report = train_all(data, metadata, "test_v1", Settings(), tmp_path)
    assert set(report["experiments"]) == {"technical", "fundamental", "combined"}
    with pytest.raises(FileExistsError):
        train_all(data, metadata, "test_v1", Settings(), tmp_path)
    classifier, regressor, artifact = load_models("test_v1", tmp_path)
    features = data[artifact["features"]].tail(4)
    probs = probability(classifier, features, artifact["calibration"])
    np.testing.assert_allclose(probs.sum(axis=1), 1.0, atol=1e-6)
    classes, expected = contribution_arrays(classifier, regressor, features)
    np.testing.assert_allclose(classes.sum(axis=2), classifier.predict(features, output_margin=True), atol=1e-5)
    np.testing.assert_allclose(expected.sum(axis=1), regressor.predict(features), atol=1e-5)
    assert (tmp_path / "plots" / "test_v1" / "combined" / "shap_global.json").is_file()

    @contextmanager
    def connection():
        yield None

    def single_ticker(conn, symbol, date):
        if symbol != "AAA":
            raise KeyError(symbol)
        return (sources[0].loc[sources[0]["symbol"].eq(symbol)], *sources[1:])

    monkeypatch.setattr(predict, "database", connection)
    monkeypatch.setattr(predict, "read_sources", single_ticker)
    monkeypatch.setattr(predict, "load_models", lambda version: load_models(version, tmp_path))
    monkeypatch.setattr(predict, "stored_scores", lambda *args: (
        {"technical_score": None, "fundamental_score": None}, []
    ))
    monkeypatch.setenv("MODULE1_MODEL_VERSION", "test_v1")
    client = TestClient(api_module.app)
    response = client.get("/api/module1/predict/aaa", params={"as_of_timestamp": cutoff.isoformat()})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["ticker"] == "AAA"
    assert set(result["direction_probabilities"]) == {"BEARISH", "SIDEWAYS", "BULLISH"}
    assert len(result["feature_explanations"]["direction_by_class"]) == 3
    assert client.get("/api/module1/predict/UNKNOWN").status_code == 404
    assert client.get("/api/module1/predict/AAA?as_of_timestamp=2023-01-01T12:00:00").status_code == 422
    assert client.get("/api/module1/predict/AAA", params={
        "as_of_timestamp": "2022-05-01T12:00:00+05:00"}).status_code == 503
    monkeypatch.setenv("MODULE1_MODEL_VERSION", "missing")
    assert client.get("/api/module1/predict/AAA").status_code == 503


def test_backtest_requires_adjusted_executions_and_accounts_for_costs(fixtures):
    _, _, prices, _ = fixtures
    signals = prices.loc[prices["symbol"].eq("AAA"), ["session", "symbol"]].iloc[10:75].assign(
        direction="BULLISH", expected_return_pct=4.0
    )
    assert simulate(signals, prices)["status"] == "unavailable"
    free = simulate(signals, prices, commission_bps=0, slippage_bps=0, adjusted=True)
    costs = simulate(signals, prices, adjusted=True)
    assert free["status"] == costs["status"] == "ok"
    assert costs["annualized_return"] < free["annualized_return"]
    assert costs["annualized_turnover"] > 0
