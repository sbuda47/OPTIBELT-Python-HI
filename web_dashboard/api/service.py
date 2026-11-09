"""Adapt the verified Python dashboard; never implement HI rules in JavaScript."""
import importlib.util
import os
import sys
import numpy as np
from functools import lru_cache
from pathlib import Path
from threading import RLock

PROJECT=Path(os.environ.get('OPTIBELT_PROJECT',str(Path(__file__).resolve().parents[2]))).resolve()
sys.path.insert(0,str(PROJECT/'src'))
spec=importlib.util.spec_from_file_location('optibelt_dashboard_adapter',PROJECT/'dashboard/data.py')
adapter=importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
from optibelt_hi.data.audit import sha256
from optibelt_hi.data.recordings import CHANNELS, RATES, matrix, validate_matrix
from .spectra import compute_spectrum, validate_band

_lock=RLock()
_stamp=None
_snapshot=None

class SourceUnavailable(RuntimeError):pass

def snapshot():
    global _stamp,_snapshot
    configured=Path(os.environ.get('OPTIBELT_REPLAY_RUN','outputs/runs/reproduction_001'))
    replay=configured if configured.is_absolute() else PROJECT/configured
    paths=[replay/'predictions.csv',replay/'run.json',PROJECT/'outputs/releases/hi_candidate_v1/bundle.json',PROJECT/'outputs/releases/hi_candidate_v1/manifest.json',PROJECT/'dataset/splits/data_admission.csv']
    paths.extend((PROJECT/'src/optibelt_hi').rglob('*.py'))
    try:
        stamp=tuple((str(p),p.stat().st_size,p.stat().st_mtime_ns) for p in paths)
        with _lock:
            if stamp!=_stamp:
                fresh=adapter.load_sources(PROJECT)
                _snapshot=fresh;_stamp=stamp
            return _snapshot
    except (OSError,ValueError,KeyError) as exc:
        raise SourceUnavailable('Frozen playback source could not be verified: '+str(exc)) from exc

def catalogue():
    source,bundle,admission=snapshot()
    records=[]
    for rid,group in source[source.arm=='C'].groupby('recording_id'):
        first=group.iloc[0]
        records.append(dict(id=rid,hp=float(first.hp),load=int(first.load),profile=str(first.profile),condition=str(first.condition),
            duration=float(first.duration),windows=len(group),start=float(group.stop_seconds.min()),end=float(group.stop_seconds.max()),
            source=str(admission.loc[rid].relative_path)))
    records.sort(key=lambda r:(r['condition']!='normal',r['id']))
    return dict(recordings=records,candidate=bundle['candidate_version'],policy='operator_zones_v1',references=['C','A'],durations=[2,3,5],channels=list(CHANNELS),
        evidence='Saved same-acquisition development checks; independent validation outstanding.',motor_telemetry=False)

def recording(rid,reference):
    source,_,_=snapshot()
    selected=source[(source.recording_id==rid)&(source.arm==reference)].sort_values('episode_window_index')
    if selected.empty:raise KeyError('Recording is not in the supported playback catalogue.')
    return selected

def playback(rid,reference='C',duration=3,acknowledgements=()):
    selected=recording(rid,reference)
    if list(acknowledgements)!=sorted(set(acknowledgements)) or any(i<0 or i>=len(selected) for i in acknowledgements):
        raise ValueError('Acknowledgement windows must be unique, ordered and inside the recording.')
    frame=adapter.timeline(selected,duration,True,acknowledgements)
    fields=['episode_window_index','stop_seconds','distance','distance_ewma','operator_hi','operator_hi_raw','eligible','zone_state','instantaneous_zone','data_valid','critical_elapsed_seconds','new_operator_alarm','operator_alarm_latched','acknowledged']
    rows=frame[fields].astype(object).where(frame[fields].notna(),None).to_dict('records')
    event_frame=adapter.events(frame)
    event_rows=event_frame.astype(object).where(event_frame.notna(),None).to_dict('records')
    return dict(recording_id=rid,reference=reference,confirmation_seconds=duration,rows=rows,events=event_rows,
        candidate='hi_candidate_v1',policy='operator_zones_v1',motor_stop_command=False)

@lru_cache(maxsize=8)
def verified_raw(path,size,mtime,digest):
    if sha256(Path(path))!=digest:raise SourceUnavailable('Raw recording differs from the admitted source.')
    return True

def signal(rid,channel,start,seconds,smooth_ms=None):
    selected=recording(rid,'C')
    if start+seconds>float(selected.iloc[0].duration):raise ValueError('Segment extends beyond the recording duration.')
    _,_,admission=snapshot();a=admission.loc[rid]
    path=adapter.source_path(PROJECT,a.relative_path)
    before=path.stat()
    verified_raw(str(path),before.st_size,before.st_mtime_ns,str(a.sha256))
    times,values,rate=adapter.read_segment(path,channel,start,seconds)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise SourceUnavailable('Raw recording changed while reading.')
    smoothed=adapter.moving_average(values,max(1,round(rate*smooth_ms/1000))).tolist() if smooth_ms is not None else None
    return dict(recording_id=rid,channel=channel,times=times.tolist(),values=values.tolist(),rate=rate,smoothed=smoothed,
        smooth_ms=smooth_ms,source=str(a.relative_path),sha256=str(a.sha256),units='Native source units',decimated=False)


def spectrum(rid,mode,start,seconds,low=None,high=None):
    selected=recording(rid,'C')
    duration=float(selected.iloc[0].duration)
    if not np.isfinite([start,seconds]).all() or start<0 or seconds not in (2,5,10) or start+seconds>duration:
        raise ValueError('Choose a 2, 5 or 10 second segment within this recording.')
    rate=RATES[0]
    band=validate_band((low,high),rate) if mode=='envelope' and low is not None and high is not None else None
    if mode=='envelope' and band is None:
        raise ValueError('Choose both envelope filter limits after inspecting the vibration spectrum.')
    if mode=='fft' and (low is not None or high is not None):
        raise ValueError('Filter limits apply only to envelope analysis.')
    _,_,admission=snapshot();a=admission.loc[rid]
    path=adapter.source_path(PROJECT,a.relative_path);before=path.stat()
    verified_raw(str(path),before.st_size,before.st_mtime_ns,str(a.sha256))
    first=round(start*rate);last=first+int(seconds*rate)
    padding=rate if mode=='envelope' else 0
    left=max(0,first-padding);right=min(round(duration*rate),last+padding)
    with matrix(path) as data:
        validate_matrix(data)
        if right>data.shape[0]:raise ValueError('Segment exceeds available samples.')
        values=np.array(data[left:right,0],dtype=float)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise SourceUnavailable('Raw recording changed while reading.')
    result=compute_spectrum(values,rate,mode,band,(first-left,last-left))
    warnings=[]
    if mode=='envelope' and (first-left<padding or right-last<padding):
        warnings.append('Record boundary limits filter context; envelope edge effects may remain.')
    if str(selected.iloc[0].profile)!='invariant_speed':
        warnings.append('Variable-speed recording: frequency peaks may spread. Manual RPM markers assume constant speed; this is not order tracking.')
    result.update(recording_id=rid,start_seconds=first/rate,end_seconds=last/rate,seconds=seconds,
                  context_before_seconds=(first-left)/rate,context_after_seconds=(right-last)/rate,
                  source=str(a.relative_path),sha256=str(a.sha256),warnings=warnings,
                  peak_selection='Up to 20 local maxima ranked by amplitude; minimum prominence 1% of spectrum maximum; no fault classification.')
    return result
