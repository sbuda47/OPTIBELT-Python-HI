"""Independent raw-to-feature checks; no production feature or resampler helper in oracle."""
import argparse, hashlib, json, shutil, sys
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from scipy.io import loadmat
from scipy.signal import resample_poly
import h5py

RECORDS = ['Normal_1HP_0%', 'Normal_3HP_60%', 'Normal_5HP_30%',
           'Bearing_5HP_30%_58Hz', 'Coil10%_3HP_60%_58Hz', 'Misalign0p3mm_3HP_0%_52Hz']
PROTOCOL = '''# Independent raw-to-feature verification
Frozen release hi_candidate_v1; no fitting or parameter changes. Prespecified six records cover healthy/fault, 1/3/5 HP, 0/30/60 percent load, invariant and variable 52/58 Hz profiles. This is stratified implementation verification, not an independent acquisition test.
Verify first, middle and final complete windows in each record. Decode MAT directly; independently build the Kaiser-windowed sinc filter for 100000 -> 25600 Hz (32/125), perform direct finite convolution with line extrapolation, and independently compute all 12 features using explicit moments and NumPy FFT. No production resampler, feature, or MD helper is used in the independent calculation. Compare resampled samples with SciPy and 1080 feature values with frozen artifacts; recompute A/C MD with the covariance linear system. Tolerances: samples 1e-10 relative and absolute; features/MD 1e-8 relative and 1e-10 absolute. Keep observed errors.
Synthetic probes check DC, sine amplitude/frequency, 200/1000/5000 Hz band edges, out-of-band rejection and noncausal filter support. Do not infer inter-sensor time offsets, channel calibration or physical units from these tests. No full-feature re-extraction or live deployment claim.
'''

def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4194304),b''): h.update(b)
    return h.hexdigest()

def direct_resample(x, indices):
    k=np.arange(-1250,1251,dtype=float)
    h=np.sinc(k/125)/125*np.kaiser(2501,5.)
    h*=32/h.sum()
    result=np.empty(len(indices))
    slope=(x[-1]-x[0])/(len(x)-1)
    for start in range(0,len(indices),4096):
        t=indices[start:start+4096]*125+1250
        n=t[:,None]//32-np.arange(79)[None,:]
        hi=t[:,None]-32*n
        valid=(hi>=0)&(hi<2501)
        values=x[np.clip(n,0,len(x)-1)]
        values=np.where(n<0,x[0]+n*slope,values)
        values=np.where(n>=len(x),x[-1]+(n-len(x)+1)*slope,values)
        result[start:start+len(t)]=np.sum(values*h[np.clip(hi,0,2500)]*valid,axis=1)
    return result

def features(x):
    mean=np.sum(x)/len(x); y=x-mean
    m2=np.dot(y,y)/len(y); ac=np.sqrt(m2)
    w=.5-.5*np.cos(2*np.pi*np.arange(len(x))/len(x))
    spectrum=np.abs(np.fft.rfft(y*w))**2/(25600*np.dot(w,w))
    spectrum[1:-1]*=2
    freq=np.arange(len(spectrum))*25600/len(x)
    freq,spectrum=freq[1:],spectrum[1:]
    total=spectrum.sum()
    result=[mean,np.sqrt(np.dot(x,x)/len(x)),ac,x.max()-x.min(),np.abs(y).max()/ac,
            np.sum(y**3)/len(y)/ac**3,np.sum(y**4)/len(y)/m2**2,np.dot(freq,spectrum)/total]
    for lo,hi in [(0,200),(200,1000),(1000,5000),(5000,12800)]:
        mask=(freq>=lo)&((freq<=hi) if hi==12800 else (freq<hi))
        result.append(spectrum[mask].sum()/total)
    return np.array(result)

def main(project,out):
    out.mkdir(parents=True,exist_ok=False)
    shutil.copy2(__file__,out/'verify_raw.py');(out/'protocol.md').write_text(PROTOCOL)
    run={'status':'running','started_utc':datetime.now(timezone.utc).isoformat(),'records':RECORDS,
         'protocol_sha256':digest(out/'protocol.md'),'script_sha256':digest(out/'verify_raw.py')}
    (out/'run.json').write_text(json.dumps(run,indent=2))
    try:
        sys.path.insert(0,str(project/'src'))
        from optibelt_hi.deployment.bundle import load_bundle
        bundle=load_bundle(project/'outputs/releases/hi_candidate_v1')
        bank=json.loads((project/'outputs/runs/candidate_features_v1/run.json').read_text())
        specs={r['recording_id']:r for r in bank['recordings']}
        routing=pd.read_csv(project/'outputs/runs/load_only_experiment_001/record_routing.csv').set_index('recording_id')
        rows,samples,mdrows,probes=[],[],[],[]
        # Known signals independently constrain the arithmetic, not just agreement with saved output.
        t=np.arange(51200)/25600
        for frequency in (50,200,1000,5000,7000):
            f=features(3+2*np.sin(2*np.pi*frequency*t))
            np.testing.assert_allclose(f[[0,1,2,4,5,6,7]],[3,np.sqrt(11),np.sqrt(2),np.sqrt(2),0,1.5,frequency],rtol=1e-9,atol=1e-9)
            if frequency in (200,1000,5000):
                boundary={200:0,1000:1,5000:2}[frequency]
                np.testing.assert_allclose(f[8+boundary:10+boundary],[1/6,5/6],atol=1e-9)
            probes.append({'test':'known sine and band placement','frequency_hz':frequency,'passed':True})
        native_t=np.arange(200000)/100000
        output_idx=np.arange(51200)
        for frequency in (0,50,1000,20000,30000):
            x=np.ones(len(native_t)) if frequency==0 else np.sin(2*np.pi*frequency*native_t)
            y=direct_resample(x,output_idx)
            np.testing.assert_allclose(y,resample_poly(x,32,125,window=('kaiser',5.),padtype='line'),rtol=1e-10,atol=1e-10)
            gain=float(np.sqrt(np.mean(y[2560:-2560]**2))*(1 if frequency==0 else np.sqrt(2)))
            assert abs(gain-1)<.005 if frequency<=1000 else gain<.01
            probes.append({'test':'resampling tone amplitude','frequency_hz':frequency,'amplitude_gain':gain,'passed':True})
        # Same past, changed future: centered offline filtering can change an earlier output.
        x=np.zeros(10000); changed=x.copy();changed[5001]=1
        delta=abs(float(direct_resample(changed,np.array([1280]))[0]-direct_resample(x,np.array([1280]))[0]))
        assert delta>0
        probes.append({'test':'future sample influences output at native index 5000','difference':delta,'passed':True})
        for rid in RECORDS:
            spec=specs[rid]; path=project/spec['input']; artifact=project/'outputs/runs/candidate_features_v1'/spec['artifact']
            assert digest(path)==spec['input_sha256'];assert digest(artifact)==spec['artifact_sha256']
            with np.load(artifact) as a:
                expected=a['features'].copy(); bounds=a['bounds'].copy();names=a['feature_names'].tolist()
            assert names==bundle['feature_names']
            windows=[0,len(bounds)//2,len(bounds)-1]
            indices=np.concatenate([np.arange(*bounds[i]) for i in windows])
            duration=300 if routing.loc[rid,'profile']=='invariant_speed' else 120
            reconstructed=np.empty((3,60)); handle=None
            if h5py.is_hdf5(path):
                handle=h5py.File(path,'r'); data=handle['data']
            else: data=loadmat(path,variable_names=['data'],verify_compressed_data_integrity=True)['data']
            assert data.ndim==2 and data.shape[1]==5
            for col,rate in enumerate([25600,25600,100000,100000,100000]):
                raw=np.asarray(data[:,col],dtype=float); n=duration*rate
                assert np.isfinite(raw[:n]).all() and np.isnan(raw[n:]).all()
                x=raw[:n]
                if rate==100000:
                    actual=direct_resample(x,indices)
                    reference=resample_poly(x,32,125,window=('kaiser',5.),padtype='line')[indices]
                    np.testing.assert_allclose(actual,reference,rtol=1e-10,atol=1e-10)
                else: actual=x[indices];reference=actual
                samples.append({'recording_id':rid,'channel':names[col*12].split('__')[0],'samples':len(actual),'max_absolute_difference':float(np.max(np.abs(actual-reference)))})
                for j,wi in enumerate(windows):
                    f=features(actual[j*51200:(j+1)*51200]); target=expected[wi,col*12:(col+1)*12]
                    np.testing.assert_allclose(f,target,rtol=1e-8,atol=1e-10)
                    reconstructed[j,col*12:(col+1)*12]=f
                    for name,value,saved in zip(names[col*12:(col+1)*12],f,target):
                        rows.append({'recording_id':rid,'window_index':wi,'feature':name,'independent':value,'saved':saved,'absolute_difference':abs(value-saved)})
                del raw,x,actual,reference
            if handle: handle.close()
            del data
            for arm in ['A','C']:
                m=bundle['references'][arm]['model']; offset=np.array(bundle['load_centres'][str(int(routing.loc[rid,'load']))]) if arm=='C' else 0.
                def score(v):
                    z=((v-offset)[:,m['indices']]-m['mean'])/m['scale']
                    return np.sqrt(np.einsum('ij,ij->i',z,np.linalg.solve(np.array(m['covariance']),z.T).T))
                actual=score(reconstructed);saved=score(expected[windows]);np.testing.assert_allclose(actual,saved,rtol=1e-8,atol=1e-10)
                for wi,a,b in zip(windows,actual,saved):mdrows.append({'recording_id':rid,'arm':arm,'window_index':wi,'independent_raw_md':a,'saved_feature_md':b,'absolute_difference':abs(a-b)})
            np.savez_compressed(out/(rid+'.npz'),features=reconstructed,window_indices=windows,feature_names=names)
            print('Independent raw verification passed: '+rid,flush=True)
        for name,values in [('features',rows),('resampled_samples',samples),('md',mdrows),('synthetic_probes',probes)]:pd.DataFrame(values).to_csv(out/(name+'.csv'),index=False)
        run.update(status='complete',completed_utc=datetime.now(timezone.utc).isoformat(),feature_comparisons=len(rows),md_comparisons=len(mdrows),
                   maximum_feature_absolute_difference=max(r['absolute_difference'] for r in rows),maximum_md_absolute_difference=max(r['absolute_difference'] for r in mdrows),
                   maximum_sample_absolute_difference=max(r['max_absolute_difference'] for r in samples),synthetic_probes=len(probes),
                   artifacts={f.name:digest(f) for f in out.iterdir() if f.is_file() and f.name!='run.json'})
    except Exception as e:
        run.update(status='failed',error=repr(e));raise
    finally:(out/'run.json').write_text(json.dumps(run,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.project,a.output)
