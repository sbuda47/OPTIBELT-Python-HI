"""Extract admitted recordings without fitting or consulting model outcomes."""
import argparse
import csv
import json
import platform
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
import numpy as np
from optibelt_hi.configuration import load_config
from optibelt_hi.data.audit import sha256, write_csv
from optibelt_hi.data.recordings import metadata, CHANNELS
from optibelt_hi.preprocessing.signals import prepare_recording
from .core import extract_windows, FEATURE_NAMES, SCHEMA_VERSION, BANDS

def run_batch(project, name):
    project=Path(project).resolve()
    if not name or name in {".",".."} or Path(name).name!=name or "/" in name or "\\" in name:
        raise ValueError("Use a single new output directory name.")
    folder=project/"outputs/runs"/name
    folder.mkdir(parents=True,exist_ok=False)
    report={"status":"running","created_utc":datetime.now(timezone.utc).isoformat(),
            "recordings":[],"schema":SCHEMA_VERSION,"feature_count":len(CHANNELS)*len(FEATURE_NAMES)}
    def save():
        (folder/"run.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    save()
    try:
        admission=project/"dataset/splits/data_admission.csv"
        frozen=project/"dataset/splits/grouped_v1"
        protocol=json.loads((frozen/"protocol.json").read_text(encoding="utf-8"))
        if sha256(admission)!=protocol["admission_sha256"]:
            raise ValueError("Dataset admission changed after split freeze.")
        if sha256(frozen/"assignments.csv")!=protocol["assignments_sha256"]:
            raise ValueError("Frozen assignments hash mismatch.")
        config_path=project/"configs/preprocessing.yaml"
        config=load_config(config_path)
        with admission.open(encoding="utf-8-sig",newline="") as handle:
            records=list(csv.DictReader(handle))
        eligible=sorted((r for r in records if r["admission_status"]=="candidate_complete_recording"),
                        key=lambda r:r["relative_path"])
        if not eligible: raise ValueError("No admitted recordings.")
        for field in ("recording_id","sha256","relative_path"):
            if len({r[field] for r in eligible})!=len(eligible):
                raise ValueError(f"Duplicate admitted {field}.")
        package=Path(__file__).resolve().parents[1]
        report.update({
            "python":platform.python_version(),
            "environment":{p:version(p) for p in ("numpy","scipy","h5py")},
            "admission_sha256":sha256(admission),"assignments_sha256":sha256(frozen/"assignments.csv"),
            "protocol_sha256":sha256(frozen/"protocol.json"),
            "configuration":config,"config_sha256":sha256(config_path),
            "implementation_sha256":{p.relative_to(package).as_posix():sha256(p) for p in sorted(package.rglob("*.py"))},
            "feature_definition":{"schema":SCHEMA_VERSION,"channel_order":CHANNELS,"statistics":FEATURE_NAMES,
                "bands_hz":BANDS,"spectral_window":"periodic Hann","spectrum":"one-sided density, DC excluded",
                "moment_bias_correction":False,"kurtosis":"Pearson","invalid_policy":"fail_recording"},
            "expected_recordings":len(eligible),
            "interpretation":"Fixed candidate features only. No feature selection, baseline fit or HI calibration."})
        windows=[]
        for record in eligible:
            path=(project/record["relative_path"]).resolve()
            if not path.is_relative_to((project/"dataset/raw").resolve()):
                raise ValueError("Admitted file escapes dataset/raw.")
            if path.stem!=record["recording_id"]:
                raise ValueError("Recording identifier differs from filename.")
            report["current_recording"]=record["recording_id"]
            save()
            if sha256(path)!=record["sha256"]:
                raise ValueError(f"Raw input hash mismatch: {path.name}")
            info=metadata(path)
            for key in ("condition",):
                if info[key]!=record[key]: raise ValueError("Filename and admission metadata disagree.")
            values=prepare_recording(path,info["expected_duration_s"])
            features,bounds,names=extract_windows(values,rate=config["target_rate_hz"],
                window_seconds=config["window_seconds"],hop_seconds=config["hop_seconds"])
            artifact=record["recording_id"]+".npz"
            np.savez_compressed(folder/artifact,features=features,
                feature_names=np.array(names),bounds=np.array(bounds,dtype=np.int64))
            for i,(start,stop) in enumerate(bounds):
                windows.append({"recording_id":record["recording_id"],"window_index":i,
                    "start_sample":start,"stop_sample":stop,"start_seconds":start/config["target_rate_hz"],
                    "stop_seconds":stop/config["target_rate_hz"],**info})
            report["recordings"].append({"recording_id":record["recording_id"],
                "input":record["relative_path"],"input_sha256":record["sha256"],"artifact":artifact,
                "artifact_sha256":sha256(folder/artifact),"windows":len(bounds),"condition":info["condition"]})
            print(f'{len(report["recordings"]):02d}/{len(eligible)} {path.name}: {len(bounds)} windows',flush=True)
            save()
            del values,features
        write_csv(folder/"windows.csv",windows)
        report.update(status="complete",completed_utc=datetime.now(timezone.utc).isoformat(),
                      total_windows=len(windows),windows_sha256=sha256(folder/"windows.csv"))
        report.pop("current_recording",None)
        save()
        return folder
    except Exception as exc:
        report.update(status="failed",error=str(exc))
        save()
        raise

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",required=True,type=Path)
    parser.add_argument("--name",required=True)
    args=parser.parse_args()
    print(run_batch(args.project,args.name))

if __name__=="__main__":
    main()

