# Frozen candidate and offline playback verification — 7 November 2026

Package both fitted references from load_only_experiment_001 with the frozen global thresholds from continuous_calibration_001. Candidate C (load-centred, shared covariance) is the default; A is the pooled-reference comparison. No retraining or threshold recalibration. Copy the exact preprocessing/feature/monitoring contracts, 17-condition evidence boundary and source hashes into a new release. Preserve all earlier outputs.

The playback monitor consumes one complete feature window per update. Use two-second windows at one-second hop, initialize EWMA from the first score, suppress alarms for the first ten windows, and require three consecutive strict threshold crossings. Preserve smoothing/persistence across calls. Reject gaps, duplicate/out-of-order windows, different recording IDs, incorrect schemas, nonfinite inputs and unsupported conditions without silently resetting or inventing values. New recording sessions require a new monitor instance.

HP is metadata used to enforce the inherited evidence boundary, not to select fitted models or thresholds. The declared load selects the reference centre in C. Live load changes are not supported. HI is the same normalized deviation score, with 50 at its threshold, not remaining-life or physical-health percentage.

Raw playback is offline: decode and validate native channels, resample current at 32/125 with the existing Kaiser/line rule, extract unchanged candidate_v1 features, then feed them sequentially to the monitor. This does not implement live streaming FIR state or hardware timing. The check scope resets at the reserved check start and must reproduce saved results. Full-record playback starts at the beginning and is a demonstration containing fit/calibration data, not an evaluation; its smoothing history is intentionally different.

Verification:
- Unit tests cover stateful/batch parity, warm-up, persistence, rejection without state advancement, recording reset, unsupported conditions and bundle/schema integrity.
- Verify stateful playback of both A/C on all 28 supported saved-feature check intervals against continuous_calibration_001.
- Freshly re-extract raw Normal_1HP_0% and Coil40%_3HP_30% using the packaged pipeline; compare every extracted feature to candidate_features_v1 and every check-scope HI/alarm to the saved candidate C experiment.
- Verify release/source hashes and preservation of prior experiments. Keep software reproducibility separate from independent scientific validation.

No dashboard integration or deployment-performance claim follows from this milestone.

