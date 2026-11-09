"""Offline raw MAT to versioned MD-HI playback."""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from optibelt_hi.data.audit import sha256,write_csv
from optibelt_hi.data.recordings import metadata
from optibelt_hi.deployment.bundle import load_bundle
from optibelt_hi.deployment.monitor import Monitor
from optibelt_hi.evaluation.long_monitoring import check_indices
from optibelt_hi.evaluation.model_run import read_csv,safe_name
from optibelt_hi.features.core import extract_windows
from optibelt_hi.preprocessing.signals import prepare_recording


def run(project,bundle_folder,recording,name,reference="C",scope="check"):
    project=Path(project).resolve();safe_name(name)
    if scope not in ("check","full"):raise ValueError("Use check or full playback scope.")
    path=(project/recording).resolve()
    if not path.is_relative_to((project/"dataset/raw").resolve()):raise ValueError("Input must be inside dataset/raw.")
    folder=project/"outputs/runs"/name;folder.mkdir(parents=True,exist_ok=False)
    report={"status":"running","created_utc":datetime.now(timezone.utc).isoformat(),
            "input":path.relative_to(project).as_posix(),"scope":scope,"reference":reference}
    def save():
        (folder/"run.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    save()
    try:
        bundle=load_bundle(bundle_folder)
        info=metadata(path)
        condition=dict(hp=info["motor_capacity_hp"],load=info["load_percent_label"],
                       profile=info["speed_profile"],upper=info["supply_high_hz"])
        monitor=Monitor(bundle,condition,path.stem,reference)
        matching=[r for r in read_csv(project/"dataset/splits/data_admission.csv")
                  if r["relative_path"]==path.relative_to(project).as_posix()]
        if len(matching)!=1 or matching[0]["admission_status"]!="candidate_complete_recording":
            raise ValueError("Recording is not admitted under the current source-quality policy.")
        digest=sha256(path)
        if digest!=matching[0]["sha256"]:raise ValueError("Raw recording differs from admitted source.")
        report.update(input_sha256=digest,condition=condition,candidate_version=bundle["candidate_version"],
                      bundle_sha256=sha256(Path(bundle_folder)/"bundle.json"),
                      manifest_sha256=sha256(Path(bundle_folder)/"manifest.json"),
                      evidence_scope=bundle["evidence_scope"],
                      processing_mode=bundle["processing_mode"])
        save()
        print("Preparing native channels and extracting features: "+path.name,flush=True)
        values=prepare_recording(path,info["expected_duration_s"])
        features,bounds,names=extract_windows(values)
        del values
        bounds=np.asarray(bounds,dtype=np.int64)
        if names!=bundle["feature_names"]:raise ValueError("Extracted feature schema differs from bundle.")
        indices=check_indices(bounds,info["expected_duration_s"]) if scope=="check" else np.arange(len(features))
        predictions=[]
        for i in indices:
            row=monitor.push(features[i],int(bounds[i,0]),int(bounds[i,1]),recording_id=path.stem,feature_names=names)
            row["original_window_index"]=int(i);predictions.append(row)
        if sha256(path)!=digest:raise ValueError("Raw source changed during playback.")
        if sha256(Path(bundle_folder)/"bundle.json")!=report["bundle_sha256"]:raise ValueError("Candidate changed during playback.")
        np.savez_compressed(folder/"features.npz",features=features,bounds=bounds,feature_names=np.array(names))
        write_csv(folder/"predictions.csv",predictions)
        eligible=[r for r in predictions if r["eligible"]]
        report.update(status="complete",completed_utc=datetime.now(timezone.utc).isoformat(),
                      extracted_windows=len(features),playback_windows=len(predictions),decision_windows=len(eligible),
                      raw_persistent_steps=sum(r["persistent"] for r in eligible),
                      ewma_persistent_steps=sum(r["persistent_ewma"] for r in eligible),
                      interpretation="Saved-interval reproduction" if scope=="check" else "Full-record demonstration includes fit/calibration data; not evaluation.",
                      artifacts={p.name:sha256(p) for p in folder.iterdir() if p.is_file() and p.name!="run.json"})
        save()
        print(json.dumps({k:report[k] for k in ("status","candidate_version","extracted_windows","playback_windows","decision_windows","ewma_persistent_steps")},indent=2))
        return folder
    except Exception as exc:
        report.update(status="failed",error=str(exc));save();raise


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",type=Path,required=True);parser.add_argument("--bundle",type=Path,required=True)
    parser.add_argument("--recording",type=Path,required=True);parser.add_argument("--name",required=True)
    parser.add_argument("--reference",choices=("A","C"),default="C")
    parser.add_argument("--scope",choices=("check","full"),default="check")
    args=parser.parse_args();run(args.project,args.bundle,args.recording,args.name,args.reference,args.scope)

