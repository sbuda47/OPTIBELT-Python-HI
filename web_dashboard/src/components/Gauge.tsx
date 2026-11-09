import type {Row} from '../types';
const point=(value:number,radius:number)=>{const a=Math.PI*(1-value/100);return [150+radius*Math.cos(a),143-radius*Math.sin(a)]};
export function Gauge({row,duration}:{row:Row;duration:number}){
 const zone=row.zone_state,valid=row.data_valid;
 const needle=point(row.operator_hi,88);
 const note=!row.eligible?`Warm-up ${row.episode_window_index+1} / 10 · alarms disabled`:row.operator_alarm_latched?'Confirmed alarm · acknowledgement required':row.instantaneous_zone==='critical'?`Confirmation ${row.critical_elapsed_seconds.toFixed(0)} / ${duration} seconds`:zone==='critical'?'Recovery band · clears at HI 30':zone==='warning'?'Warning clears when HI reaches 65':'Within the healthy reference range';
 return <section className="panel gauge-panel" aria-label="Health index"><header className="panel-head"><h2>Health index</h2><span className={`status ${zone}`}>{zone.replaceAll('_',' ')}</span></header>
 <svg viewBox="0 0 300 231" role="img" aria-label={valid?`Health index ${row.operator_hi.toFixed(1)} out of 100`:'Health index warming up'}>
  {[{from:0,to:25,color:'var(--red)'},{from:25,to:60,color:'var(--amber)'},{from:60,to:100,color:'var(--green)'}].map(({from,to,color})=>{const a=point(from,106),b=point(to,106);return <path key={from} d={`M${a.join(' ')} A106 106 0 0 1 ${b.join(' ')}`} fill="none" stroke={color} strokeWidth="13"/>})}
  {[0,25,60,100].map(v=>{const p=point(v,125);return <text key={v} x={p[0]} y={p[1]+4} textAnchor="middle" className="dial-tick">{v}</text>})}
  {valid&&<g className="needle"><line x1="150" y1="143" x2={needle[0]} y2={needle[1]} stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/><circle cx="150" cy="143" r="6" fill="currentColor"/></g>}
  <text x="150" y="193" textAnchor="middle" className="dial-value" data-testid="hi-value">{valid?row.operator_hi.toFixed(1):'—'}</text><text x="150" y="215" textAnchor="middle" className="dial-unit">OUT OF 100</text>
 </svg><div className="gauge-note" aria-live="polite">{note}</div><div className="gauge-footer">Deviation score, not remaining life</div></section>;
}
