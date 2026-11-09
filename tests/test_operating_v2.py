import json
import numpy as np
import pytest

def api():
    from optibelt_hi.model.operating_v2 import blocks, event_level, build_bank, score_episode
    return blocks,event_level,build_bank,score_episode

def example():
    rng=np.random.default_rng(2); names=["a","b","c"]
    entries=[]
    for hp,load,offset in [(1,0,2),(1,30,20),(3,0,100)]:
        noise=rng.normal(size=(119,3))
        bounds=np.column_stack([np.arange(119)*25600,np.arange(119)*25600+51200])
        entries.append(dict(recording_id=f"normal_{hp}_{load}",hp=hp,state=f"{hp}_{load}",
             condition="normal",features=noise+offset,bounds=bounds,duration=120))
    return entries,names

def test_temporal_blocks_have_sample_gaps_and_equal_horizons():
    blocks,_,_,_=api()
    for duration in (120,300):
        bounds=np.column_stack([np.arange(duration-1)*25600,np.arange(duration-1)*25600+51200])
        result=blocks(bounds,duration)
        assert len(result["calibration"])==len(result["check"])==25
        assert len(result["fit"])>=55
        for a,b in [("fit","calibration"),("calibration","check")]:
            assert bounds[result[b][0],0]-bounds[result[a][-1],1]>=4*25600
        assert not set(result["fit"])&set(result["calibration"])
    with pytest.raises(ValueError): blocks(np.array([[0,51200]]),2)

def test_event_statistic_matches_strict_three_window_event():
    _,level,_,_=api()
    x=np.array([1.,7.,8.,6.,2.,9.,9.])
    assert level(x)==6
    for q in (5.9,6,6.1):
        consecutive=any(np.all(x[i:i+3]>q) for i in range(len(x)-2))
        assert consecutive==(level(x)>q)

def test_capacity_state_routing_and_serialization():
    _,_,build,score=api()
    entries,names=example(); bank=build(entries,names)
    assert set(bank["models"])=={"1","3"} and len(bank["states"])==3
    loaded=json.loads(json.dumps(bank))
    out=score(loaded,entries[0]["features"][-25:],entries[0]["state"],names)
    assert out["status"]=="supported_development" and np.isfinite(out["distance"]).all()
    assert not out["eligible"][:10].any() and out["eligible"][10:].all()
    unsupported=score(loaded,entries[0]["features"][-25:],"5_60",names)
    assert unsupported["status"]=="unsupported" and unsupported["distance"] is None
    with pytest.raises(ValueError): score(loaded,entries[0]["features"],entries[0]["state"],list(reversed(names)))

def test_check_data_cannot_change_fitted_bank():
    blocks,_,build,_=api()
    entries,names=example(); before=build(entries,names)
    for e in entries:
        indices=blocks(e["bounds"],e["duration"])["check"]
        e["features"][indices]+=1e5
    assert json.dumps(before,sort_keys=True)==json.dumps(build(entries,names),sort_keys=True)

def test_faults_never_enter_bank():
    _,_,build,_=api()
    entries,names=example(); entries[0]["condition"]="bearing"
    with pytest.raises(ValueError,match="healthy"): build(entries,names)

def test_state_centres_remove_known_offsets_without_cross_rating_pooling():
    _,_,build,score=api()
    entries,names=example()
    base=entries[0]["features"].copy()
    entries[1]["features"]=base+50
    bank=build(entries,names)
    a=score(bank,base[-25:],entries[0]["state"],names)
    b=score(bank,(base+50)[-25:],entries[1]["state"],names)
    np.testing.assert_allclose(a["distance"],b["distance"],rtol=1e-10,atol=1e-10)
    original=json.dumps(bank["models"]["1"],sort_keys=True)
    entries[2]["features"]*=5
    assert json.dumps(build(entries,names)["models"]["1"],sort_keys=True)==original

def test_calibration_threshold_applies_to_full_event_chain():
    blocks,_,build,score=api()
    entries,names=example(); bank=build(entries,names)
    for e in entries:
        indices=blocks(e["bounds"],e["duration"])["calibration"]
        result=score(bank,e["features"][indices],e["state"],names)
        assert not result["persistent"].any()
        assert not result["persistent_ewma"].any()


