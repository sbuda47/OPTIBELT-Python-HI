# Technical decisions

## D001 — Independent Python workflow
The new model will be fitted, calibrated and evaluated in Python. The older MATLAB implementation supplies historical definitions and decisions to investigate. No old model parameters or HI values are imported into training.

## D002 — Preserve native time bases
The source description and local matrix structure establish 25.6 kHz for vibration/torque and 100 kHz for current. The old MATLAB function downsampled every column using a factor rounded to four. For current that produces 25 kHz; applying it to vibration/torque produces 6.4 kHz. Labelling both 25.6 kHz changes time and frequency interpretation.

The offline Python preparation leaves vibration and torque at their native rate and uses polyphase FIR resampling by 32/125 for each current channel. Kaiser beta 5 and linear endpoint extension are explicit provisional settings. Synthetic tests check frequency preservation and alias attenuation. Streaming filter state, latency and endpoint policy remain future validation work. [SciPy resample_poly](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample_poly.html)

## D003 — Distinguish padding and missing measurements
Only NaNs beyond the native channel duration are treated as structural padding. Native intervals containing NaNs or infinities, missing channels or constant channels fail the initial preparation gate. Zeros within measured signals are valid values. No implicit imputation, flat-signal replacement or whole-recording mean removal occurs in preparation.

## D004 — Preserve operating labels
Coil, Interturn, Bearing, Misalign and Journal are retained. A name that is not recognized is rejected. Load, motor capacity and speed-profile bounds are metadata from the filename. Future inference must define separately how operating information is obtained.

## D005 — Reserve evaluation design
Window-level random splitting is prohibited. Whole recordings and related acquisitions must stay together. physical_motor_id and acquisition_run_id are explicitly unknown. A recording-level split can prevent overlapping-window leakage but cannot establish independent-machine validation without further provenance.

No feature selection, baseline fit or threshold tuning begins before data eligibility and a documented evaluation protocol are settled. Prior use of these recordings during the final-year study is disclosed.

## D006 — Traceable runs
Each CLI invocation requires a new output directory name. Existing outputs are never overwritten. Raw inputs are ignored by Git and checked against the copy receipt. Generated preprocessing output records input SHA-256, sampling rates, filter settings and window boundaries.


## D007 — Initial cohort and evidence closure
The initial five-channel cohort retains 32 complete recordings. Seven missing-vibration recordings and two shorter recordings are held out of initial modelling, with their raw data preserved. This is an explicit initial scope choice; a duration discrepancy alone does not establish corruption. Admission is recorded in dataset/splits/data_admission.csv; measured durations and legacy label evidence are saved separately. See docs/evaluation_design.md for coverage limits and requirements before model fitting.

## D008 — Operating-group protocol
Five metadata-only rounds hold out complete capacity/load groups across speed profiles. Primary population is 27 complete 3/5 HP records; five others are exploratory. Each round has 8–9 healthy fitting and 2–3 healthy calibration recordings. All primary records are evaluated once; fault records never fit or calibrate. Scope is retrospective operating-group transfer, with unknown physical motor/run identities. See evaluation_design.md.

## D009 — Fixed first candidate feature schema
candidate_v1 contains 12 measures per channel (60 total), with explicit uncorrected central moments and Hann-periodogram broadband fractions. All 32 admitted recordings produced 5,788 windows. No learned feature selection or baseline was performed. Algebraic redundancy, physical-unit uncertainty and omitted harmonic/envelope features are documented in feature_catalog.md.

## D010 — First model protocol and honest evaluation
model_protocol_v1 fixes recording-balanced healthy fitting, deterministic redundancy/correlation pruning, 0.1 covariance shrinkage, weighted 99th-percentile healthy calibration, bounded HI mapping and alpha=0.2 reset EWMA. Five fixed variants and five frozen rounds were evaluated without post-result retuning. Fusion detected every fault record under the sustained-alert rule, but raw/EWMA alerts affected 3/14 and 7/14 normal records respectively. This is an evaluated research baseline, not a validated operational alarm. See model_results_v1.md for complete tradeoffs.

## D011 — Diagnose false alarms without altering the evaluated baseline
Post-evaluation diagnostics preserved every model_baseline_v1 file hash. At the original raw threshold, smoothing changed mean healthy alarm-window occupancy from 17.4% to 14.5%; applying the separately calibrated EWMA threshold raised it to 33.7%. Persistent-record alerts were 3/14, 4/14 and 7/14 respectively. Operating-group transfer includes a round fitted entirely on 3 HP data and tested on 5 HP/0% with 5 HP/30% calibration. Calibration leave-one-record-out thresholds varied by up to 32.1%. Targeted native screening of six records found no missing native samples or sustained flat signals; boundary cropping did not remove the persistent alarms. No revised model or threshold is deployed. See false_alarm_investigation_v1.md.

## D012 — Explicit operating-aware V2 development bank
Use exact rated-HP/load/acquisition-profile centres and shared residual covariance within each HP rating. No interpolation or silent fallback. Seventeen reference-present states route; four complete unmatched fault records abstain and nine quality exclusions remain. Healthy temporal fit/cal/check blocks are separated with four-second guards; checks use ten warm-up plus fifteen decision windows. Calibrate the three-window event statistic on healthy episodes. False alarms remain high; V2 is a development implementation, not validated deployment. Preserve V1 and prohibit misleading cross-protocol performance comparisons. See v2_protocol.md and v2_results.md.


## D013 — Defer HP modelling and compare load-only policies
Four predeclared arms share a fixed 28-record cohort and guarded temporal check episodes. Compare pooled/load-centred references crossed with global/per-load healthy event thresholds. Use 24 complete calibration episodes from 17 healthy recordings, with no HP-specific fitting or scoring. A and C both yield 0/17 healthy sustained EWMA alerts and 11/11 fault alerts; B and D add 2 and 3 healthy alerts without extra detections. Keep A as the simple control and C as the load-aware candidate; do not promote either as independently validated. Do not attribute improvement over V2 solely to removing HP because calibration pooling and coverage also changed. Next, predeclare longer frozen-model monitoring checks and obtain independent acquisitions. See load_experiment_results.md.


## D014 — Full reserved monitoring with frozen A/C models
Extend only the reserved final temporal blocks; retain the saved load_only_experiment_001 bank, global thresholds, smoothing and persistence without intra-record resets. Nine records provide 45 extra decision steps each, while 19 are unchanged. Both EWMA arms now alert on 1/17 healthy records; A has two confirmed events and C one, all in Normal_1HP_0%. Both detect all 11 supported faults. Preserve the earlier zero-alert claim only as a short-prefix result. Keep HP modelling deferred and investigate the false-alert intervals before declaring any further method change. Do not tune the frozen detector to erase these observed events. See long_monitoring_protocol.md and long_monitoring_results.md.


## D015 — Diagnose false alerts before changing models
The Normal_1HP_0% investigation preserves all fitted models, thresholds and prior results. Positive score allocations are dominated by torque shape/spectral features, with changing vibration spectral content. Unusual torque excursions are present throughout the recording, including training; raw integrity screens and exact feature reconstruction do not establish sensor/physical causes. Continuous replay of the reserved calibration interval reveals a sustained event in its unused tail (A at 218 s; C at 219 s). Recommend a separately declared continuous-calibration comparison with the existing reference models frozen; do not silently retune, remove torque, exclude this healthy-labelled record or introduce HP models based on this diagnosis. See normal_1hp0_investigation.md.


## D016 — Compare continuous calibration with frozen reference models
Replace only global thresholds in a separately saved candidate: use full reserved healthy calibration intervals, one warm-up, fixed alpha=0.2 and three-window event envelope. Both A/C reference models remain unchanged. EWMA thresholds rise 3.55%/3.13%; sustained healthy check alerts fall to 0/17 for both while 11/11 supported faults remain detected. Raw-score false alerts persist. Treat the outcome as development on exposed acquisitions; preserve the original calibration and do not claim a load-centred advantage or introduce HP models. Freeze the candidate for independent-acquisition confirmation; see continuous_calibration_results.md.


## D017 — Package the frozen candidate and verify offline playback
Release hi_candidate_v1 contains unchanged A/C fitted models and continuous-calibration thresholds; C is default. Enforce the 17-condition evidence boundary without HP-specific model routing. Keep a stateful feature-window monitor with explicit recording lifecycle, fixed warm-up/persistence and fail-fast input checks. Raw resampling remains offline. All 99 tests pass; 2,210 saved predictions and two raw-file reproductions verified. Preserve prior experiments and distinguish full-record demonstration from check-scope reproduction. Next software step is dashboard integration; independent-acquisition confirmation remains scientifically required. See candidate_playback.md.


## D018 — Simulate operator zones without automatic stopping
User-directed policy: no HP-specific model, no automatic motor stop; a critical alarm requests human inspection. Map the calibrated boundary to operator HI 60 under a separately versioned mapping. Test warning/critical entry at 60/25, recovery at 65/30 versus no hysteresis, and critical durations of 2/3/5 elapsed seconds. Keep confirmation distinct from hysteretic display recovery and latch requests until valid recovery plus acknowledgement. C generates critical requests for 10/11 faults and 0/17 healthy records for all durations; all faults reach warning, and two healthy records warn. Do not optimize the critical cutoff to the missed-critical example or claim one duration is validated. Preserve prior release/results; see operator_alarm_results.md.
