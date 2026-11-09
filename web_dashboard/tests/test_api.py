import os,sys
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

@pytest.fixture(scope='module')
def client():
    from api.app import app
    from api import service
    try:service.snapshot()
    except service.SourceUnavailable:pytest.skip('Run authorized reproduction and set OPTIBELT_REPLAY_RUN for integration tests')
    with TestClient(app) as c:yield c

def test_catalog_and_python_parity(client):
    from api.service import snapshot,adapter
    source,_,_=snapshot()
    catalogue=client.get('/api/catalog').json()
    assert len(catalogue['recordings'])==28
    total=0
    for (rid,arm),group in source.groupby(['recording_id','arm']):
        for duration in [2,3,5]:
            response=client.get(f'/api/recordings/{rid}/playback',params={'reference':arm,'duration':duration})
            assert response.status_code==200,response.text
            actual=response.json()['rows'];expected=adapter.timeline(group,duration,True)
            np.testing.assert_allclose([r['operator_hi'] for r in actual],expected.operator_hi,rtol=0,atol=1e-12)
            for key in ['zone_state','new_operator_alarm','operator_alarm_latched','critical_elapsed_seconds','eligible']:
                assert [r[key] for r in actual]==expected[key].tolist()
            total+=len(actual)
    assert total==6630

def test_invalid_inputs_and_acknowledgement(client):
    rid='Coil40%_3HP_30%'
    assert client.get('/api/recordings/not-a-record/playback').status_code==404
    for params in [{'duration':4},{'reference':'HP'},{'duration':'true'}]:
        assert client.get(f'/api/recordings/{rid}/playback',params=params).status_code==422
    response=client.post(f'/api/recordings/{rid}/playback',json={'acknowledgements':[15]})
    assert response.status_code==422
    assert 'recovered' in response.text
    for acks in [[-1],[1000],[True],[1,1],[3,2]]:
        assert client.post(f'/api/recordings/{rid}/playback',json={'acknowledgements':acks}).status_code==422

def test_native_sample_endpoint(client):
    from api.service import snapshot,adapter,PROJECT
    rid='Normal_1HP_0%'
    response=client.get(f'/api/recordings/{rid}/signal',params={'channel':'vibration','start':229,'seconds':.01,'smooth_ms':1})
    assert response.status_code==200,response.text
    result=response.json()
    _,_,admission=snapshot()
    t,y,rate=adapter.read_segment(PROJECT/admission.loc[rid].relative_path,'vibration',229,.01)
    np.testing.assert_array_equal(result['values'],y)
    np.testing.assert_array_equal(result['times'],t)
    assert result['rate']==rate==25600
    assert len(result['smoothed'])==256
    for params in [{'channel':'bad'},{'seconds':3},{'start':-1},{'start':300},{'smooth_ms':0}]:
        assert client.get(f'/api/recordings/{rid}/signal',params=params).status_code==422

def test_recovered_acknowledgement_contract(client,monkeypatch):
    # Synthetic recovery validates the HTTP contract, not scientific performance.
    from api import service
    group=service.recording('Coil40%_3HP_30%','C').copy().reset_index(drop=True)
    group.loc[16:,['distance','distance_ewma']]=0.0
    monkeypatch.setattr(service,'recording',lambda rid,reference:group)
    response=client.post('/api/recordings/synthetic-recovery/playback',json={'acknowledgements':[16]})
    assert response.status_code==200,response.text
    rows=response.json()['rows']
    assert rows[15]['operator_alarm_latched'] is True
    assert rows[16]['acknowledged'] is True
    assert rows[16]['operator_alarm_latched'] is False
    assert response.json()['motor_stop_command'] is False

def test_spectrum_matches_independent_periodogram(client):
    from scipy.signal import periodogram
    from api.service import snapshot,adapter,PROJECT
    rid='Normal_1HP_0%'
    response=client.post(f'/api/recordings/{rid}/spectrum',json={'start':229,'seconds':2})
    assert response.status_code==200,response.text
    result=response.json();_,_,admission=snapshot()
    _,values,rate=adapter.read_segment(PROJECT/admission.loc[rid].relative_path,'vibration',229,2)
    frequency,power=periodogram(values,rate,window='hann',detrend='constant',scaling='spectrum')
    expected=np.sqrt(power);expected[1:-1]*=np.sqrt(2)
    np.testing.assert_array_equal(result['frequencies'],frequency)
    np.testing.assert_allclose(result['amplitudes'],expected,rtol=1e-10,atol=1e-12)
    assert result['sha256']==admission.loc[rid].sha256
    assert result['sample_count']==51200

def test_spectrum_duration_envelope_context_and_bad_requests(client):
    rid='Normal_1HP_0%';url=f'/api/recordings/{rid}/spectrum'
    result=client.post(url,json={'start':229,'seconds':10}).json()
    assert result['sample_count']==256000
    assert result['bin_spacing_hz']==.1
    response=client.post(url,json={'mode':'envelope','start':0,'seconds':2,'low':3000,'high':5000})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['context_before_seconds']==0
    assert result['context_after_seconds']==1
    assert any('boundary' in w for w in result['warnings'])
    assert np.isfinite(result['amplitudes']).all()
    for body in [{'start':299},{'start':-1},{'seconds':30},{'mode':'bad'},
                 {'mode':'envelope'},{'mode':'envelope','low':5000,'high':3000},
                 {'mode':'envelope','low':3000,'high':3010},{'mode':'envelope','low':3000,'high':12800},
                 {'mode':'fft','low':1000,'high':5000},{'start':'NaN'}]:
        assert client.post(url,json=body).status_code==422,body
    assert client.post('/api/recordings/not-a-record/spectrum',json={}).status_code==404
