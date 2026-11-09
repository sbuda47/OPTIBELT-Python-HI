import {useMemo} from 'react';
import type {Data,Layout,Shape} from 'plotly.js';
import type {Playback} from '../types';
import {Plot} from './Plot';
const CONFIG={scrollZoom:false};
export function Trend({data,index,dark,raw=false}:{data:Playback;index:number;dark:boolean;raw?:boolean}){
 const figure=useMemo(()=>{
  const rows=data.rows.slice(0,index+1),all=data.rows;
  const traces:Data[]=[{x:rows.map(r=>r.stop_seconds),y:rows.map(r=>r.eligible?r.operator_hi:null),type:'scatter',mode:'lines',name:'Smoothed HI',line:{color:dark?'#55b695':'#237b60',width:2.3},hovertemplate:'%{x:.0f} s<br>HI %{y:.2f}<extra>Smoothed</extra>'}];
  if(raw)traces.push({x:rows.map(r=>r.stop_seconds),y:rows.map(r=>r.eligible?r.operator_hi_raw:null),type:'scatter',mode:'lines',name:'Raw MD → HI',line:{color:'#9ca9a4',width:1},hovertemplate:'%{x:.0f} s<br>HI %{y:.2f}<extra>Raw</extra>'});
  const shapes:Partial<Shape>[]=[{type:'rect',xref:'paper',x0:0,x1:1,y0:60,y1:100,fillcolor:'rgba(46,128,96,.045)',line:{width:0},layer:'below'},{type:'rect',xref:'paper',x0:0,x1:1,y0:25,y1:60,fillcolor:'rgba(194,137,42,.055)',line:{width:0},layer:'below'},{type:'rect',xref:'paper',x0:0,x1:1,y0:0,y1:25,fillcolor:'rgba(192,74,64,.055)',line:{width:0},layer:'below'},...([25,60].map(y=>({type:'line',xref:'paper',x0:0,x1:1,y0:y,y1:y,line:{color:dark?'#50615b':'#cbd4ce',width:1,dash:'dot'}})) as Partial<Shape>[]),{type:'line',x0:rows[rows.length-1].stop_seconds,x1:rows[rows.length-1].stop_seconds,y0:0,y1:100,line:{color:dark?'#b0c2b9':'#62766c',width:1,dash:'dash'}}];
  const warm=all.filter(r=>!r.eligible);if(warm.length)shapes.push({type:'rect',x0:all[0].stop_seconds-.5,x1:warm[warm.length-1].stop_seconds+.5,y0:0,y1:100,fillcolor:'rgba(127,142,132,.09)',line:{width:0},layer:'below'});
  const layout:Partial<Layout>={height:225,margin:{l:40,r:16,t:10,b:38},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{family:'Geist Variable, sans-serif',color:dark?'#a4b8ad':'#728078',size:11},xaxis:{title:{text:'Recording time (s)',font:{size:11}},range:[all[0].stop_seconds-.5,all[all.length-1].stop_seconds+.5],showgrid:false,zeroline:false},yaxis:{range:[0,100],tickvals:[0,25,60,100],gridcolor:dark?'#35433d':'#e7ece8',zeroline:false},shapes,showlegend:raw,legend:{orientation:'h',x:0,y:1.15},uirevision:data.recording_id+data.reference+raw};
  return {traces,layout};
 },[data,index,dark,raw]);
 return <Plot data={figure.traces} layout={figure.layout} label="Operator HI over recording time" config={CONFIG}/>;
}
