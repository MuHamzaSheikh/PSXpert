import joblib
import numpy as np
import pandas as pd
import pytest

from m1.decision_pipeline import (
    DecisionConfig, build_targets, predict_decisions, split_stage, train_pipeline,
)
from m1.features import FUNDAMENTAL, TECHNICAL


def inputs(n=180):
    panels, bars = [], []
    clock = np.arange(n)
    times = pd.date_range("2020-01-01", periods=n, tz="Asia/Karachi")
    for i in range(6):
        close = 100 * np.exp(.08 * np.sin(clock / 6 + i) + clock * i * .0001)
        frame = pd.DataFrame({"symbol": f"S{i}", "session": clock,
                              "prediction_timestamp": times,
                              "available_from_timestamp": times[0]})
        for j, name in enumerate(FUNDAMENTAL + TECHNICAL):
            frame[name] = i + np.sin(clock / (j + 2) + i)
        panels.append(frame)
        bars.append(pd.DataFrame({"symbol": f"S{i}", "session": clock,
                                  "adjusted_open": close * .999,
                                  "adjusted_close": close, "price_valid": True}))
    benchmark = pd.DataFrame({"session": clock, "adjusted_close": 100 + clock * .01,
                              "price_valid": True})
    return pd.concat(panels, ignore_index=True), pd.concat(bars, ignore_index=True), benchmark


def config():
    return DecisionConfig(fundamental_horizon=20, technical_horizon=3,
                          entry_margin_pct=0, cost_pct=0, embargo=2)


def test_distinct_targets_next_open_and_missing_session():
    panel, prices, benchmark = inputs()
    data = build_targets(panel, prices, benchmark, config())
    row = data.query("symbol == 'S0' and session == 0").iloc[0]
    p = prices[prices.symbol.eq("S0")].set_index("session")
    assert row.technical_target == pytest.approx(100 * (p.loc[3, "adjusted_close"] / p.loc[1, "adjusted_open"] - 1))
    assert row.fundamental_target == pytest.approx(100 * (p.loc[20, "adjusted_close"] / p.loc[0, "adjusted_close"] - benchmark.loc[20, "adjusted_close"] / benchmark.loc[0, "adjusted_close"]))
    prices = prices[~(prices.symbol.eq("S0") & prices.session.eq(1))]
    missing = build_targets(panel, prices, benchmark, config())
    assert missing.query("symbol == 'S0' and session == 0").technical_target.isna().all()


def test_publication_gate_and_price_audit():
    panel, prices, benchmark = inputs()
    panel.loc[0, "available_from_timestamp"] = panel.loc[1, "prediction_timestamp"]
    with pytest.raises(ValueError, match="publication"):
        build_targets(panel, prices, benchmark, config())
    panel, prices, benchmark = inputs()
    prices.loc[2, "price_valid"] = False
    data = build_targets(panel, prices, benchmark, config())
    assert data.query("symbol == 'S0' and session == 0").technical_target.isna().all()


def test_horizon_specific_purging():
    data = build_targets(*inputs(), config())
    for stage in ("technical", "fundamental"):
        train, valid, test = split_stage(data, stage, 60, 110, config())
        assert train[f"{stage}_target_session"].max() < 60 - config().embargo
        assert valid[f"{stage}_target_session"].max() < 110 - config().embargo
        assert test.session.min() == 110


def test_train_reload_inference_and_feature_isolation(tmp_path):
    panel, prices, benchmark = inputs()
    data = build_targets(panel, prices, benchmark, config())
    bundle, report = train_pipeline(data, 60, 110, config(), trees=4)
    assert set(bundle["feature_schema"]["fundamental"]).isdisjoint(bundle["feature_schema"]["technical"])
    assert report["fundamental"]["test"]["ndcg"] >= 0
    assert report["technical"]["test"]["rows"] > 0
    path = tmp_path / "models.joblib"
    joblib.dump(bundle, path)
    loaded = joblib.load(path)
    current = panel[panel.session.eq(179)].copy()
    result = predict_decisions(loaded, current)
    changed = current.copy()
    changed[TECHNICAL] = 999
    pd.testing.assert_series_equal(result.fundamental_score, predict_decisions(loaded, changed).fundamental_score)
    changed = current.copy()
    changed[FUNDAMENTAL] = 999
    pd.testing.assert_series_equal(result.entry_probability_raw, predict_decisions(loaded, changed).entry_probability_raw)
    single = predict_decisions(loaded, current.iloc[:1])
    assert single.decision.iloc[0] == "INSUFFICIENT_DATA"
    with pytest.raises(ValueError, match="predates"):
        predict_decisions(loaded, panel[panel.session.eq(0)])
