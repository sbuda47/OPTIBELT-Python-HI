"""Fixed grouped evaluation of the first Python MD-HI baseline."""
import argparse
import csv
import json
import platform
from collections import defaultdict
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
import numpy as np
import yaml
from optibelt_hi.data.audit import sha256, write_csv
from optibelt_hi.data.recordings import CHANNELS
from optibelt_hi.features.core import FEATURE_NAMES
from optibelt_hi.model.baseline import fit_model
from optibelt_hi.monitoring.health import calibrate, health_index, ewma, persistent_alarm

VARIANTS=("fusion","vibration","current","torque","diagonal")

def load_model_config(path):
    config=yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    required={"schema_version","protocol","feature_schema","variants","recording_weighting",
              "drop_suffixes","relative_scale_floor","correlation_limit","shrinkage",
              "calibration_quantile","ewma_alpha","persistent_windows","hi_mapping","alarm_comparison"}
    if not isinstance(config,dict) or set(config)!=required:
        raise ValueError("Model configuration keys differ from the implemented schema.")
    fixed={"schema_version":1,"protocol":"grouped_v1","feature_schema":"candidate_v1",
           "recording_weighting":"equal","hi_mapping":"100_over_1_plus_squared_threshold_ratio",
           "alarm_comparison":"strictly_greater"}
    if any(config[k]!=v for k,v in fixed.items()) or config["variants"]!=list(VARIANTS):
        raise ValueError("Unsupported model configuration policy.")
    if config["drop_suffixes"]!=["rms","power_fraction_5000_12800"]:
        raise ValueError("Unsupported fixed redundancy exclusions.")
    for key in ("relative_scale_floor","correlation_limit","shrinkage","calibration_quantile","ewma_alpha"):
        value=config[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value) or not 0<value<=1:
            raise ValueError(f"Invalid numerical setting: {key}")
    count=config["persistent_windows"]
    if isinstance(count,bool) or not isinstance(count,int) or count<1:
        raise ValueError("Invalid persistence setting.")
    return config

def variant_columns(names,variant):
    if variant in {"fusion","diagonal"}: return list(range(len(names)))
    prefixes={"vibration":("vibration__",),"torque":("torque__",),
              "current":("current_r__","current_s__","current_t__")}[variant]
    selected=[i for i,name in enumerate(names) if name.startswith(prefixes)]
    if not selected: raise ValueError("Variant has no input features.")
    return selected

def evaluate_fold(data, roles, names, config, fold):
    roles=sorted(roles,key=lambda r:r["recording_id"])
    if len({r["recording_id"] for r in roles})!=len(roles):
        raise ValueError("Duplicate recording in fold.")
    groups=defaultdict(set)
    ids={role:[] for role in ("fit","calibration","test")}
    for r in roles:
        if r["role"] not in ids: continue
        key=r["recording_id"]
        if key not in data: raise ValueError("Active assignment has no feature data.")
        record=data[key]
        if record["condition"]!=r["condition"] or record["operating_group"]!=r["operating_group"]:
            raise ValueError("Assignment and feature metadata disagree.")
        if r["role"]!="test" and r["condition"]!="normal":
            raise ValueError("Fit and calibration must be healthy only.")
        ids[r["role"]].append(key); groups[r["operating_group"]].add(r["role"])
    if not all(ids.values()): raise ValueError("Each fold needs fit, calibration and test records.")
    if any(len(roles)>1 for roles in groups.values()):
        raise ValueError("An operating group crosses active roles.")
    models={}; records=[]; predictions=[]
    for variant in config["variants"]:
        columns=variant_columns(names,variant)
        inputs=lambda key:data[key]["features"][:,columns]
        model=fit_model([inputs(key) for key in ids["fit"]],[names[i] for i in columns],
            kind="diagonal" if variant=="diagonal" else "shrinkage",
            shrinkage=config["shrinkage"],correlation_limit=config["correlation_limit"],
            relative_scale_floor=config["relative_scale_floor"],drop_suffixes=config["drop_suffixes"])
        calibration=[model.score(inputs(key)) for key in ids["calibration"]]
        smooth_cal=[ewma(values,config["ewma_alpha"]) for values in calibration]
        raw_threshold=calibrate(calibration,config["calibration_quantile"])
        smooth_threshold=calibrate(smooth_cal,config["calibration_quantile"])
        models[variant]={"model":model.to_dict(),"source_column_indices":columns,
            "fit_recordings":ids["fit"],"calibration_recordings":ids["calibration"],
            "threshold_raw":raw_threshold,"threshold_ewma":smooth_threshold,
            "calibration":[{"recording_id":key,"windows":len(raw),
                "raw_alarm_fraction":float(np.mean(raw>raw_threshold)),
                "ewma_alarm_fraction":float(np.mean(smooth>smooth_threshold))}
                for key,raw,smooth in zip(ids["calibration"],calibration,smooth_cal,strict=True)]}
        for key in ids["test"]:
            record=data[key]; raw=model.score(inputs(key)); smooth=ewma(raw,config["ewma_alpha"])
            raw_hi=health_index(raw,raw_threshold); smooth_hi=health_index(smooth,smooth_threshold)
            raw_flags=raw>raw_threshold; smooth_flags=smooth>smooth_threshold
            raw_persist=persistent_alarm(raw_flags,config["persistent_windows"])
            smooth_persist=persistent_alarm(smooth_flags,config["persistent_windows"])
            for i,(start,stop) in enumerate(record["bounds"]):
                predictions.append({"fold":fold,"variant":variant,"recording_id":key,
                    "window_index":i,"start_seconds":int(start)/25600,"stop_seconds":int(stop)/25600,
                    "condition":record["condition"],"operating_group":record["operating_group"],
                    "distance":float(raw[i]),"distance_ewma":float(smooth[i]),
                    "threshold":raw_threshold,"threshold_ewma":smooth_threshold,
                    "health_index":float(raw_hi[i]),"health_index_ewma":float(smooth_hi[i]),
                    "alarm":bool(raw_flags[i]),"alarm_ewma":bool(smooth_flags[i]),
                    "persistent_alarm":bool(raw_persist[i]),"persistent_alarm_ewma":bool(smooth_persist[i])})
            for stream,values,hi,threshold,flags,persist in [
                ("raw",raw,raw_hi,raw_threshold,raw_flags,raw_persist),
                ("ewma",smooth,smooth_hi,smooth_threshold,smooth_flags,smooth_persist)]:
                alert=np.flatnonzero(persist)
                records.append({"fold":fold,"variant":variant,"stream":stream,"recording_id":key,
                    "condition":record["condition"],"operating_group":record["operating_group"],
                    "windows":len(values),"threshold":threshold,"alarm_windows":int(flags.sum()),
                    "alarm_fraction":float(flags.mean()),"persistent_alert":bool(len(alert)),
                    "first_alert_seconds_from_start":float(record["bounds"][alert[0],1]/25600) if len(alert) else None,
                    "median_distance":float(np.median(values)),"median_health_index":float(np.median(hi)),
                    "minimum_health_index":float(hi.min())})
    return {"models":models,"records":records,"predictions":predictions}

def summarize(records):
    output=[]
    for variant in sorted({r["variant"] for r in records}):
        for stream in sorted({r["stream"] for r in records}):
            selected=[r for r in records if r["variant"]==variant and r["stream"]==stream]
            if not selected: continue
            row={"variant":variant,"stream":stream}
            for label,healthy in (("healthy",True),("fault",False)):
                cohort=[r for r in selected if (r["condition"]=="normal")==healthy]
                fractions=[r["alarm_fraction"] for r in cohort]
                row.update({f"{label}_recordings":len(cohort),
                    f"{label}_mean_alarm_fraction":float(np.mean(fractions)) if cohort else None,
                    f"{label}_minimum_alarm_fraction":min(fractions) if cohort else None,
                    f"{label}_maximum_alarm_fraction":max(fractions) if cohort else None,
                    f"{label}_records_with_persistent_alert":sum(r["persistent_alert"] for r in cohort)})
            output.append(row)
    return output

def read_csv(path):
    with Path(path).open(encoding="utf-8-sig",newline="") as f: return list(csv.DictReader(f))

def safe_name(name):
    if not name or name in {".",".."} or Path(name).name!=name or "/" in name or "\\" in name:
        raise ValueError("Use a single directory name.")

def load_inputs(project,feature_folder):
    from .splits import build_folds
    frozen=project/"dataset/splits/grouped_v1"
    protocol=json.loads((frozen/"protocol.json").read_text(encoding="utf-8"))
    admission_path=project/"dataset/splits/data_admission.csv"
    assignments_path=frozen/"assignments.csv"
    if sha256(admission_path)!=protocol["admission_sha256"] or sha256(assignments_path)!=protocol["assignments_sha256"]:
        raise ValueError("Frozen split/admission hash mismatch.")
    admission=read_csv(admission_path); assignments=read_csv(assignments_path)
    expected=build_folds(admission)
    if assignments!=[{k:str(v) for k,v in row.items()} for row in expected]:
        raise ValueError("Frozen assignments differ from the declared grouping rule.")
    feature_report=json.loads((feature_folder/"run.json").read_text(encoding="utf-8"))
    if feature_report["status"]!="complete" or feature_report["schema"]!="candidate_v1":
        raise ValueError("Feature run is not complete candidate_v1.")
    for key,value in {"admission_sha256":sha256(admission_path),
                      "assignments_sha256":sha256(assignments_path),
                      "protocol_sha256":sha256(frozen/"protocol.json")}.items():
        if feature_report[key]!=value: raise ValueError("Feature provenance differs from frozen inputs.")
    if feature_report["config_sha256"]!=sha256(project/"configs/preprocessing.yaml"):
        raise ValueError("Preprocessing configuration changed since feature extraction.")
    for relative,digest in feature_report["implementation_sha256"].items():
        if sha256(project/"src/optibelt_hi"/relative)!=digest:
            raise ValueError("Feature implementation changed since extraction.")
    if sha256(feature_folder/"windows.csv")!=feature_report["windows_sha256"]:
        raise ValueError("Feature window metadata hash mismatch.")
    admitted={r["recording_id"]:r for r in admission if r["admission_status"]=="candidate_complete_recording"}
    items=feature_report["recordings"]
    if len(items)!=len(admitted) or {r["recording_id"] for r in items}!=set(admitted):
        raise ValueError("Feature population differs from admission.")
    names=[f"{channel}__{name}" for channel in CHANNELS for name in FEATURE_NAMES]
    group_by_id={r["recording_id"]:r["operating_group"] for r in assignments}
    windows=read_csv(feature_folder/"windows.csv")
    window_lookup=defaultdict(list)
    for w in windows: window_lookup[w["recording_id"]].append(w)
    if set(window_lookup)!=set(admitted): raise ValueError("Window metadata population differs.")
    data={}
    for item in items:
        key=item["recording_id"]; source=admitted[key]
        if item["input_sha256"]!=source["sha256"] or item["condition"]!=source["condition"]:
            raise ValueError("Feature source metadata mismatch.")
        path=(feature_folder/item["artifact"]).resolve()
        if not path.is_relative_to(feature_folder.resolve()) or sha256(path)!=item["artifact_sha256"]:
            raise ValueError("Feature artifact hash/path mismatch.")
        with np.load(path,allow_pickle=False) as archive:
            x=archive["features"].copy(); bounds=archive["bounds"].copy()
            if archive["feature_names"].tolist()!=names: raise ValueError("Predictor schema mismatch.")
        if x.shape!=(item["windows"],len(names)) or not np.isfinite(x).all():
            raise ValueError("Feature matrix shape or finite-value failure.")
        if bounds.dtype.kind not in "iu" or bounds.shape!=(len(x),2):
            raise ValueError("Invalid window bounds.")
        if not np.array_equal(bounds[:,0],np.arange(len(x))*25600) or not np.all(bounds[:,1]-bounds[:,0]==51200):
            raise ValueError("Window policy differs from two seconds with one-second hop.")
        metadata=window_lookup[key]
        if len(metadata)!=len(x): raise ValueError("Window metadata length mismatch.")
        for i,w in enumerate(metadata):
            if int(w["window_index"])!=i or w["condition"]!=source["condition"] or (int(w["start_sample"]),int(w["stop_sample"]))!=tuple(bounds[i]):
                raise ValueError("Window metadata disagrees with feature artifact.")
        data[key]={"features":x,"bounds":bounds,"condition":source["condition"],"operating_group":group_by_id[key]}
    return data,assignments,names

def run(project, features, name):
    safe_name(name); safe_name(features)
    project=Path(project).resolve(); folder=project/"outputs/runs"/name
    folder.mkdir(parents=True,exist_ok=False)
    report={"status":"running","created_utc":datetime.now(timezone.utc).isoformat(),"folds_completed":[]}
    def save():
        (folder/"run.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    save()
    try:
        config_path=project/"configs/model.yaml"; config=load_model_config(config_path)
        feature_folder=project/"outputs/runs"/features
        data,assignments,names=load_inputs(project,feature_folder)
        source=project/"src/optibelt_hi"
        report.update(configuration=config,config_sha256=sha256(config_path),python=platform.python_version(),
            environment={p:version(p) for p in ("numpy","scipy","h5py")},
            feature_run=features,feature_run_sha256=sha256(feature_folder/"run.json"),
            assignments_sha256=sha256(project/"dataset/splits/grouped_v1/assignments.csv"),
            model_protocol_sha256=sha256(project/"docs/model_protocol_v1.md"),
            implementation_sha256={p.relative_to(source).as_posix():sha256(p) for p in sorted(source.rglob("*.py"))})
        # Freeze the numerical plan before any real score is computed.
        (folder/"pre_evaluation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        (folder/"model_protocol.md").write_text((project/"docs/model_protocol_v1.md").read_text(encoding="utf-8"),encoding="utf-8")
        all_records=[]; predictions=[]
        for fold in range(1,6):
            result=evaluate_fold(data,[r for r in assignments if int(r["fold"])==fold],names,config,fold)
            (folder/f"models_fold_{fold}.json").write_text(json.dumps(result["models"],indent=2,allow_nan=False),encoding="utf-8")
            all_records.extend(result["records"]); predictions.extend(result["predictions"])
            report["folds_completed"].append(fold); save()
            print(f"Fold {fold}/5 complete; all variants fixed in advance.",flush=True)
        write_csv(folder/"predictions.csv",predictions)
        write_csv(folder/"record_metrics.csv",all_records)
        summary=summarize(all_records); write_csv(folder/"comparison.csv",summary)
        breakdown=[]
        for fold in range(1,6):
            breakdown.extend({"fold":fold,**r} for r in summarize([r for r in all_records if r["fold"]==fold]))
        write_csv(folder/"fold_comparison.csv",breakdown)
        condition=[]
        for label in sorted({r["condition"] for r in all_records}):
            condition.extend({"condition":label,**r} for r in summarize([r for r in all_records if r["condition"]==label]))
        write_csv(folder/"condition_comparison.csv",condition)
        report.update(status="complete",completed_utc=datetime.now(timezone.utc).isoformat(),
            tested_recordings=len({r["recording_id"] for r in all_records}),
            prediction_rows=len(predictions),record_metric_rows=len(all_records),comparison=summary,
            interpretation="Retrospective held-out operating groups; no independent-machine or lifetime claims.",
            artifacts={p.name:sha256(p) for p in sorted(folder.iterdir()) if p.is_file() and p.name!="run.json"})
        save()
        return folder
    except Exception as exc:
        report.update(status="failed",error=str(exc)); save(); raise

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",type=Path,required=True)
    parser.add_argument("--features",required=True)
    parser.add_argument("--name",required=True)
    args=parser.parse_args()
    print(run(args.project,args.features,args.name))

