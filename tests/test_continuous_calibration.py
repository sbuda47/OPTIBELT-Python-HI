import copy
import numpy as np
import pytest
from optibelt_hi.evaluation.continuous_calibration import calibration_indices, calibrate_continuously, apply_thresholds
from optibelt_hi.model.load_aware import build_bank, score
from test_load_aware import fixture


def test_full_calibration_includes_unused_tail():
    entries,_=fixture()
    idx=calibration_indices(entries[0]["bounds"],300)
    np.testing.assert_array_equal(idx,np.arange(152,222))
    assert len(idx)-10==60


def test_calibration_ignores_check_data_hp_and_does_not_modify_or_refit_bank(monkeypatch):
    entries,names=fixture();bank=build_bank(entries,names);before=copy.deepcopy(bank)
    monkeypatch.setattr("optibelt_hi.model.baseline.fit_model",lambda *a,**k: (_ for _ in ()).throw(AssertionError("Refit")))
    result=calibrate_continuously(bank,entries,names)
    for e in entries:
        e["hp"]=999
        e["features"][227:]+=1e6
    assert calibrate_continuously(bank,entries,names)==result
    assert bank==before


def test_tail_values_influence_threshold_and_faults_are_rejected():
    entries,names=fixture();bank=build_bank(entries,names)
    original=calibrate_continuously(bank,entries,names)
    entries[0]["features"][212:222]+=1e4
    revised=calibrate_continuously(bank,entries,names)
    for arm in ("A","C"):
        assert revised["thresholds"][arm]["ewma"]>original["thresholds"][arm]["ewma"]
    entries[0]["condition"]="bearing"
    with pytest.raises(ValueError):calibrate_continuously(bank,entries,names)


def test_threshold_application_preserves_distances_and_input():
    entries,names=fixture();bank=build_bank(entries,names)
    old=score(bank,entries[0]["features"][227:297],0,"A",names);before=copy.deepcopy(old)
    new=apply_thresholds(old,{"raw":1e6,"ewma":1e6})
    for k,v in old.items():
        if isinstance(v,np.ndarray): np.testing.assert_array_equal(v,before[k])
        else: assert v==before[k]
    for k in ("distance","distance_ewma","eligible"):
        np.testing.assert_array_equal(old[k],new[k])
    assert not new["persistent"].any() and not new["persistent_ewma"].any()

