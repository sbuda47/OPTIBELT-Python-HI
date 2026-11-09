from collections import deque
from dataclasses import dataclass
import json,math,time
from pathlib import Path
import numpy as np
from optibelt_hi.deployment.monitor import Monitor
from optibelt_hi.alarms.zones import OperatorAlarm,operator_hi
from optibelt_hi.features.core import channel_features
from .fir import StreamingFIR

CHANNELS=('vibration','torque','current_r','current_s','current_t')
RATES=(25600,25600,100000,100000,100000)
TICK_NS=100_000_000

@dataclass(frozen=True)
class Packet:
    session_id:str
    sequence:int
    start_ns:int
    condition:dict
    samples:dict
    rates:tuple=RATES
    motor_on:bool|None=None

class InputRejected(ValueError):pass

class Journal:
    def __init__(self,folder,metadata):
        self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=False)
        (self.folder/'metadata.json').write_text(json.dumps(metadata,indent=2,allow_nan=False))
        self.file=(self.folder/'events.jsonl').open('x',encoding='utf-8')
    def write(self,event):
        self.file.write(json.dumps(event,allow_nan=False)+'\n');self.file.flush()
    def close(self):self.file.close()

class Pipeline:
    """One stable operating segment. Restart explicitly after any invalid input/gap."""
    def __init__(self,bundle,condition,session_id,start_ns,*,journal=None,clock=time.monotonic,
                 stale_seconds=1.,max_lag_seconds=2.,paced=True,initial_latch=False):
        if type(start_ns)!=int or start_ns<0:raise ValueError('Integer nonnegative epoch nanoseconds required')
        if not session_id or stale_seconds<=0 or max_lag_seconds<=0:raise ValueError('Invalid session settings')
        self.bundle=bundle;self.condition=dict(condition);self.session_id=session_id;self.start_ns=start_ns
        self.monitor=Monitor(bundle,condition,session_id,'C');self.alarm=OperatorAlarm(3,True);self.alarm.latched=bool(initial_latch)
        self.filters=[StreamingFIR() for _ in range(3)];self.buffers=[np.empty(0) for _ in CHANNELS]
        self.clock=clock;self.created=clock();self.last_arrival=None;self.last_score_arrival=None
        self.stale_seconds=stale_seconds;self.max_lag_seconds=max_lag_seconds;self.paced=paced;self.journal=journal
        self.sequence=0;self.window_start=0;self.status='waiting_for_data';self.reason=None
        self.blocked=False;self.terminal=False;self.last_score=None;self.history=deque(maxlen=120)
        self.motor_on=None;self.peak_buffer_samples=0;self.chunk_compute_ms=0.;self.scores=0
        self._event('session_started',condition=self.condition,paced=paced)

    def _event(self,kind,**data):
        if self.journal:self.journal.write(dict(data,event=kind,session_id=self.session_id,sequence=self.sequence))

    def invalidate(self,reason,status='data_unavailable'):
        if not self.blocked:
            self._event('input_unavailable',reason=reason,status=status)
        self.blocked=True;self.status=status;self.reason=reason
        self.alarm.pending_since=None;self.alarm.valid=False
        self.motor_on=None

    def check_stale(self):
        if self.terminal or self.blocked:return
        reference=self.created if self.last_arrival is None else self.last_arrival
        if self.clock()-reference>self.stale_seconds:self.invalidate('No timely packet; explicit new segment required')

    def _validate(self,p):
        if p.session_id!=self.session_id:raise InputRejected('Session ID mismatch')
        if type(p.sequence)!=int or p.sequence!=self.sequence:raise InputRejected('Missing, duplicate or out-of-order sequence')
        if type(p.start_ns)!=int or p.start_ns!=self.start_ns+self.sequence*TICK_NS:raise InputRejected('Timestamp gap or clock mismatch')
        if p.condition!=self.condition:raise InputRejected('Operating condition changed; new supported stable segment required')
        if tuple(p.rates)!=RATES:raise InputRejected('Native channel rates differ from model contract')
        if p.motor_on is not None and type(p.motor_on)!=bool:raise InputRejected('Motor state must be telemetry boolean or unknown')
        if set(p.samples)!=set(CHANNELS):raise InputRejected('Exactly five named channels required')
        arrays=[]
        for name,rate in zip(CHANNELS,RATES):
            raw=np.asarray(p.samples[name])
            if raw.ndim!=1 or raw.shape!=(rate//10,) or raw.dtype.kind not in 'fiu' or not np.isfinite(raw).all():raise InputRejected('Invalid 100 ms samples for '+name)
            arrays.append(raw.astype(float,copy=False))
        if self.paced and self.last_arrival is not None:
            # Anchor receipt time to the first packet, rather than trusting wall-clock epoch equality.
            expected=self.first_arrival+self.sequence*.1
            if self.clock()-expected>self.max_lag_seconds:raise InputRejected('Processing/input backlog exceeds lag budget')
        return arrays

    def push(self,packet):
        self.check_stale()
        if self.blocked or self.terminal:raise InputRejected('Segment unavailable or ended; explicit restart required')
        begin=self.clock()
        try:arrays=self._validate(packet)
        except (ValueError,TypeError,KeyError) as exc:
            self.invalidate(str(exc),'unsupported_condition' if packet.condition!=self.condition else 'data_unavailable')
            raise InputRejected(str(exc)) from exc
        # No sample-count/filter state changes occur until the entire packet is validated.
        if self.last_arrival is None:self.first_arrival=begin
        try:
            prepared=arrays[:2]+[f.push(x) for f,x in zip(self.filters,arrays[2:])]
            for i,x in enumerate(prepared):self.buffers[i]=np.concatenate([self.buffers[i],x])
            self.peak_buffer_samples=max(self.peak_buffer_samples,max(map(len,self.buffers)))
            self.motor_on=packet.motor_on;self.last_arrival=begin;self.sequence+=1
            self._event('packet_accepted',start_ns=packet.start_ns,sample_counts=[len(a) for a in arrays],motor_on=self.motor_on)
            result=self._drain()
        except Exception as exc:
            self.invalidate('Processing failed: '+str(exc));raise
        self.chunk_compute_ms=(self.clock()-begin)*1000
        if not self.last_score:self.status='collecting_window'
        return result

    def _drain(self):
        result=[]
        while min(map(len,self.buffers))>=51200:
            vector=np.array([v for x in self.buffers for v in channel_features(x[:51200]).values()])
            scored=self.monitor.push(vector,self.window_start,self.window_start+51200,recording_id=self.session_id,feature_names=self.bundle['feature_names'])
            hi=float(operator_hi(scored['distance_ewma'],scored['threshold_ewma']))
            state=self.alarm.update(scored['stop_seconds'],hi,scored['eligible'])
            row=dict(scored,operator_hi=hi,**state,measurement_end_ns=self.start_ns+round(scored['stop_seconds']*1e9),motor_on=self.motor_on)
            self.last_score=row;self.last_score_arrival=self.clock();self.history.append(row);result.append(row);self.scores+=1
            self.status='monitoring' if scored['eligible'] else 'warming_up';self._event('score',**row)
            self.buffers=[x[25600:].copy() for x in self.buffers];self.window_start+=25600
        return result

    def finish(self):
        """End without inventing a future tail; partial windows are deliberately dropped."""
        if self.terminal:return
        self.terminal=True
        if not self.blocked:self.status='ended';self.reason='Input ended; no current live health claim'
        self.alarm.valid=False;self.alarm.pending_since=None;self.motor_on=None;self._event('session_ended',scores=self.scores)

    def stop(self):
        if not self.terminal:self.invalidate('Input stopped by operator','stopped');self.terminal=True;self._event('input_stopped')

    def acknowledge(self):
        self.check_stale()
        if self.blocked or self.terminal:raise ValueError('Cannot clear alarm without current recovered data')
        cleared=self.alarm.acknowledge();self._event('acknowledgement',cleared=cleared);return cleared

    def snapshot(self):
        self.check_stale();now=self.clock();valid=not(self.blocked or self.terminal)
        return dict(session_id=self.session_id,status=self.status,reason=self.reason,condition=self.condition,
                    latest=self.last_score,score_is_current=valid and self.last_score is not None,
                    score_age_seconds=None if self.last_score_arrival is None else now-self.last_score_arrival,
                    packet_age_seconds=None if self.last_arrival is None else now-self.last_arrival,
                    accepted_packets=self.sequence,score_count=self.scores,motor_on=self.motor_on,
                    operator_alarm_latched=self.alarm.latched,motor_stop_command=False,
                    history=list(self.history),peak_channel_buffer_samples=self.peak_buffer_samples,
                    filter_buffer_samples=[len(f.buffer) for f in self.filters],last_chunk_compute_ms=self.chunk_compute_ms)
