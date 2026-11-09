import json
import numpy as np
import pytest
from optibelt_hi.model.operating_v2 import blocks

def fixture():
    rng=np.random.default_rng(42)
    bounds=np.column_stack([np.arange(299)*25600,np.arange(299)*25600+51200])
    return [dict(recording_id=f"n{load}_{j}",load=load,hp=j+1,condition="normal",duration=300,
      bounds=bounds,features=rng.normal(size=(299,3))+load/10+j) for load in (0,30,60) for j in (0,1)],["a","b","c"]

def test_calibration_uses_complete_guarded_episodes():
    from optibelt_hi.model.load_aware import calibration_episodes
    entries,_=fixture(); episodes=calibration_episodes(entries[0]["bounds"],300)
    assert len(episodes)==2 and all(len(e)==25 for e in episodes)
    assert entries[0]["bounds"][episodes[1][0],0]-entries[0]["bounds"][episodes[0][-1],1]==3*25600

def test_hp_and_check_values_cannot_change_bank():
    from optibelt_hi.model.load_aware import build_bank
    entries,names=fixture(); before=build_bank(entries,names)
    for e in entries:
        e["hp"]=999
        e["features"][blocks(e["bounds"],e["duration"])["check"]]+=1e6
    assert json.dumps(before,sort_keys=True)==json.dumps(build_bank(entries,names),sort_keys=True)

def test_paired_arms_share_scores_and_load_threshold_cannot_be_higher():
    from optibelt_hi.model.load_aware import build_bank,score
    entries,names=fixture(); bank=build_bank(entries,names)
    for e in entries:
        x=e["features"][-25:]
        for a,b in (("A","B"),("C","D")):
            one=score(bank,x,e["load"],a,names); two=score(bank,x,e["load"],b,names)
            np.testing.assert_array_equal(one["distance"],two["distance"])
            np.testing.assert_array_equal(one["distance_ewma"],two["distance_ewma"])
            assert one["threshold_raw"]>=two["threshold_raw"]
            assert one["threshold_ewma"]>=two["threshold_ewma"]
            assert np.all(~one["persistent_ewma"]|two["persistent_ewma"])

def test_unsupported_and_fault_fitting_rejected():
    from optibelt_hi.model.load_aware import build_bank,score
    entries,names=fixture(); bank=build_bank(entries,names)
    assert score(bank,entries[0]["features"],45,"B",names)["status"]=="unsupported"
    with pytest.raises(ValueError): score(bank,entries[0]["features"],0,"B",names[::-1])
    entries[0]["condition"]="bearing"
    with pytest.raises(ValueError): build_bank(entries,names)

