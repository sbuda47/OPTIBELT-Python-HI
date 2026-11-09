"""Read-only dashboard adapter; research calculations remain in optibelt_hi."""
import json,os
from pathlib import Path
import numpy as np
import pandas as pd
from optibelt_hi.alarms.zones import OperatorAlarm, operator_hi
from optibelt_hi.data.audit import sha256
from optibelt_hi.data.recordings import CHANNELS, RATES, matrix, metadata, validate_matrix
from optibelt_hi.deployment.bundle import load_bundle


def load_sources(project):
    project=Path(project)
    bundle=load_bundle(project/'outputs/releases/hi_candidate_v1')
    configured=Path(os.environ.get('OPTIBELT_REPLAY_RUN','outputs/runs/reproduction_001'))
    folder=configured if configured.is_absolute() else project/configured
    report=json.loads((folder/'run.json').read_text())
    if report['status']!='complete':raise ValueError('Source run is incomplete.')
    if report.get('release_bundle_sha256')!=sha256(project/'outputs/releases/hi_candidate_v1/bundle.json'):
        raise ValueError('Reproduction source does not reference the frozen release.')
    if sha256(folder/'predictions.csv')!=report['artifacts']['predictions.csv']:
        raise ValueError('Prediction integrity check failed.')
    all_rows=pd.read_csv(folder/'predictions.csv')
    rows=all_rows.loc[all_rows.policy=='continuous'].copy()
    admission=pd.read_csv(project/'dataset/splits/data_admission.csv').set_index('recording_id')
    if not admission.index.is_unique:raise ValueError('Ambiguous recording identifiers.')
    for (rid,arm),group in rows.groupby(['recording_id','arm']):
        a=admission.loc[rid]
        if a.admission_status!='candidate_complete_recording':raise ValueError('Unadmitted recording in playback.')
        info=metadata(project/a.relative_path)
        condition=dict(hp=info['motor_capacity_hp'],load=info['load_percent_label'],profile=info['speed_profile'],upper=info['supply_high_hz'])
        if condition not in bundle['supported_conditions']:raise ValueError('Unsupported condition in playback.')
        for field,key in [('threshold_raw','raw'),('threshold_ewma','ewma')]:
            if not np.allclose(group[field],bundle['references'][arm]['thresholds'][key],rtol=0,atol=1e-14):
                raise ValueError('Playback threshold differs from frozen candidate.')
        ordered=group.sort_values('episode_window_index')
        if not np.array_equal(ordered.episode_window_index,np.arange(len(ordered))):raise ValueError('Invalid playback window sequence.')
        if not np.allclose(np.diff(ordered.stop_seconds),1):raise ValueError('Gapped playback source.')
        if not np.isfinite(ordered[['distance','distance_ewma']]).all().all():raise ValueError('Nonfinite playback score.')
    return rows,bundle,admission


def timeline(source,duration=3,hysteresis=True,acknowledgements=()):
    source=source.sort_values('stop_seconds').reset_index(drop=True).copy()
    alarm=OperatorAlarm(duration,hysteresis)
    source['operator_hi']=operator_hi(source.distance_ewma.to_numpy(),float(source.threshold_ewma.iloc[0]))
    source['operator_hi_raw']=operator_hi(source.distance.to_numpy(),float(source.threshold_raw.iloc[0]))
    results=[]
    for i,r in source.iterrows():
        result=alarm.update(float(r.stop_seconds),float(r.operator_hi),bool(r.eligible))
        acknowledged=i in acknowledgements and alarm.acknowledge()
        result.update(acknowledged=bool(acknowledged),operator_alarm_latched=alarm.latched,audible_alarm_requested=alarm.latched)
        results.append(result)
    return pd.concat([source,pd.DataFrame(results)],axis=1)


def events(frame):
    result=[];previous=None
    for i,r in frame.iterrows():
        if r.zone_state!=previous:
            result.append(dict(window=int(i),record_seconds=float(r.stop_seconds),event='Zone: '+r.zone_state.replace('_',' '),operator_hi=float(r.operator_hi)))
            previous=r.zone_state
        if r.new_operator_alarm:result.append(dict(window=int(i),record_seconds=float(r.stop_seconds),event='Confirmed operator alarm',operator_hi=float(r.operator_hi)))
        if r.acknowledged:result.append(dict(window=int(i),record_seconds=float(r.stop_seconds),event='Alarm acknowledged after recovery',operator_hi=float(r.operator_hi)))
    return pd.DataFrame(result,columns=['window','record_seconds','event','operator_hi'])


def source_path(project,relative):
    path=(Path(project)/relative).resolve()
    if not path.is_relative_to((Path(project)/'dataset/raw').resolve()):raise ValueError('Raw path outside dataset.')
    return path


def read_segment(path,channel,start,seconds):
    if channel not in CHANNELS or not np.isfinite([start,seconds]).all() or start<0 or not 0<seconds<=2:
        raise ValueError('Choose a valid channel and a segment of at most 2 seconds.')
    index=CHANNELS.index(channel);rate=RATES[index]
    first=round(start*rate);last=first+round(seconds*rate)
    with matrix(Path(path)) as values:
        validate_matrix(values)
        if last>values.shape[0]:raise ValueError('Segment exceeds available samples.')
        segment=np.array(values[first:last,index],dtype=float)
    if not len(segment) or not np.isfinite(segment).all():raise ValueError('Segment contains missing or invalid native samples.')
    return np.arange(first,last,dtype=float)/rate,segment,rate


def moving_average(values,samples):
    samples=max(1,int(samples));c=np.r_[0.,np.cumsum(values,dtype=float)]
    end=np.arange(1,len(values)+1);start=np.maximum(0,end-samples)
    return (c[end]-c[start])/(end-start)
