"""Metadata-only operating-group folds, frozen before feature inspection."""
GROUPS = ((3.,0),(3.,30),(3.,60),(5.,0),(5.,30))
ADMISSION = {"candidate_complete_recording","hold_missing_vibration","hold_duration_review"}
CONDITIONS = {"normal","bearing","coil","interturn","misalign","journal"}

def group_key(record):
    return float(record["motor_capacity_hp"]), int(record["load_percent_label"])

def group_label(key):
    return f"{key[0]:g}HP_{key[1]}pct"

def build_folds(records):
    records=sorted(records,key=lambda r:r["recording_id"])
    for field in ("recording_id","sha256","relative_path"):
        if len({r[field] for r in records}) != len(records):
            raise ValueError(f"Reject duplicate {field}; related copies cannot cross roles.")
    if any(r["admission_status"] not in ADMISSION or r["condition"] not in CONDITIONS for r in records):
        raise ValueError("Unknown admission status or condition.")
    healthy={group_key(r) for r in records if r["condition"]=="normal" and
             r["admission_status"]=="candidate_complete_recording"}
    if not set(GROUPS).issubset(healthy):
        raise ValueError("Every primary group needs an eligible healthy recording.")
    output=[]
    for index,test in enumerate(GROUPS):
        calibration=GROUPS[(index+1)%len(GROUPS)]
        for r in records:
            group=group_key(r)
            if r["admission_status"]!="candidate_complete_recording":
                role="excluded_quality"
            elif group not in GROUPS:
                role="exploratory"
            elif group==test:
                role="test"
            elif r["condition"]!="normal":
                role="unused_fault"
            elif group==calibration:
                role="calibration"
            else:
                role="fit"
            output.append({"fold":index+1,"recording_id":r["recording_id"],
                "relative_path":r["relative_path"],"sha256":r["sha256"],"condition":r["condition"],
                "operating_group":group_label(group),"role":role})
    return output

def freeze(project):
    import csv
    import json
    from collections import Counter
    from datetime import datetime, timezone
    from pathlib import Path
    from optibelt_hi.data.audit import sha256, write_csv
    project=Path(project).resolve()
    admission=project/"dataset/splits/data_admission.csv"
    with admission.open(encoding="utf-8-sig",newline="") as handle:
        records=list(csv.DictReader(handle))
    assignments=build_folds(records)
    folder=project/"dataset/splits/grouped_v1"
    folder.mkdir(parents=True,exist_ok=False)
    write_csv(folder/"assignments.csv",assignments)
    report={
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "status":"frozen_before_feature_extraction",
        "protocol":"grouped_v1", "split_unit":"motor_capacity_hp_and_load_percent",
        "groups":[group_label(g) for g in GROUPS],
        "admission_sha256":sha256(admission),
        "assignments_sha256":sha256(folder/"assignments.csv"),
        "generator_sha256":sha256(Path(__file__)),
        "folds":[{"fold":i,"test_group":group_label(GROUPS[i-1]),
                  "calibration_group":group_label(GROUPS[i%len(GROUPS)]),
                  "role_counts":dict(Counter(r["role"] for r in assignments if r["fold"]==i))}
                 for i in range(1,len(GROUPS)+1)],
        "interpretation":"Retrospective operating-group transfer. Unknown motor/run identities prevent independent-machine claims. No model outcomes used for these assignments.",
    }
    (folder/"protocol.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return folder

if __name__=="__main__":
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",required=True,type=Path)
    print(freeze(parser.parse_args().project))

