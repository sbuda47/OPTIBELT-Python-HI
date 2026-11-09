import numpy as np
import pytest
from optibelt_hi.alarms.zones import operator_hi,OperatorAlarm


def test_mapping_places_calibration_at_sixty_and_is_monotone():
    h=operator_hi(np.array([0.,1.,np.sqrt(4.5),100.]),1.)
    np.testing.assert_allclose(h[:3],[100,60,25],atol=1e-12)
    assert np.all(np.diff(h)<0)
    with pytest.raises(ValueError):operator_hi([-1],1)


@pytest.mark.parametrize("duration",[2,3,5])
def test_elapsed_seconds_not_sample_count(duration):
    p=OperatorAlarm(duration)
    rows=[p.update(i,20.) for i in range(duration+1)]
    assert not any(r["new_operator_alarm"] for r in rows[:-1])
    assert rows[-1]["new_operator_alarm"]
    assert not any(r["motor_stop_command"] for r in rows)


def test_brief_dip_and_recovery_band_cancel_timer():
    p=OperatorAlarm(3)
    rows=[p.update(i,h) for i,h in enumerate([20,20,27,20,20,20])]
    assert rows[2]["zone_state"]=="critical" and rows[2]["critical_elapsed_seconds"]==0
    assert not any(r["new_operator_alarm"] for r in rows)


def test_hysteresis_prevents_boundary_toggling():
    a=OperatorAlarm(2,True);b=OperatorAlarm(2,False)
    values=[70,59,61,59,64,65]
    states_a=[a.update(i,h)["zone_state"] for i,h in enumerate(values)]
    states_b=[b.update(i,h)["zone_state"] for i,h in enumerate(values)]
    assert states_a==["normal","warning","warning","warning","warning","normal"]
    assert states_b==["normal","warning","normal","warning","normal","normal"]


def test_missing_and_gap_restart_confirmation_without_clearing_latch():
    p=OperatorAlarm(2)
    assert not p.update(0,20)["new_operator_alarm"]
    assert not p.update(1,20)["new_operator_alarm"]
    assert p.update(2,None)["zone_state"]=="data_unavailable"
    assert not p.update(3,20)["new_operator_alarm"]
    assert not p.update(5,20)["new_operator_alarm"]  # gap restarts
    assert p.update(6,20)["critical_elapsed_seconds"]==1
    assert p.update(7,20)["new_operator_alarm"]
    assert p.update(8,np.nan)["operator_alarm_latched"]
    with pytest.raises(ValueError):p.acknowledge()
    assert p.update(9,70)["operator_alarm_latched"]
    assert p.acknowledge()
    assert not p.update(10,70)["operator_alarm_latched"]


def test_warmup_does_not_start_confirmation_and_unsafe_ack_is_rejected():
    p=OperatorAlarm(2)
    assert p.update(0,10,False)["zone_state"]=="warming_up"
    assert not p.update(1,10)["new_operator_alarm"]
    assert not p.update(2,10)["new_operator_alarm"]
    assert p.update(3,10)["new_operator_alarm"]
    with pytest.raises(ValueError):p.acknowledge()
    assert p.update(4,29)["operator_alarm_latched"]
    with pytest.raises(ValueError):p.acknowledge()
    p.update(5,30);assert p.acknowledge()


def test_rejected_timestamp_does_not_advance_timer():
    p=OperatorAlarm(2);p.update(0,20)
    with pytest.raises(ValueError):p.update(0,20)
    with pytest.raises(ValueError):p.update(1,101)
    assert not p.update(1,20)["new_operator_alarm"]
    assert p.update(2,20)["new_operator_alarm"]

