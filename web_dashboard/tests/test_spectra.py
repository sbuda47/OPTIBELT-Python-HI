import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from api.spectra import compute_spectrum

def test_fft_amplitude_frequency_offset_and_nyquist():
    rate=25600;t=np.arange(rate*2)/rate
    y=12+3*np.sin(2*np.pi*123*t)+.4*np.cos(np.pi*np.arange(len(t)))
    result=compute_spectrum(y,rate)
    f=np.array(result['frequencies']);a=np.array(result['amplitudes'])
    assert f[np.argmax(a)]==123
    assert a[f==123][0]==pytest.approx(3,abs=1e-10)
    assert a[-1]==pytest.approx(.4,abs=1e-10)
    assert a[0]<1e-10
    assert result['bin_spacing_hz']==.5
    assert result['peaks'][0]['frequency_hz']==123

def test_envelope_recovers_modulation_frequency_and_amplitude():
    rate=25600;t=np.arange(rate*4)/rate
    y=(1+.3*np.cos(2*np.pi*37*t))*np.cos(2*np.pi*4000*t)
    result=compute_spectrum(y,rate,mode='envelope',band=(3000,5000),core=(rate,rate*3))
    f=np.array(result['frequencies']);a=np.array(result['amplitudes'])
    assert f[np.argmax(a)]==37
    assert a[f==37][0]==pytest.approx(.3,rel=.01)
    assert a[0]<1e-7
    assert result['sample_count']==rate*2

@pytest.mark.parametrize('band',[(0,5000),(5000,3000),(3000,12800),(3000,3020),(float('nan'),4000)])
def test_invalid_envelope_bands(band):
    with pytest.raises(ValueError):compute_spectrum(np.ones(51200),25600,mode='envelope',band=band)

def test_flat_and_nonfinite_signals():
    result=compute_spectrum(np.ones(51200),25600)
    assert result['peaks']==[]
    assert max(result['amplitudes'])==0
    with pytest.raises(ValueError):compute_spectrum([1,float('nan'),2],25600)

def test_length_controls_bin_spacing():
    for seconds in [2,5,10]:
        result=compute_spectrum(np.zeros(25600*seconds),25600)
        assert result['bin_spacing_hz']==pytest.approx(1/seconds)
        assert len(result['frequencies'])==25600*seconds//2+1
