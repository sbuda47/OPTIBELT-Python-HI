"""Controlled load-only references and healthy calibration; no HP routing."""
import numpy as np
from .baseline import Model, fit_model, matrix
from .operating_v2 import blocks, event_level
from optibelt_hi.monitoring.health import ewma, health_index, persistent_alarm

ARMS = {"A": ("pooled", "global"), "B": ("pooled", "load"),
        "C": ("load_centred", "global"), "D": ("load_centred", "load")}
SETTINGS = {"format": "load_only_experiment_1", "loads": [0, 30, 60],
            "episode_windows": 25, "episode_stride": 29, "warmup_windows": 10,
            "alpha": .2, "persistence": 3, "shrinkage": .1, "correlation_limit": .98,
            "relative_scale_floor": 1e-12, "drop_suffixes": ["rms", "power_fraction_5000_12800"]}


def calibration_episodes(bounds, duration):
    blocks(bounds, duration)  # Validate the existing guarded temporal contract.
    b = np.asarray(bounds)
    indices = np.flatnonzero((b[:, 0] >= round((.5*duration+2)*25600)) &
                             (b[:, 1] <= round((.75*duration-2)*25600)))
    if not np.all(np.diff(b[:, 0]) == 25600) or not np.all(b[:, 1]-b[:, 0] == 51200):
        raise ValueError("Expected consecutive two-second windows with one-second hop.")
    return [indices[i:i+25] for i in range(0, len(indices)-24, 29)]


def build_bank(healthy, names):
    if not healthy or any(e["condition"] != "normal" for e in healthy):
        raise ValueError("Only healthy recordings may fit/calibrate.")
    ordered = sorted(healthy, key=lambda e: e["recording_id"])
    if len({e["recording_id"] for e in ordered}) != len(ordered):
        raise ValueError("Duplicate healthy recording.")
    if {e["load"] for e in ordered} != {0, 30, 60}:
        raise ValueError("Need healthy coverage of exactly 0, 30 and 60 percent loads.")
    fitting = []
    for e in ordered:
        x = matrix(e["features"], len(names))
        if len(x) != len(e["bounds"]):
            raise ValueError("Features and sample boundaries differ.")
        fitting.append(x[blocks(e["bounds"], e["duration"])["fit"]])
    centres = {str(load): np.mean([x.mean(axis=0) for e, x in zip(ordered, fitting)
                                   if e["load"] == load], axis=0).tolist()
               for load in SETTINGS["loads"]}
    arrays = {"pooled": fitting, "load_centred":
              [x-np.asarray(centres[str(e["load"])]) for e, x in zip(ordered, fitting)]}
    references = {}
    for reference, values in arrays.items():
        model = fit_model(values, names, shrinkage=SETTINGS["shrinkage"],
                          correlation_limit=SETTINGS["correlation_limit"],
                          relative_scale_floor=SETTINGS["relative_scale_floor"],
                          drop_suffixes=SETTINGS["drop_suffixes"])
        events = []
        for e in ordered:
            offset = np.asarray(centres[str(e["load"])]) if reference == "load_centred" else 0
            for number, indices in enumerate(calibration_episodes(e["bounds"], e["duration"])):
                raw = model.score(e["features"][indices]-offset)
                events.append({"recording_id": e["recording_id"], "load": e["load"],
                               "episode": number, "window_indices": indices.tolist(),
                               "raw": event_level(raw[10:]),
                               "ewma": event_level(ewma(raw, .2)[10:])})
        def thresholds(selected):
            result = {stream: max(e[stream] for e in selected) for stream in ("raw", "ewma")}
            if min(result.values()) <= 0:
                raise ValueError("Positive thresholds required.")
            return result
        references[reference] = {"model": model.to_dict(), "calibration_episodes": events,
                                 "global": thresholds(events),
                                 "load": {str(load): thresholds([e for e in events if e["load"] == load])
                                          for load in SETTINGS["loads"]}}
    return {"settings": dict(SETTINGS), "feature_names": list(names), "centres": centres,
            "references": references,
            "evidence_scope": "Same-record temporal development; no independent acquisition validation."}


def score(bank, values, load, arm, names):
    if bank.get("settings") != SETTINGS or arm not in ARMS:
        raise ValueError("Unsupported bank settings or experiment arm.")
    if list(names) != bank["feature_names"]:
        raise ValueError("Feature order/schema mismatch.")
    if load not in SETTINGS["loads"]:
        return {"status": "unsupported", "distance": None, "alarm": None}
    key = str(int(load))
    reference, policy = ARMS[arm]
    spec = bank["references"][reference]
    thresholds = spec["global"] if policy == "global" else spec["load"][key]
    offset = np.asarray(bank["centres"][key]) if reference == "load_centred" else 0
    raw = Model.from_dict(spec["model"]).score(matrix(values, len(names))-offset)
    smooth = ewma(raw, .2)
    eligible = np.arange(len(raw)) >= 10
    result = {"status": "supported_development", "eligible": eligible}
    for stream, suffix, values in (("raw", "", raw), ("ewma", "_ewma", smooth)):
        flags = eligible & (values > thresholds[stream])
        result.update({"distance"+suffix: values, "health_index"+suffix: health_index(values, thresholds[stream]),
                       "alarm"+suffix: flags, "persistent"+suffix: persistent_alarm(flags, 3),
                       "threshold_"+stream: thresholds[stream]})
    return result

