"""Shadow replay of operator zones and timers; no sound or hardware interfaces."""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from optibelt_hi.alarms.zones import operator_hi,OperatorAlarm,POLICY_VERSION
from optibelt_hi.data.audit import sha256,write_csv
from optibelt_hi.deployment.bundle import load_bundle
from optibelt_hi.evaluation.model_run import read_csv,safe_name
from optibelt_hi.evaluation.operating_v2_run import file_hashes


def metrics(rows,base):
    valid=[r for r in rows if r["eligible"]]
    events=[r for r in valid if r["new_operator_alarm"]]
    crit=[r for r in valid if r["instantaneous_zone"]=="critical"]
    states=[r["zone_state"] for r in valid]
    return {**base,"decision_steps":len(valid),"minimum_operator_hi":min(r["operator_hi"] for r in valid),
            "non_normal_steps":sum(r["zone_state"]!="normal" for r in valid),
            "warning_steps":states.count("warning"),"critical_steps":states.count("critical"),
            "instantaneous_critical_steps":len(crit),
            "state_transitions":sum(a!=b for a,b in zip(states,states[1:])),
            "operator_requests":len(events),"latched_steps":sum(r["operator_alarm_latched"] for r in valid),
            "first_critical_record_seconds":crit[0]["stop_seconds"] if crit else None,
            "first_request_record_seconds":events[0]["stop_seconds"] if events else None,
            "request_seconds_after_first_decision":events[0]["stop_seconds"]-valid[0]["stop_seconds"] if events else None}


def execute(project,name):
    project=Path(project).resolve();safe_name(name)
    folder=project/"outputs/runs"/name;folder.mkdir(parents=True,exist_ok=False)
    source=project/"outputs/runs/continuous_calibration_001"
    release=project/"outputs/releases/hi_candidate_v1"
    preserved={n:file_hashes(project/"outputs/runs"/n) for n in
               ("model_baseline_v1","operating_v2_development_001","load_only_experiment_001",
                "long_monitoring_001","continuous_calibration_001","candidate_playback_healthy_001","candidate_playback_fault_001")}
    release_hashes=file_hashes(release)
    report=dict(status="running",created_utc=datetime.now(timezone.utc).isoformat(),
                policy_version=POLICY_VERSION,previous_run_hashes=preserved,release_hashes=release_hashes,
                simulation_only=True,hardware_commands_enabled=False,real_audio_enabled=False)
    def save():(folder/"run.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    save()
    try:
        bundle=load_bundle(release)
        sr=json.loads((source/"run.json").read_text())
        for filename,h in sr["artifacts"].items():
            if sha256(source/filename)!=h:raise ValueError("Source experiment artifact changed.")
        protocol=project/"docs/operator_alarm_protocol.md"
        report.update(protocol_sha256=sha256(protocol),
                      implementation_sha256={p.relative_to(project/"src/optibelt_hi").as_posix():sha256(p)
                                             for p in sorted((project/"src/optibelt_hi").rglob("*.py"))})
        (folder/"protocol.md").write_text(protocol.read_text(),encoding="utf-8")
        (folder/"pre_evaluation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        inputs=[r for r in read_csv(source/"predictions.csv") if r["policy"]=="continuous"]
        keys=sorted({(r["recording_id"],r["arm"]) for r in inputs})
        if len(keys)!=56:raise ValueError("Expected 28 records x two references.")
        predictions=[];record_rows=[]
        for rid,arm in keys:
            original=sorted([r for r in inputs if r["recording_id"]==rid and r["arm"]==arm],
                            key=lambda r:int(r["episode_window_index"]))
            q=bundle["references"][arm]["thresholds"]["ewma"]
            hi=operator_hi(np.array([float(r["distance_ewma"]) for r in original]),q)
            for hysteresis in (False,True):
                for duration in (2,3,5):
                    policy=OperatorAlarm(duration,hysteresis)
                    base={k:original[0][k] for k in ("recording_id","arm","condition","load","hp","profile","duration")}
                    base.update(hysteresis=hysteresis,confirmation_seconds=duration)
                    rows=[]
                    for i,r in enumerate(original):
                        if float(r["threshold_ewma"])!=q:raise ValueError("Frozen threshold mismatch.")
                        stop=float(r["stop_seconds"]);eligible=r["eligible"]=="True"
                        result=policy.update(stop,float(hi[i]),eligible)
                        row={**base,"original_window_index":int(r["original_window_index"]),
                             "episode_window_index":int(r["episode_window_index"]),"stop_seconds":stop,
                             "eligible":eligible,"distance_ewma":float(r["distance_ewma"]),"threshold_ewma":q,
                             "legacy_hi":float(r["health_index_ewma"]),"operator_hi":float(hi[i]),**result}
                        rows.append(row);predictions.append(row)
                    record_rows.append(metrics(rows,base))
        summaries=[]
        for arm in ("A","C"):
            for h in (False,True):
                for duration in (2,3,5):
                    for group,value in (("all","all"),("load","0"),("load","30"),("load","60"),("duration","120"),("duration","300")):
                        selected=[r for r in record_rows if r["arm"]==arm and r["hysteresis"]==h and r["confirmation_seconds"]==duration
                                  and (group=="all" or r[group]==value)]
                        row=dict(arm=arm,hysteresis=h,confirmation_seconds=duration,group=group,value=value)
                        for label,healthy in (("healthy",True),("fault",False)):
                            records=[r for r in selected if (r["condition"]=="normal")==healthy]
                            timing=[r["request_seconds_after_first_decision"] for r in records if r["operator_requests"]]
                            row.update({label+"_records":len(records),label+"_request_records":sum(r["operator_requests"]>0 for r in records),
                                        label+"_non_normal_records":sum(r["non_normal_steps"]>0 for r in records),
                                        label+"_warning_steps":sum(r["warning_steps"] for r in records),
                                        label+"_critical_steps":sum(r["critical_steps"] for r in records),
                                        label+"_requests":sum(r["operator_requests"] for r in records),
                                        label+"_latched_steps":sum(r["latched_steps"] for r in records),
                                        label+"_state_transitions":sum(r["state_transitions"] for r in records),
                                        label+"_exposure_seconds":sum(r["decision_steps"] for r in records),
                                        label+"_first_request_offset_min":min(timing) if timing else None,
                                        label+"_first_request_offset_max":max(timing) if timing else None})
                        summaries.append(row)
        # Synthetic policy examples are distinct from empirical performance.
        scenarios={"brief_dip":[70,20,20,70,70,70,70],
                   "sustained_critical":[70]+[20]*7+[70],
                   "warning_boundary":[70,59,61,59,64,65,70],
                   "critical_recovery_band":[70,20,20,27,20,20,20,30,70],
                   "missing_reading":[70,20,20,None,20,20,20,70]}
        synthetic=[]
        for scenario,values in scenarios.items():
            for h in (False,True):
                for duration in (2,3,5):
                    policy=OperatorAlarm(duration,h)
                    for i,hi in enumerate(values):
                        synthetic.append(dict(scenario=scenario,hysteresis=h,confirmation_seconds=duration,time_seconds=i,hi=hi,
                                              **policy.update(i,hi)))
        for filename,rows in (("predictions.csv",predictions),("record_metrics.csv",record_rows),
                              ("summary.csv",summaries),("synthetic_scenarios.csv",synthetic)):
            write_csv(folder/filename,rows)
        if any(r["motor_stop_command"] for r in predictions+synthetic):raise ValueError("Hardware action requested.")
        if file_hashes(release)!=release_hashes:raise ValueError("Release changed.")
        for n,h in preserved.items():
            if file_hashes(project/"outputs/runs"/n)!=h:raise ValueError("Previous results changed.")
        for path,h in report["implementation_sha256"].items():
            if sha256(project/"src/optibelt_hi"/path)!=h:raise ValueError("Implementation changed.")
        report.update(status="complete",completed_utc=datetime.now(timezone.utc).isoformat(),
                      comparison=[r for r in summaries if r["group"]=="all"],prediction_rows=len(predictions),
                      previous_results_preserved=True,release_preserved=True,
                      artifacts={p.name:sha256(p) for p in folder.iterdir() if p.is_file() and p.name!="run.json"})
        save()
        print(json.dumps({"status":"complete","comparison":[r for r in summaries if r["group"]=="all" and r["arm"]=="C"]},indent=2))
        return folder
    except Exception as exc:
        report.update(status="failed",error=str(exc));save();raise


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",type=Path,required=True);parser.add_argument("--name",required=True)
    a=parser.parse_args();execute(a.project,a.name)

