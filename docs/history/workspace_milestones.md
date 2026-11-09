# OPTIBELT Python HI

This is the new Python research workspace for raw-data processing, a multivariate health index and its future dashboard. Completed stages establish source provenance, native-channel quality, tested offline preprocessing, frozen operating-group folds, candidate feature extraction and an evaluated first Python MD-HI baseline.

## Start

Use Python 3.12–3.14 and uv. The installed environment is Python 3.14; uv.lock records exact dependencies.

~~~powershell
uv sync --locked
uv run optibelt-hi --help
uv run pytest
~~~

To repeat the raw-data audit, use a fresh run name.

~~~powershell
uv run optibelt-hi audit --name raw_audit_002
~~~

To prepare one complete recording and enumerate full windows

~~~powershell
uv run optibelt-hi prepare --recording "dataset/raw/varying_speed/Normal_3HP_30%_58Hz.mat" --name prepare_002
~~~

Each command writes a new outputs/runs directory and refuses to overwrite an existing run. A failed preparation records its error in run.json. For memory planning, the largest classic MAT matrix alone occupies approximately 1.2 GB before processing arrays.

## Current evidence

The 41 source files were copied and checked with SHA-256. The audit has 32 recordings that meet the initial five-channel, nominal-duration checks, seven missing vibration channels, and two duration discrepancies. Read docs/findings.md before planning a model fit.

Native rates are 25.6 kHz for vibration and torque and 100 kHz for current. Current is resampled by 32/125 with an explicit low-pass FIR filter. Native missing values are rejected, and structural NaN padding is removed using the source duration. No baseline or HI is fitted in this milestone.

## Project map

- dataset/raw holds the immutable source copies.
- dataset/manifests holds provenance and the initial recording manifest.
- dataset/splits records eligibility and frozen grouped_v1 assignments.
- dataset/processed is reserved for reusable derived data.
- src/optibelt_hi contains the Python implementation.
- configs contains the processing contract and the evaluation design status.
- outputs/runs contains auditable results and validation evidence.
- tests uses generated synthetic signals and small MAT fixtures.
- docs records source descriptions, research questions, decisions and findings.
- visualizations and dashboard are reserved for later work.

## Next stage

Connect verified playback and the separately versioned operator-zone simulation to Streamlit, showing zone, pending timer, latched human-review request and data quality. Do not add automatic motor stopping. Keep HP-specific models excluded and seek independent recordings plus severity/response-time evidence before finalizing alarm settings. See docs/operator_alarm_results.md.

The old MATLAB and Python playback project is historical evidence for methodology. This project will generate its own features, baseline, calibration and evaluation. Git ignores raw data, derived arrays, environment files and experiment outputs. Dataset attribution is documented in docs/dataset_description.md; software licensing remains to be selected before public release.


## Verified milestone record
The resumed validation passed 27 tests and verified a real 120-second input, its source/configuration/code hashes, five finite output channels and 119 complete two-second windows. Evidence: outputs/runs/preprocessing_validation_002/validation.json. Dataset admission: dataset/splits/data_admission.csv. Duration details: docs/duration_evidence.json. Historical label audit: docs/legacy_label_evidence.json. Evaluation feasibility: docs/evaluation_design.md. This is the historical preprocessing milestone; see the feature milestone below for the current stage.

## Candidate feature milestone
48 tests passed. All 32 admitted recordings produced 5,788 complete two-second windows, each with 60 documented candidate features. Outputs: outputs/runs/candidate_features_v1. Verification: outputs/runs/features_validation_001/validation.json. No feature selection or model fitting has occurred.

Five metadata-only operating-group rounds are frozen in dataset/splits/grouped_v1. Primary evaluation uses 27 recordings (14 normal, 13 fault-labelled); five recordings are exploratory. See docs/evaluation_design.md for scope and limitations, and docs/feature_catalog.md for formulas and known redundancy.

To repeat extraction with a fresh run name:

~~~powershell
uv run python -B -m optibelt_hi.features.batch --project . --name candidate_features_v2
~~~

## First model evaluation
The Python MD-HI baseline, separate healthy calibration and causal EWMA are implemented. All 72 tests passed and 23,265 saved predictions were reproduced from saved models. Raw fusion alerted on 13/13 fault and 3/14 normal records; EWMA fusion alerted on 13/13 fault and 7/14 normal records. This version has excessive false alarms on withheld operating groups and is not validated for operational alarms. See docs/model_results_v1.md, docs/model_protocol_v1.md and outputs/runs/model_baseline_v1. The older no-model statements above describe earlier milestones.

To run a declared model protocol with a new output name:

~~~powershell
uv run python -B -m optibelt_hi.evaluation.model_run --project . --features candidate_features_v1 --name declared_model_run
~~~
Do not use repeated test evaluation to tune parameters while claiming untouched validation.

## False-alarm investigation
The post-evaluation investigation is complete; the evaluated models and thresholds remain unchanged. Evidence points to operating-group coverage mismatch, fragile calibration with only 2–3 records, and sensitivity to joint-feature differences. Targeted raw screening found no obvious structural defect explaining the alerts. See docs/false_alarm_investigation_v1.md and outputs/runs/false_alarm_investigation_v1. A revised operating-aware baseline and full alarm calibration require a separately declared development protocol; no revision was made here.

## Version 2 operating-aware reference
Implemented and tested: 17 explicit healthy conditions, three within-rating residual covariance models, unsupported-state routing, guarded temporal blocks and full three-window event calibration. V1 is preserved. All 80 tests pass, but V2 still produces high healthy alarm rates (raw 14/17; EWMA 13/17) on its same-record temporal development checks. Supported fault alerts are 11/11. These are not comparable to V1 as a like-for-like accuracy benchmark and do not establish deployment readiness. See docs/v2_results.md and outputs/runs/operating_v2_development_001.


## Controlled load-only comparison
HP-specific modelling is deferred. Four fixed arms compare pooled versus load-centred references and global versus load-specific thresholds. All 84 tests pass. With EWMA and global thresholds, both references detect 11/11 supported fault episodes with 0/17 healthy sustained alerts; load-specific thresholds introduce 2/17 or 3/17 healthy alerts. These are short same-record temporal development checks, not independent-record validation. All 2,800 predictions and 224 metrics were verified; V1/V2 outputs are preserved. See docs/load_experiment_results.md and outputs/runs/load_only_experiment_001.


## Longer monitoring with frozen models
Completed on the full reserved check intervals. Nine records extend from 15 to 60 decision steps; 19 cannot extend. Both smoothed models now alert on 1/17 healthy records (Normal_1HP_0%): two brief events for the pooled reference and one for the load-centred reference. Both retain 11/11 fault detections. The original short prefixes reproduce, and all models/thresholds and earlier outputs remain unchanged. All 90 tests pass; 2,210 prediction rows and 336 metrics were independently verified. These remain same-acquisition development results, not continuous hours-long or independent-record validation. See docs/long_monitoring_results.md.


## Investigation of the later false alerts
Completed without changing the detector. Torque shape/spectral features dominate the positive score allocations in Normal_1HP_0%, while vibration spectral content shifts later despite nearly stable amplitude. Native screening of three records found no missing samples or flat seconds; all 17,940 target feature values reproduced exactly. Continuous replay also reveals a sustained event in an unused tail of the target's reserved calibration interval. The next controlled change should align calibration with continuous monitoring before reconsidering HP models. Physical causes remain unresolved. See docs/normal_1hp0_investigation.md and outputs/runs/normal_1hp0_investigation_001.


## Continuous healthy calibration comparison
Completed with both reference models frozen. Full continuous healthy calibration raises the EWMA thresholds by 3.55% (A) and 3.13% (C). Both then produce 0/17 healthy sustained alerts and retain 11/11 supported fault detections on the full reserved check intervals. Raw-score false alerts persist. All 94 tests passed; 4,420 predictions and 672 metrics were independently verified. This is a favourable exposed-data development result, not independent validation or a dashboard deployment. The old bank and prior runs remain unchanged. See docs/continuous_calibration_results.md and outputs/runs/continuous_calibration_001.


## Packaged Python HI and verified raw playback
hi_candidate_v1 now packages the frozen load-aware reference C and pooled comparison A with continuous-calibration thresholds, preprocessing, feature schema, supported conditions and integrity hashes. The offline raw-to-HI playback CLI and a stateful feature-window monitor are implemented. All 99 tests pass; 2,210 saved predictions reproduced, and fresh healthy/fault raw runs reproduced all 35,880 feature values and 140 check predictions. This is software reproducibility, not new independent validation or live-sensor deployment. See docs/candidate_playback.md for commands and outputs/releases/hi_candidate_v1 for the bundle.


## Operator zones and duration simulation
operator_zones_v1 maps the frozen calibration boundary to HI 60, with warning below 60 and critical below 25. It compares 2/3/5 elapsed-second critical confirmation and recovery hysteresis (65/30), producing only logged operator/audible-alarm requests. No actual sound, motor stop or restart occurs. C yields 0/17 healthy critical requests and 10/11 fault critical requests at every duration; all faults reach at least warning, and two healthy records also warn. Hysteresis reduces state switching but prolongs warnings. All 108 tests passed and 13,260 rows were independently verified. The old release is unchanged; see docs/operator_alarm_results.md for mapping versions and limits.


## Simulated-live pipeline — 9 November 2026
A separate hardware-independent raw-data pipeline, recording simulator and local engineering monitor are now available. See [setup and adapter contract](live_pipeline/README.md) and [milestone evidence](docs/live_pipeline.md). The frozen HI and original playback dashboard remain unchanged.
