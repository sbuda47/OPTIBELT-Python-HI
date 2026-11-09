"""Execution-only acceleration; same methods/protocol as research_experiments.py."""
from pathlib import Path
import sys,time,json,shutil
import numpy as np
from scipy.io import loadmat
from scipy.signal import resample_poly
import research_experiments as base
P=base.P;O=P/'outputs/runs/research_comparisons_002';CACHE=P/'outputs/runs/research_comparisons_001/features'

def extract_job(payload):
 e,spec=payload;rid=e['recording_id'];path=P/spec['input'];assert base.sha(path)==spec['input_sha256']
 folder=O/'features';folder.mkdir(exist_ok=True)
 paths={label:folder/f'{rid}_{suffix}.npz' for label,suffix in [('window_1s','window_1s'),('window_4s','window_4s'),('native_2s_fullband','native')]}
 old={label:CACHE/p.name for label,p in paths.items()};timings=[];provenance=[];result={}
 if all(p.exists() for p in old.values()):
  for label,p in old.items():
   digest=base.sha(p);shutil.copy2(p,paths[label]);assert base.sha(paths[label])==digest
   with np.load(paths[label]) as z:result[label]=dict(e,features=z['features'].copy(),bounds=z['bounds'].copy(),names=z['feature_names'].tolist())
   provenance.append({'path':str(p),'sha256':digest,'raw_sha256_verified':spec['input_sha256']})
 else:
  data=loadmat(path,variable_names=['data'])['data']
  channels=[np.array(data[:e['duration']*rate,c],dtype=float,copy=True) for c,rate in enumerate([25600,25600,100000,100000,100000])];del data
  assert all(np.isfinite(x).all() for x in channels)
  start=time.perf_counter();nx,nn,_=base.native_features(channels);timings.append({'recording_id':rid,'variant':'native_2s_fullband','seconds':time.perf_counter()-start,'windows':len(nx)})
  result['native_2s_fullband']=dict(e,features=nx,names=nn)
  start=time.perf_counter();common=np.column_stack([x if c<2 else resample_poly(x,32,125,window=('kaiser',5.),padtype='line') for c,x in enumerate(channels)]);timings.append({'recording_id':rid,'variant':'whole_record_resampling','seconds':time.perf_counter()-start,'windows':len(common)/25600});del channels
  for L in [1,4]:
   start=time.perf_counter();x,b,n=base.extract_windows(common,window_seconds=float(L));label=f'window_{L}s';timings.append({'recording_id':rid,'variant':label,'seconds':time.perf_counter()-start,'windows':len(x)});result[label]=dict(e,features=x,bounds=np.array(b),names=n)
  for label,r in result.items():np.savez_compressed(paths[label],features=r['features'],bounds=r['bounds'],feature_names=r['names'])
 n=result['native_2s_fullband'];hi=n['features'][:,[i for i,v in enumerate(n['names']) if v.endswith('12800_50000')]]
 energy=[{'recording_id':rid,'phase':c,'median_fraction_above_12800':float(np.median(hi[:,c])),'max_fraction_above_12800':float(hi[:,c].max())} for c in range(3)]
 return rid,result,energy,timings,provenance

def run():
 # Retain exact original methods. Replace only its sequential extraction block.
 source=Path(base.__file__).read_text()
 source=source.replace("O=P/'outputs/runs/research_comparisons_001'","O=P/'outputs/runs/research_comparisons_002'")
 start=source.index('  for e in entries:\n   path=P/specs')
 end=source.index('  sensitivity=[]',start)
 replacement='''  from concurrent.futures import ProcessPoolExecutor, as_completed
  from parallel_sampling import extract_job
  shutil.copy2(Path(__file__).with_name('parallel_sampling.py'),O/'parallel_sampling.py')
  provenance=[]
  with ProcessPoolExecutor(max_workers=3) as pool:
   futures=[pool.submit(extract_job,(e,specs[e['recording_id']])) for e in entries]
   for future in as_completed(futures):
    rid,result,en,ts,prov=future.result()
    for label,entry in result.items():collections[label].append(entry)
    energy.extend(en);timings.extend(ts);provenance.extend(prov)
    print('Sampling features completed '+rid,flush=True)
  for label in collections:collections[label]=sorted(collections[label],key=lambda e:e['recording_id'])
  write('reused_features.json',provenance)
'''
 source=source[:start]+replacement+source[end:]
 target=Path(__file__).with_name('research_parallel_driver.py');target.write_text(source)
 # Run generated source with its own __file__ so its exact implementation is copied to the run.
 exec(compile(source,str(target),'exec'),{'__name__':'__main__','__file__':str(target)})

if __name__=='__main__':run()
