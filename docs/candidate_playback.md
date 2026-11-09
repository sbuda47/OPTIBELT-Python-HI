# Packaged Python HI and verified playback — 7 November 2026

The Python-only candidate is packaged as hi_candidate_v1 and can process an admitted raw MAT recording through native-channel validation, current resampling, feature extraction, Mahalanobis distance, causal feature-window smoothing, bounded HI and persistent alarms. This milestone adds reproducible software packaging and playback; it does not add independent scientific validation.

Release: outputs/releases/hi_candidate_v1.
Verification: outputs/runs/candidate_playback_validation_001/validation.json and pytest.xml.
Protocol: candidate_playback_protocol.md.

## Frozen candidate

The bundle contains both references, with C (load-specific healthy centres and shared covariance) as default and A (pooled reference) as the comparison. Their fitted models exactly match load_only_experiment_001, and their thresholds exactly match continuous_calibration_001. No training, recalibration, cleaning change or new feature selection occurred.

| Reference | Raw threshold | EWMA threshold |
|---|---:|---:|
| A | 5.701655480014806 | 5.8215248790603775 |
| C | 5.941378031107631 | 5.8646090304501115 |

The release includes the exact 60-column candidate_v1 schema, preprocessing contract, selected fitted feature indices, centres, covariance, monitoring settings, 17 supported conditions and source hashes. The manifest checks bundle integrity and the installed implementation. Those checks detect accidental changes; they are not a cryptographic publisher signature.

HP remains condition metadata used to enforce the existing evidence boundary. It does not select a fitted model or threshold. Load selects the healthy centre in C. Unsupported HP/load/speed combinations are rejected rather than assigned a default model.

## Playback semantics

Native vibration and torque remain at 25.6 kHz. Current is resampled from 100 kHz with the unchanged 32/125 Kaiser/line policy. Offline two-second feature windows advance every second. The Monitor consumes one feature vector at a time and carries EWMA and persistence state across calls.

EWMA alpha is 0.2, initialized from the first distance. The first ten feature windows have status warming_up and cannot raise alarms. After warm-up, status is within_reference, threshold_exceeded, or alert, depending on the smoothed threshold and three-consecutive-window confirmation. The raw stream is retained for diagnosis. These labels describe the detector state, not independently verified machine health.

HI = 100 / (1 + (MD / threshold)^2). Higher means closer to the reference; HI is 50 at the relevant threshold. It is not percentage remaining life or physical health. Both raw and smoothed scores/HI are saved along with the candidate version and thresholds.

The monitor rejects missing/duplicate/out-of-order windows, changed recording IDs, invalid feature schemas and nonfinite values without advancing state. Use a new Monitor instance to reset between recordings. No silent reset or live load-transition behaviour is implemented.

Raw preparation is OFFLINE and loads the full recording. The current resampling filter and its boundary treatment are not a causal live-sensor streaming implementation. This release does not establish latency, memory/power suitability or hardware synchronization.

## Running a check-scope playback

From PowerShell:

~~~powershell
$projectRoot = '<project>'
$env:PYTHONPATH = "$projectRoot\src"
& "$projectRoot\.venv\Scripts\python.exe" -B -m optibelt_hi.playback --project "$projectRoot" --bundle "$projectRoot\outputs\releases\hi_candidate_v1" --recording 'dataset/raw/invariant_speed/Normal_1HP_0%.mat' --name playback_healthy_new_run --reference C --scope check
~~~

Choose a fresh output name every time. The command refuses to overwrite an existing run. A successful run saves predictions.csv, features.npz and a run.json with input/release hashes, processing scope and result counts. Errors are recorded as a failed run instead of silently producing a healthy score. Admission and source hash checks apply before extraction.

Use --reference A for the comparison. Use --scope full only for a full-record demonstration. The default check scope resets at the reserved check start and reproduces the scientific experiment. Full playback starts earlier, includes fitting/calibration data and has a different smoothing history; it must not be reported as a fresh evaluation.

Feature-window integration is available through optibelt_hi.deployment.monitor.Monitor. Load a verified bundle with optibelt_hi.deployment.bundle.load_bundle, construct a session with explicit hp/load/profile/upper metadata and a recording ID, then call push with the exact ordered feature vector, sample boundaries and recording ID. Dashboard code can use this interface without reimplementing the health calculation.

## Completed verification

All 99 tests passed. Tests cover batch/stateful agreement, warm-up, persistent alarms, new-recording reset, invalid-input rejection without state advancement, copied bundle isolation, unsupported conditions, schemas and checksum rejection.

Both references were replayed one window at a time on every full reserved check interval from all 28 supported records. All 2,210 predictions match continuous_calibration_001. The largest observed absolute distance error is approximately 2.3e-13 and HI error 3.6e-14; all alarm flags agree exactly. This verifies consistency with the saved Python experiment, not parity with MATLAB.

Fresh raw-file runs:

| Raw recording | Features re-extracted | Check windows | Sustained smoothed alert |
|---|---:|---:|---|
| Normal_1HP_0%.mat | 299 x 60 | 70 | No |
| Coil40%_3HP_30%.mat | 299 x 60 | 70 | Yes |

All 35,880 feature values across those two recordings reproduced exactly. All 140 fresh raw-check predictions matched the saved candidate C outputs. The healthy check has 60 decision windows and zero persistent-alarm steps; the fault has 60 decisions and 58 persistent-alarm steps, following the two confirmation decisions.

Artifacts: outputs/runs/candidate_playback_healthy_001 and candidate_playback_fault_001. Verifier: tests/verify_candidate_playback.py. The original models, calibration and earlier experimental outputs remain preserved.

## Current scope and next step

The default load-aware candidate remains a research/development model. Its earlier 0/17 healthy sustained alerts and 11/11 fault detections are from exposed, same-acquisition temporal checks with limited operating coverage. Nine quality exclusions and four unsupported complete faults remain. This packaging does not strengthen those scientific claims.

The next software step is Streamlit playback integration using the verified monitor and explicit candidate/coverage labels. The next scientific step is testing frozen predictions on additional independently identified complete acquisitions. HP-specific models remain deferred.

