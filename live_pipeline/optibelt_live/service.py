import json,threading,time,uuid
from pathlib import Path
from optibelt_hi.deployment.bundle import load_bundle
from . import PROJECT
from .engine import Pipeline,Journal,Packet,InputRejected
from .source import RecordingSource,catalogue,sha

class Service:
    def __init__(self,project=PROJECT,outputs=None):
        self.project=project;self.outputs=Path(outputs or project/'outputs/live_sessions')
        self.bundle=load_bundle(project/'outputs/releases/hi_candidate_v1')
        self.lock=threading.RLock();self.cancel=threading.Event();self.worker=None;self.engine=None;self.journal=None
        self.state='idle';self.error=None;self.source=None;self.mode=None;self.run_dir=None
        self.recovered_latch=self._recover_latch()
    def _recover_latch(self):
        files=list(self.outputs.glob('*/metadata.json'))
        if not files:return False
        latest=max(files,key=lambda p:p.stat().st_mtime_ns)
        latch=bool(json.loads(latest.read_text()).get('alarm_latch_carried',False))
        events=latest.with_name('events.jsonl')
        if events.exists():
            with events.open(encoding='utf-8') as handle:
                for line in handle:
                    try:event=json.loads(line)
                    except json.JSONDecodeError:
                        # Interrupted journal writes must not silently reset an alarm.
                        latch=True;continue
                    if 'operator_alarm_latched' in event:latch=bool(event['operator_alarm_latched'])
                    if event.get('event')=='acknowledgement' and event.get('cleared'):latch=False
        return latch
    def _active(self):return self.worker is not None and self.worker.is_alive()
    def _open(self,condition,mode,source,start_ns=None,paced=True):
        old_latch=self.engine.alarm.latched if self.engine else self.recovered_latch
        # Validate before changing the existing session or closing its log.
        sid=str(uuid.uuid4());epoch=time.time_ns() if start_ns is None else start_ns
        engine=Pipeline(self.bundle,condition,sid,epoch,paced=paced,initial_latch=old_latch)
        if self.journal:self.journal.close()
        self.run_dir=self.outputs/sid
        meta=dict(session_id=sid,mode=mode,source=source,start_ns=epoch,condition=condition,
                  bundle_sha256=sha(self.project/'outputs/releases/hi_candidate_v1/bundle.json'),
                  candidate='hi_candidate_v1',operator_policy='operator_zones_v1',reference='C',confirmation_seconds=3,
                  alarm_latch_carried=old_latch,physical_calibration_verified=False,hardware_commands_enabled=False,
                  filter_startup='first-two-sample line extension; no end flush',raw_packets_logged=False)
        journal=Journal(self.run_dir,meta);engine.journal=journal;engine._event('session_started',**meta)
        self.engine=engine;self.journal=journal;self.mode=mode;self.source=source;self.error=None;self.state='active'
        return sid
    def simulate(self,recording_id,seconds=30,speed=1.):
        if speed not in (0.,1.,10.):raise ValueError('Speed must be 0 (unpaced), 1 or 10')
        spec=next((r for r in catalogue(self.project) if r['recording_id']==recording_id),None)
        if spec is None or type(seconds)!=int or not 2<=seconds<=spec['duration']:raise ValueError('Unsupported recording or duration')
        with self.lock:
            if self._active() or (self.engine and not self.engine.terminal and not self.engine.blocked):raise ValueError('Stop the current input before starting another')
            self.cancel.clear();self.state='loading';self.error=None;self.mode='simulation';self.source=dict(recording_id=recording_id,speed=speed,seconds=seconds)
            self.worker=threading.Thread(target=self._replay,args=(recording_id,seconds,speed),daemon=True);self.worker.start()
        return {'status':'loading'}
    def _replay(self,rid,seconds,speed):
        try:
            source=RecordingSource(rid,seconds,self.project)
            with self.lock:
                if self.cancel.is_set():self.state='stopped';return
                self._open(source.spec['condition'],'simulation',dict(recording_id=rid,sha256=source.spec['sha256'],speed=speed,seconds=seconds),paced=speed==1.)
                engine=self.engine
            begin=time.monotonic()
            for packet in source.packets(engine.session_id,engine.start_ns):
                if speed:
                    delay=begin+(packet.sequence+1)*.1/speed-time.monotonic()
                    if delay>0:self.cancel.wait(delay)
                if self.cancel.is_set():break
                with self.lock:engine.push(packet)
            with self.lock:
                if self.cancel.is_set():engine.stop()
                else:engine.finish()
                self.state=engine.status
        except Exception as exc:
            with self.lock:
                self.error=str(exc);self.state='error'
                if self.engine:self.engine.invalidate(str(exc))
    def open_external(self,condition,start_ns,source_id,calibration_id):
        with self.lock:
            if self._active() or (self.engine and not self.engine.terminal and not self.engine.blocked):raise ValueError('Stop current input first')
            if not source_id.strip() or not calibration_id.strip():raise ValueError('Source and calibration identifiers required')
            sid=self._open(condition,'external_adapter',dict(source_id=source_id,calibration_id=calibration_id),start_ns=start_ns)
            return {'session_id':sid,'start_ns':start_ns,'packet_ns':100_000_000,'status':'waiting_for_data'}
    def ingest(self,packet):
        with self.lock:
            if self.mode!='external_adapter' or not self.engine:raise ValueError('Open an external session first')
            return self.engine.push(packet)
    def stop(self):
        self.cancel.set()
        with self.lock:
            if self.engine:self.engine.stop()
            self.state='stopped'
        return {'status':'stopped','motor_stop_command':False}
    def acknowledge(self):
        with self.lock:
            if not self.engine:raise ValueError('No session')
            return {'cleared':self.engine.acknowledge()}
    def snapshot(self):
        with self.lock:
            snap=self.engine.snapshot() if self.engine and self.state!='loading' else None
            return dict(application='optibelt-live-pipeline',mode=self.mode,state=self.state,source=self.source,
                        error=self.error,run_directory=str(self.run_dir) if self.run_dir else None,pipeline=snap,
                        recovered_alarm_latch=self.recovered_latch if not self.engine else self.engine.alarm.latched,
                        simulated=self.mode=='simulation',hardware_commands_enabled=False)
    def shutdown(self):
        self.stop()
        if self.worker:self.worker.join(timeout=5)
        with self.lock:
            if self.journal and not self._active():self.journal.close();self.journal=None
