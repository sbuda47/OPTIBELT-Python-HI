import copy
import numpy as np
import pytest
from optibelt_hi.deployment.bundle import FORMAT,MONITORING,validate
from optibelt_hi.deployment.monitor import Monitor,UnsupportedCondition
from optibelt_hi.data.recordings import CHANNELS
from optibelt_hi.features.core import FEATURE_NAMES
from optibelt_hi.model.baseline import fit_model
from optibelt_hi.monitoring.health import ewma,persistent_alarm

CONDITION=dict(hp=1.,load=0,profile="invariant_speed",upper=50)


def example():
    names=[f"{c}__{f}" for c in CHANNELS for f in FEATURE_NAMES]
    rng=np.random.default_rng(32)
    model=fit_model([rng.normal(size=(100,len(names)))],names)
    bundle=dict(format=FORMAT,candidate_version="test_candidate",feature_names=names,monitoring=dict(MONITORING),
        preprocessing=dict(target_rate_hz=25600,window_seconds=2.,hop_seconds=1.),
        load_centres={str(load):np.zeros(len(names)).tolist() for load in (0,30,60)},
        supported_conditions=[dict(CONDITION)],
        references={arm:dict(model=model.to_dict(),thresholds=dict(raw=4.,ewma=4.)) for arm in ("A","C")})
    return bundle,rng.normal(size=(45,len(names)))


def push(m,x,i,names,rid="one"):
    return m.push(x,i*25600,(i+2)*25600,recording_id=rid,feature_names=names)


def test_stateful_scoring_matches_batch_and_warmup():
    b,x=example();m=Monitor(b,CONDITION,"one")
    rows=[push(m,v,i,b["feature_names"]) for i,v in enumerate(x)]
    from optibelt_hi.model.baseline import Model
    raw=Model.from_dict(b["references"]["C"]["model"]).score(x)
    sm=ewma(raw,.2);flags=(sm>4)&(np.arange(len(x))>=10)
    np.testing.assert_allclose([r["distance_ewma"] for r in rows],sm,rtol=1e-12,atol=1e-12)
    np.testing.assert_array_equal([r["persistent_ewma"] for r in rows],persistent_alarm(flags,3))
    assert all(r["status"]=="warming_up" and not r["persistent_ewma"] for r in rows[:10])


def test_invalid_input_does_not_advance_state():
    b,x=example();m=Monitor(b,CONDITION,"one")
    first=push(m,x[0],0,b["feature_names"])
    for vector,start,names,rid in [(np.full(60,np.nan),1,b["feature_names"],"one"),
                                   (x[1],0,b["feature_names"],"one"),(x[1],2,b["feature_names"],"one"),
                                   (x[1],1,b["feature_names"][::-1],"one"),(x[1],1,b["feature_names"],"two")]:
        with pytest.raises(ValueError):push(m,vector,start,names,rid)
    second=push(m,x[1],1,b["feature_names"])
    assert second["episode_window_index"]==1
    assert second["distance_ewma"]==pytest.approx(.2*second["distance"]+.8*first["distance"])


def test_new_session_resets_and_bundle_is_detached():
    b,x=example();m=Monitor(b,CONDITION,"one")
    for i,v in enumerate(x):push(m,v,i,b["feature_names"])
    new=Monitor(b,CONDITION,"two")
    first=push(new,x[0],100,b["feature_names"],"two")
    assert first["distance"]==first["distance_ewma"] and first["status"]=="warming_up"
    b["references"]["C"]["thresholds"]["ewma"]=1e9
    result=push(new,x[1],101,b["feature_names"],"two")
    assert result["threshold_ewma"]==4.


def test_unsupported_condition_and_corrupt_schema_rejected():
    b,_=example()
    with pytest.raises(UnsupportedCondition):Monitor(b,{**CONDITION,"hp":5.},"one")
    bad=copy.deepcopy(b);bad["references"]["C"]["thresholds"]["raw"]=-1
    with pytest.raises(ValueError):validate(bad)
    bad=copy.deepcopy(b);bad["feature_names"]=bad["feature_names"][::-1]
    with pytest.raises(ValueError):validate(bad)


def test_bundle_checksum_rejects_changed_artifact(tmp_path):
    import json
    from optibelt_hi.data.audit import sha256
    from optibelt_hi.deployment.bundle import load_bundle
    b,_=example()
    artifact=tmp_path/"bundle.json";artifact.write_text(json.dumps(b))
    (tmp_path/"manifest.json").write_text(json.dumps(dict(format=FORMAT,candidate_version="test_candidate",bundle_sha256=sha256(artifact))))
    assert load_bundle(tmp_path,verify_code=False)==b
    artifact.write_text(artifact.read_text()+" ")
    with pytest.raises(ValueError):load_bundle(tmp_path,verify_code=False)

