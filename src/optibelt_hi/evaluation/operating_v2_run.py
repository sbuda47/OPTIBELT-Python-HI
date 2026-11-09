"""Version 2 condition-aware temporal development run."""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import json
import numpy as np
from optibelt_hi.data.audit import sha256,write_csv
from optibelt_hi.data.recordings import metadata
from optibelt_hi.evaluation.model_run import load_inputs,read_csv,safe_name
from optibelt_hi.model.operating_v2 import state_key,blocks,build_bank,score_episode,SETTINGS

def file_hashes(folder):
    return {p.name:sha256(p) for p in folder.iterdir() if p.is_file()}

def assemble(project,data):
    rows=read_csv(project/"dataset/splits/data_admission.csv")
    entries=[]
    for r in rows:
        info=metadata(project/r["relative_path"])
        key=state_key(info["motor_capacity_hp"],info["load_percent_label"],info["speed_profile"],info["supply_high_hz"])
        e={"recording_id":r["recording_id"],"state":key,"hp":info["motor_capacity_hp"],
           "load":info["load_percent_label"],"profile":info["speed_profile"],"upper":info["supply_high_hz"],
           "duration":info["expected_duration_s"],"condition":info["condition"],
           "admission":r["admission_status"]}
        if e["recording_id"] in data:
            e.update(features=data[e["recording_id"]]["features"],bounds=data[e["recording_id"]]["bounds"])
        entries.append(e)
    return entries

def coverage(entries):
    output=[]
    for hp in (1,3,5):
        for load in (0,30,60):
            for profile,upper in (("invariant_speed",50),("varying_speed",52),("varying_speed",58)):
                key=state_key(hp,load,profile,upper)
                related=[e for e in entries if e["state"]==key]
                healthy=[e for e in related if e["condition"]=="normal" and "features" in e]
                output.append({"state":key,"hp":hp,"load":load,"profile":profile,"supply_upper_hz":upper,
                   "complete_healthy_recordings":len(healthy),
                   "complete_fault_recordings":sum(e["condition"]!="normal" and "features" in e for e in related),
                   "excluded_recordings":sum("features" not in e for e in related),
                   "status":"supported_development" if healthy else "unsupported",
                   "reason":"Healthy reference present; independent replication unavailable." if healthy else "No complete healthy five-channel reference."})
    return output

def execute(project,name):
    project=Path(project).resolve(); safe_name(name)
    folder=project/"outputs/runs"/name; folder.mkdir(parents=True,exist_ok=False)
    old=project/"outputs/runs/model_baseline_v1"; preserved=file_hashes(old)
    report={"status":"running","created_utc":datetime.now(timezone.utc).isoformat(),"v1_hashes_before":preserved}
    def save(): (folder/"run.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    save()
    try:
        data,_,names=load_inputs(project,project/"outputs/runs/candidate_features_v1")
        entries=assemble(project,data); cov=coverage(entries)
        healthy=[e for e in entries if "features" in e and e["condition"]=="normal"]
        source=project/"src/optibelt_hi"
        report.update(settings=SETTINGS,protocol_sha256=sha256(project/"docs/v2_protocol.md"),
            feature_run_sha256=sha256(project/"outputs/runs/candidate_features_v1/run.json"),
            admission_sha256=sha256(project/"dataset/splits/data_admission.csv"),
            implementation_sha256={p.relative_to(source).as_posix():sha256(p) for p in sorted(source.rglob("*.py"))})
        (folder/"pre_fit.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        (folder/"protocol.md").write_text((project/"docs/v2_protocol.md").read_text(encoding="utf-8"),encoding="utf-8")
        write_csv(folder/"condition_coverage.csv",cov)
        bank=build_bank(healthy,names)
        (folder/"bank.json").write_text(json.dumps(bank,indent=2,allow_nan=False),encoding="utf-8")
        routing=[]; splitting=[]; predictions=[]; metrics=[]
        for e in entries:
            base={k:e[k] for k in ("recording_id","state","hp","load","profile","upper","condition")}
            if "features" not in e:
                routing.append({**base,"status":"excluded_quality","reason":e["admission"]}); continue
            if e["state"] not in bank["states"]:
                routing.append({**base,"status":"unsupported","reason":"No complete healthy reference at this declared condition."}); continue
            routing.append({**base,"status":"supported_development","reason":"Temporal development evidence only."})
            split=blocks(e["bounds"],e["duration"])
            roles=split if e["condition"]=="normal" else {"check":split["check"]}
            for role,indices in roles.items():
                splitting.append({**base,"role":role,"window_indices":json.dumps(indices.tolist()),
                    "start_seconds":int(e["bounds"][indices[0],0])/25600,
                    "stop_seconds":int(e["bounds"][indices[-1],1])/25600,
                    "windows":len(indices)})
            indices=split["check"]
            scored=score_episode(bank,e["features"][indices],e["state"],names)
            spec=bank["states"][e["state"]]
            for j,i in enumerate(indices):
                predictions.append({**base,"original_window_index":int(i),"episode_window_index":j,
                    "start_seconds":int(e["bounds"][i,0])/25600,"stop_seconds":int(e["bounds"][i,1])/25600,
                    "eligible":bool(scored["eligible"][j]),"distance":float(scored["distance"][j]),
                    "distance_ewma":float(scored["distance_ewma"][j]),
                    "hi":float(scored["health_index"][j]),"hi_ewma":float(scored["health_index_ewma"][j]),
                    "alarm":bool(scored["alarm"][j]),"alarm_ewma":bool(scored["alarm_ewma"][j]),
                    "persistent":bool(scored["persistent"][j]),"persistent_ewma":bool(scored["persistent_ewma"][j])})
            for stream,suffix in (("raw",""),("ewma","_ewma")):
                eligible=scored["eligible"]; alert=scored["persistent"+suffix]
                metrics.append({**base,"stream":stream,"decision_windows":int(eligible.sum()),
                    "threshold":spec["threshold_raw" if stream=="raw" else "threshold_ewma"],
                    "alarm_fraction":float(scored["alarm"+suffix][eligible].mean()),
                    "persistent_alert":bool(alert.any()),
                    "first_alert_seconds_from_record_start":float(e["bounds"][indices[np.flatnonzero(alert)[0]],1]/25600) if alert.any() else None})
        for filename,values in (("record_routing.csv",routing),("temporal_blocks.csv",splitting),
                                ("predictions.csv",predictions),("record_metrics.csv",metrics)):
            write_csv(folder/filename,values)
        comparisons=[]
        for stream in ("raw","ewma"):
            row={"stream":stream}
            for label,normal in (("healthy",True),("fault",False)):
                selected=[r for r in metrics if r["stream"]==stream and (r["condition"]=="normal")==normal]
                row.update({label+"_recordings":len(selected),label+"_alerts":sum(r["persistent_alert"] for r in selected),
                            label+"_mean_alarm_fraction":float(np.mean([r["alarm_fraction"] for r in selected])) if selected else None})
            comparisons.append(row)
        write_csv(folder/"summary.csv",comparisons)
        if file_hashes(old)!=preserved: raise ValueError("Original v1 results changed.")
        report.update(status="complete",completed_utc=datetime.now(timezone.utc).isoformat(),
            supported_conditions=len(bank["states"]),capacity_models=len(bank["models"]),
            healthy_recordings=len(healthy),scored_recordings=len({r["recording_id"] for r in metrics}),
            unsupported_recordings=sum(r["status"]=="unsupported" for r in routing),
            excluded_recordings=sum(r["status"]=="excluded_quality" for r in routing),
            comparison=comparisons,v1_preserved=True,
            evidence_scope="Same-record temporal checks on exposed data, not independent-record validation.",
            artifacts={p.name:sha256(p) for p in folder.iterdir() if p.is_file() and p.name!="run.json"})
        save(); print(json.dumps({k:report[k] for k in ("status","supported_conditions","capacity_models","scored_recordings","unsupported_recordings","comparison")},indent=2))
        return folder
    except Exception as exc:
        report.update(status="failed",error=str(exc)); save(); raise

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",required=True,type=Path); parser.add_argument("--name",required=True)
    args=parser.parse_args(); execute(args.project,args.name)

