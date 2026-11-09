"""Versioned operator score, zone hysteresis and elapsed-time confirmation."""
import math
import numpy as np

POLICY_VERSION="operator_zones_v1"


def operator_hi(distance,threshold):
    x=np.asarray(distance,dtype=float)
    if not np.isfinite(x).all() or np.any(x<0) or not math.isfinite(threshold) or threshold<=0:
        raise ValueError("Finite nonnegative MD and positive threshold required.")
    return 100*(threshold/np.hypot(threshold,np.sqrt(2/3)*x))**2


class OperatorAlarm:
    def __init__(self,confirmation_seconds=3,hysteresis=True):
        if confirmation_seconds not in (2,3,5) or isinstance(confirmation_seconds,bool):
            raise ValueError("Experiment permits 2, 3 or 5 elapsed seconds.")
        if not isinstance(hysteresis,bool):raise ValueError("Boolean hysteresis setting required.")
        self.duration=confirmation_seconds;self.warning_clear=65 if hysteresis else 60
        self.critical_clear=30 if hysteresis else 25
        self.last_time=None;self.pending_since=None;self.warning=False;self.critical=False
        self.latched=False;self.valid=False;self.last_hi=None

    def update(self,time_seconds,hi,eligible=True):
        if isinstance(time_seconds,bool) or not isinstance(time_seconds,(int,float,np.number)) or not math.isfinite(time_seconds):
            raise ValueError("Finite numerical timestamp required.")
        if self.last_time is not None and time_seconds<=self.last_time:raise ValueError("Timestamp must increase.")
        if not isinstance(eligible,(bool,np.bool_)):raise ValueError("Boolean eligibility required.")
        if hi is not None and (not isinstance(hi,(int,float,np.number)) or isinstance(hi,bool)):
            raise ValueError("Numerical HI or missing value required.")
        valid=hi is not None and math.isfinite(hi)
        if valid and not 0<=hi<=100:raise ValueError("HI outside 0–100.")
        gap=self.last_time is not None and not math.isclose(time_seconds-self.last_time,1.,rel_tol=0,abs_tol=1e-9)
        self.last_time=float(time_seconds)
        if gap:self.pending_since=None
        self.valid=bool(valid and eligible);self.last_hi=float(hi) if valid else None
        if not self.valid:
            self.pending_since=None
            return self._result("warming_up" if not eligible else "data_unavailable",None,False,gap,0.)
        if hi<60:self.warning=True
        elif hi>=self.warning_clear:self.warning=False
        if hi<25:self.critical=True
        elif hi>=self.critical_clear:self.critical=False
        elapsed=0.
        if hi<25:
            if self.pending_since is None:self.pending_since=float(time_seconds)
            elapsed=float(time_seconds-self.pending_since)
        else:self.pending_since=None
        event=not self.latched and self.pending_since is not None and elapsed>=self.duration
        if event:self.latched=True
        instantaneous="critical" if hi<25 else "warning" if hi<60 else "normal"
        state="critical" if self.critical else "warning" if self.warning else "normal"
        return self._result(state,instantaneous,event,gap,elapsed)

    def _result(self,state,instantaneous,event,gap,elapsed):
        return dict(policy_version=POLICY_VERSION,zone_state=state,instantaneous_zone=instantaneous,
                    data_valid=self.valid,data_gap=gap,critical_elapsed_seconds=elapsed,
                    new_operator_alarm=bool(event),operator_alarm_latched=self.latched,
                    audible_alarm_requested=self.latched,motor_stop_command=False)

    def acknowledge(self):
        if not self.latched:return False
        if not self.valid or self.last_hi<self.critical_clear:
            raise ValueError("Cannot clear request without valid recovered HI.")
        self.latched=False
        return True

