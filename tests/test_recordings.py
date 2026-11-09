from pathlib import Path

import h5py
import numpy as np
import pytest
from scipy.io import savemat

from optibelt_hi.data.recordings import matrix, metadata, native_channels, profile_channel, validate_matrix


@pytest.mark.parametrize("name,condition,load,hp", [
    ("Coil60%_3HP_30%.mat", "coil", 30, 3),
    ("Interturn60%_3HP_0%.mat", "interturn", 0, 3),
    ("Journal0p85um_7p5HP_0%.mat", "journal", 0, 7.5),
    ("Bearing_3HP_30%.mat", "bearing", 30, 3),
])
def test_labels_preserve_fault_and_load(name, condition, load, hp):
    result = metadata(Path("invariant_speed") / name)
    assert (result["condition"], result["load_percent_label"], result["motor_capacity_hp"]) == (condition, load, hp)


def test_variable_frequency_is_profile_upper_bound():
    result = metadata(Path("varying_speed/Normal_1HP_0%_52Hz.mat"))
    assert (result["supply_low_hz"], result["supply_high_hz"]) == (50, 52)


def test_unknown_labels_never_become_healthy():
    with pytest.raises(ValueError, match="Unrecognized"):
        metadata(Path("invariant_speed/Unknown_3HP_0%.mat"))


@pytest.mark.parametrize("kind", ["mat5", "hdf5"])
def test_matrix_formats(tmp_path, kind):
    path = tmp_path / "sample.mat"
    expected = np.arange(50, dtype=float).reshape(10, 5)
    if kind == "mat5":
        savemat(path, {"data": expected})
    else:
        with h5py.File(path, "w") as f:
            f.create_dataset("data", data=expected)
    with matrix(path) as data:
        validate_matrix(data)
        np.testing.assert_array_equal(data[:], expected)


def test_orientation_requires_explicit_schema():
    with pytest.raises(ValueError, match="N x 5"):
        validate_matrix(np.ones((5, 10)))


def test_trailing_padding_differs_from_internal_missingness():
    valid = np.array([1., 0., 2., 0., np.nan, np.nan])
    result = profile_channel(valid, 2, 4)
    assert result["usable"] and result["padding_rows"] == 2
    valid[1] = np.nan
    result = profile_channel(valid, 2, 4)
    assert not result["usable"] and result["missing_native_samples"] == 1


def test_missing_sensor_is_rejected():
    result = profile_channel(np.full(20, np.nan), 10, 10)
    assert result["all_missing"] and not result["usable"]


def test_zeros_after_native_end_are_not_assumed_padding():
    result = profile_channel(np.array([1., 2., 3., 4., 0., 0.]), 2, 4)
    assert not result["padding_is_all_nan"] and not result["usable"]


def test_native_loader_preserves_rates_and_does_not_fill_missing(tmp_path):
    path = tmp_path / "sample.mat"
    x = np.full((1000, 5), np.nan)
    x[:256, 0] = np.linspace(-1, 1, 256)
    x[:256, 1] = np.linspace(0, 5, 256)
    x[:, 2:] = np.arange(1000)[:, None]
    savemat(path, {"data": x})
    channels = native_channels(path, .01)
    assert [len(c) for c in channels] == [256, 256, 1000, 1000, 1000]
    np.testing.assert_array_equal(channels[0], x[:256, 0])
    x[10, 0] = np.nan
    savemat(path, {"data": x})
    with pytest.raises(ValueError, match="missing samples"):
        native_channels(path, .01)

