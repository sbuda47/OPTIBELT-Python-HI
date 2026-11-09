import json
import numpy as np
import pytest
from pathlib import Path
import yaml

def population():
    from optibelt_hi.features.core import FEATURE_NAMES
    from optibelt_hi.data.recordings import CHANNELS
    rng=np.random.default_rng(3)
    names=[f"{channel}__{f}" for channel in CHANNELS for f in FEATURE_NAMES]
    data={}
    for name,group,condition,offset in [("fit_a","a","normal",0),("fit_b","b","normal",.1),
                                      ("cal","c","normal",.2),("test","d","normal",.3),
                                      ("fault","d","bearing",5.)]:
        x=rng.normal(size=(30,len(names)))+offset
        data[name]={"features":x,"bounds":np.column_stack([np.arange(30)*25600,np.arange(30)*25600+51200]),
                    "condition":condition,"operating_group":group}
    roles=[{"recording_id":key,"role":"fit" if key.startswith("fit") else "calibration" if key=="cal" else "test",
            "condition":r["condition"],"operating_group":r["operating_group"]} for key,r in data.items()]
    config=yaml.safe_load((Path(__file__).parents[1]/"configs/model.yaml").read_text())
    return data,roles,names,config

def test_heldout_values_cannot_change_model_or_calibration():
    from optibelt_hi.evaluation.model_run import evaluate_fold
    data,roles,names,config=population()
    first=evaluate_fold(data,roles,names,config,fold=1)
    data["test"]["features"][:]=1e6
    data["fault"]["features"][:]=-1e6
    second=evaluate_fold(data,roles,names,config,fold=1)
    assert json.dumps(first["models"],sort_keys=True)==json.dumps(second["models"],sort_keys=True)
    assert len(first["models"])==5 and len(first["records"])==20
    assert len(first["predictions"])==300
    assert first["records"]!=second["records"]
    for record in first["records"]:
        assert record["recording_id"] in {"test","fault"}

def test_fault_fit_or_shared_group_rejected():
    from optibelt_hi.evaluation.model_run import evaluate_fold
    data,roles,names,config=population()
    roles[0]["condition"]="bearing"
    with pytest.raises(ValueError,match="healthy|metadata"):
        evaluate_fold(data,roles,names,config,1)
    data,roles,names,config=population()
    roles[-1]["operating_group"]="a"
    data["fault"]["operating_group"]="a"
    with pytest.raises(ValueError,match="group"):
        evaluate_fold(data,roles,names,config,1)

def test_serialized_model_and_threshold_reproduce_predictions():
    from optibelt_hi.evaluation.model_run import evaluate_fold
    from optibelt_hi.model.baseline import Model
    from optibelt_hi.monitoring.health import health_index, ewma
    data,roles,names,config=population()
    result=evaluate_fold(data,roles,names,config,1)
    state=result["models"]["fusion"]
    model=Model.from_dict(state["model"])
    predicted=[r for r in result["predictions"] if r["variant"]=="fusion" and r["recording_id"]=="test"]
    raw=model.score(data["test"]["features"])
    np.testing.assert_allclose([r["distance"] for r in predicted],raw)
    np.testing.assert_allclose([r["health_index"] for r in predicted],health_index(raw,state["threshold_raw"]))
    np.testing.assert_allclose([r["distance_ewma"] for r in predicted],ewma(raw))
    assert state["fit_recordings"]==["fit_a","fit_b"] and state["calibration_recordings"]==["cal"]

def test_summary_weights_records_not_windows():
    from optibelt_hi.evaluation.model_run import summarize
    rows=[]
    for key,n,fraction,condition in [("a",1000,0.,"normal"),("b",10,1.,"normal"),("c",10,.8,"bearing")]:
        rows.append({"variant":"fusion","stream":"raw","condition":condition,"alarm_fraction":fraction,
                     "persistent_alert":fraction>0,"windows":n,"recording_id":key})
    result=summarize(rows)[0]
    assert result["healthy_mean_alarm_fraction"]==.5
    assert result["fault_mean_alarm_fraction"]==.8
    assert result["healthy_recordings"]==2 and result["fault_recordings"]==1

def test_invalid_config_and_output_names_fail(tmp_path):
    from optibelt_hi.evaluation.model_run import run
    for name in ("..","nested/run",""):
        with pytest.raises(ValueError):
            run(tmp_path,"features",name)

def on_disk_population(project):
    import hashlib
    import shutil
    from optibelt_hi.data.audit import sha256, write_csv
    from optibelt_hi.evaluation.splits import freeze
    from optibelt_hi.features.core import FEATURE_NAMES
    from optibelt_hi.data.recordings import CHANNELS
    stage=Path(__file__).parents[1]
    (project/"configs").mkdir(parents=True)
    (project/"docs").mkdir()
    for name in ("model.yaml","preprocessing.yaml"):
        shutil.copyfile(stage/"configs"/name,project/"configs"/name)
    shutil.copyfile(stage/"docs/model_protocol_v1.md",project/"docs/model_protocol_v1.md")
    (project/"dataset/splits").mkdir(parents=True)
    records=[]; rng=np.random.default_rng(9)
    names=[f"{c}__{f}" for c in CHANNELS for f in FEATURE_NAMES]
    folder=project/"outputs/runs/features"; folder.mkdir(parents=True)
    artifacts=[]; windows=[]
    for hp,load in [(3,0),(3,30),(3,60),(5,0),(5,30)]:
        for condition in ("normal","bearing"):
            name=f"{condition}_{hp}_{load}"
            digest=hashlib.sha256(name.encode()).hexdigest()
            records.append({"recording_id":name,"relative_path":f"dataset/raw/{name}.mat",
                "sha256":digest,"condition":condition,"motor_capacity_hp":str(hp),
                "load_percent_label":str(load),"admission_status":"candidate_complete_recording"})
            bounds=np.column_stack([np.arange(20)*25600,np.arange(20)*25600+51200])
            x=rng.normal(size=(20,60))+(3 if condition=="bearing" else 0)
            np.savez_compressed(folder/(name+".npz"),features=x,bounds=bounds,feature_names=np.array(names))
            artifacts.append({"recording_id":name,"input_sha256":digest,"condition":condition,
                "artifact":name+".npz","artifact_sha256":sha256(folder/(name+".npz")),"windows":20})
            windows.extend({"recording_id":name,"window_index":i,"condition":condition,
                "start_sample":int(start),"stop_sample":int(stop)} for i,(start,stop) in enumerate(bounds))
    write_csv(project/"dataset/splits/data_admission.csv",records)
    frozen=freeze(project); write_csv(folder/"windows.csv",windows)
    report={"status":"complete","schema":"candidate_v1","recordings":artifacts,
        "admission_sha256":sha256(project/"dataset/splits/data_admission.csv"),
        "assignments_sha256":sha256(frozen/"assignments.csv"),"protocol_sha256":sha256(frozen/"protocol.json"),
        "config_sha256":sha256(project/"configs/preprocessing.yaml"),
        "implementation_sha256":{},"windows_sha256":sha256(folder/"windows.csv")}
    (folder/"run.json").write_text(json.dumps(report))
    return folder

def test_full_disk_run_is_immutable_and_verifies_artifacts(tmp_path):
    from optibelt_hi.evaluation.model_run import run
    folder=on_disk_population(tmp_path)
    result=run(tmp_path,"features","model")
    report=json.loads((result/"run.json").read_text())
    assert report["status"]=="complete" and report["tested_recordings"]==10
    assert report["prediction_rows"]==1000 and report["record_metric_rows"]==100
    assert len(report["comparison"])==10
    with pytest.raises(FileExistsError): run(tmp_path,"features","model")
    artifact=next(folder.glob("*.npz")); artifact.write_bytes(b"changed")
    with pytest.raises(ValueError,match="hash"): run(tmp_path,"features","tampered")
    assert json.loads((tmp_path/"outputs/runs/tampered/run.json").read_text())["status"]=="failed"

def test_config_rejects_unimplemented_policy(tmp_path):
    from optibelt_hi.evaluation.model_run import load_model_config
    _,_,_,config=population()
    config["recording_weighting"]="windows"
    path=tmp_path/"config.yaml"; path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError): load_model_config(path)


