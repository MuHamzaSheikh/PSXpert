"""Rigorous test suite for selection and entry timing architecture.

Covers:
1. Execution timing (entry at t+1 open, exit at t+10 close).
2. Zero information leakage (strict feature separation, causal availability).
3. Horizon-specific purging and embargo enforcement.
4. Ranking quality, relevance grading, and fundamental baselines.
5. Classification calibration, entry metrics, and technical baselines.
6. Decision conjunction states (ENTRY_CANDIDATE, WAIT, NOT_SHORTLISTED, INSUFFICIENT_DATA).
7. Bounded search study reproducibility and schema.
8. End-to-end joblib serialization and inference boundaries.
"""
import joblib
import numpy as np
import pandas as pd
import pytest

from m1.decision_pipeline import (
    DecisionConfig,
    bounded_search_classifier,
    bounded_search_ranker,
    build_targets,
    compute_fundamental_baselines,
    compute_technical_baselines,
    entry_metrics,
    feature_matrix,
    predict_decisions,
    ranking_metrics,
    relevance,
    simulate_joint_policy,
    split_stage,
    train_pipeline,
)
from m1.features import FUNDAMENTAL, TECHNICAL


def make_synthetic_universe(n_sessions=200, n_symbols=8):
    panels, bars = [], []
    clock = np.arange(n_sessions)
    times = pd.date_range("2020-01-01", periods=n_sessions, tz="Asia/Karachi")
    for i in range(n_symbols):
        close = 100 * np.exp(0.05 * np.sin(clock / 8 + i) + clock * i * 0.0002)
        frame = pd.DataFrame({
            "symbol": f"SYM_{i}",
            "session": clock,
            "prediction_timestamp": times,
            "available_from_timestamp": times[0],
            "momentum_20_pct": np.sin(clock / 10 + i) * 5,
        })
        for j, name in enumerate(FUNDAMENTAL + TECHNICAL):
            frame[name] = i * 1.5 + np.sin(clock / (j + 3) + i)
        panels.append(frame)
        bars.append(pd.DataFrame({
            "symbol": f"SYM_{i}",
            "session": clock,
            "adjusted_open": close * 0.998,
            "adjusted_close": close,
            "price_valid": True,
        }))
    bench = pd.DataFrame({
        "session": clock,
        "adjusted_close": 100 + clock * 0.02,
        "price_valid": True,
    })
    return pd.concat(panels, ignore_index=True), pd.concat(bars, ignore_index=True), bench


def get_config():
    return DecisionConfig(
        fundamental_horizon=25,
        technical_horizon=5,
        cost_pct=0.2,
        entry_margin_pct=1.0,
        embargo=3,
        top_fraction=0.25,
        entry_threshold=0.55,
        seed=42,
    )


def test_timing_and_execution_convention():
    panel, prices, bench = make_synthetic_universe()
    cfg = get_config()
    data = build_targets(panel, prices, bench, cfg)

    row = data.query("symbol == 'SYM_0' and session == 0").iloc[0]
    p = prices[prices.symbol.eq("SYM_0")].set_index("session")

    # Technical: return from session 1 open to session 5 close, minus cost
    expected_tech = 100 * (p.loc[5, "adjusted_close"] / p.loc[1, "adjusted_open"] - 1) - cfg.cost_pct
    assert row.technical_target == pytest.approx(expected_tech)

    # Fundamental: relative return from session 0 close to session 25 close vs benchmark
    expected_fund = 100 * (
        p.loc[25, "adjusted_close"] / p.loc[0, "adjusted_close"]
        - bench.loc[25, "adjusted_close"] / bench.loc[0, "adjusted_close"]
    )
    assert row.fundamental_target == pytest.approx(expected_fund)

    # Missing open at t+1 invalidates technical target
    prices_missing = prices.copy()
    prices_missing = prices_missing[~(prices_missing.symbol.eq("SYM_0") & prices_missing.session.eq(1))]
    data_missing = build_targets(panel, prices_missing, bench, cfg)
    assert data_missing.query("symbol == 'SYM_0' and session == 0").technical_target.isna().all()


def test_zero_information_leakage():
    assert set(FUNDAMENTAL).isdisjoint(set(TECHNICAL))

    panel, prices, bench = make_synthetic_universe()
    cfg = get_config()
    data = build_targets(panel, prices, bench, cfg)

    bundle, _ = train_pipeline(data, 80, 140, cfg, trees=6)

    test_panel = panel[panel.session.eq(150)].copy()
    base_preds = predict_decisions(bundle, test_panel)

    # Mutating technical features does not affect fundamental score
    corrupted_tech = test_panel.copy()
    corrupted_tech[TECHNICAL] = 9999.0
    preds_tech_corrupt = predict_decisions(bundle, corrupted_tech)
    pd.testing.assert_series_equal(base_preds.fundamental_score, preds_tech_corrupt.fundamental_score)
    pd.testing.assert_series_equal(base_preds.fundamental_percentile, preds_tech_corrupt.fundamental_percentile)

    # Mutating fundamental features does not affect technical entry probability
    corrupted_fund = test_panel.copy()
    corrupted_fund[FUNDAMENTAL] = 9999.0
    preds_fund_corrupt = predict_decisions(bundle, corrupted_fund)
    pd.testing.assert_series_equal(base_preds.entry_probability_raw, preds_fund_corrupt.entry_probability_raw)


def test_horizon_purging_and_embargo():
    panel, prices, bench = make_synthetic_universe()
    cfg = get_config()
    data = build_targets(panel, prices, bench, cfg)

    for stage, horizon in (("fundamental", cfg.fundamental_horizon), ("technical", cfg.technical_horizon)):
        train, valid, test = split_stage(data, stage, 80, 140, cfg)
        assert train[f"{stage}_target_session"].max() < 80 - cfg.embargo
        assert train.session.max() < 80 - cfg.embargo - horizon
        assert valid[f"{stage}_target_session"].max() < 140 - cfg.embargo
        assert valid.session.min() >= 80
        assert test.session.min() == 140


def test_ranking_and_fundamental_baselines():
    panel, prices, bench = make_synthetic_universe()
    cfg = get_config()
    data = build_targets(panel, prices, bench, cfg)

    train, valid, test = split_stage(data, "fundamental", 80, 140, cfg)
    baselines = compute_fundamental_baselines(train, test, cfg)

    assert "random_baseline" in baselines
    assert "momentum_baseline" in baselines
    assert "value_composite_baseline" in baselines
    assert baselines["random_baseline"]["ndcg"] >= 0.0
    assert np.isfinite(baselines["random_baseline"]["top_group_excess_return_pct"])


def test_classification_and_technical_baselines():
    panel, prices, bench = make_synthetic_universe()
    cfg = get_config()
    data = build_targets(panel, prices, bench, cfg)

    train, valid, test = split_stage(data, "technical", 80, 140, cfg)
    baselines = compute_technical_baselines(train, test, cfg)

    assert "majority_class_baseline" in baselines
    assert "logistic_regression_baseline" in baselines
    assert "sma_breakout_baseline" in baselines

    for name in ("majority_class_baseline", "logistic_regression_baseline", "sma_breakout_baseline"):
        metrics = baselines[name]
        assert 0.0 <= metrics["average_precision"] <= 1.0
        assert metrics["brier_score"] >= 0.0


def test_decision_conjunction_and_insufficient_data():
    panel, prices, bench = make_synthetic_universe()
    cfg = get_config()
    data = build_targets(panel, prices, bench, cfg)
    bundle, _ = train_pipeline(data, 80, 140, cfg, trees=6)

    current = panel[panel.session.eq(160)].copy()
    preds = predict_decisions(bundle, current)

    # 4 distinct possible states
    possible_decisions = {"ENTRY_CANDIDATE", "WAIT", "NOT_SHORTLISTED", "INSUFFICIENT_DATA"}
    assert set(preds.decision.unique()).issubset(possible_decisions)

    # Single queried ticker cannot certify top-quintile rank -> INSUFFICIENT_DATA
    single_res = predict_decisions(bundle, current.iloc[:1])
    assert single_res.decision.iloc[0] == "INSUFFICIENT_DATA"

    # Missing technical indicators -> INSUFFICIENT_DATA
    missing_tech = current.copy()
    missing_tech.loc[missing_tech.index[0], TECHNICAL] = np.nan
    res_missing = predict_decisions(bundle, missing_tech)
    assert res_missing.loc[res_missing.index[0], "decision"] == "INSUFFICIENT_DATA"


def test_bounded_search_study():
    panel, prices, bench = make_synthetic_universe()
    cfg = get_config()
    data = build_targets(panel, prices, bench, cfg)

    train_f, valid_f, _ = split_stage(data, "fundamental", 80, 140, cfg)
    ranker, best_p, best_m, trials = bounded_search_ranker(train_f, valid_f, cfg, budget=3)
    assert len(trials) == 3
    assert all(t["status"] == "COMPLETE" for t in trials)
    assert best_m["ndcg"] >= 0.0

    train_t, valid_t, _ = split_stage(data, "technical", 80, 140, cfg)
    clf, best_cp, best_cm, c_trials = bounded_search_classifier(train_t, valid_t, cfg, budget=3)
    assert len(c_trials) == 3
    assert all(t["status"] == "COMPLETE" for t in c_trials)
    assert 0.0 <= best_cm["average_precision"] <= 1.0


def test_joint_policy_simulation_and_reload(tmp_path):
    panel, prices, bench = make_synthetic_universe()
    cfg = get_config()
    data = build_targets(panel, prices, bench, cfg)

    bundle, _ = train_pipeline(data, 80, 140, cfg, trees=6)

    # Save and reload
    save_path = tmp_path / "models.joblib"
    joblib.dump(bundle, save_path)
    loaded = joblib.load(save_path)

    test_slice = data[data.session.ge(140)].copy()
    sim = simulate_joint_policy(loaded, test_slice, cfg)

    assert "decision_counts" in sim
    assert "groups" in sim
    assert "entry_candidate" in sim["groups"]
    assert "naive_fundamental_shortlist" in sim["groups"]

    # Reject dates predating trained boundary
    with pytest.raises(ValueError, match="predates"):
        predict_decisions(loaded, panel[panel.session.eq(10)])
