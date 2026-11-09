"""Exploratory frozen-model replay of the two duration-held recordings."""
import sys,json,hashlib,shutil
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from scipy.io import loadmat
from scipy.signal import resample_poly
from verify_raw import features as independent_features

P=Path(__file__).resolve().parents[2]
O=P/'outputs/runs/short_recordings_001'
PROTOCOL='''# Duration-held recording test
Prepared before HI scoring. Only Bearing_3HP_30% and Coil60%_5HP_30%_58Hz. Frozen hi_candidate_v1, operator_zones_v1; primary C, hysteresis on, three-second confirmation; A comparator and 2/5-second sensitivity. No fitting, calibration, threshold changes, acknowledgements or motor-stop commands.
Read and verify native finite intervals. Require each channel to have a contiguous finite prefix, only NaN suffix padding, no internal missingness and nonzero variation. Preserve the filename condition/load/profile labels. Verify the condition exists in the release support list. Assume common start provisionally as in the original pipeline; finite-prefix agreement does not prove physical synchronization.
Resample each full measured current prefix with the frozen 32/125 Kaiser-5 line-padding policy, then crop the common-rate arrays to the shared whole-second duration. Do not interpolate or fabricate missing samples. Do not cut away genuine filter context before resampling. Use all complete two-second windows, one-second hop; reset monitor once at the recording start, first ten windows ineligible. Independently recompute features using explicit moments/FFT and compare with extraction. Verify hashes and retain per-window outputs and all prespecified policies.
Keep this run separate from the main admitted cohort. These recordings were excluded from the current model fit/calibration/check cohort but are historically exposed project files, not demonstrably independent acquisitions. Report fault response as exploratory only, with source labels and unknown physical onset. Do not modify the main admission manifest, bundle or dashboard.
'''

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4194304),b''):h.update(b)
    return h.hexdigest()

def main():
    O.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,O/'test_short_records.py');shutil.copy2(Path(__file__).with_name('verify_raw.py'),O/'verify_raw.py')
    (O/'protocol.md').write_text(PROTOCOL)
    sys.path.insert(0,str(P/'src'))
    from optibelt_hi.features.core import extract_windows
    from optibelt_hi.deployment.bundle import load_bundle
    from optibelt_hi.deployment.monitor import Monitor
    from optibelt_hi.alarms.zones import OperatorAlarm,operator_hi
    run={'status':'running','started_utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':sha(O/'protocol.md')}
    (O/'run.json').write_text(json.dumps(run,indent=2))
    try:
        bundle=load_bundle(P/'outputs/releases/hi_candidate_v1')
        routing=pd.read_csv(P/'reproducibility/reference/record_routing.csv').set_index('recording_id')
        admission=pd.read_csv(P/'dataset/splits/data_admission.csv')
        held=admission[admission.admission_status=='hold_duration_review'];assert len(held)==2
        freeze=[P/'dataset/splits/data_admission.csv',P/'outputs/releases/hi_candidate_v1/bundle.json',P/'outputs/releases/hi_candidate_v1/manifest.json']
        before={str(f):sha(f) for f in freeze}
        audit,predictions,metrics,errors=[],[],[],[]
        inputs=[]
        for r in held.to_dict('records'):
            rid=r['recording_id'];path=P/r['relative_path'];assert sha(path)==r['sha256']
            inputs.append({'recording_id':rid,'path':str(path),'sha256':r['sha256']})
            meta=routing.loc[rid];cond={k:meta[k].item() if hasattr(meta[k],'item') else meta[k] for k in ['hp','load','profile','upper']}
            assert cond in bundle['supported_conditions']
            data=loadmat(path,variable_names=['data'],verify_compressed_data_integrity=True)['data']
            arrays=[];durations=[]
            for col,(channel,rate) in enumerate(zip(['vibration','torque','current_r','current_s','current_t'],[25600,25600,100000,100000,100000])):
                x=np.asarray(data[:,col],dtype=float);ix=np.flatnonzero(np.isfinite(x))
                assert len(ix)>0 and ix[0]==0 and np.all(np.diff(ix)==1)
                n=int(ix[-1])+1;assert np.isnan(x[n:]).all() and np.ptp(x[:n])>0
                duration=n/rate;durations.append(duration)
                audit.append(dict(recording_id=rid,channel=channel,rate_hz=rate,finite_samples=n,start_sample=0,duration_seconds=duration,padding_rows=len(x)-n,contiguous_prefix=True))
                arrays.append(x[:n].copy() if rate==25600 else resample_poly(x[:n],32,125,window=('kaiser',5.),padtype='line'))
            seconds=int(np.floor(min(durations))); n=seconds*25600
            common=np.column_stack([x[:n] for x in arrays]);del data,arrays
            values,bounds,names=extract_windows(common)
            for wi,(start,stop) in enumerate(bounds):
                oracle=np.concatenate([independent_features(common[start:stop,c]) for c in range(5)])
                np.testing.assert_allclose(values[wi],oracle,rtol=1e-8,atol=1e-10)
                errors.append({'recording_id':rid,'window_index':wi,'max_absolute_feature_difference':float(np.max(abs(oracle-values[wi])))})
            np.savez_compressed(O/(rid+'.npz'),features=values,bounds=bounds,feature_names=names)
            del common
            for arm in ['A','C']:
                monitor=Monitor(bundle,cond,rid,arm)
                scored=[monitor.push(v,int(b[0]),int(b[1]),recording_id=rid,feature_names=names) for v,b in zip(values,bounds)]
                for confirm in [2,3,5]:
                    alarm=OperatorAlarm(confirm,True);out=[]
                    for s in scored:
                        hi=float(operator_hi(s['distance_ewma'],s['threshold_ewma']))
                        state=alarm.update(s['stop_seconds'],hi,s['eligible'])
                        row=dict(s,operator_hi=hi,confirmation_seconds=confirm,**state)
                        out.append(row);predictions.append(row)
                    eligible=[s for s in out if s['eligible']];requests=[s for s in eligible if s['new_operator_alarm']]
                    critical=[s for s in eligible if s['instantaneous_zone']=='critical']
                    nonnormal=[s for s in eligible if s['zone_state']!='normal']
                    metrics.append(dict(recording_id=rid,reference=arm,confirmation_seconds=confirm,shared_whole_seconds=seconds,
                        measured_min_seconds=min(durations),measured_max_seconds=max(durations),windows=len(out),eligible_steps=len(eligible),
                        min_eligible_hi=min(s['operator_hi'] for s in eligible),max_eligible_hi=max(s['operator_hi'] for s in eligible),
                        warning_steps=sum(s['zone_state']=='warning' for s in eligible),critical_steps=sum(s['zone_state']=='critical' for s in eligible),
                        instantaneous_critical_steps=len(critical),requests=len(requests),first_eligible_seconds=eligible[0]['stop_seconds'],
                        first_non_normal_seconds=nonnormal[0]['stop_seconds'] if nonnormal else None,
                        first_critical_seconds=critical[0]['stop_seconds'] if critical else None,
                        first_request_seconds=requests[0]['stop_seconds'] if requests else None))
            print('Completed duration-held replay: '+rid,flush=True)
        for name,rows in [('channel_audit',audit),('predictions',predictions),('record_metrics',metrics),('independent_feature_checks',errors)]:pd.DataFrame(rows).to_csv(O/(name+'.csv'),index=False)
        for path,d in before.items():assert sha(path)==d
        load_bundle(P/'outputs/releases/hi_candidate_v1')
        run.update(status='complete',completed_utc=datetime.now(timezone.utc).isoformat(),inputs=inputs,preserved_inputs=before,
                   feature_windows_verified=len(errors),independent_feature_values=len(errors)*60,
                   artifacts={f.name:sha(f) for f in O.iterdir() if f.is_file() and f.name!='run.json'})
        print(pd.DataFrame(metrics).query("reference=='C' and confirmation_seconds==3").to_string(index=False),flush=True)
    except Exception as e:run.update(status='failed',error=repr(e));raise
    finally:(O/'run.json').write_text(json.dumps(run,indent=2))

if __name__=='__main__':main()
