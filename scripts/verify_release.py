"""No-dataset frozen-release integrity and synthetic monitor smoke test."""
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from optibelt_hi.deployment.bundle import load_bundle
from optibelt_hi.deployment.monitor import Monitor
from optibelt_hi.alarms.zones import operator_hi,OperatorAlarm
b=load_bundle(ROOT/'outputs/releases/hi_candidate_v1');c=b['supported_conditions'][0]
m=Monitor(b,c,'synthetic-software-check');a=OperatorAlarm(3,True)
x=np.array(b['load_centres'][str(int(c['load']))],dtype=float)
for i in range(20):
 r=m.push(x,i*25600,(i+2)*25600,recording_id='synthetic-software-check',feature_names=b['feature_names'])
 h=float(operator_hi(r['distance_ewma'],r['threshold_ewma']));s=a.update(r['stop_seconds'],h,r['eligible'])
 assert np.isfinite(h) and 0<=h<=100 and not s['motor_stop_command']
print('PASS: frozen code/model hashes and 20 synthetic feature-window updates. This is a software check, not sensor-data validation.')
