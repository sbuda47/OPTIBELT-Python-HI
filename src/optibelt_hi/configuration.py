"""Validate the small, explicit preprocessing contract."""
import math
from pathlib import Path

import yaml

from .data.recordings import CHANNELS, RATES


def load_config(path: Path):
    config = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    required = {
        "schema_version", "channels", "native_rates_hz", "target_rate_hz",
        "window_seconds", "hop_seconds", "filter", "invalid_samples",
        "flat_channels", "trailing_padding", "alignment",
    }
    if not isinstance(config, dict) or set(config) != required:
        raise ValueError("Unknown or missing preprocessing configuration fields.")
    fixed = {
        "schema_version": 1,
        "channels": list(CHANNELS), "native_rates_hz": list(RATES),
        "target_rate_hz": 25600,
        "filter": {"method": "resample_poly", "window": ["kaiser", 5.0], "padtype": "line"},
        "invalid_samples": "reject_recording", "flat_channels": "reject_recording",
        "trailing_padding": "nan_only_after_expected_native_samples",
        "alignment": "common_start_reported_by_source",
    }
    for name, value in fixed.items():
        if config[name] != value:
            raise ValueError(f"Unsupported preprocessing setting: {name}")
    for name in ("window_seconds", "hop_seconds"):
        value = config[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be positive and finite.")
        samples = value * config["target_rate_hz"]
        if not math.isclose(samples, round(samples), rel_tol=0, abs_tol=1e-8) or samples < 1:
            raise ValueError(f"{name} must represent a whole number of samples.")
    return config

