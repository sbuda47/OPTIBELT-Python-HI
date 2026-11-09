"""Refit and evaluate the current candidate from authorized raw data or verified features."""
import argparse,csv,json,sys,copy
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from optibelt_hi.data.audit import sha256
from optibelt_hi.preprocessing.signals import prepare_recording
from optibelt_hi.features.core import extract_windows
from optibelt_hi.model.load_aware import build_bank
from optibelt_hi.evaluation.continuous_calibration import calibrate_continuously
from optibelt_hi.evaluation.long_monitoring import check_indices
from optibelt_hi.evaluation.model_run import load_inputs
from optibelt_hi.deployment.bundle import load_bundle
from optibelt_hi.deployment.monitor import Monitor
from optibelt_hi.alarms.zones import OperatorAlarm,operator_hi

def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def csvout(path,rows):
    with path.open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def execute(data_root,cache,output):
    frozen=load_bundle(ROOT/'outputs/releases/hi_candidate_v1')
    routes=[r for r in read(ROOT/'reproducibility/reference/record_routing.csv') if r['status']=='supported_development']
    admission={r['recording_id']:r for r in read(ROOT/'dataset/splits/data_admission.csv')}
    if data_root:
        missing=[str(data_root/Path(admission[r['recording_id']]['relative_path']).relative_to('dataset/raw')) for r in routes if not (data_root/Path(admission[r['recording_id']]['relative_path']).relative_to('dataset/raw')).is_file()]
        if missing:raise FileNotFoundError('Authorized raw files required; missing examples: '+', '.join(missing[:3]))
    output.mkdir(parents=True,exist_ok=False)
    report=dict(status='running',started_utc=datetime.now(timezone.utc).isoformat(),input_mode='verified_features' if cache else 'raw_reextraction',release_bundle_sha256=sha256(ROOT/'outputs/releases/hi_candidate_v1/bundle.json'),script_sha256=sha256(Path(__file__)))
    def save(): (output/'run.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    save()
    try:
        cached=None
        if cache:cached,_,_=load_inputs(ROOT,cache)
        entries=[];sources=[]
        for r in routes:
            rid=r['recording_id'];duration=300 if r['profile']=='invariant_speed' else 120;a=admission[rid]
            if cached:
                x,b=cached[rid]['features'],cached[rid]['bounds'];names=frozen['feature_names']
            else:
                relative=Path(a['relative_path']).relative_to('dataset/raw');path=(data_root/relative).resolve()
                if not path.is_relative_to(data_root.resolve()) or sha256(path)!=a['sha256']:raise ValueError('Raw integrity mismatch: '+rid)
                prepared=prepare_recording(path,duration);x,b,names=extract_windows(prepared);b=np.asarray(b);del prepared
            assert names==frozen['feature_names']
            entry=dict(recording_id=rid,condition=r['condition'],hp=float(r['hp']),load=int(r['load']),profile=r['profile'],upper=int(r['upper']),duration=duration,features=x,bounds=b)
            entries.append(entry);sources.append(dict(recording_id=rid,relative_path=a['relative_path'],sha256=a['sha256']))
            print('Prepared '+rid,flush=True)
        healthy=[e for e in entries if e['condition']=='normal'];assert len(healthy)==17 and len(entries)==28
        bank=build_bank(healthy,names);cal=calibrate_continuously(bank,healthy,names)
        fitted=copy.deepcopy(frozen);fitted['load_centres']=bank['centres']
        for arm,key in [('A','pooled'),('C','load_centred')]:
            new=bank['references'][key]['model'];old=frozen['references'][arm]['model']
            assert new['names']==old['names'] and new['indices']==old['indices']
            for field in ['mean','scale','covariance']:np.testing.assert_allclose(new[field],old[field],rtol=1e-9,atol=1e-10)
            for field in ['raw','ewma']:np.testing.assert_allclose(cal['thresholds'][arm][field],frozen['references'][arm]['thresholds'][field],rtol=1e-9,atol=1e-10)
            fitted['references'][arm]={'model':new,'thresholds':cal['thresholds'][arm]}
        for load,centre in bank['centres'].items():np.testing.assert_allclose(centre,frozen['load_centres'][load],rtol=1e-9,atol=1e-10)
        (output/'refitted_bundle.json').write_text(json.dumps(fitted,indent=2))
        (output/'calibration.json').write_text(json.dumps(cal,indent=2))
        golden={(r['recording_id'],r['arm']):r for r in read(ROOT/'reproducibility/reference/operator_record_metrics.csv') if r['hysteresis']=='True' and r['confirmation_seconds']=='3'}
        predictions=[];metrics=[]
        for e in entries:
            condition={k:e[k] for k in ['hp','load','profile','upper']};ix=check_indices(e['bounds'],e['duration'])
            for arm in ['A','C']:
                mon=Monitor(fitted,condition,e['recording_id'],arm);alarm=OperatorAlarm(3,True);rows=[]
                for k in ix:
                    s=mon.push(e['features'][k],int(e['bounds'][k,0]),int(e['bounds'][k,1]),recording_id=e['recording_id'],feature_names=names)
                    h=float(operator_hi(s['distance_ewma'],s['threshold_ewma']));state=alarm.update(s['stop_seconds'],h,s['eligible'])
                    rows.append(dict(s,operator_hi=h,**state))
                    predictions.append(dict(s,arm=arm,policy='continuous',condition=e['condition'],load=e['load'],hp=e['hp'],profile=e['profile'],duration=e['duration'],original_window_index=int(k)))
                valid=[r for r in rows if r['eligible']]
                m=dict(recording_id=e['recording_id'],arm=arm,condition=e['condition'],decision_steps=len(valid),minimum_operator_hi=min(r['operator_hi'] for r in valid),warning_steps=sum(r['zone_state']=='warning' for r in valid),critical_steps=sum(r['zone_state']=='critical' for r in valid),operator_requests=sum(r['new_operator_alarm'] for r in valid))
                expected=golden[(e['recording_id'],arm)]
                for field in ['decision_steps','minimum_operator_hi','warning_steps','critical_steps','operator_requests']:np.testing.assert_allclose(m[field],float(expected[field]),rtol=1e-8,atol=1e-9)
                metrics.append(m)
        csvout(output/'predictions.csv',predictions);csvout(output/'record_metrics.csv',metrics)
        report.update(status='complete',completed_utc=datetime.now(timezone.utc).isoformat(),source_recordings=sources,records=28,healthy_records=17,fault_records=11,refit_matches_frozen=True,check_metrics_match_reference=True,prediction_rows=len(predictions),artifacts={f.name:sha256(f) for f in output.iterdir() if f.is_file() and f.name!='run.json'})
        save();print('PASS: healthy-only refit, thresholds and 56 recording/reference checks reproduce the frozen candidate.')
    except Exception as exc:report.update(status='failed',error=str(exc));save();raise
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--data-root',type=Path,help='Authorized raw root containing invariant_speed/ and varying_speed/')
    group.add_argument('--features-cache',type=Path,help='Existing full candidate_features_v1 artifact directory; skips raw extraction')
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/runs/reproduction_001')
    args=parser.parse_args();execute(args.data_root,args.features_cache,args.output)
