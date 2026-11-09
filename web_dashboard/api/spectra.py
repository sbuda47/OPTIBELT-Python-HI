"""Offline spectral inspection. This module does not participate in HI scoring."""
import numpy as np
from scipy import signal
from scipy.fft import rfft, rfftfreq


def validate_band(band, rate):
    if band is None or len(band)!=2:
        raise ValueError('Choose both envelope filter limits after inspecting the vibration spectrum.')
    low,high=band
    if not np.isfinite([low,high]).all() or not 10<=low<high<rate/2 or high-low<50:
        raise ValueError(f'Envelope band must start at least at 10 Hz, span at least 50 Hz and end below {rate/2:g} Hz.')
    return float(low),float(high)


def compute_spectrum(values, rate, mode='fft', band=None, core=None):
    x=np.asarray(values,dtype=np.float64)
    if x.ndim!=1 or len(x)<32 or not np.isfinite(x).all() or not np.isfinite(rate) or rate<=0:
        raise ValueError('A spectrum needs a finite one-dimensional signal and a positive sampling rate.')
    if mode not in ('fft','envelope'):
        raise ValueError('Choose FFT or envelope spectrum.')
    first,last=core if core is not None else (0,len(x))
    if not 0<=first<last<=len(x) or last-first<32:
        raise ValueError('Invalid analysis sample interval.')
    processing=['Remove selected-segment mean','Periodic Hann window','One-sided peak-amplitude FFT; coherent-gain correction; no zero-padding']
    if mode=='envelope':
        low,high=validate_band(band,rate)
        sos=signal.butter(4,[low,high],btype='bandpass',fs=rate,output='sos')
        filtered=signal.sosfiltfilt(sos,x-x.mean())
        x=np.abs(signal.hilbert(filtered))[first:last]
        processing=['Remove context-signal mean','Butterworth band-pass (fourth-order prototype), forward/backward zero-phase filtering','Hilbert amplitude envelope on context signal','Crop selected segment','Remove envelope mean',*processing[1:]]
    else:
        x=x[first:last]
    count=len(x);window=signal.windows.hann(count,sym=False)
    amplitudes=np.abs(rfft((x-x.mean())*window))/window.sum()
    amplitudes[1:]*=2
    if count%2==0:amplitudes[-1]/=2
    frequencies=rfftfreq(count,1/rate)
    # Measured local maxima, not diagnostic thresholds or fault classifications.
    peak_indices,_=signal.find_peaks(amplitudes,prominence=float(amplitudes.max())*.01)
    peak_indices=sorted(peak_indices,key=lambda i:float(amplitudes[i]),reverse=True)[:20]
    peaks=[dict(frequency_hz=float(frequencies[i]),amplitude=float(amplitudes[i])) for i in peak_indices]
    return dict(frequencies=frequencies.tolist(),amplitudes=amplitudes.tolist(),peaks=peaks,
                rate=rate,sample_count=count,bin_spacing_hz=rate/count,nyquist_hz=rate/2,
                units='Native source units (peak amplitude)',scaling='one-sided peak amplitude',
                window='Hann (periodic)',processing=processing,mode=mode,
                band_hz=list(band) if mode=='envelope' else None)
