# Continuous calibration comparison — 7 November 2026

Continuous healthy calibration removed the sustained EWMA false alerts observed in the full reserved check intervals, while retaining all 11 supported fault-record detections. This holds for both the pooled reference A and load-centred reference C. It is a favourable development comparison on previously examined recordings, not independent validation.

Run: outputs/runs/continuous_calibration_001.
Protocol: continuous_calibration_protocol.md, frozen and copied into the run before calibration.
Verification: outputs/runs/continuous_calibration_validation_001/validation.json and pytest.xml.

## What changed, and what stayed frozen

Only global thresholds changed. The exact fitted source bank from load_only_experiment_001 remains unchanged: selected features, scaling, healthy means, covariance and load-specific centres. EWMA alpha remains 0.2, with ten warm-up windows and three consecutive strict threshold crossings required for a sustained alert. HP-specific modelling remains deferred.

The new calibration uses each healthy record's full reserved interval continuously, with one warm-up and no short-episode resets or discarded tail. Seven 300-second records contribute 70 windows/60 decisions each; ten 120-second records contribute 25/15. This is 740 windows and 570 decision steps from 17 recordings, compared with 600 windows and 360 decisions from the old 24 short episodes.

The fixed maximum three-consecutive-window event statistic was computed on healthy calibration scores only. New thresholds and their source-bank hash were saved before check evaluation. No threshold multiplier, tuning search or fault/check-based exclusion was applied.

| Model | Stream | Original threshold | Continuous-calibration threshold | Change |
|---|---|---:|---:|---:|
| A, pooled reference | EWMA | 5.622113 | 5.821525 | +3.55% |
| C, load-centred reference | EWMA | 5.686401 | 5.864609 | +3.13% |
| A | Raw | 5.699750 | 5.701655 | +0.033% |
| C | Raw | 5.941378 | 5.941378 | Unchanged |

Normal_1HP_0% supplies both new EWMA thresholds. The raw threshold suppliers are Normal_5HP_0% for A and Normal_5HP_0%_58Hz for C. Zero sustained events when replaying calibration are expected by construction and are not validation results.

## Paired results on identical full check intervals

Every reference/calibration combination uses the same 28 supported records: 17 healthy and 11 fault. Check exposure remains 570 healthy and 255 fault decision seconds, summed across separate recordings. Nine recordings provide 60 decisions each and 19 provide 15 each; this is not a single uninterrupted monitoring run.

| Reference and calibration | Healthy records with sustained EWMA alerts | Healthy EWMA events | Fault records detected |
|---|---:|---:|---:|
| A, original | 1/17 | 2 | 11/11 |
| A, continuous | 0/17 | 0 | 11/11 |
| C, original | 1/17 | 1 | 11/11 |
| C, continuous | 0/17 | 0 | 11/11 |

The former alerts in Normal_1HP_0% at 263 s (A and C) and 295 s (A only) no longer satisfy three consecutive crossings. Isolated crossings remain: A has 8/570 healthy decision steps above its new EWMA threshold (1.40%), and C has 7/570 (1.23%). Neither has any persistent-alarm steps. Zero sustained alerts must not be described as zero anomalous windows.

Every one of the 255 fault decision steps remains above the corresponding EWMA threshold. Persistent-alarm occupancy is 233/255 because each recording needs the first two above-threshold decisions before confirmation. First alert timing is unchanged for all supported faults. This is monitoring-relative timing, not latency from physical fault onset, which is unknown.

By load, both candidates have healthy sustained alerts 0/6 at 0%, 0/7 at 30%, and 0/4 at 60%. Fault detections are 3/3, 5/5 and 3/3, respectively. Only two fault recordings at 30% provide the longer exposure. No unsupported condition was added.

The raw diagnostic does not show the same improvement: A retains 2/17 healthy alerted records and C retains 1/17, with 11/11 fault detections for both. The favourable result belongs to continuous calibration combined with EWMA and persistence.

## Interpretation

The investigation identified healthy excursions in a calibration tail excluded by short-episode packing. Including that tail and maintaining continuous state gives a somewhat higher healthy event envelope. The check scores themselves are identical: the reduction in alerts comes from the threshold change, not from cleaning the raw signal or refitting the model.

The HI formula is unchanged, but its numerical values change with the normalization threshold. Preserve the calibration version alongside any saved HI or dashboard result; different threshold versions should not be plotted as if their scale were identical.

A and C remain tied on recording-level false alerts and detections. One fewer isolated crossing for C is not evidence of a general load-centring advantage. Retain C as the load-aware candidate and A as the simpler control. The current result provides no reason to add HP-specific model banks.

## Validation and remaining limits

All 94 tests passed, including calibration-tail coverage, check-data/HP-label invariance, no in-memory bank mutation, rejection of fault calibration records, and preservation of distances when applying thresholds. Independent covariance-solve arithmetic verified 34 calibration record/reference pairs, all 4,420 saved prediction rows, 672 record/segment metrics and 97 event rows across original/new policies and raw/EWMA streams. The prior longer-monitoring results reproduce. New calibration artifacts were frozen before checks; the old bank and earlier run files remain hash-identical.

Manual verifier: tests/verify_continuous_calibration_artifacts.py. Candidate thresholds and their provenance are stored in calibration.json; the original bank is not overwritten. The comparison is an offline experiment, not a dashboard/deployment change.

These records and their earlier outcomes informed the decision to study continuous calibration. The result is therefore exposed-data development even though threshold values come only from reserved healthy calibration data. Fit, calibration and checks still share acquisitions. Unknown motor/run identity, short monitoring duration, absent condition combinations, nine quality exclusions and four unsupported complete faults remain limitations. No probability guarantee, long-term false-alert rate, weak-fault sensitivity or load-transition capability is established. The maximum-envelope threshold is influenced by one unusual healthy-labelled recording, whose sensor/physical interpretation remains unresolved.

## Next step

Freeze this candidate and retain the original calibration as the comparison. Seek additional complete, independently identified healthy and fault recordings covering repeated runs and supported loads before claiming generalization. If no new acquisitions are available, any further resplitting or robustness study must be declared as development on exposed data, with no implied fresh validation.

Do not raise thresholds further or alter persistence merely to optimize these same results. Investigate sensor provenance and repeated 1 HP/0% behaviour when that evidence becomes available. A later playback/dashboard integration should name the candidate calibration and display supported-condition limits, rather than implying independent validation.

Review status: share with the stated development and coverage caveats.

