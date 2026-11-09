import {useEffect,useMemo,useRef,useState} from 'react';
import {ArrowClockwise,DownloadSimple,Waveform} from '@phosphor-icons/react';
import type {Data,Layout,Shape,Annotations} from 'plotly.js';
import {request,recordingUrl,csvDownload} from '../api';
import type {Recording,SpectrumResult} from '../types';
import {Plot} from './Plot';

const CONFIG={scrollZoom:true};
type Mode='fft'|'envelope';
export function Spectrum({recording,stop,dark,mode}:{recording:Recording;stop:number;dark:boolean;mode:Mode}){
 const [start,setStart]=useState(Math.max(0,stop-2)),[seconds,setSeconds]=useState(2);
 const [low,setLow]=useState(''),[high,setHigh]=useState('');
 const [minimum,setMinimum]=useState(0),[maximum,setMaximum]=useState(12800);
 const [log,setLog]=useState(false),[rpm,setRpm]=useState(''),[markPeaks,setMarkPeaks]=useState(true),[zoom,setZoom]=useState(0);
 const [result,setResult]=useState<{key:string;data:SpectrumResult}|null>(null),[loading,setLoading]=useState(false),[error,setError]=useState('');
 const controller=useRef<AbortController|null>(null),generation=useRef(0);
 const panel=useRef<HTMLElement>(null),[plotWidth,setPlotWidth]=useState(900);
 useEffect(()=>{const element=panel.current;if(!element)return;const observer=new ResizeObserver(entries=>setPlotWidth(Math.max(100,entries[0].contentRect.width-95)));observer.observe(element);return()=>observer.disconnect()},[]);
 const signature=JSON.stringify([recording.id,mode,start,seconds,mode==='envelope'?low:null,mode==='envelope'?high:null]);
 const current=useRef(signature);current.current=signature;
 const data=result?.key===signature?result.data:null;
 useEffect(()=>{
  generation.current++;controller.current?.abort();setLoading(false);setError('');setResult(null);
  return()=>controller.current?.abort();
 },[signature]);
 useEffect(()=>{setMinimum(0);setMaximum(mode==='envelope'?1000:12800);setZoom(n=>n+1)},[mode]);

 async function generate(){
  controller.current?.abort();const c=new AbortController();controller.current=c;
  const epoch=++generation.current,key=signature;
  setLoading(true);setError('');setResult(null);
  if(mode==='envelope'&&(Number(high)-Number(low)<50)){
   setError('The upper filter limit must be at least 50 Hz above the lower limit.');setLoading(false);return;
  }
  try{
   const value=await request<SpectrumResult>(`${recordingUrl(recording.id)}/spectrum`,{
    method:'POST',signal:c.signal,body:JSON.stringify({mode,start,seconds,...(mode==='envelope'?{low:Number(low),high:Number(high)}:{})})
   });
   if(!c.signal.aborted&&epoch===generation.current&&key===current.current){setResult({key,data:value});setZoom(n=>n+1)}
  }catch(e){if(!c.signal.aborted&&epoch===generation.current)setError((e as Error).message)}
  finally{if(!c.signal.aborted&&epoch===generation.current)setLoading(false)}
 }
 const validRange=Number.isFinite(minimum)&&Number.isFinite(maximum)&&minimum>=0&&maximum>minimum&&maximum<=12800;
 const rpmValue=Number(rpm),validRpm=rpm!==''&&Number.isFinite(rpmValue)&&rpmValue>0&&rpmValue<=768000;
 const figure=useMemo(()=>{
  if(!data||!validRange)return null;
  const peaks=data.peaks.filter(p=>p.frequency_hz>=minimum&&p.frequency_hz<=maximum&&p.amplitude>0);
  const traces:Data[]=[{
   type:'scattergl',mode:'lines',x:data.frequencies,y:log?data.amplitudes.map(a=>a>0?a:null):data.amplitudes,
   name:mode==='fft'?'Vibration FFT':'Envelope spectrum',line:{color:dark?'#59bc9a':'#2b8267',width:1.2},
   hovertemplate:'%{x:.3f} Hz<br>%{y:.6g} source units (peak)<extra></extra>'
  }];
  if(markPeaks)traces.push({type:'scatter',mode:'markers',x:peaks.map(p=>p.frequency_hz),y:peaks.map(p=>p.amplitude),name:'Measured peaks',marker:{color:'#cd9b48',size:7,symbol:'circle-open'},hovertemplate:'Peak %{x:.3f} Hz<br>%{y:.6g} source units<extra></extra>'});
  const shapes:Partial<Shape>[]=[],annotations:Partial<Annotations>[]=[];
  const labelStep=validRpm?Math.max(1,Math.ceil(25/((rpmValue/60)/(maximum-minimum)*plotWidth))):1;
  if(validRpm)for(let order=1;order<=10;order++){
   const frequency=order*rpmValue/60;if(frequency<minimum||frequency>maximum)continue;
   shapes.push({type:'line',xref:'x',yref:'paper',x0:frequency,x1:frequency,y0:0,y1:1,line:{color:dark?'#b1baac':'#8e9b91',dash:'dot',width:1}});
   if(order===1||order%labelStep===0)annotations.push({xref:'x',yref:'paper',x:frequency,y:1,text:`${order}×`,showarrow:false,font:{size:10,color:dark?'#b1baac':'#6c7c71'},yshift:10});
  }
  const layout:Partial<Layout>={height:390,margin:{l:70,r:25,t:45,b:55},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{family:'Geist Variable, sans-serif',color:dark?'#a4b8ad':'#728078',size:11},
   xaxis:{title:{text:'Frequency (Hz)'},range:[minimum,maximum],gridcolor:dark?'#34433d':'#edf0ec'},
   yaxis:{title:{text:'Peak amplitude (source units)'},type:log?'log':'linear',rangemode:log?undefined:'tozero',gridcolor:dark?'#34433d':'#edf0ec'},
   showlegend:false,dragmode:'zoom',shapes,annotations,uirevision:`${signature}-${minimum}-${maximum}-${log}-${zoom}`};
  return {traces,layout};
 },[data,minimum,maximum,validRange,log,mode,dark,markPeaks,validRpm,rpmValue,signature,zoom,plotWidth]);

 function exportSpectrum(){
  if(!data)return;
  csvDownload(`${recording.id}-${mode}-spectrum.csv`,data.frequencies.map((f,i)=>({
   frequency_hz:f,peak_amplitude_source_units:data.amplitudes[i],recording_id:data.recording_id,
   start_seconds:data.start_seconds,end_seconds:data.end_seconds,mode:data.mode,window:data.window,
   sample_rate_hz:data.rate,bin_spacing_hz:data.bin_spacing_hz,filter_low_hz:data.band_hz?.[0]??'',filter_high_hz:data.band_hz?.[1]??'',
   assumed_constant_rpm:validRpm?rpmValue:'',source_sha256:data.sha256
  })));
 }
 return <section ref={panel} className="panel spectrum-panel" aria-label="Vibration spectral analysis">
  <header className="panel-head"><div><h2>{mode==='fft'?'Vibration FFT spectrum':'Vibration envelope spectrum'}</h2><p className="secondary">Native vibration · independent of HI scoring</p></div><span className="small-tag">25.6 kHz</span></header>
  <form className="signal-controls spectral-inputs" onSubmit={e=>{e.preventDefault();generate()}}>
   <label>Start (seconds)<input aria-label="Spectrum start seconds" type="number" min={0} max={recording.duration-seconds} step="any" required value={start} onChange={e=>setStart(Number(e.target.value))}/></label>
   <label>Duration<select aria-label="Spectrum duration" value={seconds} onChange={e=>{const next=Number(e.target.value);setStart(s=>Math.max(0,Math.min(s+seconds,recording.duration)-next));setSeconds(next)}}>{[2,5,10].map(n=><option key={n} value={n}>{n} seconds</option>)}</select></label>
   {mode==='envelope'&&<><label>Filter lower limit (Hz)<input aria-label="Envelope lower frequency" type="number" min={10} max={12749} step="any" placeholder="Choose from FFT" required value={low} onChange={e=>setLow(e.target.value)}/></label><label>Filter upper limit (Hz)<input aria-label="Envelope upper frequency" type="number" min={60} max={12799} step="any" placeholder="Below 12,800 Hz" required value={high} onChange={e=>setHigh(e.target.value)}/></label></>}
   <button className="button primary-button" type="submit" disabled={loading}><Waveform size={16}/>{loading?'Calculating…':'Generate spectrum'}</button>
  </form>
  {mode==='envelope'&&<p className="footnote spectral-help">Inspect the FFT first, then choose a band containing the impact-related vibration. The filter is applied before envelope extraction; no diagnostic band is assumed.</p>}
  <div className="spectrum-display-controls">
   <label>Show from (Hz)<input aria-label="Minimum display frequency" type="number" min={0} max={12799} value={minimum} onChange={e=>setMinimum(Number(e.target.value))}/></label>
   <label>Show to (Hz)<input aria-label="Maximum display frequency" type="number" min={1} max={12800} value={maximum} onChange={e=>setMaximum(Number(e.target.value))}/></label>
   <label>Amplitude axis<select aria-label="Amplitude scale" value={log?'log':'linear'} onChange={e=>setLog(e.target.value==='log')}><option value="linear">Linear</option><option value="log">Logarithmic</option></select></label>
   <label>Assumed RPM (optional)<input aria-label="Assumed RPM" type="number" min={1} max={768000} step="any" placeholder="No speed assumed" value={rpm} onChange={e=>setRpm(e.target.value)}/></label>
  </div>
  <div className="signal-sub"><label className="check"><input type="checkbox" checked={markPeaks} onChange={e=>setMarkPeaks(e.target.checked)}/>Mark measured peaks</label><button className="text-button" disabled={!data} onClick={()=>setZoom(n=>n+1)}><ArrowClockwise size={14}/>Reset zoom</button></div>
  {rpm!==''&&<p className="footnote spectral-help">{validRpm?`1× = ${(rpmValue/60).toFixed(3)} Hz · markers 1×–10× assume constant ${rpmValue} RPM. These are reference lines, not measured speed or fault diagnoses.`:'Enter a finite positive RPM to show reference markers.'}</p>}
  {!validRange&&<p role="alert" className="error-box">Choose an increasing display range between 0 and 12,800 Hz.</p>}
  {error&&<div className="error-box" role="alert">{error}</div>}
  {loading&&<div className="chart-loading" role="status">Verifying source and calculating the spectrum…</div>}
  {!data&&!loading&&!error&&<div className="spectrum-empty"><Waveform size={30}/><strong>Select an interval and generate its spectrum</strong><p>The full recording is available for offline inspection. Changing processing settings clears the previous result.</p></div>}
  {figure&&<Plot data={figure.traces} layout={figure.layout} config={CONFIG} label={mode==='fft'?'Vibration FFT spectrum plot':'Vibration envelope spectrum plot'}/>}
  {data&&<>
   <footer className="signal-footer"><span data-testid="spectrum-summary">{data.start_seconds.toFixed(3)}–{data.end_seconds.toFixed(3)} s · {data.sample_count.toLocaleString()} samples · {data.bin_spacing_hz.toFixed(2)} Hz bins · Hann</span><button className="text-button" onClick={exportSpectrum}><DownloadSimple size={15}/>Export spectrum CSV</button></footer>
   {data.warnings.map(w=><p className="spectrum-warning" key={w}>{w}</p>)}
   <div className="spectrum-peaks"><h3>Largest measured peaks</h3><p className="secondary">Across the full spectrum · local maxima, not fault labels</p><div className="table-scroll"><table><thead><tr><th>Frequency (Hz)</th><th>Peak amplitude (source units)</th>{validRpm&&<th>Assumed order</th>}</tr></thead><tbody>{data.peaks.slice(0,8).map(p=><tr key={p.frequency_hz}><td>{p.frequency_hz.toFixed(3)}</td><td>{p.amplitude.toPrecision(5)}</td>{validRpm&&<td>{(p.frequency_hz/(rpmValue/60)).toFixed(3)}×</td>}</tr>)}{!data.peaks.length&&<tr><td colSpan={validRpm?3:2}>No local peaks meet the display selection rule.</td></tr>}</tbody></table></div></div>
   <details className="spectrum-provenance"><summary>Processing and source details</summary><p>{data.processing.join(' → ')}</p>{data.band_hz&&<p>Band: {data.band_hz[0]}–{data.band_hz[1]} Hz. Available context: {data.context_before_seconds} s before / {data.context_after_seconds} s after. Offline zero-phase filtering uses surrounding samples.</p>}<p>{data.peak_selection}</p><p className="break-all">{data.source}<br/>SHA-256: {data.sha256}</p></details>
  </>}
  <p className="footnote spectral-help">Source units are not verified as g or mm/s. Bin spacing is not guaranteed peak-separation resolution. Logarithmic display retains the same amplitude units; it is not a dB conversion. Spectral inspection does not change the HI.</p>
 </section>;
}
