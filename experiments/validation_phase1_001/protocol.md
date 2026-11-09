# Frozen HI validation, phase 1

Prepared before this phase's scoring. Target: <project>, release hi_candidate_v1, operator_zones_v1. This does not validate the separate <other-local-workspace>/md_hi model.

## Fixed choices

- Primary: load-centred C, EWMA alpha 0.2, existing continuous-calibration threshold, 2-second windows / 1-second hop, first ten windows ineligible. No HP-specific model.
- Operator HI = 100 / (1 + (2/3)(MD_EWMA/q)^2). Normal >=60, warning <60, critical <25. Hysteresis clears warning at 65 and critical at 30. A request needs 3 elapsed seconds strictly below 25, i.e. four consecutive one-second readings. Human response only; no motor stop.
- Prespecified comparisons: pooled A, hysteresis off/on, confirmation 2/3/5 seconds. Report every comparison; do not select or tune against these results.
- Each recording starts a fresh monitor and alarm session. No simulated acknowledgements. A latched request can occur at most once per recording; request counts are not repeated alarm-event rates.

## Evidence and checks

1. Verify all 41 copied raw file hashes against the copy receipt; detect exact-content duplicates. Verify 32 feature artifacts, feature schema, finite values, window continuity, input lineage, frozen code, model and historical outputs. Do not re-extract features in this phase; a matching hash establishes integrity, not the scientific correctness of feature extraction.
2. Audit admission and condition routing. Use only the 28 supported complete recordings for scoring. Preserve the nine quality exclusions and four unsupported complete records. Check that unsupported conditions are rejected.
3. Independently calculate MD using the covariance linear system rather than the production Cholesky scoring helper; independently reconstruct EWMA and the HI formula. Compare every scored window with the frozen production monitor.
4. Independently reconstruct alarm state, duration and latch behavior; compare with the production implementation and saved evaluation. Test explicit boundary, elapsed-time, missing/gapped-data, warm-up and acknowledgement scenarios.
5. Reproduce all 336 saved record-level operator-policy results on the original reserved check intervals, including the original reset at each check interval. Compare saved continuous-calibration MD/EWMA and saved operator scores/states/events.
6. Replay the full supported recordings without resetting at the former check boundary. Report full-record results and check-segment results with carried state separately. Attribute each scored window to historical fit/calibration/check/guard intervals, and distinguish healthy fitting/calibration data from previously exposed fault data.
7. Report record counts and decision-step exposure by load, HP (reporting only), speed profile and condition. Do not treat overlapping windows as independent trials, infer detection delay from unknown fault onset, or infer generalisation from healthy fitting/calibration data. Do not attach nominal independent-binomial confidence intervals to these unknown acquisition groups.

## Interpretation and next phase

This is reproducibility and exposed-data robustness validation, not untouched test-set validation. Prior check data influenced development decisions. Full-record replay adds coverage of earlier periods and startup but introduces no independent recordings. Zero requests in limited healthy data does not establish a deployment false-alarm rate.

Record the eligibility of additional local data pools. A pool without the frozen model's synchronized vibration, torque and three current channels, sampling metadata, and supported load/capacity/profile labels cannot be evaluated by silently omitting or inventing features. Matching filename/size is only a duplicate candidate until hashing confirms it.

Before prospective validation, register truly new acquisition IDs and physical motor IDs, freeze this release/policy, hash and screen for duplicates, and keep complete acquisitions outside fitting/calibration. Collect sustained healthy operation in each claimed condition plus faults with known onset/severity where feasible. Evaluate unsupported conditions as unsupported; do not expand claims by testing faults without healthy reference coverage. Dynamic load transitions, sensor drift/missing data, live preprocessing causality and processing latency need separate validation. Agree operational false-request and missed-fault tolerances before calling the system deployment-ready; this phase does not invent acceptance targets.
