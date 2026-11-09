# Operating-aware Python HI redesign: legacy review and proposed next stage

User clarification (6 November 2026): the intended system supports 1, 3 and 5 HP motors across 0%, 30% and 60% loads, accounting for operating-dependent vibration, current and torque. Motor rating and load percentage are distinct variables. The first Python pooled-baseline experiment and operating-group transfer split do not yet implement that complete requirement.

## Verified historical implementation

Inspected paths are under the separate historical MATLAB/playback workspace.

- MATLAB/Build_HI_v2.m: lines 53–76 pool Normal-labelled data at 0/30/60% into a single mean/covariance. Lines 108–139 derive load-specific yellow/red HI thresholds.
- The per-load threshold mask selects all records at a load, not only healthy records; its quantiles therefore include faults. Feature filtering/correlation selection earlier in the file also operates on the combined dataset. These practices must not be inherited.
- Python_HI/src/hi_monitor.py lines 50–55 hard-code yellow/red thresholds: 0% = 0.2972/0.1484; 30% = 0.3453/0.1192; 60% = 0.3678/0.2262. hi_status selects by load (line 195); playback supplies Load from metadata. Unknown loads use fallback thresholds and missing load defaults to 30% elsewhere in the script.
- AC/HI_params_v2.mat contains one 49-element mu and one 49x49 SigmaInv. Its fields are featNames, mu, SigmaInv, minMD, maxMD, loadPenalty, fs, L, hop. No capacity-specific model bank is present in this saved artifact.
- No explicit HP-dependent routing was found in the inspected builder/scorer. This finding does not establish that no other historical experimental version existed.
- The builder smooths raw HI separately with moving average and EWMA, while the inspected Python smooth_hi chains moving average into EWMA. Consequently historical smoothing behaviours should not be assumed identical from comments.
- Old Simulink reference files multiply HI by 0.7 at zero load; the compact paramsHI export uses a neutral factor of 1.0. These are version differences, not a single policy to reproduce.
- Previously documented sampling and fault-label errors also remain reasons to re-fit from corrected raw data. Historical results are design references, not trusted numerical ground truth.

## Proposed architecture

Recording + known motor rating + observed/declared operating state
-> validated raw preprocessing
-> features
-> healthy reference appropriate to rating and operating state
-> regularized Mahalanobis residual distance
-> causal smoothing with explicit state/reset/transition rules
-> healthy-only calibration of the actual warning/fault decision
-> HI, operating state, support status and explanation.

Start with capacity-specific healthy references so 5 HP equipment does not use a 3 HP-only fitted baseline. Within each rating, investigate a simple healthy feature expectation versus load and speed/profile; compute deviation from that expectation. Share statistical information within a rating where justified rather than constructing many poorly estimated separate covariance matrices. The exact normalization and covariance approach must be fixed and tested in a v2 development protocol before evaluating its results.

Motor rating comes from equipment configuration. For recorded playback, known load/speed metadata can be supplied explicitly. A live system needs a verified measurement, controller signal or validated estimator; filenames are not an online measurement. Unknown states and unvalidated interpolation/extrapolation must be reported explicitly, with no silent default to 30% load. Sensor changes need calibration compatibility before pooling.

## Coverage constraints

17 complete healthy records remain:
- 1 HP: one invariant-speed recording at each of 0/30/60%; variable-speed healthy vibration is missing.
- 3 HP: variable-speed records at 0/30/60%; invariant-speed records at 30/60%; no complete invariant-speed 0% healthy comparator in this subset.
- 5 HP: invariant- and variable-speed records at 0/30%; no complete healthy 60% recording in this subset.

Full support for all ratings, loads and speed profiles is a design target, not a validated capability. Retain 1 HP constant-speed data for development. Explore current/torque-only 1 HP variable-speed models separately if remaining channels pass admission; do not pretend they validate five-channel fusion. Obtain additional independent healthy acquisitions for missing and sparsely repeated operating states.

## How the investigation findings will be addressed

1. Coverage mismatch: capacity-specific references and operating-aware normalization; declare supported states. Preserve grouped_v1 as a transfer stress test, not the sole measure of performance in represented conditions.
2. Feature/covariance sensitivity: training-only stability checks across healthy operating states; compare a compact residual feature set and simpler covariance models with regularized fusion. Do not remove features because they triggered a particular exposed test case.
3. Calibration fragility: healthy-only calibration representative of the supported range. Two or three records cannot support precise rare-event guarantees; document calibration uncertainty and collect repeat acquisitions.
4. Smoothing and persistence: calibrate the exact deployed chain (chosen smoothing, warning/fault thresholds, persistence and monitoring duration). A 99th percentile of windows is not a 1% recording-alert guarantee. Handle operating-state transitions explicitly; arbitrary state resets must not hide faults.
5. Evaluation mismatch: keep healthy fit, calibration and evaluation acquisitions disjoint within supported conditions where repeats exist. Assess new operating-state transfer separately. Where only one recording exists, blocked temporal checks with overlap/filter guards are development evidence only, not independent-record validation.
6. Reproducibility: implement as v2 with versioned configurations, per-state coverage, input/code hashes and unchanged v1 evidence. Every later comparison must disclose that the current dataset has already been inspected.

## Next implementation sequence

Build a condition-coverage manifest and explicit model-selection/metadata contract; specify a small capacity/load-aware v2 development experiment; test state routing and normalization for leakage; fit/calibrate using healthy development populations; compare false alarms and fault sensitivity using the declared protocol. Add dashboard playback after the operating-aware scores and coverage semantics are defined.

This document is a reviewed direction, not an implemented or validated v2 model. Some problems can be corrected in software now; strong claims across every requested operating state require additional independent data.

