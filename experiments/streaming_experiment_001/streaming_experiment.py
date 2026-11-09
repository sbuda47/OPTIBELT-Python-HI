import sys,json,hashlib,shutil,time,platform
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from scipy.signal import resample_poly
from scipy.io import loadmat
from importlib.metadata import version
P=Path(__file__).resolve().parents[2];O=P/'outputs/runs/streaming_experiment_001'
sys.path.insert(0,str(P/'src'))
from optibelt_hi.features.core import extract_windows,channel_features
from optibelt_hi.deployment.bundle import load_bundle
from optibelt_hi.deployment.monitor import Monitor
from optibelt_hi.model.baseline import Model
from optibelt_hi.alarms.zones import OperatorAlarm,operator_hi
RECORDS=['Normal_1HP_0%','Normal_3HP_60%','Normal_5HP_30%','Bearing_5HP_30%_58Hz','Coil10%_3HP_60%_58Hz','Misalign0p3mm_3HP_0%_52Hz']
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()

class StreamingFIR:
 def __init__(self):
  k=np.arange(-1250,1251);self.h=np.sinc(k/125)/125*np.kaiser(2501,5.);self.h*=32/self.h.sum()
  self.buffer=np.empty(0);self.origin=0;self.count=0;self.next=0;self.first=[];self.last=None;self.closed=False;self.peak=0
 def push(self,x,final=False):
  x=np.asarray(x,dtype=float)
  if self.closed or x.ndim!=1 or not np.isfinite(x).all():raise ValueError('Invalid chunk or closed stream')
  if len(x):
   self.first=(self.first+x[:2].tolist())[:2] if len(self.first)<2 else self.first
   self.buffer=np.concatenate([self.buffer,x]);self.count+=len(x);self.last=float(x[-1]);self.peak=max(self.peak,len(self.buffer))
  if self.count<2:
   if final:raise ValueError('Need at least two samples')
   return np.empty(0)
  end=(self.count*32+124)//125 if final else max(0,(32*(self.count-1)-1250)//125+1)
  m=np.arange(self.next,end,dtype=np.int64);result=np.empty(len(m))
  for i in range(0,len(m),4096):
   t=m[i:i+4096]*125+1250;n=t[:,None]//32-np.arange(79)[None,:];hidx=t[:,None]-32*n;valid=(hidx>=0)&(hidx<2501)
   actual=n[(n>=0)&(n<self.count)&valid];assert len(actual)==0 or actual.min()>=self.origin
   vals=self.buffer[np.clip(n-self.origin,0,len(self.buffer)-1)]
   vals=np.where(n<0,self.first[0]+n*(self.first[1]-self.first[0]),vals)
   if final:vals=np.where(n>=self.count,self.last+(n-self.count+1)*(self.last-self.first[0])/(self.count-1),vals)
   result[i:i+len(t)]=np.sum(vals*self.h[np.clip(hidx,0,2500)]*valid,axis=1)
  self.next=end
  keep=max(0,(self.next*125-1250)//32);drop=min(len(self.buffer),max(0,keep-self.origin));self.buffer=self.buffer[drop:];self.origin+=drop
  self.closed=final
  return result

def stream(x,chunk):
 s=StreamingFIR();pieces=[];times=[]
 for start in range(0,len(x),chunk):
  a=time.perf_counter();pieces.append(s.push(x[start:start+chunk]));times.append(time.perf_counter()-a)
 pieces.append(s.push([],final=True));return np.concatenate(pieces),times,s.peak

def main():
 O.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,O/Path(__file__).name);shutil.copy2(Path(__file__).with_name('investigation_protocol.md'),O/'protocol.md')
 run=dict(status='running',started_utc=datetime.now(timezone.utc).isoformat(),protocol_sha256=sha(O/'protocol.md'),host=platform.platform(),processor=platform.processor(),python=sys.version,packages={n:version(n) for n in ['numpy','scipy','pandas']});(O/'run.json').write_text(json.dumps(run,indent=2))
 try:
  bundle=load_bundle(P/'outputs/releases/hi_candidate_v1');bundlehash=sha(P/'outputs/releases/hi_candidate_v1/bundle.json')
  t=np.arange(200000)/100000;rng=np.random.default_rng(461);x=np.sin(2*np.pi*123*t)+.1*rng.normal(size=len(t))
  outputs=[stream(x,c)[0] for c in [137,10000,50000]]
  for y in outputs[1:]:np.testing.assert_allclose(y,outputs[0],rtol=1e-12,atol=1e-12)
  offline=resample_poly(x,32,125,window=('kaiser',5.),padtype='line');np.testing.assert_allclose(outputs[0][11:],offline[11:],rtol=1e-10,atol=1e-10)
  s=StreamingFIR();s.push(x[:1000]);before=(s.count,s.next,s.origin,s.buffer.copy())
  try:s.push([np.nan])
  except ValueError:pass
  else:raise AssertionError('Nonfinite input accepted')
  assert (s.count,s.next,s.origin)==before[:3];np.testing.assert_array_equal(s.buffer,before[3])
  # Same prefix yields exactly same emitted output irrespective of future input.
  a=StreamingFIR();b=StreamingFIR();np.testing.assert_array_equal(a.push(x[:1000]),b.push(x[:1000]));a.push(x[1000:]);b.push(-x[1000:])
  specs={r['recording_id']:r for r in json.loads((P/'outputs/runs/candidate_features_v1/run.json').read_text())['recordings']}
  routing=pd.read_csv(P/'reproducibility/reference/record_routing.csv').set_index('recording_id');comparisons=[];timings=[];pred=[];featuretimes=[];inputrefs=[]
  for rid in RECORDS:
   spec=specs[rid];path=P/spec['input'];assert sha(path)==spec['input_sha256'];inputrefs.append(spec)
   data=loadmat(path,variable_names=['data'])['data'];old=[];live=[]
   for c,rate in enumerate([25600,25600,100000,100000,100000]):
    x=np.array(data[:30*rate,c],dtype=float,copy=True)
    if c<2:old.append(x);live.append(x)
    else:
     y,ts,peak=stream(x,10000);off=resample_poly(x,32,125,window=('kaiser',5.),padtype='line')
     np.testing.assert_allclose(y[11:],off[11:],rtol=1e-10,atol=1e-10)
     old.append(off);live.append(y);timings.extend({'recording_id':rid,'phase':c-2,'chunk':i,'compute_seconds':v,'input_chunk_seconds':.1,'peak_buffer_samples':peak} for i,v in enumerate(ts))
     comparisons.append({'recording_id':rid,'phase':c-2,'interior_max_abs_error':float(abs(y[11:]-off[11:]).max()),'startup_max_abs_error':float(abs(y[:11]-off[:11]).max()),'peak_buffer_samples':peak})
   del data
   old=np.column_stack(old);live=np.column_stack(live);xf,bounds,names=extract_windows(old);xl,_,_=extract_windows(live)
   np.testing.assert_allclose(xl[1:],xf[1:],rtol=1e-8,atol=1e-10)
   meta=routing.loc[rid];cond={k:meta[k].item() if hasattr(meta[k],'item') else meta[k] for k in ['hp','load','profile','upper']}
   streams={}
   for label,features in [('offline_prefix',xf),('live_prefix',xl)]:
    mon=Monitor(bundle,cond,rid);alarm=OperatorAlarm(3,True);rows=[]
    for v,bd in zip(features,bounds):
     z=mon.push(v,int(bd[0]),int(bd[1]),recording_id=rid,feature_names=names);hi=float(operator_hi(z['distance_ewma'],z['threshold_ewma']));z.update(operator_hi=hi,**alarm.update(z['stop_seconds'],hi,z['eligible']));rows.append(z);pred.append(dict(z,stream=label))
    streams[label]=rows
   maxhi=max(abs(a['operator_hi']-b['operator_hi']) for a,b in zip(*streams.values()))
   decisions_equal=all((a['zone_state'],a['new_operator_alarm'])==(b['zone_state'],b['new_operator_alarm']) for a,b in zip(*streams.values()))
   comparisons.append({'recording_id':rid,'phase':'downstream','maximum_hi_difference':maxhi,'same_alarm_states_and_requests':decisions_equal,'first_window_max_feature_difference':float(abs(xl[0]-xf[0]).max())})
   model=Model.from_dict(bundle['references']['C']['model']);offset=np.array(bundle['load_centres'][str(cond['load'])])
   # Three repetitions, compute-only, one five-channel feature vector plus MD per window.
   for rep in range(3):
    for i,(start,stop) in enumerate(bounds):
     begin=time.perf_counter();v=np.array([value for c in range(5) for value in channel_features(live[start:stop,c]).values()]);model.score((v-offset)[None,:]);featuretimes.append({'recording_id':rid,'repeat':rep,'window':i,'compute_seconds':time.perf_counter()-begin})
   print('Streaming and timing verified '+rid,flush=True)
  for name,rows in [('comparisons',comparisons),('chunk_timing',timings),('feature_md_timing',featuretimes),('predictions',pred)]:pd.DataFrame(rows).to_csv(O/(name+'.csv'),index=False)
  assert sha(P/'outputs/releases/hi_candidate_v1/bundle.json')==bundlehash;load_bundle(P/'outputs/releases/hi_candidate_v1')
  run.update(status='complete',completed_utc=datetime.now(timezone.utc).isoformat(),inputs=inputrefs,synthetic_chunk_sizes=[137,10000,50000],invalid_chunk_preserves_state=True,bundle_preserved=True,
   artifacts={f.name:sha(f) for f in O.iterdir() if f.is_file() and f.name!='run.json'})
 except Exception as e:run.update(status='failed',error=repr(e));raise
 finally:(O/'run.json').write_text(json.dumps(run,indent=2))
if __name__=='__main__':main()
