# Investigation of the first Python model's healthy alarms

The clearest issue is transfer between different healthy operating conditions, compounded by calibration of the smoothed score. No missing-channel or numerical-scoring failure was found in the checks performed. Physical sensor effects and true machine condition remain unresolved; source Normal labels are treated as the available reference.

This is a post-evaluation investigation of model_baseline_v1. No model was refitted, no threshold replaced, no feature removed from the evaluated model, and no split changed. All original run-file hashes remained unchanged.

## 1. What smoothing actually changed

The investigation scored the same 14 held-out normal recordings with the saved fusion models. The middle row below is a diagnostic counterfactual using the original raw threshold with smoothed scores. It is not a recommended or newly validated alarm configuration.

| Scores and threshold | Mean healthy-record window alarm fraction | Records with a three-window sustained alert |
|---|---:|---:|
| Raw scores, original raw threshold | 17.4% | 3/14 |
| EWMA scores, original raw threshold (diagnostic only) | 14.5% | 4/14 |
| EWMA scores, original separately calibrated EWMA threshold | 33.7% | 7/14 |

Holding the threshold fixed, smoothing reduced alarm-window occupancy by 2.94 percentage points. Changing from the raw to the EWMA threshold after smoothing added 19.23 percentage points, producing the net 16.29-point increase. This sequential decomposition is exact for the saved scores; it does not imply that thresholds should simply be swapped.

Smoothing still increased the count of records with consecutive alarms from three to four at the fixed raw threshold. Therefore it is not harmless for event-level decisions: fewer isolated exceedances can coexist with more persistent runs.

In round 1, the raw threshold was 10.6459 and the EWMA threshold was 8.03733, about 24.5% lower. Normal_3HP_0%_52Hz had a smoothed median distance of 8.68482; Normal_3HP_0%_58Hz had 9.04280. Both sit above the smoothed threshold even though their smoothed values never crossed the raw threshold. Their EWMA alarm fractions became 93.3% and 98.3%.

The calibration 3 HP/30% recordings had lower median distances than these withheld 3 HP/0% recordings. A threshold correctly calculated for the former is not guaranteed to transfer to the latter.

## 2. The split tests operating-condition transfer as well as faults

The fixed split deliberately withholds complete capacity/load groups. This is a harder and different question from detecting a fault at an already represented operating condition.

- In round 4, the fitting population contains only 3 HP recordings. The calibration population is 5 HP at 30% load, and evaluation is 5 HP at 0% load. A single healthy ellipsoid learned from 3 HP behaviour is therefore being asked to transfer across capacity and load.
- In round 2, the fitting population contains no invariant-speed 3 HP healthy recording. The invariant-speed Normal_3HP_30% case has substantial alarms, while its variable-speed 52 Hz and 58 Hz counterparts have none.
- In round 1, the withheld group is 3 HP/0% while the calibration group is 3 HP/30%.

These are verified coverage facts, not evidence that any particular normal record is damaged. The current experiment cannot cleanly attribute an alarm to a fault rather than an unfamiliar healthy operating pattern.

Capacity/load grouping also does not identify acquisition sessions or physical motors. Constant- versus variable-speed acquisitions used different vibration sensors according to the dataset description. The available subset cannot separate load, capacity, sensor and acquisition effects causally.

## 3. Which measurements drive the distances

The analysis examined the saved standardized features and covariance without changing them. An exact signed decomposition z[j] * (C_inverse*z)[j] sums to squared Mahalanobis distance; channel totals can be negative because cross-feature terms are shared. A separate nonnegative conditional reduction measures how much squared distance falls if one feature is mathematically marginalized with all remaining model parameters fixed. These reductions are not additive and are not causal importance measures.

Examples:

| Normal recording | Diagnostic feature | Fitting reference | Recording median | Interpretation |
|---|---|---:|---:|---|
| Normal_5HP_0% | R-phase current power fraction, 200–1000 Hz | Mean 0.00811% of positive-frequency power | 0.06021% | About +6.53 fitting standard deviations; strongest conditional contributor in this record |
| Normal_3HP_30% | R-phase current AC RMS | Mean 4.736 stored units | 3.046 stored units | About -2.74 fitting standard deviations; a decrease can also raise MD |
| Normal_5HP_0%_58Hz | Vibration Pearson kurtosis | Mean 2.874 | 2.515 | About -3.49 fitting standard deviations; also a joint-feature discrepancy |

For Normal_5HP_0%, the fitted covariance makes mean squared distance about 4.55 times the squared standardized Euclidean norm on the same retained features. For Normal_3HP_30%, the factor is about 3.51. This is meaningful sensitivity to learned feature relationships, not proof of unstable matrix arithmetic: regularized condition numbers across the five models are approximately 87–118, and the exact decomposition checks passed.

A joint pattern can be unusual even when individual features are only moderately different. Conversely, unusual does not necessarily mean damaged. The HI remains an anomaly score, not a monotonic physical damage measurement.

The feature diagnostics do not justify automatically deleting these features: the same measurements may carry genuine fault information. Any reduction or invariance rule needs development-only assessment and a new declared model version.

## 4. Calibration is supported by very few independent recordings

There are only two or three calibration recordings in each round. Recomputing a threshold after omitting one calibration recording changed it by as much as 32.1% in this diagnostic.

For example, omitting invariant-speed Normal_3HP_60% from round 2 changes the EWMA threshold from 15.3472 to 10.4205. Omitting Normal_3HP_30%_58Hz from round 1 changes the raw threshold from 10.6459 to 7.29861. These replacements were not deployed.

The current 99th-percentile rule targets a weighted window-score distribution. It does not promise a 1% probability of a recording ever producing a three-window alert. Window overlap and EWMA dependence further distinguish those objectives. Event-level alarm calibration requires an explicit event/monitoring-duration target and enough independent healthy episodes.

## 5. Data-quality and boundary checks

Three raw-score false-alert cases and three controls were screened at native sampling rates:

| False-alert case | Control with same capacity and speed profile |
|---|---|
| Normal_3HP_30% | Normal_3HP_60% |
| Normal_5HP_0% | Normal_5HP_30% |
| Normal_5HP_0%_58Hz | Normal_5HP_30%_58Hz |

Controls have different loads; these comparisons are not controlled physical experiments.

All 30 native channels had finite samples over their expected intervals and valid NaN-only storage padding. The longest exact constant run across these checks was 0.00018 seconds. The largest fraction of samples equal to the observed channel minimum or maximum was approximately 0.000108%. These checks found no obvious sustained flat signal or repeated-extrema problem. ADC rails, sensor calibration and actual physical health are unknown, so subtle sensor faults or clipping cannot be ruled out categorically.

Excluding the first and last 12 windows left the sustained-alert counts unchanged: 3/14 for raw scores and 7/14 for EWMA. Mean healthy alarm-window fractions were approximately 17.3% and 33.6%, close to the original 17.4% and 33.7%. Startup/endpoint behaviour alone therefore does not explain the observed alarms. This is a diagnostic crop using the original thresholds, not a new evaluation protocol.

The earlier source audit already established the missing-vibration exclusions. No excluded recording was introduced into this investigation's fitting, calibration or evaluation.

## 6. What is established and what is still uncertain

**Established:** operating groups differ across roles; the smoothed threshold change accounts for the large increase in window alarm occupancy; covariance emphasizes particular joint-feature discrepancies; the calibration thresholds depend strongly on a few records; the alerts persist away from recording boundaries; inspected raw records passed the stated structural screens.

**Not established:** a single physical cause, mislabelled healthy data, faulty sensors, an optimal smoothing setting, or a correction that preserves fault detection on new data. Unknown acquisition identity, sensor scaling, hardware timing and normal-population coverage remain limitations.

## 7. Recommended next development step

1. Define the supported operating envelope explicitly. Treat the original grouped_v1 result as a transfer stress test; do not describe its alarms as evidence of damage in an unfamiliar operating state. A future coverage indicator should use justified operating metadata and report unsupported states separately, with abstention/coverage measured.
2. Investigate capacity-specific or operating-condition-normalized healthy references using development data. Capacity is known equipment metadata; online load/speed information must have an explicit source. Do not assume filename labels are available during deployment.
3. Review feature stability across healthy operating regimes, especially small spectral fractions and strongly coupled shape/amplitude features. Compare a compact stable set and simpler covariance models under a declared development protocol. Do not select features using the held-out fault outcomes.
4. Specify whether the alarm objective is window exceedance or a persistent event over a defined duration. Calibrate the exact score/smoothing/persistence chain using representative, independently acquired healthy recordings.
5. Seek additional healthy acquisitions in the target operating conditions and independent fault confirmation. This subset has many windows but few independent records. With the current exposed data, any next revision is a development iteration, not fresh external validation.

No revision is implemented by this investigation. The original models, thresholds and results remain the reference.

## Evidence and reproduction

Evidence lives in outputs/runs/false_alarm_investigation_v1:
- healthy_scores_by_role.csv: all 70 healthy record/round combinations with explicit role.
- smoothing_decomposition.csv: threshold/smoothing comparison for 14 held-out normal records.
- calibration_record_details.csv and calibration_leave_one_record_out.csv.
- healthy_feature_diagnostics.csv, healthy_channel_diagnostics.csv and healthy_covariance_diagnostics.csv.
- targeted_raw_quality.csv and targeted_raw_quality_summary.json.
- analysis_plan.json, summary.json and investigation_manifest.json.

The two included Python scripts accept --project and --output. To reproduce, first run investigate_false_alarms.py with a new output folder; then run screen_false_alarm_raw.py pointing at that folder. Both use the project's pinned Python environment. Exact algebraic identities, input hash agreement and unchanged original run hashes were checked. No independent-window significance tests or generalization claims are made.
