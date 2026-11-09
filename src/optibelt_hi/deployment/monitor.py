"""One-window-at-a-time MD-HI monitor with explicit recording lifecycle."""
import copy
import numpy as np
from optibelt_hi.model.baseline import Model
from .bundle import validate


class UnsupportedCondition(ValueError):
    pass


class Monitor:
    def __init__(self, bundle, condition, recording_id, reference="C"):
        self._bundle=copy.deepcopy(validate(bundle))
        if reference not in ("A","C"):raise ValueError("Use reference A or C.")
        if not isinstance(recording_id,str) or not recording_id:raise ValueError("Recording ID required.")
        required={"hp","load","profile","upper"}
        if set(condition)!=required:raise ValueError("Explicit complete condition metadata required.")
        if any(isinstance(condition[k],bool) or not isinstance(condition[k],(int,float)) or not np.isfinite(condition[k]) for k in ("hp","load","upper")):
            raise ValueError("Finite numeric condition metadata required.")
        if condition not in self._bundle["supported_conditions"]:
            raise UnsupportedCondition("No complete healthy evidence for this declared condition.")
        self._condition=copy.deepcopy(condition)
        self._reference=reference;self._recording_id=recording_id
        spec=self._bundle["references"][reference]
        self._model=Model.from_dict(spec["model"]);self._thresholds=dict(spec["thresholds"])
        self._offset=np.array(self._bundle["load_centres"][str(int(condition["load"]))]) if reference=="C" else 0
        self._count=0;self._last_start=None;self._smooth=None;self._streak={"raw":0,"ewma":0}

    def push(self, features, start_sample, stop_sample, *, recording_id, feature_names):
        if recording_id!=self._recording_id:raise ValueError("Create a new monitor to reset between recordings.")
        if list(feature_names)!=self._bundle["feature_names"]:raise ValueError("Feature order/schema mismatch.")
        if any(isinstance(v,bool) or not isinstance(v,(int,np.integer)) for v in (start_sample,stop_sample)):
            raise ValueError("Integer sample boundaries required.")
        if start_sample<0 or start_sample%25600 or stop_sample-start_sample!=51200:
            raise ValueError("Expected whole-second aligned two-second windows.")
        if self._last_start is not None and start_sample!=self._last_start+25600:
            raise ValueError("Out-of-order, duplicated or missing window; explicit new session required.")
        x=np.asarray(features)
        if x.shape!=(len(self._bundle["feature_names"]),):raise ValueError("Exactly one feature vector required.")
        # Validate and score before advancing any state.
        distance=float(self._model.score((x-self._offset)[None,:])[0])
        smooth=distance if self._smooth is None else .2*distance+.8*self._smooth
        eligible=self._count>=10
        out={"candidate_version":self._bundle["candidate_version"],"reference":self._reference,
             "recording_id":self._recording_id,"episode_window_index":self._count,
             "start_seconds":start_sample/25600,"stop_seconds":stop_sample/25600,
             "eligible":eligible,"distance":distance,"distance_ewma":smooth}
        streaks={}
        for stream,suffix,value in (("raw","",distance),("ewma","_ewma",smooth)):
            q=self._thresholds[stream];flag=eligible and value>q
            streaks[stream]=self._streak[stream]+1 if flag else 0
            out.update({"threshold_"+stream:q,"health_index"+suffix:float(100*(q/np.hypot(value,q))**2),
                        "alarm"+suffix:bool(flag),"persistent"+suffix:streaks[stream]>=3})
        out["status"]="warming_up" if not eligible else "alert" if out["persistent_ewma"] else "threshold_exceeded" if out["alarm_ewma"] else "within_reference"
        self._last_start=int(start_sample);self._count+=1;self._smooth=smooth;self._streak=streaks
        return out

