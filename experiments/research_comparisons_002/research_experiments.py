import sys,json,hashlib,shutil,time,platform
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from scipy.io import loadmat
from scipy.signal import resample_poly,periodogram

P=Path(__file__).resolve().parents[2];O=P/'outputs/runs/research_comparisons_001'
sys.path.insert(0,str(P/'src'))
from optibelt_hi.model.baseline import fit_model,Model
from optibelt_hi.monitoring.health import ewma
from optibelt_hi.alarms.zones import OperatorAlarm,operator_hi
from optibelt_hi.features.core import extract_windows,FEATURE_NAMES
from optibelt_hi.deployment.bundle import load_bundle

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
def write(name,obj): (O/name).write_text(json.dumps(obj,indent=2,allow_nan=False))
def indices(e,role,common=False):
 T=e['duration'];lo,hi={'fit':(2,T/2-2),'cal':(T/2+2,3*T/4-2),'check':(3*T/4+2,T-2)}[role]
 b=e['bounds']/25600
 return np.flatnonzero((b[:,1]>=lo+4 if common else b[:,0]>=lo)&(b[:,1]<=hi))
def native_features(channels):
 rates=[25600,25600,100000,100000,100000];names=[];out=[];high=[]
 for col,(x,rate) in enumerate(zip(channels,rates)):
  channel=['vibration','torque','current_r','current_s','current_t'][col]
  suffix=list(FEATURE_NAMES)+(['power_fraction_12800_50000'] if rate==100000 else [])
  names.extend(channel+'__'+s for s in suffix);a=[]
  for start in range(0,len(x)-2*rate+1,rate):
   v=x[start:start+2*rate];mean=v.mean();y=v-mean;sd=np.sqrt(np.mean(y*y));z=y/sd
   f,psd=periodogram(y,fs=rate,window='hann',detrend=False);f,psd=f[1:],psd[1:];total=psd.sum()
   row=[mean,np.sqrt(np.mean(v*v)),sd,np.ptp(v),np.max(abs(z)),np.mean(z**3),np.mean(z**4),np.sum(f*psd)/total]
   edges=[0,200,1000,5000,12800]+([50000] if rate==100000 else [])
   for lo,hi in zip(edges,edges[1:]):row.append(psd[(f>=lo)&((f<=hi) if hi==rate/2 else (f<hi))].sum()/total)
   a.append(row)
  out.append(np.array(a))
  if col>=2:high.append(np.array(a)[:,-1])
 return np.column_stack(out),names,np.column_stack(high)

def evaluate(label,entries,cols=None,kind='shrinkage',pooled=False,common=False,full=True):
 names=entries[0]['names'];cols=list(range(len(names))) if cols is None else cols;names=[names[i] for i in cols]
 healthy=sorted([e for e in entries if e['condition']=='normal'],key=lambda e:e['recording_id'])
 fitted=[e['features'][indices(e,'fit',common)][:,cols] for e in healthy]
 centres={str(load):np.mean([x.mean(axis=0) for e,x in zip(healthy,fitted) if e['load']==load],axis=0) for load in [0,30,60]}
 offset=lambda e: 0 if pooled else centres[str(e['load'])]
 model=fit_model([x-offset(e) for e,x in zip(healthy,fitted)],names,kind=kind,drop_suffixes=('rms','power_fraction_5000_12800','power_fraction_12800_50000'))
 score=lambda e,ix:model.score(e['features'][ix][:,cols]-offset(e))
 calibration=[]
 for e in healthy:
  ix=indices(e,'cal',common);s=ewma(score(e,ix),.2)[10:]
  q=float(np.max(np.minimum(np.minimum(s[:-2],s[1:-1]),s[2:])))
  calibration.append({'recording_id':e['recording_id'],'q':q,'indices':ix.tolist()})
 q=max(c['q'] for c in calibration);assert q>0
 if label in ['fusion','pooled']:
  ref='A' if pooled else 'C';np.testing.assert_allclose(q,BUNDLE['references'][ref]['thresholds']['ewma'],rtol=1e-11)
  saved=Model.from_dict(BUNDLE['references'][ref]['model'])
  for e in entries:
   off=0 if pooled else np.array(BUNDLE['load_centres'][str(e['load'])])
   np.testing.assert_allclose(score(e,np.arange(len(e['features']))),saved.score(e['features']-off),rtol=1e-10,atol=1e-10)
 modelpath=O/'models'/f'{label}.json';modelpath.parent.mkdir(exist_ok=True)
 modelpath.write_text(json.dumps({'model':model.to_dict(),'centres':{k:v.tolist() for k,v in centres.items()},'pooled':pooled,'threshold':q,'calibration':calibration},indent=2))
 rows=[];pred=[]
 for e in entries:
  for scope in (['check','full'] if full else ['check']):
   ix=indices(e,'check',common) if scope=='check' else np.arange(len(e['features']))
   raw=score(e,ix);sm=ewma(raw,.2);hi=operator_hi(sm,q);alarm=OperatorAlarm(3,True);states=[]
   for j,k in enumerate(ix):
    state=alarm.update(float(e['bounds'][k,1]/25600),float(hi[j]),j>=10);states.append(state)
    pred.append(dict(variant=label,scope=scope,recording_id=e['recording_id'],window_index=int(k),stop_seconds=float(e['bounds'][k,1]/25600),eligible=j>=10,distance=float(raw[j]),distance_ewma=float(sm[j]),operator_hi=float(hi[j]),**state))
   active=states[10:];req=[j for j,s in enumerate(states) if s['new_operator_alarm']]
   rows.append(dict(variant=label,scope=scope,recording_id=e['recording_id'],condition=e['condition'],load=e['load'],hp=e['hp'],profile=e['profile'],selected_features=len(model.indices),candidate_features=len(names),threshold=q,decision_steps=len(active),warning_steps=sum(s['zone_state']=='warning' for s in active),critical_steps=sum(s['zone_state']=='critical' for s in active),non_normal=any(s['zone_state']!='normal' for s in active),request=bool(req),min_hi=float(hi[10:].min()),first_request_seconds=float(e['bounds'][ix[req[0]],1]/25600) if req else None))
 pd.DataFrame(pred).to_csv(O/f'predictions_{label}.csv',index=False)
 print('Evaluated '+label,flush=True);return rows

def main():
 global BUNDLE
 O.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,O/Path(__file__).name);shutil.copy2(Path(__file__).with_name('investigation_protocol.md'),O/'protocol.md')
 run=dict(status='running',started_utc=datetime.now(timezone.utc).isoformat(),protocol_sha256=sha(O/'protocol.md'),python=sys.version,host=platform.platform());write('run.json',run)
 try:
  BUNDLE=load_bundle(P/'outputs/releases/hi_candidate_v1')
  preserve={str(f):sha(f) for f in [P/'outputs/releases/hi_candidate_v1/bundle.json',P/'outputs/releases/hi_candidate_v1/manifest.json',P/'dataset/splits/data_admission.csv']}
  routing=pd.read_csv(P/'reproducibility/reference/record_routing.csv');routing=routing[routing.status=='supported_development']
  fr=json.loads((P/'outputs/runs/candidate_features_v1/run.json').read_text());specs={r['recording_id']:r for r in fr['recordings']}
  entries=[]
  for r in routing.to_dict('records'):
   spec=specs[r['recording_id']];f=P/'outputs/runs/candidate_features_v1'/spec['artifact'];assert sha(f)==spec['artifact_sha256']
   with np.load(f) as z:r.update(features=z['features'].copy(),bounds=z['bounds'].copy(),names=z['feature_names'].tolist())
   r['duration']=300 if r['profile']=='invariant_speed' else 120;entries.append(r)
  names=entries[0]['names'];suffix=lambda s:s.split('__')[-1];channel=lambda s:s.split('__')[0]
  variants={'fusion':lambda s:True,'vibration':lambda s:channel(s)=='vibration','current':lambda s:channel(s).startswith('current'),'torque':lambda s:channel(s)=='torque','vibration_current':lambda s:channel(s)!='torque','vibration_torque':lambda s:not channel(s).startswith('current'),'current_torque':lambda s:channel(s)!='vibration','time_only':lambda s:suffix(s) in FEATURE_NAMES[:7],'spectral_only':lambda s:suffix(s) in FEATURE_NAMES[7:],'compact':lambda s:suffix(s) in ['ac_rms','crest_factor_ac','kurtosis_pearson','spectral_centroid_hz']}
  metrics=[]
  for label,select in variants.items():metrics+=evaluate(label,entries,[i for i,n in enumerate(names) if select(n)])
  metrics+=evaluate('diagonal',entries,kind='diagonal');metrics+=evaluate('pooled',entries,pooled=True)
  pd.DataFrame(metrics).to_csv(O/'ablation_metrics.csv',index=False)
  # Extract all variants in one sequential raw-data pass to bound memory.
  collections={'window_1s':[],'window_2s_matched':entries,'window_4s':[],'native_2s_fullband':[]};energy=[];timings=[]
  featurefolder=O/'features';featurefolder.mkdir()
  for e in entries:
   path=P/specs[e['recording_id']]['input'];assert sha(path)==specs[e['recording_id']]['input_sha256']
   begin=time.perf_counter();data=loadmat(path,variable_names=['data'])['data']
   channels=[np.array(data[:e['duration']*rate,c],dtype=float,copy=True) for c,rate in enumerate([25600,25600,100000,100000,100000])];del data
   assert all(np.isfinite(x).all() for x in channels)
   native_begin=time.perf_counter();nx,nn,high=native_features(channels);native_elapsed=time.perf_counter()-native_begin
   collections['native_2s_fullband'].append(dict(e,features=nx,names=nn))
   for c in range(3):energy.append({'recording_id':e['recording_id'],'phase':c,'median_fraction_above_12800':float(np.median(high[:,c])),'max_fraction_above_12800':float(high[:,c].max())})
   prepare=time.perf_counter();common=np.column_stack([x if c<2 else resample_poly(x,32,125,window=('kaiser',5.),padtype='line') for c,x in enumerate(channels)]);resample_elapsed=time.perf_counter()-prepare;del channels
   for L in [1,4]:
    start=time.perf_counter();x,b,n=extract_windows(common,window_seconds=float(L));elapsed=time.perf_counter()-start
    label=f'window_{L}s';collections[label].append(dict(e,features=x,bounds=np.array(b),names=n))
    np.savez_compressed(featurefolder/f"{e['recording_id']}_{label}.npz",features=x,bounds=b,feature_names=n)
    timings.append({'recording_id':e['recording_id'],'variant':label,'seconds':elapsed,'windows':len(x)})
   np.savez_compressed(featurefolder/f"{e['recording_id']}_native.npz",features=nx,bounds=e['bounds'],feature_names=nn)
   timings.append({'recording_id':e['recording_id'],'variant':'native_2s_fullband','seconds':native_elapsed,'windows':len(nx)})
   timings.append({'recording_id':e['recording_id'],'variant':'whole_record_resampling','seconds':resample_elapsed,'windows':len(common)/25600})
   del common;print('Sampling features completed '+e['recording_id'],flush=True)
  sensitivity=[]
  for label,es in collections.items():sensitivity+=evaluate(label,es,common=True,full=False)
  pd.DataFrame(sensitivity).to_csv(O/'sensitivity_metrics.csv',index=False);pd.DataFrame(energy).to_csv(O/'current_high_frequency_power.csv',index=False);pd.DataFrame(timings).to_csv(O/'extraction_timing.csv',index=False)
  allmetrics=pd.DataFrame(metrics+sensitivity);summaries=[]
  for (v,s),g in allmetrics.groupby(['variant','scope']):
   h=g[g.condition=='normal'];f=g[g.condition!='normal']
   summaries.append(dict(variant=v,scope=s,selected_features=int(g.selected_features.iloc[0]),threshold=float(g.threshold.iloc[0]),healthy_records=len(h),fault_records=len(f),healthy_decisions=int(h.decision_steps.sum()),fault_decisions=int(f.decision_steps.sum()),healthy_warning_records=int(h.non_normal.sum()),healthy_request_records=int(h.request.sum()),fault_non_normal_records=int(f.non_normal.sum()),fault_request_records=int(f.request.sum()),healthy_warning_steps=int(h.warning_steps.sum()),healthy_critical_steps=int(h.critical_steps.sum())))
  pd.DataFrame(summaries).to_csv(O/'summary.csv',index=False)
  for path,d in preserve.items():assert sha(path)==d
  load_bundle(P/'outputs/releases/hi_candidate_v1')
  run.update(status='complete',completed_utc=datetime.now(timezone.utc).isoformat(),preserved_inputs=preserve,source_feature_run_sha256=sha(P/'outputs/runs/candidate_features_v1/run.json'),artifacts={f.relative_to(O).as_posix():sha(f) for f in O.rglob('*') if f.is_file() and f.name!='run.json'})
 except Exception as e:run.update(status='failed',error=repr(e));raise
 finally:write('run.json',run)
if __name__=='__main__':main()
