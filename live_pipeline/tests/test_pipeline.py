import sys,json
from pathlib import Path
import numpy as np
import pytest
from scipy.signal import resample_poly
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from optibelt_live import PROJECT
from optibelt_live.engine import Pipeline,Packet,InputRejected,CHANNELS,RATES,TICK_NS
from optibelt_live.fir import StreamingFIR
from optibelt_hi.deployment.bundle import load_bundle

@pytest.fixture(scope='module')
def bundle():return load_bundle(PROJECT/'outputs/releases/hi_candidate_v1')
class Clock:
    def __init__(self):self.now=0.
    def __call__(self):return self.now
def engine(bundle,clock=None):
    return Pipeline(bundle,dict(hp=1.,load=0,profile='invariant_speed',upper=50),'test',0,clock=clock or Clock(),paced=False)
def packet(e,seq=None):
    i=e.sequence if seq is None else seq
    arrays={name:np.sin(2*np.pi*50*(np.arange(rate//10)/rate+i*.1))+.2*np.cos(2*np.pi*127*np.arange(rate//10)/rate) for name,rate in zip(CHANNELS,RATES)}
    return Packet(e.session_id,i,i*TICK_NS,dict(e.condition),arrays)

def test_filter_chunk_invariance_and_offline_interior():
    x=np.random.default_rng(22).normal(size=35000);outputs=[]
    for size in [1,137,10000]:
        f=StreamingFIR();out=[f.push(x[i:i+size]) for i in range(0,len(x),size)];outputs.append(np.concatenate(out))
        assert len(f.buffer)<=80
    np.testing.assert_allclose(outputs[0],outputs[1],atol=1e-12)
    np.testing.assert_allclose(outputs[0],outputs[2],atol=1e-12)
    ref=resample_poly(x,32,125,window=('kaiser',5.),padtype='line')
    np.testing.assert_allclose(outputs[0][11:],ref[11:len(outputs[0])],atol=1e-10)

def test_two_second_window_with_filter_wait_and_bounded_buffers(bundle):
    e=engine(bundle);rows=[]
    for _ in range(41):rows.extend(e.push(packet(e)))
    assert [r['stop_seconds'] for r in rows]==[2.,3.,4.]
    assert all(not r['eligible'] for r in rows)
    assert e.peak_buffer_samples<=53760
    assert max(len(x) for x in e.buffers)<51200
    assert e.snapshot()['motor_on'] is None
    e.finish();assert e.snapshot()['score_is_current'] is False

@pytest.mark.parametrize('case',['missing_sequence','duplicate','timestamp','rate','missing_channel','bad_length','nan','condition','session'])
def test_bad_packet_invalidates_without_advancing_filters(bundle,case):
    e=engine(bundle);e.push(packet(e));p=packet(e);d=dict(p.__dict__)
    if case=='missing_sequence':d['sequence']+=1
    elif case=='duplicate':d['sequence']-=1
    elif case=='timestamp':d['start_ns']+=1
    elif case=='rate':d['rates']=(25600,25600,99999,100000,100000)
    elif case=='missing_channel':d['samples'].pop('torque')
    elif case=='bad_length':d['samples']['torque']=np.ones(4)
    elif case=='nan':d['samples']['current_r'][3]=np.nan
    elif case=='condition':d['condition']=dict(p.condition,load=30)
    elif case=='session':d['session_id']='other'
    state=[f.count for f in e.filters]
    with pytest.raises(InputRejected):e.push(Packet(**d))
    assert e.sequence==1 and [f.count for f in e.filters]==state
    assert not e.snapshot()['score_is_current']
    with pytest.raises(InputRejected):e.push(packet(e))

def test_stale_input_preserves_latch_and_blocks_ack(bundle):
    c=Clock();e=engine(bundle,c);e.push(packet(e));e.alarm.latched=True;e.alarm.pending_since=0
    c.now=1.1;s=e.snapshot()
    assert s['status']=='data_unavailable' and s['operator_alarm_latched'] and e.alarm.pending_since is None
    with pytest.raises(ValueError):e.acknowledge()
    e.stop();assert e.alarm.latched

def test_paced_backlog_is_rejected(bundle):
    c=Clock();e=engine(bundle,c);e.paced=True;e.max_lag_seconds=.2
    e.push(packet(e));c.now=.5
    with pytest.raises(InputRejected,match='backlog'):e.push(packet(e))

def test_unsupported_condition_refused(bundle):
    with pytest.raises(ValueError):Pipeline(bundle,dict(hp=5.,load=60,profile='invariant_speed',upper=50),'x',0)

def test_stop_does_not_issue_motor_command(bundle):
    e=engine(bundle);e.alarm.latched=True;e.stop();s=e.snapshot()
    assert s['status']=='stopped' and s['operator_alarm_latched'] and not s['motor_stop_command']

def test_external_api_contract_and_restart_latch(tmp_path):
    from fastapi.testclient import TestClient
    from optibelt_live.api import create_app
    from optibelt_live.service import Service
    service=Service(outputs=tmp_path/'sessions')
    with TestClient(create_app(service)) as c:
        assert c.get('/api/health').json()['hardware_commands_enabled'] is False
        assert c.post('/api/stop',headers={'Origin':'https://example.invalid'}).status_code==403
        assert c.post('/api/stop',headers={'Content-Length':'2000001'}).status_code==413
        assert len(c.get('/api/catalog').json())==28
        body=dict(condition=dict(hp=1.,load=0,profile='invariant_speed',upper=50),start_ns=0,source_id='test',calibration_id='unverified-test')
        r=c.post('/api/session',json=body);assert r.status_code==200
        service.engine.alarm.latched=True
        assert c.post('/api/session',json=body).status_code==422
        assert c.post('/api/stop').status_code==200
        r=c.post('/api/session',json=body);assert r.status_code==200
        assert service.engine.alarm.latched
        p=packet(service.engine);d=dict(p.__dict__);d['samples']={k:v.tolist() for k,v in p.samples.items()}
        assert c.post('/api/packets',json=d).status_code==200
        d['sequence']=True
        assert c.post('/api/packets',json=d).status_code==422
        assert c.post('/api/acknowledge').status_code==422
        assert c.get('/').status_code==200
    logs=list((tmp_path/'sessions').glob('*/events.jsonl'));assert len(logs)==2
    assert any(json.loads(line)['event']=='packet_accepted' for line in logs[1].read_text().splitlines()) or any(json.loads(line)['event']=='packet_accepted' for line in logs[0].read_text().splitlines())
    restored=Service(outputs=tmp_path/'sessions')
    assert restored.snapshot()['recovered_alarm_latch']
    restored.shutdown()

def test_journal_truncation_does_not_silently_clear_alarm(tmp_path):
    from optibelt_live.service import Service
    session=tmp_path/'sessions'/'old';session.mkdir(parents=True)
    (session/'metadata.json').write_text('{"alarm_latch_carried": false}')
    (session/'events.jsonl').write_text('{"event":"score"')
    restored=Service(outputs=tmp_path/'sessions');assert restored.recovered_latch
    restored.shutdown()
