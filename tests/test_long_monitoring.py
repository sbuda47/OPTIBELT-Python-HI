import numpy as np
import pytest
from optibelt_hi.evaluation.long_monitoring import check_indices, alert_events, record_metrics, summarize
from optibelt_hi.monitoring.health import persistent_alarm


def boundaries(duration):
    starts = np.arange(duration-1)*25600
    return np.column_stack((starts, starts+51200))


@pytest.mark.parametrize("duration,count,start,stop", [(120,25,92,118),(300,70,227,298)])
def test_reserved_interval(duration,count,start,stop):
    b = boundaries(duration)
    idx = check_indices(b,duration)
    assert len(idx)==count
    assert b[idx[0],0]==start*25600 and b[idx[-1],1]==stop*25600


def test_incomplete_or_discontinuous_interval_rejected():
    with pytest.raises(ValueError): check_indices(boundaries(300)[:-5],300)
    with pytest.raises(ValueError): check_indices(np.delete(boundaries(300),240,axis=0),300)


def test_events_ignore_short_excursions_and_mark_censoring():
    flags=np.array([False,True,True,False,True,True,True,False,True,True,True,True])
    assert alert_events(flags)==[
        dict(start=4,confirmed=6,last=6,exceedance_steps=3,persistent_steps=1,right_censored=False),
        dict(start=8,confirmed=10,last=11,exceedance_steps=4,persistent_steps=2,right_censored=True)]


def test_persistence_crosses_old_endpoint_without_reset():
    b=boundaries(300); idx=check_indices(b,300)
    flags=np.zeros(70,dtype=bool); flags[23:28]=True; flags[60:63]=True
    result=dict(eligible=np.arange(70)>=10,alarm=flags,persistent=persistent_alarm(flags,3))
    rows,events=record_metrics(result,b,idx,"raw",dict(arm="A",condition="normal"))
    by={r["segment"]:r for r in rows}
    assert by["prefix"]["persistent_alert"] is False
    assert by["extension"]["events_confirmed"]==2
    assert by["full"]["events_confirmed"]==2
    assert by["extension"]["persistent_alarm_steps"]==4
    assert by["full"]["decision_steps"]==60
    assert by["extension"]["decision_steps"]==45
    assert events[0]["confirmed"]==25
    assert by["extension"]["first_alert_seconds_after_first_decision"]==15


def test_no_extension_is_missing_exposure_not_zero_alarm_evidence():
    row=dict(arm="A",stream="ewma",segment="extension",condition="normal",decision_steps=0,
             persistent_alert=False,events_confirmed=0,above_threshold_steps=0,persistent_alarm_steps=0)
    summary=summarize([row],"all","all","A","ewma","extension")
    assert summary["healthy_records"]==0 and summary["healthy_above_fraction"] is None

