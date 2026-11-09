from collections import Counter
import pytest

def rows():
    result=[]
    for hp,load in [(3,0),(3,30),(3,60),(5,0),(5,30)]:
        for condition in ("normal","coil"):
            name=f"{condition}_{hp}_{load}"
            result.append(dict(recording_id=name,sha256=name,relative_path=name,condition=condition,
                motor_capacity_hp=str(hp),load_percent_label=str(load),
                admission_status="candidate_complete_recording"))
    result.append(dict(result[0],recording_id="missing",sha256="missing",relative_path="missing",admission_status="hold_missing_vibration"))
    result.append(dict(result[0],recording_id="outside",sha256="outside",relative_path="outside",motor_capacity_hp="1"))
    return result

def test_folds_keep_groups_apart_and_only_fit_healthy():
    from optibelt_hi.evaluation.splits import build_folds
    source=rows(); assignments=build_folds(source)
    assert assignments == build_folds(list(reversed(source)))
    assert len(assignments)==60
    byid={r["recording_id"]:r for r in source}
    tests=Counter()
    for fold in range(1,6):
        active=[r for r in assignments if r["fold"]==fold and r["role"] in ("fit","calibration","test")]
        groups={}
        for r in active:
            groups.setdefault(r["operating_group"],set()).add(r["role"])
            if r["role"]!="test": assert byid[r["recording_id"]]["condition"]=="normal"
            else: tests[r["recording_id"]]+=1
        assert all(len(roles)==1 for roles in groups.values())
        assert Counter(r["role"] for r in active)=={"fit":3,"calibration":1,"test":2}
    assert len(tests)==10 and set(tests.values())=={1}
    assert {r["role"] for r in assignments if r["recording_id"]=="missing"}=={"excluded_quality"}
    assert {r["role"] for r in assignments if r["recording_id"]=="outside"}=={"exploratory"}

def test_duplicate_content_and_missing_healthy_group_rejected():
    from optibelt_hi.evaluation.splits import build_folds
    source=rows(); source[1]["sha256"]=source[0]["sha256"]
    with pytest.raises(ValueError,match="duplicate"): build_folds(source)
    source=rows()
    with pytest.raises(ValueError,match="healthy"): build_folds([r for r in source if r["recording_id"]!="normal_3_0"])

