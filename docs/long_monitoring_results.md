# Longer monitoring with frozen models — 6 November 2026

Extending the reserved monitoring periods exposed healthy false alerts that the shorter check missed. Both smoothed models now alert on one of 17 healthy recordings. The pooled reference produces two confirmed false-alert events; the load-centred reference produces one. Both continue to detect all 11 supported fault recordings. One fewer event in one recording is insufficient to establish a general advantage for load centring.

Evidence: outputs/runs/long_monitoring_001. Protocol: long_monitoring_protocol.md. Validation: outputs/runs/long_monitoring_validation_001/validation.json and pytest.xml.

## What was frozen

The exact bank from load_only_experiment_001 was loaded, with unchanged feature selection, centres, scales, covariance, thresholds, HI mapping, EWMA alpha 0.2 and three-window persistence. Arm A uses a pooled healthy reference and global threshold; arm C uses load-specific centres, one shared residual covariance and global threshold. HP-specific modelling remains deferred.

The EWMA thresholds remain A 5.6221133802141985 and C 5.686401400088516. There was no fitting or calibration in this experiment. The first 25 windows reproduce the preceding experiment. EWMA and persistence continue through that endpoint without reset, and reset only between recordings.

## How much longer?

The 300-second source recordings now use all 70 feature windows inside their reserved interval [227, 298] seconds, rather than the first 25. After ten warm-up windows, that is 60 one-second decision steps instead of 15. The 120-second recordings have only 25 windows inside [92, 118] seconds, so their checks cannot be extended under this split.

Only nine records extend: seven healthy and two fault. The remaining 19 records are unchanged. New exposure totals 405 one-second decision steps: 315 healthy and 90 fault. Total decision exposure per model is 570 seconds healthy and 255 seconds fault, summed across separate recordings. This is not one continuous 13.75-minute run. A two-second raw feature window advances each second; exposure is counted by decision steps, not by summing overlapping window lengths.

## Primary smoothed results

| Measure | A: shared reference | C: load-centred reference |
|---|---:|---:|
| Healthy recordings with sustained alerts, old short check | 0/17 | 0/17 |
| Healthy recordings with sustained alerts, full reserved interval | 1/17 | 1/17 |
| Healthy confirmed events in full interval | 2 | 1 |
| Fault recordings with sustained alerts | 11/11 | 11/11 |
| Healthy above-threshold steps | 16/570 (2.81%) | 15/570 (2.63%) |
| Healthy persistent-alarm steps | 2/570 (0.35%) | 1/570 (0.18%) |

A confirmed event starts at the third consecutive eligible threshold crossing. Each observed healthy event consists of exactly three crossings, leaving one decision step with the persistent alarm active before it clears. There is no operational latch or hysteresis in this rule. The event count should not be confused with the number of above-threshold windows.

On the newly added portion alone, both models alert on 1/7 healthy records and remain in alarm on both extended fault records. Those two fault events began in the old prefix; there are zero newly confirmed fault events in the extension. Across all full intervals, every fault decision exceeds threshold, with 233/255 persistent-alarm steps after the two confirmation steps per recording. Fault onset is unknown, so this is not an estimate of detection latency.

## Which healthy recording triggered?

The EWMA false-alert recording is invariant_speed/Normal_1HP_0%.mat for both models.

| Model | Consecutive above-threshold decision times, seconds from record start | Confirmation time | Persistent-alarm steps |
|---|---|---:|---:|
| A | 261, 262, 263 | 263 s | 1 |
| A | 293, 294, 295 | 295 s | 1 |
| C | 261, 262, 263 | 263 s | 1 |

Times refer to each feature window's end, when its decision becomes available. All three events clear on the next decision and are not right-censored. C crosses threshold at 293 and 294 seconds but drops below it at 295, so that excursion does not satisfy persistence. At 295 seconds A is only about 0.15% above its threshold; this illustrates how the event difference depends on a boundary crossing rather than proving broad model superiority.

The 0% group accounts for all smoothed false-alert events: 1/6 healthy records. Neither model produces a sustained smoothed alert among the seven 30% or four 60% healthy records. Fault detections by load remain 3/3, 5/5 and 3/3, respectively. Only two fault recordings, both at 30% load, receive longer exposure.

The raw-score diagnostic gives A 2/17 healthy alerted records and C 1/17, with 11/11 fault detections for both. A adds a three-window raw event in Normal_1HP_60%.mat at decision times 280–282 s. Both retain the earlier four-window raw event in Normal_3HP_60%_52Hz.mat at 110–113 s. These raw outcomes do not replace the predeclared primary EWMA comparison.

## Interpretation and next step

The prior statement of zero sustained healthy alerts applies to the short prefix only. The frozen detector is sensitive to additional normal variation later in the recording. Longer duration gives more opportunities for threshold crossings, and thresholds calibrated using short episodes do not guarantee a longer-period false-alert rate.

Keep C as a load-aware candidate and A as its control. The small observed event difference does not justify selecting a final model or introducing HP-specific models. It also does not justify raising thresholds or increasing persistence after seeing these outcomes and describing the result as untouched validation.

Next, investigate the existing false-alert intervals in Normal_1HP_0%.mat: identify the contributing features and channels, compare their fit/calibration/check behaviour, and inspect the corresponding raw signals for transient variation or acquisition artifacts. This diagnosis should preserve the frozen results and distinguish plausible explanations from demonstrated causes. Any alternative alarm rule or reference revision needs its own declared development comparison.

The entire reserved check interval is now used. Longer untouched monitoring requires additional recordings or an explicitly different evaluation design; concatenating unrelated records, reusing training/calibration periods as test data, or replaying a recording does not create independent evidence. New acquisitions should cover repeated healthy runs, fault examples, known load and acquisition/motor identity. Load transitions remain untested.

## Verification and limitations

All 90 tests passed, including reserved-interval boundaries, incomplete intervals, event counting, right-censoring, persistence across the old endpoint and zero-extension handling. Separate covariance-solve arithmetic reproduced all 2,210 prediction rows, 336 record/segment metrics and 50 event rows across both models and both streams. Summary denominators and event times were checked. The earlier 25-window predictions match, the source bank hash is unchanged, and V1/V2/load-only run files remain unchanged. Manual verifier: tests/verify_long_monitoring_artifacts.py.

This is additional development on previously exposed acquisitions. Healthy fitting, calibration and checks use separated raw-time blocks of the same recordings, so acquisition-specific information remains shared. Nine quality exclusions and four unsupported fault records remain outside the comparison. No independent-machine, deployment false-alarm rate, rare-event guarantee, hours-long monitoring, subtle-fault or load-transition claim follows. Review status: share with these scope caveats.

