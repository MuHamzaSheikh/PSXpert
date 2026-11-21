"""Verify saved v2 models and persist the separate inspected-history refit."""
import json
import joblib
import numpy as np
import pandas as pd
from .settings import ROOT
from .training import encode,write_json
from .v2 import load_pair, probabilities, calibrate, fit, calibration_fit, metrics, configs


def main():
    out=ROOT/'artifacts/combined_v2'
    data=pd.read_csv(out/'eligible_rows.csv.gz',parse_dates=['trading_date'])
    checks={}
    for experiment in ('technical','fundamental','combined'):
        report=json.loads((out/experiment/'comparison.json').read_text())
        saved=pd.read_csv(out/experiment/'walk_forward_predictions.csv',parse_dates=['trading_date'])
        terminal=saved[saved.fold.eq(saved.fold.max())]
        rows=terminal[['symbol','session']].merge(data,on=['symbol','session'],validate='one_to_one')
        bundle,reg=load_pair(experiment)
        p=calibrate(probabilities(bundle['classifier'],rows,bundle['features']),bundle['calibrator'])
        np.testing.assert_allclose(p,terminal[['p_bearish','p_sideways','p_bullish']],rtol=1e-6,atol=1e-7)
        assert np.isfinite(reg.predict(rows[bundle['features']])).all()
        # Keep the historical refit distinct from the terminal walk-forward artifact.
        boundary=int(rows.session.min())
        train=data[data.target_session.lt(boundary-110-5)]
        cal=data[data.session.ge(boundary-110)&data.target_session.lt(boundary-5)]
        selected=report['selected']
        model=fit(train,selected['features'],selected['configuration'])
        fitted=calibration_fit(probabilities(model,cal,selected['features']),encode(cal.future_direction),selected['calibration'])
        hp=calibrate(probabilities(model,rows,selected['features']),fitted)
        m=metrics(encode(rows.future_direction),hp)
        for key in ('accuracy','balanced_accuracy','macro_f1','log_loss'):
            np.testing.assert_allclose(m[key],report['historical_v2'][key],atol=1e-6)
        target=out/experiment/'historical_benchmark'
        target.mkdir(exist_ok=False)
        joblib.dump(dict(classifier=model,calibrator=fitted,features=selected['features']),target/'classifier.joblib')
        pred=rows[['symbol','session','trading_date','future_direction']].copy()
        pred[['p_bearish','p_sideways','p_bullish']]=hp
        pred.to_csv(target/'predictions.csv',index=False)
        write_json(target/'metadata.json',dict(note='Inspected historical benchmark; not fresh holdout',
            train_rows=len(train),calibration_rows=len(cal),train_last_target=int(train.target_session.max()),
            calibration_last_target=int(cal.target_session.max()),evaluation_first_session=boundary,
            selected=selected['name']))
        checks[experiment]=dict(saved_classifier_matches_terminal_predictions=True,regressor_finite=True,
                                historical_refit_reproduces_report=True,rows=len(rows))
    before=json.loads((out/'preservation_before.json').read_text())
    after=json.loads((out/'preservation_after.json').read_text())
    assert before==after
    write_json(out/'artifact_verification.json',dict(experiments=checks,protected_files_unchanged=len(before)))
    print(json.dumps(checks,indent=2))

if __name__=='__main__':
    main()
