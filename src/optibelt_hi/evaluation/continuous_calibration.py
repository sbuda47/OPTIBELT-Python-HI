"""Healthy continuous-calibration comparison with previously frozen references."""
import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from optibelt_hi.data.audit import sha256, write_csv
from optibelt_hi.evaluation.model_run import load_inputs, read_csv, safe_name
from optibelt_hi.evaluation.operating_v2_run import assemble, file_hashes
from optibelt_hi.evaluation.long_monitoring import check_indices, record_metrics, summarize
from optibelt_hi.model.load_aware import score
from optibelt_hi.model.operating_v2 import event_level
from optibelt_hi.monitoring.health import health_index, persistent_alarm

REFERENCES = {"A": "pooled", "C": "load_centred"}


def calibration_indices(bounds, duration):
    check_indices(bounds, duration)  # Validate complete fixed-rate record boundaries.
    b = np.asarray(bounds)
    idx = np.flatnonzero((b[:, 0] >= round((.5*duration+2)*25600)) &
                         (b[:, 1] <= round((.75*duration-2)*25600)))
    if len(idx) != (70 if duration == 300 else 25):
        raise ValueError("Incomplete calibration interval.")
    return idx


def calibrate_continuously(bank, healthy, names):
    if not healthy or any(e["condition"] != "normal" for e in healthy):
        raise ValueError("Calibration requires healthy records only.")
    if len({e["recording_id"] for e in healthy}) != len(healthy):
        raise ValueError("Duplicate calibration recording.")
    events = []
    for e in sorted(healthy, key=lambda e: e["recording_id"]):
        idx = calibration_indices(e["bounds"], e["duration"])
        for arm in REFERENCES:
            result = score(bank, e["features"][idx], e["load"], arm, names)
            if result["status"] != "supported_development":
                raise ValueError("Unsupported calibration load.")
            events.append({"recording_id": e["recording_id"], "arm": arm, "load": e["load"],
                           "duration": e["duration"], "indices": idx.tolist(),
                           "windows": len(idx), "decision_steps": len(idx)-10,
                           "raw": event_level(result["distance"][10:]),
                           "ewma": event_level(result["distance_ewma"][10:])})
    thresholds = {arm: {s: max(e[s] for e in events if e["arm"] == arm) for s in ("raw", "ewma")}
                  for arm in REFERENCES}
    if any(q <= 0 or not np.isfinite(q) for v in thresholds.values() for q in v.values()):
        raise ValueError("Positive finite thresholds required.")
    return {"format": "continuous_calibration_v1", "thresholds": thresholds, "records": events,
            "policy": "Full guarded healthy calibration interval; one warm-up; maximum three-window event level."}


def apply_thresholds(result, thresholds):
    out = copy.deepcopy(result)
    for stream, suffix in (("raw", ""), ("ewma", "_ewma")):
        q = thresholds[stream]
        out["health_index"+suffix] = health_index(out["distance"+suffix], q)
        out["alarm"+suffix] = out["eligible"] & (out["distance"+suffix] > q)
        out["persistent"+suffix] = persistent_alarm(out["alarm"+suffix], 3)
        out["threshold_"+stream] = q
    return out


def execute(project, name):
    project = Path(project).resolve(); safe_name(name)
    folder = project/"outputs/runs"/name
    folder.mkdir(parents=True, exist_ok=False)
    previous = ("model_baseline_v1", "operating_v2_development_001", "load_only_experiment_001",
                "long_monitoring_001", "normal_1hp0_investigation_001")
    preserved = {n: file_hashes(project/"outputs/runs"/n) for n in previous}
    source = project/"outputs/runs/load_only_experiment_001"
    report = {"status": "running", "created_utc": datetime.now(timezone.utc).isoformat(),
              "previous_runs_before": preserved, "source_bank_sha256": sha256(source/"bank.json"),
              "reference_refitting": False}
    def save():
        (folder/"run.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    save()
    try:
        original = json.loads((source/"run.json").read_text())
        for relative, h in original["artifacts"].items():
            if sha256(source/relative) != h: raise ValueError("Source artifact changed.")
        prior_run = project/"outputs/runs/long_monitoring_001"
        prior_report = json.loads((prior_run/"run.json").read_text())
        for relative, h in prior_report["implementation_sha256"].items():
            if sha256(project/"src/optibelt_hi"/relative) != h: raise ValueError("Previous implementation changed.")
        for relative, h in prior_report["artifacts"].items():
            if sha256(prior_run/relative) != h: raise ValueError("Previous monitoring artifact changed.")
        data, _, names = load_inputs(project, project/"outputs/runs/candidate_features_v1")
        entries = {e["recording_id"]: e for e in assemble(project, data)}
        active = [entries[r["recording_id"]] for r in read_csv(source/"record_routing.csv")
                  if r["status"] == "supported_development"]
        healthy = [e for e in active if e["condition"] == "normal"]
        if len(active) != 28 or len(healthy) != 17: raise ValueError("Cohort changed.")
        bank = json.loads((source/"bank.json").read_text())
        before_bank = copy.deepcopy(bank)
        protocol = project/"docs/continuous_calibration_protocol.md"
        report.update(protocol_sha256=sha256(protocol),
                      implementation_sha256={p.relative_to(project/"src/optibelt_hi").as_posix(): sha256(p)
                                             for p in sorted((project/"src/optibelt_hi").rglob("*.py"))})
        (folder/"protocol.md").write_text(protocol.read_text(), encoding="utf-8")
        (folder/"pre_calibration.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        calibration = calibrate_continuously(bank, healthy, names)
        calibration["source_bank_sha256"] = report["source_bank_sha256"]
        (folder/"calibration.json").write_text(json.dumps(calibration, indent=2, allow_nan=False), encoding="utf-8")
        report["calibration_sha256_before_check"] = sha256(folder/"calibration.json")
        (folder/"pre_check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        threshold_rows = []
        for arm, ref in REFERENCES.items():
            for stream in ("raw", "ewma"):
                old = bank["references"][ref]["global"][stream]
                new = calibration["thresholds"][arm][stream]
                suppliers = [e["recording_id"] for e in calibration["records"] if e["arm"] == arm and e[stream] == new]
                threshold_rows.append(dict(arm=arm, stream=stream, original=old, continuous=new,
                                           change_percent=100*(new/old-1), suppliers=json.dumps(suppliers)))
        write_csv(folder/"threshold_changes.csv", threshold_rows)
        # Self-check is construction verification, not validation performance.
        for e in healthy:
            idx = calibration_indices(e["bounds"], e["duration"])
            for arm in REFERENCES:
                scored = apply_thresholds(score(bank, e["features"][idx], e["load"], arm, names),
                                          calibration["thresholds"][arm])
                if scored["persistent"].any() or scored["persistent_ewma"].any():
                    raise ValueError("Calibration envelope self-check failed.")
        old_lookup = {(r["recording_id"], r["arm"], int(r["original_window_index"])): r
                      for r in read_csv(prior_run/"predictions.csv")}
        predictions, metrics, events = [], [], []
        for e in active:
            idx = check_indices(e["bounds"], e["duration"])
            for arm in REFERENCES:
                old = score(bank, e["features"][idx], e["load"], arm, names)
                results = {"original": old, "continuous": apply_thresholds(old, calibration["thresholds"][arm])}
                for policy, result in results.items():
                    base = {k: e[k] for k in ("recording_id", "condition", "load", "hp", "profile", "duration")}
                    base.update(arm=arm, policy=policy)
                    for j, i in enumerate(idx):
                        row = {**base, "original_window_index": int(i), "episode_window_index": j,
                               "stop_seconds": float(e["bounds"][i, 1]/25600),
                               "threshold_raw": result["threshold_raw"], "threshold_ewma": result["threshold_ewma"]}
                        for k in ("distance", "distance_ewma", "health_index", "health_index_ewma"):
                            row[k] = float(result[k][j])
                        for k in ("eligible", "alarm", "alarm_ewma", "persistent", "persistent_ewma"):
                            row[k] = bool(result[k][j])
                        earlier = old_lookup[(e["recording_id"], arm, int(i))]
                        for k in ("distance", "distance_ewma"):
                            np.testing.assert_allclose(row[k], float(earlier[k]), rtol=1e-12, atol=1e-12)
                        if policy == "original":
                            for k in ("health_index", "health_index_ewma", "threshold_raw", "threshold_ewma"):
                                np.testing.assert_allclose(row[k], float(earlier[k]), rtol=1e-12, atol=1e-12)
                            for k in ("eligible", "alarm", "alarm_ewma", "persistent", "persistent_ewma"):
                                if row[k] != (earlier[k] == "True"): raise ValueError("Original outcome changed.")
                        predictions.append(row)
                    for stream in ("raw", "ewma"):
                        r, ev = record_metrics(result, e["bounds"], idx, stream, base)
                        metrics.extend(r)
                        for number, event in enumerate(ev):
                            events.append({**base, "stream": stream, "event_number": number, **event,
                                           "confirmed_record_seconds": float(e["bounds"][idx[event["confirmed"]], 1]/25600)})
        summaries = [{**summarize([r for r in metrics if r["policy"] == policy], group, value, arm, stream, segment),
                      "policy": policy}
                     for policy in ("original", "continuous")
                     for group, value in (("all", "all"), ("duration", 120), ("duration", 300),
                                          ("load", 0), ("load", 30), ("load", 60))
                     for arm in REFERENCES for stream in ("raw", "ewma") for segment in ("full", "prefix", "extension")]
        for name, rows in (("predictions.csv", predictions), ("record_metrics.csv", metrics),
                           ("events.csv", events), ("summary.csv", summaries)):
            write_csv(folder/name, rows)
        if bank != before_bank: raise ValueError("Frozen in-memory bank modified.")
        if sha256(folder/"calibration.json") != report["calibration_sha256_before_check"]:
            raise ValueError("Calibration changed during checks.")
        for n, hashes in preserved.items():
            if file_hashes(project/"outputs/runs"/n) != hashes: raise ValueError("Earlier output changed.")
        for relative, h in report["implementation_sha256"].items():
            if sha256(project/"src/optibelt_hi"/relative) != h: raise ValueError("Implementation changed.")
        report.update(status="complete", completed_utc=datetime.now(timezone.utc).isoformat(),
                      previous_runs_preserved=True, fitted_bank_unchanged=True, original_outcomes_reproduced=True,
                      comparison=[r for r in summaries if r["group"] == "all" and r["segment"] == "full"],
                      artifacts={p.name: sha256(p) for p in folder.iterdir() if p.is_file() and p.name != "run.json"})
        save()
        print(json.dumps({"status": report["status"], "thresholds": threshold_rows, "comparison": report["comparison"]}, indent=2))
        return folder
    except Exception as exc:
        report.update(status="failed", error=str(exc)); save(); raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path); parser.add_argument("--name", required=True)
    args = parser.parse_args(); execute(args.project, args.name)

