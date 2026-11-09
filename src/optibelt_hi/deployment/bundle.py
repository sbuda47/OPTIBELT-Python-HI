"""Export and validate the frozen continuous-calibration candidate."""
import argparse
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
import numpy as np
from optibelt_hi.configuration import load_config
from optibelt_hi.data.audit import sha256
from optibelt_hi.data.recordings import CHANNELS
from optibelt_hi.features.core import FEATURE_NAMES
from optibelt_hi.evaluation.model_run import read_csv, safe_name
from optibelt_hi.model.baseline import Model

FORMAT = "optibelt_hi_candidate_v1"
MONITORING = {"alpha": .2, "warmup_windows": 10, "persistence": 3,
              "comparison": "strict_greater", "hi_mapping": "100_over_1_plus_squared_threshold_ratio"}


def validate(bundle):
    if bundle.get("format") != FORMAT or bundle.get("monitoring") != MONITORING:
        raise ValueError("Unsupported bundle format or monitoring policy.")
    names = [f"{c}__{f}" for c in CHANNELS for f in FEATURE_NAMES]
    if bundle["feature_names"] != names or set(bundle["references"]) != {"A", "C"}:
        raise ValueError("Bundle feature/reference schema mismatch.")
    if bundle["preprocessing"]["target_rate_hz"] != 25600 or bundle["preprocessing"]["window_seconds"] != 2 or bundle["preprocessing"]["hop_seconds"] != 1:
        raise ValueError("Unsupported preprocessing clock/window policy.")
    for ref in bundle["references"].values():
        model = Model.from_dict(ref["model"])
        if model.names != names: raise ValueError("Model feature schema mismatch.")
        if set(ref["thresholds"]) != {"raw", "ewma"} or any(not np.isfinite(q) or q <= 0 for q in ref["thresholds"].values()):
            raise ValueError("Invalid thresholds.")
    if set(bundle["load_centres"]) != {"0", "30", "60"}:
        raise ValueError("Invalid load centres.")
    if any(np.asarray(c).shape != (len(names),) or not np.isfinite(c).all() for c in bundle["load_centres"].values()):
        raise ValueError("Invalid centre values.")
    states = bundle["supported_conditions"]
    if not states or len(states) != len({tuple(s[k] for k in ("hp","load","profile","upper")) for s in states}):
        raise ValueError("Missing or duplicate supported conditions.")
    if any(s["load"] not in (0,30,60) or s["hp"] not in (1,3,5) or
           (s["profile"],s["upper"]) not in (("invariant_speed",50),("varying_speed",52),("varying_speed",58))
           for s in states): raise ValueError("Invalid evidence coverage.")
    return bundle


def load_bundle(folder, verify_code=True):
    folder = Path(folder)
    manifest = json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != FORMAT or sha256(folder/"bundle.json") != manifest["bundle_sha256"]:
        raise ValueError("Bundle integrity failure.")
    if verify_code:
        source = Path(__file__).resolve().parents[1]
        for relative, digest in manifest["implementation_sha256"].items():
            path = (source/relative).resolve()
            if not path.is_relative_to(source) or sha256(path) != digest:
                raise ValueError("Runtime implementation differs from frozen bundle: "+relative)
    bundle = validate(json.loads((folder/"bundle.json").read_text(encoding="utf-8")))
    if manifest["candidate_version"] != bundle["candidate_version"]:
        raise ValueError("Candidate version mismatch.")
    return bundle


def export(project, name):
    project = Path(project).resolve(); safe_name(name)
    source = project/"outputs/runs/load_only_experiment_001"
    calibrated = project/"outputs/runs/continuous_calibration_001"
    report = json.loads((calibrated/"run.json").read_text())
    if report["status"] != "complete": raise ValueError("Incomplete source experiment.")
    for filename, digest in report["previous_runs_before"]["load_only_experiment_001"].items():
        if sha256(source/filename) != digest: raise ValueError("Frozen bank/coverage source changed.")
    for relative, digest in report["artifacts"].items():
        if sha256(calibrated/relative) != digest: raise ValueError("Calibration artifact changed.")
    for relative, digest in report["implementation_sha256"].items():
        if sha256(project/"src/optibelt_hi"/relative) != digest: raise ValueError("Experiment implementation changed.")
    cal = json.loads((calibrated/"calibration.json").read_text())
    if sha256(source/"bank.json") != cal["source_bank_sha256"]:
        raise ValueError("Frozen reference bank changed.")
    bank = json.loads((source/"bank.json").read_text())
    config = load_config(project/"configs/preprocessing.yaml")
    conditions = []
    for r in read_csv(source/"record_routing.csv"):
        if r["status"] == "supported_development" and r["condition"] == "normal":
            conditions.append(dict(hp=float(r["hp"]),load=int(r["load"]),profile=r["profile"],upper=int(r["upper"])))
    if len(conditions) != 17: raise ValueError("Evidence coverage changed.")
    bundle = {"format": FORMAT, "candidate_version": name, "primary_reference": "C",
              "feature_names": bank["feature_names"], "feature_schema": "candidate_v1",
              "preprocessing": config, "monitoring": MONITORING,
              "load_centres": bank["centres"], "supported_conditions": conditions,
              "references": {arm: {"model": bank["references"][ref]["model"], "thresholds": cal["thresholds"][arm]}
                             for arm,ref in (("A","pooled"),("C","load_centred"))},
              "evidence_scope": "Exposed-data same-acquisition development. Independent validation outstanding.",
              "processing_mode": "Offline raw resampling; causal feature-window EWMA/persistence playback. Live FIR streaming and load transitions unvalidated.",
              "provenance": {"bank_sha256": sha256(source/"bank.json"),"calibration_sha256": sha256(calibrated/"calibration.json"),
                             "experiment_run_sha256": sha256(calibrated/"run.json")}}
    validate(bundle)
    folder = project/"outputs/releases"/name
    folder.mkdir(parents=True,exist_ok=False)
    (folder/"bundle.json").write_text(json.dumps(bundle,indent=2,allow_nan=False),encoding="utf-8")
    source_dir = project/"src/optibelt_hi"
    manifest = {"format": FORMAT, "candidate_version": name, "created_utc": datetime.now(timezone.utc).isoformat(),
                "bundle_sha256": sha256(folder/"bundle.json"),
                "implementation_sha256": {p.relative_to(source_dir).as_posix(): sha256(p) for p in sorted(source_dir.rglob("*.py"))},
                "packages": {n: version(n) for n in ("numpy","scipy","h5py","PyYAML")}}
    (folder/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    assert load_bundle(folder) == bundle
    print(json.dumps({"bundle":str(folder),"supported_conditions":len(conditions),"primary_reference":"C"},indent=2))
    return folder


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",type=Path,required=True);parser.add_argument("--name",required=True)
    args=parser.parse_args();export(args.project,args.name)

