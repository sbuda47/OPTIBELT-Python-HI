import numpy as np
import pytest

def api():
    from optibelt_hi.monitoring.health import calibrate, health_index, ewma, persistent_alarm
    return calibrate,health_index,ewma,persistent_alarm

def test_calibration_equal_record_weights_and_no_interpolation():
    cal,_,_,_=api()
    assert cal([np.array([0.,1.]),np.array([10.])],quantile=.75)==10
    assert cal([np.tile([0.,1.],20),np.array([10.])],quantile=.75)==10
    assert cal([np.arange(1.,101.)])==99

def test_health_is_bounded_monotone_and_threshold_is_fifty():
    _,hi,_,_=api()
    result=hi(np.array([0.,5.,10.,20.,1e200]),10.)
    assert result[0]==100 and result[2]==pytest.approx(50)
    assert np.all(np.diff(result)<0) and np.all((result>=0)&(result<=100))
    with pytest.raises(ValueError): hi(np.array([1.]),0)

def test_ewma_causal_prefix_reset_and_step_response():
    _,_,smooth,_=api()
    short=np.array([0.,1.,1.])
    np.testing.assert_allclose(smooth(short),[0.,.2,.36])
    np.testing.assert_array_equal(smooth(np.r_[short,99.,-20.])[:3],smooth(short))
    np.testing.assert_array_equal(smooth(np.array([5.,5.])),[5.,5.])
    result=smooth(np.r_[0.,np.ones(11)])
    assert result[-2]<.9 and result[-1]>=.9

def test_persistent_alarm_requires_consecutive_windows():
    _,_,_,alarm=api()
    np.testing.assert_array_equal(alarm(np.array([True,True,False,True,True,True,True])),
                                  [False,False,False,False,False,True,True])

@pytest.mark.parametrize("x",[np.array([]),np.array([1.,np.nan]),np.array([np.inf])])
def test_invalid_monitoring_inputs_rejected(x):
    cal,hi,smooth,_=api()
    for function in (lambda:cal([x]),lambda:hi(x,1),lambda:smooth(x)):
        with pytest.raises(ValueError): function()

