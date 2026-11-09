"""Recording adapter. Replace this producer with acquisition hardware later."""
import csv,hashlib,json
from dataclasses import dataclass
import numpy as np
from optibelt_hi.data.recordings import native_channels
from . import PROJECT
from .engine import Packet,CHANNELS,RATES,TICK_NS

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4194304),b''):h.update(b)
    return h.hexdigest()

def catalogue(project=PROJECT):
    route=project/'reproducibility/reference/record_routing.csv'
    routing=list(csv.DictReader(route.open()))
    receipts={r['recording_id']:r for r in csv.DictReader((project/'dataset/splits/data_admission.csv').open())}
    return [dict(recording_id=r['recording_id'],condition=dict(hp=float(r['hp']),load=int(r['load']),profile=r['profile'],upper=int(r['upper'])),
                 label=r['condition'],duration=300 if r['profile']=='invariant_speed' else 120,
                 path=receipts[r['recording_id']]['relative_path'],sha256=receipts[r['recording_id']]['sha256'])
            for r in routing if r['status']=='supported_development']

class RecordingSource:
    def __init__(self,recording_id,seconds,project=PROJECT):
        self.spec=next((r for r in catalogue(project) if r['recording_id']==recording_id),None)
        if self.spec is None:raise ValueError('Recording is outside supported simulation catalogue')
        if type(seconds)!=int or not 2<=seconds<=self.spec['duration']:raise ValueError('Invalid simulation duration')
        path=project/self.spec['path']
        if sha(path)!=self.spec['sha256']:raise ValueError('Raw source integrity failure')
        self.channels=native_channels(path,self.spec['duration']);self.seconds=seconds
    def packets(self,session_id,start_ns):
        for i in range(self.seconds*10):
            yield Packet(session_id,i,start_ns+i*TICK_NS,self.spec['condition'],
                         {name:x[i*(rate//10):(i+1)*(rate//10)] for name,rate,x in zip(CHANNELS,RATES,self.channels)},motor_on=None)
