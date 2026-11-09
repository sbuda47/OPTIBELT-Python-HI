"""Exact-condition healthy centres with within-rating residual covariance."""
from collections import defaultdict
import numpy as np
from .baseline import Model, fit_model, matrix
from optibelt_hi.monitoring.health import ewma, health_index, persistent_alarm, vector

SETTINGS={"version":2,"alpha":.2,"warmup_windows":10,"decision_windows":15,
          "persistence":3,"shrinkage":.1,"correlation_limit":.98,
          "relative_scale_floor":1e-12,"drop_suffixes":["rms","power_fraction_5000_12800"]}

def state_key(hp,load,profile,upper):
    return f"{float(hp):g}HP_{int(load)}pct_{profile}_50to{int(upper)}Hz"

def blocks(bounds,duration):
    b=np.asarray(bounds)
    if b.ndim!=2 or b.shape[1]!=2 or b.dtype.kind not in "iu" or duration<=0:
        raise ValueError("Invalid sample boundaries.")
    intervals={"fit":(2,.5*duration-2),"calibration":(.5*duration+2,.75*duration-2),
               "check":(.75*duration+2,duration-2)}
    result={}
    for role,(start,stop) in intervals.items():
        indices=np.flatnonzero((b[:,0]>=round(start*25600))&(b[:,1]<=round(stop*25600)))
        minimum=25
        if len(indices)<minimum: raise ValueError(f"Insufficient guarded windows for {role}.")
        result[role]=indices if role=="fit" else indices[:25]
    return result

def event_level(values):
    x=vector(values,nonnegative=True)
    if len(x)<3: raise ValueError("Three decision windows required.")
    return float(np.max(np.minimum(np.minimum(x[:-2],x[1:-1]),x[2:])))

def build_bank(healthy,names):
    if not healthy or any(e["condition"]!="normal" for e in healthy):
        raise ValueError("Only healthy records may fit or calibrate the bank.")
    if len({e["recording_id"] for e in healthy})!=len(healthy):
        raise ValueError("Duplicate healthy record.")
    grouped=defaultdict(list); split={}
    for e in sorted(healthy,key=lambda e:e["recording_id"]):
        matrix(e["features"],len(names))
        split[e["recording_id"]]=blocks(e["bounds"],e["duration"])
        grouped[e["state"]].append(e)
    states={}; residuals=defaultdict(list)
    for state,entries in sorted(grouped.items()):
        hps={float(e["hp"]) for e in entries}
        if len(hps)!=1: raise ValueError("Condition crosses motor ratings.")
        hp=f"{next(iter(hps)):g}"
        fitting=[e["features"][split[e["recording_id"]]["fit"]] for e in entries]
        centre=np.mean([a.mean(axis=0) for a in fitting],axis=0)
        residuals[hp].extend(a-centre for a in fitting)
        states[state]={"hp":hp,"centre":centre.tolist(),"healthy_recordings":[e["recording_id"] for e in entries]}
    models={hp:fit_model(arrays,names).to_dict() for hp,arrays in sorted(residuals.items())}
    for state,entries in sorted(grouped.items()):
        current=states[state]; model=Model.from_dict(models[current["hp"]]); events=[]
        for e in entries:
            indices=split[e["recording_id"]]["calibration"]
            d=model.score(e["features"][indices]-np.array(current["centre"]))
            sm=ewma(d,.2)
            events.append({"recording_id":e["recording_id"],"window_indices":indices.tolist(),
                "raw_event_level":event_level(d[10:]),"ewma_event_level":event_level(sm[10:])})
        qr=max(e["raw_event_level"] for e in events); qs=max(e["ewma_event_level"] for e in events)
        if qr<=0 or qs<=0: raise ValueError("Positive calibration event thresholds required.")
        current.update(threshold_raw=qr,threshold_ewma=qs,calibration_episodes=events,
            status="supported_development",independent_calibration_acquisitions=len(entries))
    return {"format_version":2,"settings":dict(SETTINGS),"feature_names":list(names),"states":states,"models":models,
        "evidence_scope":"Within-record temporal development; no independent-record validation."}

def score_episode(bank,values,state,names):
    if bank.get("format_version")!=2 or bank.get("settings")!=SETTINGS:
        raise ValueError("Unsupported bank version/settings.")
    if list(names)!=bank["feature_names"]: raise ValueError("Feature order/schema mismatch.")
    if state not in bank["states"]:
        return {"status":"unsupported","reason":"No complete healthy reference for declared condition.",
                "distance":None,"health_index":None,"alarm":None}
    x=matrix(values,len(names)); spec=bank["states"][state]
    model=Model.from_dict(bank["models"][spec["hp"]])
    raw=model.score(x-np.array(spec["centre"])); smooth=ewma(raw,.2)
    eligible=np.arange(len(raw))>=10
    flags=(raw>spec["threshold_raw"])&eligible
    sm_flags=(smooth>spec["threshold_ewma"])&eligible
    return {"status":"supported_development","distance":raw,"distance_ewma":smooth,
        "health_index":health_index(raw,spec["threshold_raw"]),
        "health_index_ewma":health_index(smooth,spec["threshold_ewma"]),
        "eligible":eligible,"alarm":flags,"alarm_ewma":sm_flags,
        "persistent":persistent_alarm(flags,3),"persistent_ewma":persistent_alarm(sm_flags,3)}

