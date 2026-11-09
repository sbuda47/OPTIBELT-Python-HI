"""Run the frozen four-arm load-only temporal development experiment."""
import argparse
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from importlib.metadata import version
import numpy as np
from optibelt_hi.data.audit import sha256, write_csv
from optibelt_hi.evaluation.model_run import load_inputs, safe_name
from optibelt_hi.evaluation.operating_v2_run import assemble, file_hashes
from optibelt_hi.model.operating_v2 import blocks
from optibelt_hi.model.load_aware import ARMS, SETTINGS, build_bank, score, calibration_episodes


def summarize(metrics, arm, stream, load="all"):
    selected = [r for r in metrics if r["arm"] == arm and r["stream"] == stream
                and (load == "all" or r["load"] == load)]
    result = {"arm": arm, "stream": stream, "load": load}
    for label, normal in (("healthy", True), ("fault", False)):
        rows = [r for r in selected if (r["condition"] == "normal") == normal]
        result.update({label+"_recordings": len(rows),
                       label+"_alerts": sum(r["persistent_alert"] for r in rows),
                       label+"_mean_alarm_fraction": float(np.mean([r["alarm_fraction"] for r in rows])) if rows else None})
    return result


def execute(project, name):
    project = Path(project).resolve()
    safe_name(name)
    folder = project/"outputs/runs"/name
    folder.mkdir(parents=True, exist_ok=False)
    old_names = ("model_baseline_v1", "operating_v2_development_001")
    preserved = {n: file_hashes(project/"outputs/runs"/n) for n in old_names}
    source = project/"src/optibelt_hi"
    source_hashes = {p.relative_to(source).as_posix(): sha256(p) for p in sorted(source.rglob("*.py"))}
    report = {"status": "running", "created_utc": datetime.now(timezone.utc).isoformat(),
              "preserved_runs_before": preserved, "implementation_sha256": source_hashes,
              "settings": SETTINGS, "arms": ARMS, "python": platform.python_version(),
              "packages": {n: version(n) for n in ("numpy", "scipy", "h5py")}}
    def save():
        (folder/"run.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    save()
    try:
        data, _, names = load_inputs(project, project/"outputs/runs/candidate_features_v1")
        entries = assemble(project, data)
        healthy = [e for e in entries if "features" in e and e["condition"] == "normal"]
        supported_states = {e["state"] for e in healthy}
        active = [e for e in entries if "features" in e and e["state"] in supported_states]
        if len(healthy) != 17 or len(active) != 28:
            raise ValueError("Frozen cohort changed; update protocol explicitly before proceeding.")
        protocol = project/"docs/load_experiment_protocol.md"
        report.update(protocol_sha256=sha256(protocol),
                      admission_sha256=sha256(project/"dataset/splits/data_admission.csv"),
                      feature_run_sha256=sha256(project/"outputs/runs/candidate_features_v1/run.json"))
        (folder/"protocol.md").write_text(protocol.read_text(encoding="utf-8"), encoding="utf-8")
        routing = []
        temporal = []
        for e in entries:
            base = {k: e[k] for k in ("recording_id", "state", "hp", "load", "profile", "upper", "condition")}
            status = ("excluded_quality" if "features" not in e else
                      "unsupported" if e["state"] not in supported_states else "supported_development")
            routing.append({**base, "status": status, "admission": e["admission"]})
            if status != "supported_development":
                continue
            split = blocks(e["bounds"], e["duration"])
            roles = [("check", 0, split["check"])]
            if e["condition"] == "normal":
                roles += [("fit", 0, split["fit"])]
                roles += [("calibration", i, idx) for i, idx in enumerate(calibration_episodes(e["bounds"], e["duration"]))]
            for role, episode, indices in roles:
                temporal.append({**base, "role": role, "episode": episode,
                                 "window_indices": json.dumps(indices.tolist()),
                                 "start_seconds": int(e["bounds"][indices[0], 0])/25600,
                                 "stop_seconds": int(e["bounds"][indices[-1], 1])/25600,
                                 "windows": len(indices)})
        write_csv(folder/"record_routing.csv", routing)
        write_csv(folder/"temporal_blocks.csv", temporal)
        (folder/"pre_fit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        bank = build_bank(healthy, names)
        (folder/"bank.json").write_text(json.dumps(bank, indent=2, allow_nan=False), encoding="utf-8")
        report["bank_sha256_before_check"] = sha256(folder/"bank.json")
        (folder/"pre_check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        predictions = []
        metrics = []
        for e in active:
            base = {k: e[k] for k in ("recording_id", "state", "hp", "load", "profile", "upper", "condition")}
            indices = blocks(e["bounds"], e["duration"])["check"]
            results = {arm: score(bank, e["features"][indices], e["load"], arm, names) for arm in ARMS}
            for a, b in (("A", "B"), ("C", "D")):
                for suffix in ("", "_ewma"):
                    if not np.array_equal(results[a]["distance"+suffix], results[b]["distance"+suffix]):
                        raise ValueError("Paired arm scores differ.")
                    if np.any(results[a]["persistent"+suffix] & ~results[b]["persistent"+suffix]):
                        raise ValueError("Global/load threshold monotonicity violated.")
            for arm, result in results.items():
                for j, idx in enumerate(indices):
                    row = {**base, "arm": arm, "original_window_index": int(idx),
                           "episode_window_index": j,
                           "start_seconds": int(e["bounds"][idx, 0])/25600,
                           "stop_seconds": int(e["bounds"][idx, 1])/25600,
                           "eligible": bool(result["eligible"][j]),
                           "threshold_raw": result["threshold_raw"], "threshold_ewma": result["threshold_ewma"]}
                    for key in ("distance", "distance_ewma", "health_index", "health_index_ewma"):
                        row[key] = float(result[key][j])
                    for key in ("alarm", "alarm_ewma", "persistent", "persistent_ewma"):
                        row[key] = bool(result[key][j])
                    predictions.append(row)
                for stream, suffix in (("raw", ""), ("ewma", "_ewma")):
                    eligible = result["eligible"]
                    metrics.append({**base, "arm": arm, "stream": stream,
                                    "threshold": result["threshold_"+stream],
                                    "decision_windows": int(eligible.sum()),
                                    "alarm_fraction": float(result["alarm"+suffix][eligible].mean()),
                                    "persistent_alert": bool(result["persistent"+suffix].any())})
        comparisons = [summarize(metrics, a, s) for a in ARMS for s in ("raw", "ewma")]
        loads = [summarize(metrics, a, s, load) for a in ARMS for s in ("raw", "ewma") for load in (0, 30, 60)]
        paired = []
        for e in active:
            for stream in ("raw", "ewma"):
                rows = {r["arm"]: r for r in metrics if r["recording_id"] == e["recording_id"] and r["stream"] == stream}
                paired.append({"recording_id": e["recording_id"], "condition": e["condition"],
                               "load": e["load"], "stream": stream,
                               **{a+"_alert": rows[a]["persistent_alert"] for a in ARMS}})
        support = []
        for reference, spec in bank["references"].items():
            for load in (0, 30, 60):
                episodes = [e for e in spec["calibration_episodes"] if e["load"] == load]
                support.append({"reference": reference, "load": load,
                                "distinct_healthy_recordings": len({e["recording_id"] for e in episodes}),
                                "correlated_calibration_episodes": len(episodes),
                                "load_threshold_raw": spec["load"][str(load)]["raw"],
                                "load_threshold_ewma": spec["load"][str(load)]["ewma"],
                                "global_threshold_raw": spec["global"]["raw"],
                                "global_threshold_ewma": spec["global"]["ewma"]})
        for filename, rows in (("predictions.csv", predictions), ("record_metrics.csv", metrics),
                               ("summary.csv", comparisons), ("by_load.csv", loads),
                               ("paired_outcomes.csv", paired), ("calibration_support.csv", support)):
            write_csv(folder/filename, rows)
        if any(file_hashes(project/"outputs/runs"/n) != preserved[n] for n in old_names):
            raise ValueError("Earlier results changed.")
        if sha256(folder/"bank.json") != report["bank_sha256_before_check"]:
            raise ValueError("Bank changed after check evaluation.")
        if {p.relative_to(source).as_posix(): sha256(p) for p in sorted(source.rglob("*.py"))} != source_hashes:
            raise ValueError("Implementation changed during evaluation.")
        report.update(status="complete", completed_utc=datetime.now(timezone.utc).isoformat(),
                      healthy_recordings=len(healthy), scored_recordings=len(active),
                      comparison=comparisons, previous_runs_preserved=True,
                      evidence_scope=bank["evidence_scope"],
                      artifacts={p.name: sha256(p) for p in folder.iterdir() if p.is_file() and p.name != "run.json"})
        save()
        print(json.dumps({"status": report["status"], "comparison": comparisons}, indent=2))
        return folder
    except Exception as exc:
        report.update(status="failed", error=str(exc))
        save()
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    execute(args.project, args.name)

