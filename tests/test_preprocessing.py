import numpy as np
import pytest

from optibelt_hi.preprocessing.signals import common_rate, window_bounds


def test_rate_conversion_preserves_frequency_duration_and_channel_alignment():
    native_rates = [25600, 25600, 100000, 100000, 100000]
    channels = [np.sin(2 * np.pi * 1000 * np.arange(2 * fs) / fs) for fs in native_rates]
    result = common_rate(channels)
    assert result.shape == (51200, 5)
    np.testing.assert_array_equal(result[:, 0], channels[0])
    np.testing.assert_array_equal(result[:, 1], channels[1])
    np.testing.assert_allclose(result[100:-100, 2], result[100:-100, 0], atol=.002)
    frequency = np.fft.rfftfreq(len(result), 1 / 25600)[np.argmax(np.abs(np.fft.rfft(result[:, 2])))]
    assert frequency == 1000
    assert list(window_bounds(len(result))) == [(0, 51200)]


def test_current_above_new_nyquist_is_attenuated():
    fs = 100000
    signal = np.sin(2 * np.pi * 30000 * np.arange(fs) / fs)
    result = common_rate([signal], rates=[fs])[:, 0]
    assert np.sqrt(np.mean(result[100:-100] ** 2)) < .01


def test_resampling_never_bridges_missing_samples():
    with pytest.raises(ValueError, match="finite"):
        common_rate([np.array([1., np.nan, 2.])], rates=[100000])


def test_different_durations_require_investigation():
    with pytest.raises(ValueError, match="durations"):
        common_rate([np.arange(25600), np.arange(90000)], rates=[25600, 100000])


def test_windowing_never_pads_a_tail_or_crosses_a_recording():
    assert list(window_bounds(6, rate=2, window_seconds=2, hop_seconds=1)) == [(0, 4), (2, 6)]
    assert list(window_bounds(5, rate=2, window_seconds=2, hop_seconds=1)) == [(0, 4)]
    assert list(window_bounds(3, rate=2, window_seconds=2, hop_seconds=1)) == []


@pytest.mark.parametrize("duration", [0, -1, .25])
def test_invalid_window_duration(duration):
    with pytest.raises(ValueError):
        list(window_bounds(10, rate=2, window_seconds=duration))

