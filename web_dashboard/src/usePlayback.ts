import {useCallback,useEffect,useRef,useState} from 'react';
import {recordingUrl,request} from './api';
import type {Duration,Notice,Playback,Reference} from './types';

export function usePlayback(id:string,reference:Reference,duration:Duration){
 const [data,setData]=useState<Playback|null>(null),[base,setBase]=useState<Playback|null>(null);
 const [index,setIndex]=useState(0),[playing,setPlaying]=useState(false),[speed,setSpeed]=useState(1);
 const [loading,setLoading]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState<Notice|null>(null);
 const [acks,setAcks]=useState<number[]>([]),[ackBusy,setAckBusy]=useState(false),[dismissed,setDismissed]=useState<string[]>([]);
 const generation=useRef(0);const ackAbort=useRef<AbortController|null>(null);
 const [reload,setReload]=useState(0);
 useEffect(()=>{
  generation.current++;ackAbort.current?.abort();setAckBusy(false);
  setPlaying(false);setData(null);setBase(null);setIndex(0);setNotice(null);setDismissed([]);setAcks([]);setError('');
  if(!id)return;
  const controller=new AbortController();setLoading(true);
  request<Playback>(`${recordingUrl(id)}/playback?reference=${reference}&duration=${duration}`,{signal:controller.signal})
   .then(value=>{if(!controller.signal.aborted){setData(value);setBase(value)}})
   .catch(e=>{if(!controller.signal.aborted)setError(e.message)})
   .finally(()=>{if(!controller.signal.aborted)setLoading(false)});
  return()=>{controller.abort();ackAbort.current?.abort()};
 },[id,reference,duration,reload]);
 useEffect(()=>{
  if(!data)return;
  const pending:Notice[]=[];
  for(let i=0;i<=index;i++){
   const row=data.rows[i];
   if(row.zone_state==='critical'&&(i===0||data.rows[i-1].zone_state!=='critical'))pending.push({token:`critical-${i}`,confirmed:false,row});
   if(row.new_operator_alarm)pending.push({token:`confirmed-${i}`,confirmed:true,row});
  }
  const unread=pending.filter(n=>!dismissed.includes(n.token));
  const latest=unread[unread.length-1];
  if(latest&&latest.token!==notice?.token){setNotice(latest);setDismissed(old=>[...old,...unread.slice(0,-1).map(n=>n.token)])}
 },[data,index,dismissed,notice]);
 useEffect(()=>{
  if(!playing||!data||ackBusy)return;
  if(index>=data.rows.length-1){setPlaying(false);return}
  const timer=setTimeout(()=>setIndex(i=>Math.min(i+1,data.rows.length-1)),1000/speed);
  return()=>clearTimeout(timer);
 },[playing,data,index,speed,ackBusy]);
 const seek=useCallback((next:number)=>{
  if(!base)return;
  generation.current++;ackAbort.current?.abort();setAckBusy(false);
  setPlaying(false);setIndex(Math.max(0,Math.min(next,base.rows.length-1)));setData(base);setAcks([]);setDismissed([]);setNotice(null);setError('');
 },[base]);
 const dismiss=()=>{if(notice)setDismissed(old=>[...old,notice.token]);setNotice(null)};
 const toggle=()=>{if(!data)return;if(index===data.rows.length-1){seek(0);setPlaying(true)}else setPlaying(v=>!v)};
 const acknowledge=async()=>{
  if(!data||ackBusy)return;
  const row=data.rows[index];if(!row.data_valid||row.operator_hi<30||!row.operator_alarm_latched)return;
  setPlaying(false);setAckBusy(true);setError('');
  const epoch=generation.current,controller=new AbortController();ackAbort.current=controller;
  const next=[...acks,index];
  try{
   const result=await request<Playback>(`${recordingUrl(id)}/playback`,{method:'POST',body:JSON.stringify({reference,duration,acknowledgements:next}),signal:controller.signal});
   if(epoch===generation.current&&!controller.signal.aborted){setData(result);setAcks(next)}
  }catch(e){if(epoch===generation.current&&!controller.signal.aborted)setError((e as Error).message)}
  finally{if(epoch===generation.current)setAckBusy(false)}
 };
 return {data,index,row:data?.rows[index],playing,setPlaying,speed,setSpeed,loading,error,notice,dismiss,seek,toggle,acknowledge,ackBusy,retry:()=>setReload(n=>n+1)};
}
