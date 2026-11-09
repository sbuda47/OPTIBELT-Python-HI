from pathlib import Path

import pytest
import yaml

from optibelt_hi.configuration import load_config

CONFIG = Path(__file__).resolve().parents[1] / "configs/preprocessing.yaml"


def test_active_config_is_valid():
    assert load_config(CONFIG)["target_rate_hz"] == 25600


@pytest.mark.parametrize("field,value", [
    ("invalid_samples", "interpolate"),
    ("native_rates_hz", [100000] * 5),
    ("window_seconds", float("nan")),
    ("hop_seconds", 0),
    ("window_seconds", True),
])
def test_unimplemented_or_invalid_policies_cannot_be_silently_ignored(tmp_path, field, value):
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8-sig"))
    config[field] = value
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError):
        load_config(path)

