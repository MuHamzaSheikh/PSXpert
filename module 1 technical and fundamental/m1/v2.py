"""Reproducible, read-only-source v2 audit and chronological experiments.
Run: python -m m1.v2 --as-of 2026-11-16T14:00:00+05:00
Outputs are exclusively created under artifacts/combined_v2; refuses overwrite.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn
import xgboost as xgb
from scipy.optimize import minimize_scalar
from scipy.special import softmax
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss, recall_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text, inspect

from .features import (GROUPS, FUNDAMENTAL, TECHNICAL, as_of, build_dataset, directions,
                       research_rows, statement_panel, technical_frame)
from .settings import ROOT, REPO, CLASSES, Settings
from .sources import database, read_sources, normalize_prices, fetch_pypsx, compare_prices, DataUnavailable
from .training import MODEL_PARAMETERS, encode, write_json
from .evaluation import describe_split, regression

EXTRA = {'technical': ['relative_return_5', 'relative_return_20', 'relative_volume_prior20'],
         'fundamental': ['filing_age_days']}
EXTRA['combined'] = EXTRA['technical'] + EXTRA['fundamental']


def metrics(y, p):
    p = np.asarray(p, dtype=float)
    p = np.clip(p, 1e-12, 1)
    p /= p.sum(axis=1, keepdims=True)
    pred = p.argmax(axis=1)
    recall = recall_score(y, pred, labels=[0, 1, 2], average=None, zero_division=0)
    return dict(rows=len(y), accuracy=float(accuracy_score(y, pred)),
                balanced_accuracy=float(recall.mean()), macro_f1=float(f1_score(
                    y, pred, labels=[0, 1, 2], average='macro', zero_division=0)),
                per_class_recall=dict(zip(CLASSES, recall.tolist())),
                confusion_matrix=confusion_matrix(y, pred, labels=[0, 1, 2]).tolist(),
                log_loss=float(log_loss(y, p, labels=[0, 1, 2])), class_order=list(CLASSES),
                predicted_class_frequencies=dict(zip(CLASSES, (np.bincount(pred, minlength=3)/len(y)).tolist())))


def calibration_fit(p, y, method):
    z = np.log(np.clip(p, 1e-12, 1))
    if method == 'raw':
        return None
    if len(np.unique(y)) != 3:
        raise ValueError('Calibration window must contain all classes')
    if method == 'temperature':
        result = minimize_scalar(lambda t: log_loss(y, softmax(z / np.exp(t), axis=1), labels=[0, 1, 2]),
                                 bounds=(-3, 3), method='bounded')
        return float(np.exp(result.x))
    return LogisticRegression(C=0.1, max_iter=2000).fit(z, y)


def calibrate(p, fitted):
    if fitted is None:
        return p
    z = np.log(np.clip(p, 1e-12, 1))
    return softmax(z/fitted, axis=1) if isinstance(fitted, float) else fitted.predict_proba(z)


def calibration_allowed(raw, calibrated):
    # Require a gain in EVERY forward window and no class losing >2 recall points in any window.
    return all(c['log_loss'] < r['log_loss'] - 1e-6 and all(
        c['per_class_recall'][k] >= r['per_class_recall'][k] - 0.02 for k in CLASSES)
        for r, c in zip(raw, calibrated))


def partition(data, train_end, cal_end, eval_end, embargo=5):
    train = data[data.target_session.lt(train_end - embargo)].copy()
    cal = data[data.session.ge(train_end) & data.target_session.lt(cal_end - embargo)].copy()
    valid = data[data.session.ge(cal_end) & data.session.lt(eval_end)
                 & data.target_session.lt(eval_end - embargo)].copy()
    for part in (train, cal, valid):
        if len(part) < 100 or part.future_direction.nunique() != 3:
            raise DataUnavailable('Insufficient rows/classes after global purge and embargo')
    assert train.target_session.max() < cal.session.min() - embargo
    assert cal.target_session.max() < valid.session.min() - embargo
    return train, cal, valid


def folds(data):
    sessions = np.sort(data.session.unique())
    if len(sessions) < 450:
        raise DataUnavailable('Need at least 450 eligible market sessions for three disjoint forward windows')
    result = []
    for a, b, c in ((.35, .48, .64), (.51, .64, .80), (.67, .80, 1.0)):
        edges = [int(sessions[min(int(len(sessions)*f), len(sessions)-1)]) for f in (a,b,c)]
        if c == 1:
            edges[-1] = int(data.target_session.max()) + 6
        result.append(partition(data, *edges))
    return result


def configs():
    result = [dict(name='majority', kind='majority', extra=False, weighted=False),
              dict(name='v1_recipe', kind='xgb', extra=False, weighted=False, parameters=MODEL_PARAMETERS)]
    for extra in (False, True):
        for weighted in (False, True):
            for strength in (0.01, 0.1, 1.0):
                result.append(dict(name=f'logistic_C{strength}_extra{int(extra)}_weighted{int(weighted)}',
                                   kind='logistic', C=strength, extra=extra, weighted=weighted))
            for depth, trees in ((2, 160), (3, 240)):
                result.append(dict(name=f'xgb_d{depth}_n{trees}_extra{int(extra)}_weighted{int(weighted)}',
                                   kind='xgb', extra=extra, weighted=weighted,
                                   parameters={**MODEL_PARAMETERS, 'max_depth': depth, 'n_estimators': trees,
                                               'reg_lambda': 10, 'min_child_weight': 20, 'learning_rate': .03}))
    return result


def fit(train, names, config):
    y = encode(train.future_direction)
    counts = np.bincount(y, minlength=3)
    if config['kind'] == 'majority':
        return (counts + 1) / (len(y) + 3)
    weights = len(y)/(3*counts[y]) if config['weighted'] else np.ones(len(y))
    if config['kind'] == 'logistic':
        model = make_pipeline(SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True),
                              StandardScaler(), LogisticRegression(C=config['C'], max_iter=3000, random_state=42))
        model.fit(train[names], y, logisticregression__sample_weight=weights)
    else:
        model = xgb.XGBClassifier(**config['parameters'], random_state=42,
                                  objective='multi:softprob', num_class=3, eval_metric='mlogloss')
        model.fit(train[names], y, sample_weight=weights)
    return model


def probabilities(model, frame, names):
    return np.tile(model, (len(frame), 1)) if isinstance(model, np.ndarray) else model.predict_proba(frame[names])


def inventory():
    paths = set(REPO.rglob('*.csv')) | set(REPO.rglob('*.csv.gz')) | set((ROOT/'artifacts/combined_v1').rglob('*'))
    paths |= {p for p in (REPO/'data').rglob('*.db')}
    return {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if p.is_file() and 'combined_v2' not in p.parts}


def audit_sources(sources, connection, out):
    prices = normalize_prices(sources[0]).sort_values(['symbol', 'trading_date']).reset_index(drop=True)
    raw = pd.read_sql_query(text('SELECT p.*, s.source_name FROM stock_prices p LEFT JOIN data_sources s '
                                'ON p.source_id=s.id WHERE p.symbol IN '
                                '(SELECT symbol FROM companies WHERE is_kse100=TRUE)'), connection)
    raw['trading_date'] = pd.to_datetime(raw.trading_date)
    raw = raw[raw.trading_date.le(prices.trading_date.max())]
    actions = pd.read_sql_query(text('SELECT * FROM corporate_payouts'), connection)
    announcements = pd.read_sql_query(text('SELECT * FROM corporate_announcements WHERE '
        "LOWER(title) LIKE '%split%' OR LOWER(title) LIKE '%bonus%' OR LOWER(title) LIKE '%book closure%'"), connection)
    actions.to_csv(out/'corporate_actions_source.csv', index=False)
    announcements.to_csv(out/'action_announcements_source.csv', index=False)
    bad = (prices.high.lt(prices[['open','close','low']].max(axis=1))
           | prices.low.gt(prices[['open','close']].min(axis=1))
           | prices[['open','high','low']].le(0).any(axis=1))
    prices['daily_return_pct'] = prices.groupby('symbol').close.pct_change(fill_method=None)*100
    suspects = prices[bad | prices.daily_return_pct.abs().ge(20)].copy()
    suspects['inconsistent_candle'] = bad.loc[suspects.index]
    suspects = suspects.merge(raw, on=['symbol','trading_date'], suffixes=('', '_source'), validate='one_to_one')
    suspects['decision'] = np.where(suspects.inconsistent_candle, 'mask OHL; retain positive close and volume',
                                    'retain unless unresolved >=35% discontinuity crosses label')
    suspects['reason'] = np.where(suspects.inconsistent_candle, 'OHLC ordering or positivity violation',
                                  'magnitude alone does not establish error')
    suspects.to_csv(out/'price_source_trace.csv', index=False)
    largest = prices.reindex(prices.daily_return_pct.abs().sort_values(ascending=False).head(100).index)
    largest.merge(raw, on=['symbol','trading_date'], suffixes=('', '_source')).to_csv(out/'largest_daily_returns.csv', index=False)
    provider = {}
    from .__main__ import evidence
    status = evidence()
    if status['credentials_configured'] and status['sdk_installed']:
        for symbol, part in suspects.groupby('symbol'):
            try:
                secondary = fetch_pypsx(symbol, part.trading_date.min(), part.trading_date.max())
                secondary.to_csv(out/f'pypsx_{symbol}.csv', index=False)
                provider[symbol], conflicts = compare_prices(prices[prices.symbol.eq(symbol)], secondary)
                conflicts.to_csv(out/f'pypsx_conflicts_{symbol}.csv', index=False)
            except DataUnavailable as exc:
                provider[symbol] = {'unavailable': str(exc)}
    status['comparisons'] = provider
    # No ex/effective dates exist in current source schema. Never reinterpret announcements as ex-dates.
    summary = dict(inconsistent_candles_all_source=int(bad.sum()), suspect_records=len(suspects),
        price_sources=raw.source_name.value_counts().to_dict(), pypsx=status,
        action_columns=[c['name'] for c in inspect(connection).get_columns('corporate_payouts')],
        effective_dates_verified=False,
        action_policy='No verified ex-date/factor evidence. No numerical price adjustments. Quarantine >=35% '
                      'discontinuity labels; announcement +/-5-day exclusions retained from v1, explicitly provisional.',
        filing_limitation='Accounting values are current database snapshots; original revision vintages unavailable. '
                          'Public availability gated by unambiguous PSX annual transmission; not fully vintage verified.')
    write_json(out/'source_audit.json', summary)
    clean = prices.drop(columns='daily_return_pct').copy()
    clean.loc[bad, ['open','high','low']] = np.nan
    return (clean, *sources[1:]), summary


def feature_extras(data, index):
    index = index.sort_values('trading_date').copy()
    index['trading_date'] = pd.to_datetime(index.trading_date)
    if index.trading_date.duplicated().any():
        raise DataUnavailable('Duplicate KSE100 sessions')
    for n in (5,20):
        index[f'index_return_{n}'] = index.close.pct_change(n, fill_method=None)*100
    result = data.merge(index[['trading_date', 'index_return_5', 'index_return_20']], on='trading_date', how='left', validate='many_to_one')
    for n in (5,20):
        result[f'relative_return_{n}'] = result[f'momentum_{n}_pct'] - result[f'index_return_{n}']
    result = result.sort_values(['symbol','session'])
    result['relative_volume_prior20'] = result.groupby('symbol').volume.transform(
        lambda v: v / v.shift(1).rolling(20, min_periods=20).mean())
    publication = pd.to_datetime(result.available_from_timestamp, utc=True)
    result['filing_age_days'] = (pd.to_datetime(result.prediction_timestamp, utc=True)-publication).dt.total_seconds()/86400
    return result.replace([np.inf, -np.inf], np.nan).sort_values(['session','symbol']).reset_index(drop=True)


def audit_dataset(data, original, sources, out):
    common = research_rows(data)
    old = research_rows(original)
    keys = ['symbol','trading_date']
    ledger = data[keys + ['sector','session','target_session','future_direction']].copy()
    ledger['v1_eligible'] = pd.MultiIndex.from_frame(data[keys]).isin(pd.MultiIndex.from_frame(old[keys]))
    ledger['v2_eligible'] = pd.MultiIndex.from_frame(data[keys]).isin(pd.MultiIndex.from_frame(common[keys]))
    ledger['reason'] = 'eligible; candle-derived features may be missing'
    ledger.loc[data.future_direction.isna(), 'reason'] = 'missing 20th market-session close or provisional action/discontinuity quarantine'
    ledger.loc[data.momentum_20_pct.isna(), 'reason'] = 'technical warmup or discontinuity reset'
    ledger.loc[~data[FUNDAMENTAL].notna().any(axis=1), 'reason'] = 'no eligible filing features'
    ledger.to_csv(out/'row_eligibility_ledger.csv.gz', index=False)
    # Separate all overlapping exclusion flags, not only the primary reason.
    flags = data[keys].copy()
    flags['missing_target'] = data.future_direction.isna()
    flags['technical_unavailable'] = data.momentum_20_pct.isna()
    flags['filing_unavailable'] = ~data[FUNDAMENTAL].notna().any(axis=1)
    flags.to_csv(out/'exclusion_flags.csv.gz', index=False)
    data = data.assign(year=data.trading_date.dt.year)
    for group in ('symbol','sector','year'):
        missing = data.groupby(group, dropna=False)[GROUPS['combined']+EXTRA['combined']].agg(lambda s: s.isna().mean())
        missing['rows'] = data.groupby(group, dropna=False).size()
        missing.to_csv(out/f'missing_features_by_{group}.csv')
    for group in ('symbol','trading_date','future_direction'):
        pd.concat([old.groupby(group).size().rename('v1'), common.groupby(group).size().rename('v2')], axis=1).fillna(0).to_csv(out/f'coverage_by_{group}.csv')
    panel, counts = statement_panel(sources[3], sources[4])
    pd.DataFrame([dict(symbol=s, **p) for s, values in panel.items() for p in values]).to_csv(out/'filing_panel.csv', index=False)
    sources[3].to_csv(out/'filing_source_metrics.csv.gz', index=False)
    sources[4].to_csv(out/'filing_source_announcements.csv.gz', index=False)
    joined = common[keys+['period_end_date','publication_date','available_from_timestamp','prediction_timestamp','filing_source']]
    assert (pd.to_datetime(joined.available_from_timestamp, utc=True) <= pd.to_datetime(joined.prediction_timestamp, utc=True)).all()
    joined.to_csv(out/'filing_joins.csv.gz', index=False)
    # Independently reconstruct raw 20-market-session returns before existing quarantine rules.
    raw = data[keys+['close']].rename(columns={'trading_date':'target_date','close':'target_close'})
    check = common.merge(raw, on=['symbol','target_date'], how='left', validate='many_to_one')
    reconstructed = 100*(check.target_close/check.close-1)
    np.testing.assert_allclose(reconstructed, check.future_20_day_return_pct, rtol=0, atol=1e-9)
    pd.testing.assert_series_equal(directions(reconstructed).reset_index(drop=True), check.future_direction.reset_index(drop=True), check_names=False)
    check.nlargest(100, 'future_20_day_return_pct')[['symbol','trading_date','target_date','close','target_close','future_20_day_return_pct']].to_csv(out/'largest_20_session_returns.csv', index=False)
    write_json(out/'dataset_audit.json', dict(v1_rows=len(old), v2_rows=len(common), verified_targets=len(check), filing_audit=counts,
        original=describe_split(old), eligible=describe_split(common),
        price_policy='Unadjusted price returns, excluding dividends. Unknown action dates and accounting vintages remain limitations.'))
    return common


def evaluate_experiment(experiment, split_list, out):
    results, predictions = [], {}
    for config in configs():
        names = GROUPS[experiment] + (EXTRA[experiment] if config['extra'] else [])
        records = {method: [] for method in ('raw','temperature','multinomial')}
        buffers = {method: [] for method in records}
        for fold, (train, cal, valid) in enumerate(split_list):
            model = fit(train, names, config)
            cp, vp = probabilities(model, cal, names), probabilities(model, valid, names)
            for method in records:
                fitted = calibration_fit(cp, encode(cal.future_direction), method)
                p = calibrate(vp, fitted)
                records[method].append(metrics(encode(valid.future_direction), p))
                pred = valid[['symbol','session','trading_date','future_direction']].copy()
                pred['fold'] = fold
                pred[['p_bearish','p_sideways','p_bullish']] = p
                buffers[method].append(pred)
        for method, values in records.items():
            allowed = method == 'raw' or (config['kind'] != 'majority' and calibration_allowed(records['raw'], values))
            name = config['name'] + ':' + method
            row = dict(name=name, configuration=config, features=names, calibration=method, calibration_allowed=allowed,
                       windows=values, mean_log_loss=float(np.mean([v['log_loss'] for v in values])),
                       mean_macro_f1=float(np.mean([v['macro_f1'] for v in values])))
            results.append(row)
            predictions[name] = pd.concat(buffers[method], ignore_index=True)
        print(experiment, config['name'], 'complete', flush=True)
    # Primary selection metric: mean forward-window macro F1; tie-break log loss.
    eligible = [r for r in results if r['calibration_allowed']]
    best = min(eligible, key=lambda r: (-r['mean_macro_f1'], r['mean_log_loss']))
    directory = out/experiment
    directory.mkdir()
    write_json(directory/'validation.json', results)
    chosen = predictions[best['name']]
    chosen.to_csv(directory/'walk_forward_predictions.csv', index=False)
    summary = dict(selected=best, selection='maximum mean validation macro F1, tie-break minimum log loss',
                   walk_forward=metrics(encode(chosen.future_direction), chosen[['p_bearish','p_sideways','p_bullish']].values),
                   selection_bias='Walk-forward scores used for selection; not an unbiased final held-out estimate.')
    for key in ('majority:raw', 'v1_recipe:raw'):
        p = predictions[key]
        summary[key] = metrics(encode(p.future_direction), p[['p_bearish','p_sideways','p_bullish']].values)
    write_json(directory/'evaluation.json', summary)
    return best, summary


def save_pair(best, train, cal, experiment, out):
    names = best['features']
    model = fit(train, names, best['configuration'])
    fitted = calibration_fit(probabilities(model, cal, names), encode(cal.future_direction), best['calibration'])
    regressor = xgb.XGBRegressor(**{**MODEL_PARAMETERS, 'reg_lambda':10}, random_state=42, objective='reg:squarederror')
    regressor.fit(train[names], train.future_20_day_return_pct)
    directory = out/experiment
    joblib.dump(dict(classifier=model, calibrator=fitted, features=names, classes=CLASSES), directory/'classifier.joblib')
    if isinstance(model, xgb.XGBClassifier):
        model.save_model(directory/'classifier.ubj')
    regressor.save_model(directory/'regressor.ubj')
    write_json(directory/'metadata.json', dict(version='combined_v2', feature_version=2, experiment=experiment,
        selected=best['name'], configuration=best['configuration'], features=names, classes=list(CLASSES),
        calibration=best['calibration'], train=describe_split(train), calibration_window=describe_split(cal),
        horizon=20, thresholds=[-3,3], seed=42, embargo=5, inference='m1.v2.load_pair; research artifacts, not v1 API schema'))
    return model, fitted, regressor


def load_pair(experiment='combined', root=ROOT/'artifacts/combined_v2'):
    bundle = joblib.load(root/experiment/'classifier.joblib')
    regressor = xgb.XGBRegressor()
    regressor.load_model(root/experiment/'regressor.ubj')
    return bundle, regressor


def run(cutoff, out):
    before = inventory()
    out.mkdir(parents=True, exist_ok=False)
    audit = out/'audit'
    audit.mkdir()
    write_json(out/'preservation_before.json', before)
    with database() as connection:
        if connection.dialect.name != 'postgresql':
            raise DataUnavailable('v2 comparison requires PostgreSQL; refusing silent SQLite fallback')
        sources = read_sources(connection, cutoff=cutoff.date())
        clean, source_audit = audit_sources(sources, connection, audit)
        index = pd.read_sql_query(text("SELECT trading_date, close FROM market_indices WHERE index_symbol='KSE100' AND close>0 AND trading_date<=:cutoff"), connection, params={'cutoff':cutoff.date()})
    print('Source audit saved; rebuilding original and audited features', flush=True)
    original, original_meta = build_dataset(sources, cutoff, research_only=True)
    data, metadata = build_dataset(clean, cutoff, research_only=True)
    data = feature_extras(data, index)
    common = audit_dataset(data, original, sources, audit)
    common.to_csv(out/'eligible_rows.csv.gz', index=False)
    write_json(out/'source_metadata.json', metadata)
    historical = pd.read_csv(ROOT/'artifacts/combined_v1/combined/held_out_predictions.csv')
    old_last = pd.to_datetime(historical.prediction_timestamp, utc=True).max()
    old_label_end = pd.to_datetime(historical.target_timestamp, utc=True).max()
    # Fresh assessment must start after every inspected v1 outcome has resolved plus embargo.
    past = common[pd.to_datetime(common.target_timestamp, utc=True).le(old_label_end)]
    fresh = common[pd.to_datetime(common.prediction_timestamp, utc=True).gt(old_label_end)]
    if len(fresh):
        fresh = fresh[fresh.session.ge(fresh.session.min()+5)]
    has_fresh = len(fresh) >= 1000 and fresh.session.nunique() >= 60 and fresh.future_direction.nunique() == 3
    selection_data = past if has_fresh else common
    split_list = folds(selection_data)
    manifest = []
    for fold, parts in enumerate(split_list):
        for role, frame in zip(('train','calibration','validation'), parts):
            frame[['symbol','session','target_session','trading_date','target_date']].assign(fold=fold, role=role).to_csv(out/f'split_{fold}_{role}.csv.gz', index=False)
            manifest.append(dict(fold=fold, role=role, **describe_split(frame)))
    write_json(out/'splits.json', dict(embargo_market_sessions=5, market_wide_target_purge=True, windows=manifest,
        fresh_eligible_rows=len(fresh), fresh_eligible_sessions=int(fresh.session.nunique()), fresh_test_available=has_fresh,
        historical_last_signal=old_last, historical_last_label=old_label_end))
    summaries = {}
    for experiment in GROUPS:
        best, summary = evaluate_experiment(experiment, split_list, out)
        if has_fresh:
            boundary = int(fresh.session.min())
            cal_start = int(np.sort(selection_data.session.unique())[-100])
            train = common[common.target_session.lt(cal_start-5)]
            cal = common[common.session.ge(cal_start) & common.target_session.lt(boundary-5)]
        else:
            train, cal, _ = split_list[-1]
        model, calibrator, regressor = save_pair(best, train, cal, experiment, out)
        if has_fresh:
            fresh.to_csv(out/'fresh_assessment_rows.csv.gz', index=False) if experiment == 'technical' else None
            p = calibrate(probabilities(model, fresh, best['features']), calibrator)
            summary['fresh_test'] = metrics(encode(fresh.future_direction), p)
            baseline = fit(train, best['features'], configs()[0])
            summary['fresh_majority'] = metrics(encode(fresh.future_direction), probabilities(baseline, fresh, best['features']))
        # Identical historical keys and targets, with v1 features supplied to the saved raw classifier.
        history_keys = historical[['symbol','prediction_timestamp']].copy()
        history_keys['trading_date'] = pd.to_datetime(history_keys.prediction_timestamp, utc=True).dt.tz_convert('Asia/Karachi').dt.tz_localize(None).dt.normalize()
        comparable = common.merge(history_keys[['symbol','trading_date']], on=['symbol','trading_date'], validate='one_to_one')
        # Use a separately trained pre-historical model; selections still used inspected history, explicitly descriptive.
        start = int(comparable.session.min())
        cal_start = start - 110
        hist_train = common[common.target_session.lt(cal_start-5)]
        hist_cal = common[common.session.ge(cal_start) & common.target_session.lt(start-5)]
        hist_model = fit(hist_train, best['features'], best['configuration'])
        hist_fitted = calibration_fit(probabilities(hist_model,hist_cal,best['features']), encode(hist_cal.future_direction), best['calibration'])
        summary['historical_v2'] = metrics(encode(comparable.future_direction), calibrate(probabilities(hist_model,comparable,best['features']),hist_fitted))
        v1 = xgb.XGBClassifier()
        v1.load_model(ROOT/'artifacts/combined_v1'/experiment/'classifier.ubj')
        v1rows = original.merge(comparable[['symbol','trading_date']], on=['symbol','trading_date'], validate='one_to_one').sort_values(['trading_date','symbol'])
        comparable = comparable.sort_values(['trading_date','symbol'])
        assert v1rows[['symbol','trading_date']].reset_index(drop=True).equals(comparable[['symbol','trading_date']].reset_index(drop=True))
        summary['historical_raw_v1'] = metrics(encode(comparable.future_direction), v1.predict_proba(v1rows[GROUPS[experiment]]))
        majority = fit(hist_train, best['features'], configs()[0])
        summary['historical_training_majority'] = metrics(encode(comparable.future_direction), probabilities(majority, comparable, best['features']))
        summary['historical_caveat'] = 'Inspected v1 benchmark; v2 selected using overlapping dates. Descriptive only, not fresh performance.'
        test = fresh if has_fresh else split_list[-1][2]
        summary['regression'] = regression(test.future_20_day_return_pct, regressor.predict(test[best['features']]), train.future_20_day_return_pct.mean())
        write_json(out/experiment/'comparison.json', summary)
        summaries[experiment] = summary
    after = inventory()
    if before != after:
        raise AssertionError('Protected artifact/CSV/database inventory changed')
    write_json(out/'preservation_after.json', after)
    write_json(out/'comparison.json', dict(experiments=summaries, fresh_held_out_verified=has_fresh,
        limitations=['Historical KSE100 roster and accounting revision vintages unavailable',
                    'Corporate effective dates unavailable; action quarantines provisional',
                    'No independent raw-price verification without pyPSX credentials/coverage',
                    'Walk-forward selection scores are not nested unbiased performance estimates']))
    write_json(out/'reproducibility.json', dict(command=f'python -m m1.v2 --as-of {cutoff.isoformat()}',
        tests='python -m pytest -q', python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__,
        sklearn=sklearn.__version__, scipy=scipy.__version__, xgboost=xgb.__version__, seed=42,
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    print(json.dumps({k:{'selected':v['selected']['name'],'walk_forward':v['walk_forward'],
                         'historical_v2':v['historical_v2'],'historical_raw_v1':v['historical_raw_v1']} for k,v in summaries.items()}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of', required=True)
    args = parser.parse_args()
    run(as_of(args.as_of), ROOT/'artifacts/combined_v2')


if __name__ == '__main__':
    main()
