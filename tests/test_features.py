import numpy as np
import pytest

def api():
    from optibelt_hi.features.core import channel_features, extract_windows, FEATURE_NAMES
    return channel_features, extract_windows, FEATURE_NAMES

def sine(freq=1000, amp=2, offset=3):
    t = np.arange(51200) / 25600
    return offset + amp * np.sin(2*np.pi*freq*t)

def test_offset_sine_has_analytic_statistics():
    channel, _, names = api()
    out = channel(sine())
    assert list(out) == list(names)
    assert out["mean"] == pytest.approx(3)
    assert out["rms"] == pytest.approx(np.sqrt(11))
    assert out["ac_rms"] == pytest.approx(np.sqrt(2))
    assert out["peak_to_peak"] == pytest.approx(4)
    assert out["crest_factor_ac"] == pytest.approx(np.sqrt(2))
    assert out["skewness"] == pytest.approx(0, abs=1e-12)
    assert out["kurtosis_pearson"] == pytest.approx(1.5)
    assert out["spectral_centroid_hz"] == pytest.approx(1000, abs=1e-8)

def test_spectral_bands_are_power_fractions():
    channel, _, _ = api()
    t=np.arange(51200)/25600
    out=channel(np.sin(2*np.pi*100*t)+2*np.sin(2*np.pi*3000*t))
    assert out["power_fraction_0_200"] == pytest.approx(.2)
    assert out["power_fraction_1000_5000"] == pytest.approx(.8)
    assert sum(v for k,v in out.items() if k.startswith("power_fraction")) == pytest.approx(1)
    assert out["spectral_centroid_hz"] == pytest.approx(2420, abs=1e-7)

def test_scale_and_offset_only_change_expected_features():
    channel, _, _ = api()
    a=channel(sine(offset=0)); b=channel(4*sine(offset=0)+7)
    assert b["mean"] == pytest.approx(7)
    for name in ("ac_rms","peak_to_peak"):
        assert b[name] == pytest.approx(4*a[name])
    for name in ("crest_factor_ac","skewness","kurtosis_pearson","spectral_centroid_hz","power_fraction_1000_5000"):
        assert b[name] == pytest.approx(a[name],abs=1e-10)

@pytest.mark.parametrize("x", [np.zeros(10), np.ones(10), np.array([0,1,np.nan,2]), np.array([0,1,np.inf,2]), np.ones((2,5)), np.array([1+1j,2+2j,3+3j,4+4j]), np.array([1.,2.,3.])])
def test_invalid_and_undefined_signal_rejected(x):
    channel, _, _ = api()
    with pytest.raises(ValueError):
        channel(x)

def test_feature_windows_are_separate_and_complete():
    _, extract, names=api()
    t=np.arange(25600*3+100)/25600
    data=np.column_stack([(i+1)*np.sin(2*np.pi*(100+i*300)*t) for i in range(5)])
    before=data.copy()
    result, bounds, columns=extract(data)
    assert result.shape == (2,60)
    assert bounds == [(0,51200),(25600,76800)]
    assert columns[0] == "vibration__mean"
    assert columns[-1] == "current_t__power_fraction_5000_12800"
    assert len(set(columns)) == 5*len(names)
    assert np.isfinite(result).all()
    np.testing.assert_array_equal(data,before)

def test_short_recording_cannot_silently_create_empty_features():
    _,extract,_=api()
    with pytest.raises(ValueError,match="complete window"):
        extract(np.zeros((100,5)))

