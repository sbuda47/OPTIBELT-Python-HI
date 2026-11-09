import {useEffect,useRef,useState} from 'react';
import type {Data,Layout,Config,PlotlyHTMLElement} from 'plotly.js';
export function Plot({data,layout,label,config={}}:{data:Data[];layout:Partial<Layout>;label:string;config?:Partial<Config>}){
 const ref=useRef<HTMLDivElement>(null),[error,setError]=useState('');
 const generation=useRef(0);
 useEffect(()=>{
  const epoch=++generation.current;let active=true;
  import('plotly.js-dist-min').then(({default:Plotly})=>{if(active&&epoch===generation.current&&ref.current)return Plotly.react(ref.current,data,layout,{responsive:true,displaylogo:false,...config})}).catch(e=>{if(active)setError(e.message)});
  return()=>{active=false};
 },[data,layout,config]);
 useEffect(()=>{
  const element=ref.current;if(!element)return;
  let mounted=true;
  const observer=new ResizeObserver(()=>{import('plotly.js-dist-min').then(({default:p})=>{if(mounted&&(element as unknown as PlotlyHTMLElement).layout)p.Plots.resize(element)})});observer.observe(element);
  return()=>{mounted=false;observer.disconnect();import('plotly.js-dist-min').then(({default:p})=>p.purge(element))};
 },[]);
 const height=layout.height??300;
 return <div className="plot-wrap" role="group" aria-label={label} style={{minHeight:height}}>{error?<p role="alert">Chart unavailable: {error}</p>:<div ref={ref} className="plot-canvas" style={{width:'100%',height}}/>}</div>;
}
