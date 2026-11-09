# Controlled load-only experiment — 6 November 2026

The load-centred model can operate without HP-specific models, but load-specific thresholds did not improve this development comparison. The simplest pooled reference and the load-centred reference both detected all 11 supported fault episodes with no sustained healthy alerts after EWMA when using a global threshold. Retain both as candidates; there is no demonstrated detection benefit from load centring on these checks.

Run: outputs/runs/load_only_experiment_001.
Frozen protocol: docs/load_experiment_protocol.md (also copied and hashed inside the run).
Validation: outputs/runs/load_experiment_validation_001/validation.json and pytest.xml.

## Controlled comparison

All arms use exactly the same 28 records and check indices: 17 normal and 11 fault. Healthy training blocks alone determine feature selection, scaling, means and covariance. No HP or speed value selects a fitted model or alarm threshold. Both fitted references retained 36 features from the fixed 60-feature candidate schema. HP remains descriptive metadata and part of the inherited evidence-coverage boundary, not an input to fitting or scoring.

| Arm | Healthy reference | Threshold | Raw healthy sustained alerts | EWMA healthy sustained alerts | Raw / EWMA fault detections |
|---|---|---|---:|---:|---:|
| A | One pooled reference | Global | 1/17 | 0/17 | 11/11; 11/11 |
| B | Same pooled reference | Per load | 2/17 | 2/17 | 11/11; 11/11 |
| C | Load-specific centres, one shared residual covariance | Global | 1/17 | 0/17 | 11/11; 11/11 |
| D | Same load-centred reference | Per load | 3/17 | 3/17 | 11/11; 11/11 |

A sustained alert requires three consecutive decision windows strictly above threshold. EWMA alpha is 0.2. Each check has ten warm-up windows followed by fifteen decision windows; a two-second feature window advances every second. These are short episodes, not full-record monitoring results or false alarms per hour.

No sustained alert does not mean no threshold crossings. Healthy EWMA threshold-crossing fractions were A 7/255 (2.75%), B 16/255 (6.27%), C 8/255 (3.14%), D 21/255 (8.24%). Windows overlap and are correlated; these fractions are descriptive, not independent trial probabilities. Every one of the 165 fault decision windows exceeded its arm's raw and smoothed threshold.

## Why separate load thresholds did not help here

Global calibration takes the largest healthy calibration event level across all loads. Per-load calibration takes the largest within that load. A per-load threshold therefore cannot exceed its corresponding global threshold. A/B have identical distances, as do C/D: lowering the threshold can add alarms but cannot remove them.

For the pooled model, the EWMA global threshold was 5.6221. The per-load thresholds were 5.6221 (0%), 5.1199 (30%) and 5.2367 (60%). The lower 30% and 60% thresholds introduced two healthy sustained alerts without detecting any additional fault episode.

For the load-centred model, the EWMA global threshold was 5.6864. Per-load thresholds were 5.6864, 5.1367 and 5.0845. Three healthy episodes alerted with these thresholds. Thresholds belong to their fitted reference: numerical distances from different references are not directly comparable.

This is evidence for retaining broad healthy calibration in the present experiment. It does not establish that load-specific calibration is always inferior, or that weaker faults would be detected at the global threshold.

## Cases and calibration support

EWMA false-alert cases:

- B and D: Normal_3HP_30%_58Hz.mat.
- B and D: Normal_3HP_60%_52Hz.mat.
- D only: Normal_3HP_60%_58Hz.mat.

For raw scores, A and C alerted on Normal_3HP_60%_52Hz.mat; B added Normal_3HP_30%_58Hz.mat; D additionally alerted on Normal_3HP_60%_58Hz.mat. No fault episodes in the supported cohort were missed. All cases and per-load outcomes are retained in record_metrics.csv, paired_outcomes.csv and by_load.csv.

| Load | Healthy records | Calibration episodes | Fault check records | A/C EWMA healthy alerts | B EWMA healthy alerts | D EWMA healthy alerts |
|---|---:|---:|---:|---:|---:|---:|
| 0% | 6 | 8 | 3 | 0/6 | 0/6 | 0/6 |
| 30% | 7 | 10 | 5 | 0/7 | 1/7 | 1/7 |
| 60% | 4 | 6 | 3 | 0/4 | 1/4 | 2/4 |

The 24 calibration episodes come from 17 recordings. Longer recordings provide two complete guarded episodes, shorter ones one. These are correlated episodes from the same acquisitions used for fitting and checking, not 24 independent calibration acquisitions. Maximum-envelope calibration yields no guaranteed future event rate.

## Relationship to earlier work

The original code used a pooled reference with load-dependent thresholds; B preserves that architectural idea. It does not reproduce the original numerical pipeline: corrected Python features and healthy-only calibration replace the historical mixed-rate extraction and thresholds derived using fault-labelled data.

Version 2's EWMA result was 13/17 healthy sustained alerts and 11/11 fault detections on these same check indices. This experiment also changes reference pooling, calibration pooling and the number of calibration episodes. Its improvement cannot be attributed solely to removing HP models. The four new arms are the controlled comparisons; V2 is historical context.

V1 used a different population and operating-group holdout design. Do not rank it against these same-record results as if the validation conditions were identical. V1 and V2 result files remain hash-identical.

## Verification and scientific limits

All 84 tests passed. The saved bank rebuilt exactly, and replacing all HP labels in the real healthy entries left it unchanged. Separate arithmetic using a covariance solve reproduced all 2,800 prediction rows, 224 recording metrics and 48 calibration event values (24 per reference), including EWMA, HI mapping, thresholds and persistence. Artifact hashes and earlier-run hashes matched. Verification script: tests/verify_load_experiment_artifacts.py (a manual verifier, not a pytest test module).

Nine source-quality exclusions and four complete but unmatched fault recordings remain outside the primary comparison. The unchanged cohort restriction does not imply support for every HP/load/speed combination, especially missing healthy 5 HP/60% and 1 HP variable-speed five-channel references.

These recordings were previously exposed during development and the earlier study. Guarded time blocks prevent shared raw samples across roles, but fitting, calibration and checking still share an acquisition. No independent-machine, independent-record or prospective performance claim follows. The index is a normalized deviation score, not a percentage of physical remaining health.

## Next experiment, before adding HP models

Keep A as the simple control and C as the load-aware candidate, with their saved models and thresholds frozen. Predeclare a longer chronological monitoring check across the remaining reserved check interval, specifying EWMA initialization, any resets and episode duration. Report all sustained events, time above threshold, and per-load fault sensitivity without using outcomes to tune thresholds. Such a follow-up is additional exposed-data development, not fresh validation.

Then test on new, complete healthy and fault recordings with known acquisition/motor identity and load. Include repeated runs, weaker faults where available, and load/speed transitions. Define how load metadata will be supplied to the dashboard. HP-specific models should be reconsidered only after the load-only design shows a reproducible limitation that they can address.

