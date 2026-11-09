# Frozen evaluation protocol: grouped_v1

The assignments are frozen before computing the new features. The authoritative file is dataset/splits/grouped_v1/assignments.csv; protocol.json records its SHA-256, admission SHA-256, generator SHA-256, time and role counts. The earlier admission manifest's split=unassigned field records the initial admission stage; use this versioned assignment file for all modelling.

## Study question and population

The primary question is whether healthy behaviour learned at some motor-capacity/load combinations transfers to a withheld combination in this subset. This is retrospective operating-group validation, not a matched-condition detection experiment or independent-machine validation.

The primary population contains 27 complete recordings from 3 HP and 5 HP motors: 14 normal and 13 fault-labelled. All speed profiles at a given capacity/load stay in one group. Five groups are ordered using metadata only: (3 HP,0%), (3 HP,30%), (3 HP,60%), (5 HP,0%), (5 HP,30%).

The three complete invariant-speed 1 HP normal recordings, one variable-speed 1 HP misalignment record and one 7.5 HP journal record remain available as five exploratory records. They are extracted but excluded from the primary protocol. Missing variable-speed 1 HP healthy vibration and the absence of any 7.5 HP healthy comparator prevent matched-condition fusion claims for those cases.

Seven missing-vibration and two duration-discrepant recordings remain excluded from this initial extraction/model cohort. The bearing record contains 120 contiguous seconds; the short coil record has approximately 31.6274 seconds of vibration/torque versus 31.6377 seconds of current. They may support separately declared shortened-recording work later. Originals are retained.

## Five fixed rounds

In round i, group i is the evaluation group. The next group in the above cyclic ordering supplies healthy calibration recordings. Healthy recordings in the remaining three groups supply fitting data. Fault-labelled records outside the evaluation group have role unused_fault and do not fit, select features or calibrate.

| Round | Evaluation group | Healthy calibration group |
|---|---|---|
| 1 | 3 HP, 0% load | 3 HP, 30% load |
| 2 | 3 HP, 30% load | 3 HP, 60% load |
| 3 | 3 HP, 60% load | 5 HP, 0% load |
| 4 | 5 HP, 0% load | 5 HP, 30% load |
| 5 | 5 HP, 30% load | 3 HP, 0% load |

Every primary recording appears in evaluation once. Whole recordings and all their overlapping windows stay together. No random window split is performed. A recording can have different roles in different rounds, as in cross-validation; transformations and model state must reset completely for each round. No evaluation-derived information may feed later rounds.

The cyclic calibration assignment is a predeclared, metadata-only design choice, not an optimized split. Each calibration set is small and represents one operating group, so it cannot establish a universal false-alarm rate. Report per-round counts and operating regimes. Any sensitivity analysis that rotates calibration groups must be declared separately and must not count repeated predictions as new independent observations.

## Fit, calibration and reporting contract

Fit scaling, feature selection, covariance and any development choices on healthy fitting data only. Calibration data will set distance/HI scaling and alarm thresholds under a separately documented numerical rule. Evaluation records must not select a covariance estimator, feature list or smoothing strength. Preserve unbounded distance alongside any bounded HI.

Compare fusion and single-modality methods using identical primary assignments and threshold policies. Report per-recording, per-fault and per-operating-group outcomes. Use recording-aware uncertainty; overlapping windows are not independent experimental replications. The three fit groups per fold supply only a small number of recordings despite many windows.

Physical motor and acquisition-run identities remain unknown. Grouping capacity/load conservatively keeps related operating examples together, but cannot guarantee independent hardware or acquisition sessions across roles. Constant and variable-speed acquisitions also used different vibration sensors according to the source paper. Model alarms may reflect operating/sensor shift as well as damage.

These recordings were used previously in the final-year study. Freeze timing prevents outcome-based split choices in this Python rebuild but does not turn them into unseen external validation data. A subsequent paper must disclose this history.

## Stage boundary

This milestone freezes splits and extracts fixed candidate features only. No model or threshold is yet fitted. Next: predeclare training-only feature reduction, covariance strategy, healthy calibration rule and causal smoothing policy before calculating evaluation outcomes.

