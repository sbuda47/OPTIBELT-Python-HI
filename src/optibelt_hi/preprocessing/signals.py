"""Offline preparation on the common 25.6 kHz clock."""
from fractions import Fraction

import numpy as np
from scipy.signal import resample_poly

from optibelt_hi.data.recordings import CHANNELS, RATES, native_channels


def common_rate(channels, rates=RATES, target_rate=25600):
    if len(channels) != len(rates) or not channels:
        raise ValueError("Each channel needs its native rate.")
    if target_rate <= 0 or any(rate <= 0 for rate in rates):
        raise ValueError("Sampling rates must be positive.")
    result = []
    for values, rate in zip(channels, rates, strict=True):
        values = np.asarray(values)
        if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
            raise ValueError("Resampling requires a finite, nonempty one-dimensional signal.")
        ratio = Fraction(target_rate, rate)
        result.append(values.copy() if ratio == 1 else resample_poly(
            values, ratio.numerator, ratio.denominator,
            window=("kaiser", 5.0), padtype="line"
        ))
    lengths = {len(values) for values in result}
    if len(lengths) != 1:
        raise ValueError(f"Channel durations disagree after rate conversion: {sorted(lengths)}")
    return np.column_stack(result)


def window_bounds(n_samples, rate=25600, window_seconds=2.0, hop_seconds=1.0):
    if rate <= 0 or window_seconds <= 0 or hop_seconds <= 0 or n_samples < 0:
        raise ValueError("Invalid sampling rate, duration, hop or sample count.")
    length_float, hop_float = rate * window_seconds, rate * hop_seconds
    length, hop = round(length_float), round(hop_float)
    if length < 1 or hop < 1 or abs(length - length_float) > 1e-8 or abs(hop - hop_float) > 1e-8:
        raise ValueError("Window and hop must be whole numbers of samples.")
    for start in range(0, n_samples - length + 1, hop):
        yield start, start + length


def prepare_recording(path, duration_s):
    return common_rate(native_channels(path, duration_s))

