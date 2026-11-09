import csv
import json
from pathlib import Path
import numpy as np
import pytest
from optibelt_hi.data.audit import sha256, write_csv

def fixture(project):
    (project/"dataset/splits").mkdir(parents=True)
    (project/"configs").mkdir()
    import shutil
    shutil.copyfile(Path(__file__).parents[1]/"configs/preprocessing.yaml",project/"configs/preprocessing.yaml")
    records=[]
    for i,(hp,load) in enumerate([(3,0),(3,30),(3,60),(5,0),(5,30)]):
        path=project/f"dataset/raw/varying_speed/Normal_{hp}HP_{load}%_58Hz.mat"
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(f"raw-fixture-{i}".encode())
        records.append(dict(recording_id=path.stem,relative_path=path.relative_to(project).as_posix(),
            sha256=sha256(path),condition="normal",motor_capacity_hp=str(hp),
            load_percent_label=str(load),admission_status="candidate_complete_recording"))
    write_csv(project/"dataset/splits/data_admission.csv",records)
    return records

def test_freeze_and_batch_traceable_outputs(tmp_path,monkeypatch):
    from optibelt_hi.evaluation.splits import freeze
    from optibelt_hi.features import batch
    fixture(tmp_path)
    frozen=freeze(tmp_path)
    with pytest.raises(FileExistsError): freeze(tmp_path)
    t=np.arange(3*25600)/25600
    samples=np.column_stack([np.sin(2*np.pi*(100+300*i)*t) for i in range(5)])
    calls=[]
    def prepared(path,duration):
        calls.append(path.stem)
        return samples
    # Raw MAT loading/resampling has dedicated real fixtures and analytic tests.
    # This test isolates orchestration and its actual filesystem provenance.
    monkeypatch.setattr(batch,"prepare_recording",prepared)
    folder=batch.run_batch(tmp_path,"demo")
    report=json.loads((folder/"run.json").read_text())
    assert report["status"]=="complete" and report["total_windows"]==10
    assert len(calls)==5 and report["feature_count"]==60
    for r in report["recordings"]:
        with np.load(folder/r["artifact"],allow_pickle=False) as d:
            assert d["features"].shape==(2,60)
            assert len(d["feature_names"])==60
        assert r["artifact_sha256"]==sha256(folder/r["artifact"])
    with pytest.raises(FileExistsError): batch.run_batch(tmp_path,"demo")
    assert frozen.is_dir()

def test_hash_mismatch_stops_before_processing(tmp_path,monkeypatch):
    from optibelt_hi.evaluation.splits import freeze
    from optibelt_hi.features import batch
    records=fixture(tmp_path); freeze(tmp_path)
    (tmp_path/records[0]["relative_path"]).write_bytes(b"changed")
    def forbidden(*args): raise AssertionError("Must verify raw hash before preparation")
    monkeypatch.setattr(batch,"prepare_recording",forbidden)
    with pytest.raises(ValueError,match="hash"):
        batch.run_batch(tmp_path,"bad")
    report=json.loads((tmp_path/"outputs/runs/bad/run.json").read_text())
    assert report["status"]=="failed"

def test_changed_admission_after_freeze_is_rejected(tmp_path):
    from optibelt_hi.evaluation.splits import freeze
    from optibelt_hi.features import batch
    fixture(tmp_path); freeze(tmp_path)
    with (tmp_path/"dataset/splits/data_admission.csv").open("a") as f: f.write("\n")
    with pytest.raises(ValueError,match="admission"):
        batch.run_batch(tmp_path,"changed_admission")

@pytest.mark.parametrize("name",["..","../outside","nested/run",""])
def test_output_path_cannot_escape(tmp_path,name):
    from optibelt_hi.features import batch
    with pytest.raises(ValueError):
        batch.run_batch(tmp_path,name)

