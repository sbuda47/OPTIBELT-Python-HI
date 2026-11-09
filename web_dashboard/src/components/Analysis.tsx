import {useEffect,useMemo,useRef,useState} from 'react';
import {DownloadSimple,ArrowClockwise} from '@phosphor-icons/react';
import type {Data,Layout} from 'plotly.js';
import {csvDownload,recordingUrl,request} from '../api';
import type {Playback,Recording,Signal} from '../types';
import {Plot} from './Plot';
import {Trend} from './Trend';
import {Spectrum} from './Spectrum';
const CONFIG={scrollZoom:true};
export function Analysis({recording,playback,index,dark}:{recording:Recording;playback:Playback;index:number;dark:boolean}){
 const stop=playback.rows[index].stop_seconds;
 const [plotType,setPlotType]=useState<'waveform'|'fft'|'envelope'>('waveform');
 const [channel,setChannel]=useState('vibration'),[start,setStart]=useState(Math.max(0,stop-2)),[seconds,setSeconds]=useState(.1),[smoothMs,setSmoothMs]=useState(1),[showSmooth,setShowSmooth]=useState(false);
 const [result,setResult]=useState<Signal|null>(null),[loading,setLoading]=useState(false),[error,setError]=useState('');
 const controller=useRef<AbortController|null>(null);
 async function load(){
  controller.current?.abort();const c=new AbortController();controller.current=c;setLoading(true);setError('');setResult(null);
  const params=new URLSearchParams({channel,start:String(start),seconds:String(seconds),smooth_ms:String(smoothMs)});
  try{const data=await request<Signal>(`${recordingUrl(recording.id)}/signal?${params}`,{signal:c.signal});if(!c.signal.aborted)setResult(data)}
  catch(e){if(!c.signal.aborted)setError((e as Error).message)}finally{if(!c.signal.aborted)setLoading(false)}
 }
 useEffect(()=>{load();return()=>controller.current?.abort()},[recording.id]);
 const figure=useMemo(()=>{
  if(!result)return null;
  const data:Data[]=[{type:'scattergl',mode:'lines',x:result.times,y:result.values,name:'Raw native samples',line:{color:dark?'#59bc9a':'#2b8267',width:1},hovertemplate:'%{x:.6f} s<br>%{y:.7g}<extra>Raw</extra>'}];
  if(showSmooth&&result.smoothed)data.push({type:'scattergl',mode:'lines',x:result.times,y:result.smoothed,name:`Causal mean · ${result.smooth_ms} ms`,line:{color:'#cc963e',width:2}});
  const layout:Partial<Layout>={height:330,margin:{l:52,r:15,t:18,b:45},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{family:'Geist Variable, sans-serif',color:dark?'#a4b8ad':'#728078',size:11},xaxis:{title:{text:'Recording time (s)'},gridcolor:dark?'#34433d':'#edf0ec'},yaxis:{title:{text:'Native source value'},gridcolor:dark?'#34433d':'#edf0ec'},legend:{orientation:'h',y:1.16},dragmode:'zoom',uirevision:`${result.recording_id}-${result.channel}-${result.times[0]}`};
  return {data,layout};
 },[result,showSmooth,dark]);
 return <div className="analysis-grid"><section className="panel"><header className="panel-head"><div><h2>HI comparison</h2><p className="secondary">Raw and smoothed distance, on the same operator scale</p></div></header><Trend data={playback} index={index} dark={dark} raw/></section>
 <div className="analysis-view-select"><label>Plot type<select aria-label="Plot type" value={plotType} onChange={e=>setPlotType(e.target.value as typeof plotType)}><option value="waveform">Time waveform · all signals</option><option value="fft">FFT spectrum · vibration</option><option value="envelope">Envelope spectrum · vibration</option></select></label><p className="secondary">Inspect native signals in time or frequency.</p></div>
 {plotType!=='waveform'?<Spectrum recording={recording} stop={stop} dark={dark} mode={plotType}/>:<section className="panel"><header className="panel-head"><div><h2>Native signals</h2><p className="secondary">Inspect the original samples from this recording</p></div><span className="small-tag">Raw data</span></header>
 <form className="signal-controls" onSubmit={e=>{e.preventDefault();load()}}><label>Signal<select value={channel} onChange={e=>setChannel(e.target.value)}>{['vibration','torque','current_r','current_s','current_t'].map(c=><option key={c} value={c}>{c.replace('_',' ').replace(/^./,x=>x.toUpperCase())}</option>)}</select></label><label>Start (seconds)<input type="number" value={start} min={0} max={Math.max(0,stop-seconds)} step="any" onChange={e=>setStart(Number(e.target.value))}/></label><label>Length (seconds)<input type="number" value={seconds} min={.001} max={Math.min(2,stop-start)} step="any" onChange={e=>setSeconds(Number(e.target.value))}/></label><label>Mean window (ms)<input type="number" value={smoothMs} min={.01} max={100} step="any" onChange={e=>setSmoothMs(Number(e.target.value))}/></label><button className="button secondary-button" type="submit" disabled={loading}><ArrowClockwise size={16}/>{loading?'Loading…':'Load segment'}</button></form>
 <div className="signal-sub"><label className="check"><input type="checkbox" checked={showSmooth} onChange={e=>setShowSmooth(e.target.checked)}/>Overlay smoothed signal</label><span className="secondary">Drag to zoom · double-click to reset</span></div>
 {loading&&<div className="chart-loading" role="status">Verifying and reading native samples…</div>}{error&&<div className="error-box" role="alert">{error}</div>}{figure&&<Plot data={figure.data} layout={figure.layout} config={CONFIG} label="Native signal samples"/>}
 {result&&<footer className="signal-footer"><span>{result.rate.toLocaleString()} Hz · {result.values.length.toLocaleString()} samples · no decimation</span><button className="text-button" onClick={()=>csvDownload(`${recording.id}-${result.channel}.csv`,result.times.map((t,i)=>({record_seconds:t,raw_value:result.values[i],...(showSmooth?{display_smoothed:result.smoothed?.[i]}:{})})))}><DownloadSimple size={15}/>Export samples</button></footer>}
 <p className="footnote">Smoothing here is for display only and starts at the selected segment. It does not change the HI.</p></section>}
 <details className="panel details-panel"><summary>Window values and source provenance</summary><div className="table-scroll"><table><thead><tr><th>Time (s)</th><th>MD</th><th>Smoothed MD</th><th>Operator HI</th><th>State</th></tr></thead><tbody>{playback.rows.slice(0,index+1).map(r=><tr key={r.episode_window_index}><td>{r.stop_seconds}</td><td>{r.distance.toFixed(4)}</td><td>{r.distance_ewma.toFixed(4)}</td><td>{r.eligible?r.operator_hi.toFixed(2):'Warm-up'}</td><td>{r.zone_state.replaceAll('_',' ')}</td></tr>)}</tbody></table></div><p className="footnote break-all">{recording.source}{result&&<><br/>SHA-256: {result.sha256}</>}</p></details></div>;
}
