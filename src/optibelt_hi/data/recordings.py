"""Decode the source MAT matrix while retaining native channel rates."""
from contextlib import contextmanager
from pathlib import Path
import re

import h5py
import numpy as np
from scipy.io import loadmat

CHANNELS = ("vibration", "torque", "current_r", "current_s", "current_t")
RATES = (25600, 25600, 100000, 100000, 100000)
DURATIONS = {"invariant_speed": 300, "varying_speed": 120}
NAME = re.compile(
    r"^(?P<condition>Normal|Bearing|Coil|Interturn|Misalign|Journal)"
    r"(?P<severity>[^_]*)_(?P<hp>\d+(?:p\d+)?)HP_"
    r"(?P<load>\d+)%(?:_(?P<upper>\d+)Hz)?$", re.IGNORECASE
)


def metadata(path: Path):
    match = NAME.fullmatch(path.stem)
    if match is None or path.parent.name not in DURATIONS:
        raise ValueError(f"Unrecognized recording name or speed folder: {path}")
    fields = match.groupdict()
    return {
        "condition": fields["condition"].casefold(),
        "severity_label": fields["severity"],
        "motor_capacity_hp": float(fields["hp"].replace("p", ".")),
        "load_percent_label": int(fields["load"]),
        "speed_profile": path.parent.name,
        "supply_low_hz": 50,
        "supply_high_hz": int(fields["upper"] or 50),
        "expected_duration_s": DURATIONS[path.parent.name],
        "acquisition_run_id": None,
        "physical_motor_id": None,
    }


@contextmanager
def matrix(path: Path):
    """Yield data in stored orientation; never transpose a file by guesswork."""
    if h5py.is_hdf5(path):
        with h5py.File(path, "r") as handle:
            if "data" not in handle:
                raise ValueError(f"Missing data variable: {path}")
            yield handle["data"]
    else:
        content = loadmat(path, variable_names=["data"], verify_compressed_data_integrity=True)
        if "data" not in content:
            raise ValueError(f"Missing data variable: {path}")
        yield content["data"]


def validate_matrix(data):
    if data.ndim != 2 or data.shape[1] != 5:
        raise ValueError(f"Expected an N x 5 matrix, found {data.shape}")
    if data.dtype.kind not in "fiu":
        raise ValueError(f"Expected real numeric samples, found {data.dtype}")


def profile_channel(values, rate, expected_samples):
    values = np.asarray(values)
    prefix = values[:expected_samples]
    finite = np.isfinite(prefix)
    available = prefix[finite]
    missing = int(expected_samples - available.size)
    tail = values[expected_samples:]
    padding_ok = bool(np.isnan(tail).all())
    flat = bool(available.size > 0 and np.ptp(available) == 0)
    return {
        "native_rate_hz": rate,
        "expected_samples": expected_samples,
        "stored_rows": len(values),
        "finite_native_samples": int(available.size),
        "missing_native_samples": missing,
        "native_nan_samples": int(np.isnan(prefix).sum()),
        "native_infinite_samples": int(np.isinf(prefix).sum()),
        "padding_rows": len(tail),
        "padding_is_all_nan": padding_ok,
        "all_missing": available.size == 0,
        "constant_available_samples": flat,
        "minimum": float(available.min()) if available.size else None,
        "maximum": float(available.max()) if available.size else None,
        "mean": float(available.mean()) if available.size else None,
        "std": float(available.std()) if available.size else None,
        "usable": missing == 0 and padding_ok and not flat,
    }


def native_channels(path: Path, duration_s):
    """Load complete native channels; missing data is never fabricated."""
    channels = []
    with matrix(path) as data:
        validate_matrix(data)
        for index, (name, rate) in enumerate(zip(CHANNELS, RATES, strict=True)):
            values = np.asarray(data[:, index])
            expected = round(duration_s * rate)
            profile = profile_channel(values, rate, expected)
            if not profile["usable"]:
                raise ValueError(
                    f"{path.name}/{name} is unusable: "
                    f"{profile['missing_native_samples']} missing samples, "
                    f"constant={profile['constant_available_samples']}, "
                    f"padding_valid={profile['padding_is_all_nan']}"
                )
            channels.append(np.array(values[:expected], dtype=np.float64, copy=True))
    return channels

