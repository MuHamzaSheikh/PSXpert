"""Supplement the immutable training outputs with detailed exclusion and ablation reports.
Run after m1.v2: python -m m1.v2_report
"""
import json
import numpy as np
import pandas as pd
from sqlalchemy import text
from .settings import ROOT, CLASSES
from .features import build_dataset, research_rows, as_of
from .sources import database, read_sources, normalize_prices
from .training import write_json


def main():
    out = ROOT/'artifacts/combined_v2'
    audit = out/'audit'
    result = json.loads((out/'comparison.json').read_text())
    cutoff = json.loads((out/'source_metadata.json').read_text()).get('raw_date_max','2026-10-13')
    with database() as connection:
        sources = read_sources(connection, cutoff=pd.Timestamp(cutoff).date())
        source_keys = pd.read_sql_query(text('SELECT id, symbol, trading_date, source_id FROM stock_prices WHERE symbol IN (SELECT symbol FROM companies WHERE is_kse100=TRUE)'),connection)
        source_keys['trading_date'] = pd.to_datetime(source_keys.trading_date)
    # Reuse the verified run cohort; no second technical-indicator rebuild is needed for reporting.
    cohort = pd.read_csv(out/'eligible_rows.csv.gz',parse_dates=['trading_date','target_date'])
    ledger = pd.read_csv(audit/'row_eligibility_ledger.csv.gz',parse_dates=['trading_date'])
    v1keys = ledger.loc[ledger.v1_eligible,['symbol','trading_date']].sort_values(['symbol','trading_date']).reset_index(drop=True)
    v2keys = cohort[['symbol','trading_date']].sort_values(['symbol','trading_date']).reset_index(drop=True)
    assert v1keys.equals(v2keys), 'Report expects identical v1/v2 eligible keys; inspect coverage changes first'
    calendar = pd.Series(sorted(pd.to_datetime(sources[1].trading_date).unique()))
    calendar = calendar[calendar.dt.weekday.lt(5)].reset_index(drop=True)
    dates = pd.DataFrame({'trading_date':calendar,'target_date':calendar.shift(-20)})
    original = normalize_prices(sources[0]).merge(dates,on='trading_date',validate='many_to_one')
    original = original[np.isfinite(original.close)&original.close.gt(0)].sort_values(['symbol','trading_date']).reset_index(drop=True)
    original['segment'] = original.groupby('symbol').close.transform(lambda s:s.pct_change(fill_method=None).abs().ge(.35).cumsum())
    original = original.merge(ledger[['symbol','trading_date','future_direction']],on=['symbol','trading_date'],validate='one_to_one')
    largest20=cohort.reindex(cohort.future_20_day_return_pct.abs().nlargest(100).index)
    largest20=largest20[['symbol','trading_date','target_date','close','future_20_day_return_pct']].merge(source_keys,on=['symbol','trading_date'])
    largest20=largest20.merge(source_keys.rename(columns={'trading_date':'target_date','id':'target_source_record_id','source_id':'target_source_id'}),on=['symbol','target_date'])
    largest20.to_csv(audit/'largest_absolute_20_session_source_trace.csv',index=False)
    raw = normalize_prices(sources[0]).sort_values(['symbol','trading_date'])
    calendar = pd.to_datetime(sources[1].trading_date)
    raw['excluded_nonpositive_close'] = ~np.isfinite(raw.close) | raw.close.le(0)
    raw['excluded_nonmarket_date'] = ~raw.trading_date.isin(calendar) | raw.trading_date.dt.weekday.ge(5)
    raw.loc[raw.excluded_nonpositive_close | raw.excluded_nonmarket_date].to_csv(audit/'raw_price_exclusions.csv.gz',index=False)
    raw['daily_return_pct'] = raw.groupby('symbol').close.pct_change(fill_method=None)*100
    finite = raw[np.isfinite(raw.daily_return_pct)]
    finite.reindex(finite.daily_return_pct.abs().nlargest(100).index).to_csv(audit/'largest_finite_daily_returns.csv',index=False)
    evidence = [dict(symbol='BML', effective_trading_date='2026-02-02',
        source='https://dps.psx.com.pk/download/attachment/268834-1.pdf',
        finding='PSX N-77 dated 2026-01-19 confirms revised price and shares from 2026-02-02 following 2026-01-31 book closure.',
        decision='Existing >=35% crossing quarantine retained; jump is action-related. No numerical adjustment factor inferred.'),
        dict(symbol='MARI', record_date='2024-09-18', book_closure_start='2024-09-19', credit_date='2024-09-27',
        source='https://dps.psx.com.pk/download/document/236240.pdf',
        credit_source='https://dps.psx.com.pk/download/document/237827.pdf',
        finding='800% bonus entitlement and book closure verified; credit date differs from announcement and ex-trading date.',
        decision='No exact ex-trading date independently confirmed from these documents. Retain quarantine; do not shift on credit date.')]
    write_json(audit/'verified_action_evidence.json',evidence)
    flags = original[['symbol','trading_date','target_date','close','future_direction']].copy()
    flags['missing_target_date'] = original.target_date.isna()
    lookup = original.set_index(['symbol','trading_date']).close
    keys = pd.MultiIndex.from_arrays([original.symbol,original.target_date])
    flags['missing_target_close'] = lookup.reindex(keys).isna().to_numpy()
    flags['crosses_unverified_jump'] = False
    flags['provisional_announcement_window'] = False
    events=[]
    for symbol,bars in original.groupby('symbol'):
        jumps=bars.loc[bars.segment.diff().fillna(0).gt(0),'trading_date']
        for date in jumps:
            mask=original.symbol.eq(symbol)&original.trading_date.lt(date)&original.target_date.ge(date)
            flags.loc[mask,'crosses_unverified_jump']=True
            events.append(dict(symbol=symbol,date=date,kind='unverified >=35% discontinuity',affected_rows=int(mask.sum())))
        payouts=sources[5]
        if not payouts.empty:
            for date in pd.to_datetime(payouts.loc[payouts.symbol.str.upper().eq(symbol),'announcement_date']).unique():
                date=pd.Timestamp(date)
                mask=original.symbol.eq(symbol)&original.trading_date.le(date+pd.Timedelta(days=5))&original.target_date.ge(date-pd.Timedelta(days=5))
                flags.loc[mask,'provisional_announcement_window']=True
                events.append(dict(symbol=symbol,date=date,kind='v1 announcement +/-5 days, NOT verified effective date',affected_rows=int(mask.sum())))
    flags.to_csv(audit/'target_exclusion_reasons.csv.gz',index=False)
    pd.DataFrame(events).to_csv(audit/'quarantine_events.csv',index=False)
    trace=pd.read_csv(audit/'price_source_trace.csv',parse_dates=['trading_date'])
    traced=trace.merge(cohort[['symbol','trading_date','future_direction','sector']],on=['symbol','trading_date'])
    traced.to_csv(audit/'v1_cohort_candle_source_trace.csv',index=False)
    inconsistent=int(traced.inconsistent_candle.sum())
    # Describe every matched feature/weight intervention at the SAME hyperparameters and calibration.
    ablations=[]
    for experiment in ('technical','fundamental','combined'):
        rows=json.loads((out/experiment/'validation.json').read_text())
        by_name={r['name']:r for r in rows}
        for row in rows:
            if row['calibration']!='raw':
                continue
            for change,a,b in [('causal_features','extra0','extra1'),('class_weights','weighted0','weighted1')]:
                if a in row['name'] and row['name'].replace(a,b) in by_name:
                    other=by_name[row['name'].replace(a,b)]
                    ablations.append(dict(experiment=experiment,change=change,base=row['name'],variant=other['name'],
                        delta_mean_macro_f1=other['mean_macro_f1']-row['mean_macro_f1'],
                        delta_mean_log_loss=other['mean_log_loss']-row['mean_log_loss']))
    pd.DataFrame(ablations).to_csv(out/'ablations.csv',index=False)
    dataset=json.loads((audit/'dataset_audit.json').read_text())
    source=json.loads((audit/'source_audit.json').read_text())
    splits=json.loads((out/'splits.json').read_text())
    lines=['# PSXpert combined_v2 results','',
        f"Rebuilt {dataset['v2_rows']:,} common eligible rows with fixed 20-market-session targets and inclusive sideways boundaries [-3%, +3%]. All three experiments use identical row keys and partitions.",'',
        f"The v1 eligible cohort contains **{inconsistent} inconsistent candles**, traced to source primary keys in `audit/v1_cohort_candle_source_trace.csv`. Across all raw source history, {source['inconsistent_candles_all_source']:,} candles were flagged. OHL fields are masked only in memory; positive closes and volumes are retained. No raw prices were numerically adjusted.",'',
        '## Audit and limitations','',
        'Largest daily moves are traced to original IDs and source names. Large moves below the discontinuity threshold remain in the data. No large move was independently certified as economically genuine: pyPSX credentials/coverage status is recorded in source_audit.json. Unresolved >=35% jumps retain the v1 segment reset and label quarantine. This deliberately avoids guessing split factors, but may exclude genuine moves. The full target-exclusion ledger distinguishes missing endpoints, discontinuity exposure, and provisional announcement windows.','',
        'Corporate payouts contain announcement dates but no effective/ex-dates or adjustment factors. The external PSX notice verifies BML revised-price trading from February 2, 2026; this confirms the existing jump quarantine. MARI bonus entitlement, book closure and credit dates were checked, but these do not establish its exact ex-trading date. See verified_action_evidence.json for primary-source URLs. Remaining effective dates have not been independently verified. The v1 announcement +/-5-day quarantine remains provisional. Thus the requested corporate-action validation is incomplete, and these results are conditional on that limitation.','',
        'Financial joins were checked against eligible annual-report transmission evidence, with publication availability at or before every prediction. Source financial metrics, announcements, accepted panel and row-level joins are saved. Missingness is broken down by ticker, sector and year, including tickers without eligible filings. Current statement snapshots cannot prove historical accounting vintages; the current roster also introduces survivorship risk.','',
        '## Validation protocol','',
        'Three expanding market-wide folds use distinct training, calibration and forward validation windows. Target resolution must precede each following window by more than five market sessions. Imputation, scaling, class weights and estimator parameters are fitted using training data only. Candidates cover the training-majority baseline, the raw v1 recipe refitted per fold, regularized logistic regression and a small XGBoost grid. Macro F1 selects the configuration, with log loss breaking ties. Calibration is accepted only if every window improves log loss and no class loses more than two recall percentage points.','',
        'Walk-forward scores below are model-selection results, not an unbiased nested assessment. The saved raw v1 model is compared only on its historical test keys. A newly refitted v1 recipe provides the leakage-safe walk-forward comparison.','',
        f"Fresh eligible rows after the inspected v1 outcomes and embargo: **{splits['fresh_eligible_rows']}**. Fresh held-out performance {'was assessed' if result['fresh_held_out_verified'] else 'remains unverified'}.",'',
        '## Walk-forward model-selection results','',
        '| Experiment | Selected | Accuracy | Balanced accuracy | Macro F1 | Log loss | Majority accuracy | V1 recipe accuracy |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for name,v in result['experiments'].items():
        w=v['walk_forward']
        lines.append(f"| {name} | {v['selected']['name']} | {w['accuracy']:.2%} | {w['balanced_accuracy']:.2%} | {w['macro_f1']:.4f} | {w['log_loss']:.4f} | {v['majority:raw']['accuracy']:.2%} | {v['v1_recipe:raw']['accuracy']:.2%} |")
    lines+=['','## Inspected historical v1 benchmark','','These comparisons use identical historical rows and unchanged targets. V2 model selection used overlapping dates, so these are descriptive comparisons.','','| Experiment | Rows | V2 accuracy | Training-majority accuracy | Saved raw v1 accuracy | V2 minus v1 |','|---|---:|---:|---:|---:|---:|']
    for name,v in result['experiments'].items():
        h=v['historical_v2']; b=v['historical_training_majority']; r=v['historical_raw_v1']
        lines.append(f"| {name} | {h['rows']} | {h['accuracy']:.2%} | {b['accuracy']:.2%} | {r['accuracy']:.2%} | {100*(h['accuracy']-r['accuracy']):+.2f} pp |")
    lines+=['','## What helped','']
    a=pd.DataFrame(ablations)
    for (experiment,change),g in a.groupby(['experiment','change']):
        lines.append(f"- {experiment}, {change}: mean paired change in validation macro F1 {g.delta_mean_macro_f1.mean():+.4f}; log loss {g.delta_mean_log_loss.mean():+.4f}. Individual paired results are in ablations.csv; an average does not imply every candidate improved.")
    lines+=['','The audit masking change was not isolated in a separate full model ablation, so its predictive contribution cannot be attributed. It makes the candle treatment explicit. Per-class recall, confusion matrices, predicted class frequencies, log loss and regressor errors are saved in each experiment comparison.json.','','## Reproduction','','Run from `module 1 technical and fundamental`:','','```powershell','python -m pytest -q','python -m m1.v2 --as-of 2026-11-16T14:00:00+05:00','python -m m1.v2_report','python -m m1.v2_verify','```','','The training command refuses an existing combined_v2 directory. Reproduce in a separate checkout with the same read-only source snapshot. The PostgreSQL connection enforces read-only transactions. Before/after SHA-256 manifests cover existing CSVs, SQLite data and combined_v1 artifacts. The v1 serving API is preserved; load v2 research classifier/calibrator and regressor using `m1.v2.load_pair`.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))

if __name__=='__main__':
    main()
