"""End-to-end raw replay plus independent offline-reference comparison."""
import sys,json,time
from pathlib import Path
import numpy as np
from scipy.signal import resample_poly
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from optibelt_live import PROJECT
from optibelt_live.service import Service
from optibelt_live.source import RecordingSource
from optibelt_hi.features.core import extract_windows
from optibelt_hi.deployment.monitor import Monitor
from optibelt_hi.alarms.zones import OperatorAlarm,operator_hi

def main():
    output=Path(sys.argv[1]);output.mkdir(parents=True,exist_ok=False);results=[]
    for rid in ['Normal_5HP_0%_58Hz','Bearing_5HP_30%_58Hz']:
        service=Service(outputs=output/'sessions');service.simulate(rid,30,0.)
        deadline=time.monotonic()+120
        while service.worker.is_alive():
            if time.monotonic()>deadline:raise RuntimeError('Replay timed out')
            time.sleep(.1)
        snapshot=service.snapshot();assert snapshot['error'] is None,snapshot
        rows=[json.loads(line) for line in (service.run_dir/'events.jsonl').read_text().splitlines()]
        live=[r for r in rows if r['event']=='score'];assert len(live)==28
        assert [r['stop_seconds'] for r in live]==list(range(2,30))
        assert len([r for r in rows if r['event']=='packet_accepted'])==300
        assert sum(r['eligible'] for r in live)==18
        source=RecordingSource(rid,30);channels=[x[:30*rate] for x,rate in zip(source.channels,[25600,25600,100000,100000,100000])]
        common=np.column_stack([x if i<2 else resample_poly(x,32,125,window=('kaiser',5.),padtype='line') for i,x in enumerate(channels)])
        features,bounds,names=extract_windows(common);monitor=Monitor(service.bundle,source.spec['condition'],'reference');alarm=OperatorAlarm(3,True);ref=[]
        for f,b in zip(features,bounds):
            s=monitor.push(f,int(b[0]),int(b[1]),recording_id='reference',feature_names=names);hi=float(operator_hi(s['distance_ewma'],s['threshold_ewma']));ref.append(dict(s,operator_hi=hi,**alarm.update(s['stop_seconds'],hi,s['eligible'])))
        error=max(abs(a['operator_hi']-b['operator_hi']) for a,b in zip(live,ref))
        assert error<.01
        assert all((a['zone_state'],a['new_operator_alarm'])==(b['zone_state'],b['new_operator_alarm']) for a,b in zip(live,ref))
        requests=[r['stop_seconds'] for r in live if r['new_operator_alarm']]
        assert requests==([] if rid.startswith('Normal') else [15.])
        assert not snapshot['pipeline']['score_is_current']
        assert not any(r['motor_stop_command'] for r in live)
        results.append(dict(recording_id=rid,packets=300,scores=28,eligible=18,maximum_hi_difference=error,requests=requests,peak_buffer_samples=snapshot['pipeline']['peak_channel_buffer_samples'],run_directory=str(service.run_dir)))
        service.shutdown();print('Real-data replay verified: '+rid,flush=True)
    (output/'results.json').write_text(json.dumps(results,indent=2))
if __name__=='__main__':main()
