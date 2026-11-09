import numpy as np
from optibelt_hi.evaluation.operating_v2_run import coverage
from optibelt_hi.model.operating_v2 import state_key

def test_grid_never_infers_support_from_a_fault_or_missing_channel():
    key=state_key(1,0,"varying_speed",52)
    entries=[dict(state=key,condition="bearing",features=np.zeros((1,2))),
             dict(state=state_key(1,0,"invariant_speed",50),condition="normal",features=np.zeros((1,2))),
             dict(state=key,condition="normal")]
    grid=coverage(entries)
    assert len(grid)==27
    assert sum(r["status"]=="supported_development" for r in grid)==1
    missing=next(r for r in grid if r["state"]==key)
    assert missing["complete_fault_recordings"]==1 and missing["status"]=="unsupported"

