"""Frozen-bank monitoring across full reserved check intervals."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from optibelt_hi.data.audit import sha256, write_csv
from optibelt_hi.evaluation.model_run import load_inputs, read_csv, safe_name
from optibelt_hi.evaluation.operating_v2_run import assemble, file_hashes
from optibelt_hi.model.load_aware import score

ARMS = ("A", "C")
SOURCE_RUN = "load_only_experiment_001"


def check_indices(bounds, duration):
    b = np.asarray(bounds)
    if duration not in (120, 300) or b.ndim != 2 or b.shape[1] != 2 or b.dtype.kind not in "iu":
        raise ValueError("Unexpected recording duration or boundaries.")
    if not np.all(b[:, 1]-b[:, 0] == 51200) or not np.all(np.diff(b[:, 0]) == 25600):
        raise ValueError("Expected complete two-second windows at one-second hop.")
    idx = np.flatnonzero((b[:, 0] >= round((.75*duration+2)*25600)) &
                         (b[:, 1] <= round((duration-2)*25600)))
    if len(idx) != (25 if duration == 120 else 70):
        raise ValueError("Reserved check interval is incomplete.")
    return idx


def alert_events(flags):
    f = np.asarray(flags)
    if f.ndim != 1 or f.dtype.kind != "b":
        raise ValueError("Expected boolean alarm flags.")
    changes = np.diff(np.r_[False, f, False].astype(int))
    starts = np.flatnonzero(changes == 1)
    stops = np.flatnonzero(changes == -1)
    return [{"start": int(a), "confirmed": int(a+2), "last": int(b-1),
             "exceedance_steps": int(b-a), "persistent_steps": int(b-a-2),
             "right_censored": bool(b == len(f))}
            for a, b in zip(starts, stops) if b-a >= 3]


def record_metrics(result, bounds, indices, stream, base):
    suffix = "" if stream == "raw" else "_ewma"
    flags = result["alarm"+suffix]
    persistent = result["persistent"+suffix]
    events = alert_events(flags)
    rows = []
    pos = np.arange(len(indices))
    for segment, mask in (("full", result["eligible"]),
                          ("prefix", result["eligible"] & (pos < 25)),
                          ("extension", result["eligible"] & (pos >= 25))):
        count = int(mask.sum())
        selected = [e for e in events if mask[e["confirmed"]]]
        hits = np.flatnonzero(persistent & mask)
        rows.append({**base, "stream": stream, "segment": segment, "decision_steps": count,
                     "decision_exposure_seconds": count,
                     "above_threshold_steps": int((flags & mask).sum()),
                     "persistent_alarm_steps": int((persistent & mask).sum()),
                     "persistent_alert": bool(len(hits)), "events_confirmed": len(selected),
                     "first_alert_record_seconds": float(bounds[indices[hits[0]], 1]/25600) if len(hits) else None,
                     "first_alert_seconds_after_first_decision": float((bounds[indices[hits[0]], 1]-bounds[indices[10], 1])/25600) if len(hits) else None})
    return rows, events


def summarize(metrics, group, value, arm, stream, segment):
    rows = [r for r in metrics if r["arm"] == arm and r["stream"] == stream and r["segment"] == segment
            and r["decision_steps"] > 0 and (group == "all" or r[group] == value)]
    result = {"group": group, "value": value, "arm": arm, "stream": stream, "segment": segment}
    for label, normal in (("healthy", True), ("fault", False)):
        selected = [r for r in rows if (r["condition"] == "normal") == normal]
        exposure = sum(r["decision_steps"] for r in selected)
        above = sum(r["above_threshold_steps"] for r in selected)
        persistent = sum(r["persistent_alarm_steps"] for r in selected)
        result.update({label+"_records": len(selected),
                       label+"_alert_records": sum(r["persistent_alert"] for r in selected),
                       label+"_events": sum(r["events_confirmed"] for r in selected),
                       label+"_exposure_seconds": exposure,
                       label+"_above_threshold_steps": above, label+"_persistent_steps": persistent,
                       label+"_above_fraction": above/exposure if exposure else None,
                       label+"_persistent_fraction": persistent/exposure if exposure else None})
    return result


def execute(project, name):
    project = Path(project).resolve()
    safe_name(name)
    folder = project/"outputs/runs"/name
    folder.mkdir(parents=True, exist_ok=False)
    preserved = {n: file_hashes(project/"outputs/runs"/n)
                 for n in ("model_baseline_v1", "operating_v2_development_001", SOURCE_RUN)}
    source = project/"outputs/runs"/SOURCE_RUN
    report = {"status": "running", "created_utc": datetime.now(timezone.utc).isoformat(),
              "previous_runs_before": preserved, "source_bank_sha256": sha256(source/"bank.json"),
              "arms": ARMS, "fit_or_calibration_performed": False}
    def save():
        (folder/"run.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    save()
    try:
        original = json.loads((source/"run.json").read_text(encoding="utf-8"))
        if original["status"] != "complete":
            raise ValueError("Source experiment incomplete.")
        for relative, digest in original["artifacts"].items():
            if sha256(source/relative) != digest:
                raise ValueError("Source artifact changed: "+relative)
        for relative, digest in original["implementation_sha256"].items():
            if sha256(project/"src/optibelt_hi"/relative) != digest:
                raise ValueError("Original implementation changed: "+relative)
        data, _, names = load_inputs(project, project/"outputs/runs/candidate_features_v1")
        entries = {e["recording_id"]: e for e in assemble(project, data)}
        routing = read_csv(source/"record_routing.csv")
        active = [entries[r["recording_id"]] for r in routing if r["status"] == "supported_development"]
        if len(active) != 28 or sum(e["condition"] == "normal" for e in active) != 17:
            raise ValueError("Frozen cohort changed.")
        bank = json.loads((source/"bank.json").read_text(encoding="utf-8"))
        prior = {(r["recording_id"], r["arm"], int(r["episode_window_index"])): r
                 for r in read_csv(source/"predictions.csv") if r["arm"] in ARMS}
        protocol = project/"docs/long_monitoring_protocol.md"
        report.update(protocol_sha256=sha256(protocol),
                      implementation_sha256={p.relative_to(project/"src/optibelt_hi").as_posix(): sha256(p)
                                             for p in sorted((project/"src/optibelt_hi").rglob("*.py"))})
        (folder/"protocol.md").write_text(protocol.read_text(encoding="utf-8"), encoding="utf-8")
        (folder/"pre_evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        manifest = []
        for e in active:
            idx = check_indices(e["bounds"], e["duration"])
            manifest.append({"recording_id": e["recording_id"], "condition": e["condition"],
                             "duration": e["duration"], "windows": len(idx), "added_windows": len(idx)-25,
                             "indices": json.dumps(idx.tolist()),
                             "raw_start_seconds": float(e["bounds"][idx[0], 0]/25600),
                             "raw_stop_seconds": float(e["bounds"][idx[-1], 1]/25600)})
        write_csv(folder/"check_manifest.csv", manifest)
        predictions, metrics, event_rows = [], [], []
        for e in active:
            idx = check_indices(e["bounds"], e["duration"])
            for arm in ARMS:
                base = {k: e[k] for k in ("recording_id", "condition", "load", "hp", "profile", "duration")}
                base["arm"] = arm
                result = score(bank, e["features"][idx], e["load"], arm, names)
                for j, i in enumerate(idx):
                    row = {**base, "episode_window_index": j, "original_window_index": int(i),
                           "stop_seconds": float(e["bounds"][i, 1]/25600),
                           "threshold_raw": result["threshold_raw"], "threshold_ewma": result["threshold_ewma"]}
                    for key in ("distance", "distance_ewma", "health_index", "health_index_ewma"):
                        row[key] = float(result[key][j])
                    for key in ("eligible", "alarm", "alarm_ewma", "persistent", "persistent_ewma"):
                        row[key] = bool(result[key][j])
                    if j < 25:
                        old = prior[(e["recording_id"], arm, j)]
                        if int(old["original_window_index"]) != i:
                            raise ValueError("Prefix indices differ.")
                        for key in ("distance", "distance_ewma", "health_index", "health_index_ewma", "threshold_raw", "threshold_ewma"):
                            np.testing.assert_allclose(row[key], float(old[key]), rtol=1e-12, atol=1e-12)
                        for key in ("eligible", "alarm", "alarm_ewma", "persistent", "persistent_ewma"):
                            if row[key] != (old[key] == "True"):
                                raise ValueError("Prefix alarm result differs.")
                    predictions.append(row)
                for stream in ("raw", "ewma"):
                    rows, events = record_metrics(result, e["bounds"], idx, stream, base)
                    metrics.extend(rows)
                    for number, event in enumerate(events):
                        event_rows.append({**base, "stream": stream, "event_number": number,
                                           **event,
                                           "start_record_seconds": float(e["bounds"][idx[event["start"]], 1]/25600),
                                           "confirmed_record_seconds": float(e["bounds"][idx[event["confirmed"]], 1]/25600),
                                           "last_record_seconds": float(e["bounds"][idx[event["last"]], 1]/25600)})
        summaries = [summarize(metrics, group, value, arm, stream, segment)
                     for group, value in (("all", "all"), ("duration", 120), ("duration", 300),
                                          ("load", 0), ("load", 30), ("load", 60))
                     for arm in ARMS for stream in ("raw", "ewma") for segment in ("prefix", "extension", "full")]
        paired = []
        for e in active:
            for stream in ("raw", "ewma"):
                selected = {(r["arm"], r["segment"]): r for r in metrics
                            if r["recording_id"] == e["recording_id"] and r["stream"] == stream}
                paired.append({"recording_id": e["recording_id"], "condition": e["condition"],
                               "load": e["load"], "duration": e["duration"], "stream": stream,
                               **{a+"_"+s+"_alert": selected[(a,s)]["persistent_alert"]
                                  for a in ARMS for s in ("prefix", "extension", "full")}})
        for filename, rows in (("predictions.csv", predictions), ("record_metrics.csv", metrics),
                               ("events.csv", event_rows), ("summary.csv", summaries), ("paired_outcomes.csv", paired)):
            write_csv(folder/filename, rows)
        for n, hashes in preserved.items():
            if file_hashes(project/"outputs/runs"/n) != hashes:
                raise ValueError("Earlier run changed: "+n)
        if {p.relative_to(project/"src/optibelt_hi").as_posix(): sha256(p)
            for p in sorted((project/"src/optibelt_hi").rglob("*.py"))} != report["implementation_sha256"]:
            raise ValueError("Implementation changed.")
        report.update(status="complete", completed_utc=datetime.now(timezone.utc).isoformat(),
                      prefix_reproduced=True, previous_runs_preserved=True,
                      prediction_rows=len(predictions), metric_rows=len(metrics),
                      added_windows_per_arm=sum(r["added_windows"] for r in manifest),
                      comparison=[r for r in summaries if r["group"] == "all"],
                      artifacts={p.name: sha256(p) for p in folder.iterdir() if p.is_file() and p.name != "run.json"})
        save()
        print(json.dumps({k: report[k] for k in ("status", "prediction_rows", "added_windows_per_arm", "comparison")}, indent=2))
        return folder
    except Exception as exc:
        report.update(status="failed", error=str(exc))
        save()
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    execute(args.project, args.name)

