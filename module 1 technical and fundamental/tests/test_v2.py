import numpy as np
import pandas as pd
import pytest
from m1.v2 import (metrics, calibration_fit, calibrate, calibration_allowed, partition,
                   feature_extras, fit, probabilities, configs)
from m1.features import directions


def test_fixed_boundaries():
    assert directions(pd.Series([-3.01,-3,0,3,3.01])).tolist() == ['BEARISH','SIDEWAYS','SIDEWAYS','SIDEWAYS','BULLISH']


def test_global_purge_embargo():
    n=800
    frame=pd.DataFrame({'session':np.repeat(np.arange(n),3),
                        'target_session':np.repeat(np.arange(n)+20,3),
                        'future_direction':['BEARISH','SIDEWAYS','BULLISH']*n})
    train,cal,valid=partition(frame,300,450,650)
    assert train.target_session.max()<cal.session.min()-5
    assert cal.target_session.max()<valid.session.min()-5
    assert valid.target_session.max()<650-5
    assert set(train.session).isdisjoint(cal.session)


def test_calibration_guard_rejects_collapse():
    y=np.tile([0,1,2],30)
    p=np.tile([.33,.33,.34],(90,1))
    raw=metrics(y,np.eye(3)[y]*.3+.7/3)
    collapse=metrics(y,p)
    assert not calibration_allowed([raw],[collapse])
    improved={**raw,'log_loss':raw['log_loss']-.01}
    assert calibration_allowed([raw],[improved])


def test_temperature_preserves_argmax():
    rng=np.random.default_rng(1)
    p=rng.dirichlet([1,1,1],size=90)
    y=np.tile([0,1,2],30)
    t=calibration_fit(p,y,'temperature')
    q=calibrate(p,t)
    np.testing.assert_array_equal(p.argmax(1),q.argmax(1))
    np.testing.assert_allclose(q.sum(1),1)


def test_majority_uses_training_only():
    data=pd.DataFrame({'future_direction':['BEARISH']*8+['SIDEWAYS','BULLISH']})
    m=fit(data,[],configs()[0])
    assert probabilities(m,pd.DataFrame(index=range(5)),[]).argmax(1).tolist()==[0]*5


def test_causal_extras_do_not_change_past(fixtures):
    _,_,frame,_=fixtures
    dates=frame.trading_date.drop_duplicates().sort_values()
    index=pd.DataFrame({'trading_date':dates,'close':100+np.arange(len(dates))})
    first=feature_extras(frame,index)
    index.loc[index.index[-1],'close']=1000000
    second=feature_extras(frame,index)
    cols=['relative_return_5','relative_return_20','relative_volume_prior20','filing_age_days']
    pd.testing.assert_frame_equal(first.loc[first.trading_date.lt(dates.max()),cols],second.loc[second.trading_date.lt(dates.max()),cols])


def test_logistic_handles_missing_features_and_roundtrip(tmp_path):
    import joblib
    frame=pd.DataFrame({'x':[np.nan]*60,'y':np.tile([1,2,3],20),
                        'future_direction':['BEARISH','SIDEWAYS','BULLISH']*20})
    config=next(c for c in configs() if c['kind']=='logistic')
    model=fit(frame,['x','y'],config)
    before=probabilities(model,frame,['x','y'])
    joblib.dump(model,tmp_path/'model.joblib')
    np.testing.assert_allclose(before,probabilities(joblib.load(tmp_path/'model.joblib'),frame,['x','y']))
