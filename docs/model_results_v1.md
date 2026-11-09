# First Python health-index results

The Python model, empirical calibration and causal score smoothing are implemented and evaluated under the predeclared grouped_v1 protocol. The first fusion model detected faults in this subset but produced substantial alarms on normal-labelled recordings. It is not validated for operational use.

## Scope and verification

Five fixed capacity/load-group rounds evaluated 27 recordings once each (14 normal, 13 fault-labelled). Five other complete recordings remain exploratory and were not scored in this primary evaluation. The software passed 72 tests; all 23,265 saved prediction rows across five model variants were reproduced from their saved model states. There are 25 fold/variant models, not one deployment model.

Feature selection, scaling and covariance used only healthy fitting records. Separate healthy calibration records set a weighted empirical 99th-percentile threshold for each raw/smoothed model. All recordings have equal weight within their role. No threshold or parameter was changed after viewing these results.

## Fixed comparisons

Window alarm percentages below are averages of each recording's alarm fraction. Each recording contributes equally; these are not percentages of independent experiments. A recording alert requires three consecutive above-threshold windows. All fractions/counts refer to the same corresponding calibrated threshold.

| Variant | Score | Healthy window alarm fraction | Fault window alarm fraction | Healthy records with alert | Fault records with alert |
|---|---|---:|---:|---:|---:|
| current | ewma | 9.7% | 58.9% | 2/14 | 9/13 |
| current | raw | 7.8% | 46.5% | 1/14 | 7/13 |
| diagonal | ewma | 27.2% | 96.3% | 5/14 | 13/13 |
| diagonal | raw | 16.3% | 93.3% | 4/14 | 13/13 |
| fusion | ewma | 33.7% | 100.0% | 7/14 | 13/13 |
| fusion | raw | 17.4% | 99.4% | 3/14 | 13/13 |
| torque | ewma | 24.4% | 93.5% | 4/14 | 13/13 |
| torque | raw | 22.6% | 92.2% | 4/14 | 12/13 |
| vibration | ewma | 24.1% | 50.5% | 6/14 | 8/13 |
| vibration | raw | 11.4% | 45.4% | 4/14 | 8/13 |

## What the results establish

- Raw fusion raised sustained alerts in all 13 fault records and 3 of 14 normal records. Its mean normal-record window alarm fraction was 17.4%, well above the nominal 1% calibration target.
- EWMA fusion also alerted on all 13 fault records, but alerted on 7 of 14 normal records; its mean normal-record window alarm fraction rose to 33.7%. Smoothing did not improve false alarms in this test. Its threshold was calibrated separately, so this is not a comparison using the wrong raw threshold.
- Current-only EWMA had a lower mean healthy alarm fraction (9.7%), with alerts on 2 of 14 normal and 9 of 13 fault records. This is an observed tradeoff, not evidence to select a winning model using the evaluation set.
- The diagonal comparison also detected all 13 fault records with EWMA and had a lower healthy alarm fraction than fusion. These results do not establish that modelling covariance improves on a simpler standardized-distance baseline.

## Where fusion alarms occurred

| Normal recording | Raw alarm fraction | EWMA alarm fraction | Raw sustained alert | EWMA sustained alert |
|---|---:|---:|---|---|
| Normal_3HP_0%_52Hz | 0.0% | 93.3% | no | yes |
| Normal_3HP_0%_58Hz | 11.8% | 98.3% | no | yes |
| Normal_3HP_30% | 63.5% | 81.6% | yes | yes |
| Normal_3HP_30%_52Hz | 0.0% | 0.0% | no | no |
| Normal_3HP_30%_58Hz | 0.0% | 0.0% | no | no |
| Normal_3HP_60% | 0.0% | 0.0% | no | no |
| Normal_3HP_60%_52Hz | 0.0% | 0.0% | no | no |
| Normal_3HP_60%_58Hz | 0.0% | 0.0% | no | no |
| Normal_5HP_0% | 100.0% | 100.0% | yes | yes |
| Normal_5HP_0%_52Hz | 37.0% | 57.1% | no | yes |
| Normal_5HP_0%_58Hz | 29.4% | 38.7% | yes | yes |
| Normal_5HP_30% | 0.0% | 3.3% | no | yes |
| Normal_5HP_30%_52Hz | 0.0% | 0.0% | no | no |
| Normal_5HP_30%_58Hz | 2.5% | 0.0% | no | no |

The strongest healthy alarm fractions cluster in the withheld 3 HP/0% and 5 HP/0% groups for EWMA, with an additional invariant-speed 3 HP/30% case. This pattern is consistent with operating-condition and/or sensor-distribution shift, but it does not establish the cause. Calibration on a different group does not guarantee a 1% false-alarm rate on the held-out group.

Post-evaluation descriptive diagnostics list each normal record's three largest median absolute standardized feature deviations in outputs/runs/model_validation_001/healthy_marginal_diagnostics.csv. These are relative to that fold's healthy fitting statistics. They are not causal feature attributions, and they were not used to change this model.

## Fitted state and score meaning

| Round | Fusion retained features | Raw threshold | EWMA threshold |
|---|---:|---:|---:|
| 1 | 38 | 10.6459 | 8.03733 |
| 2 | 33 | 15.4837 | 15.3472 |
| 3 | 39 | 20.6607 | 17.129 |
| 4 | 35 | 21.2479 | 20.7203 |
| 5 | 37 | 11.3204 | 10.0026 |

Raw distance remains unbounded. The displayed HI is 100/(1+(distance/threshold)^2), with 50 at the warning boundary. It describes deviation from a learned reference; it is not remaining useful life, percentage physical health, wear or fault probability. The score is fold-calibrated, so equal values from different folds do not establish equal damage severity.

EWMA uses alpha=0.2, resets at each recording and needs 11 one-second updates to reach 90% of a sustained step after initialization. The raw feature window adds two seconds of acquisition, and upstream resampling is still offline. First-alert timestamps are from recording start; no verified fault-onset timestamps exist.

## Limits and next decisions

Only five operating groups and unknown physical motor/run identities are represented. Overlapping windows are correlated, and recordings were used in earlier project work. No independent-window confidence intervals or unseen-machine generalization claim is made. Observed per-record min/max variability is retained in comparison.csv; uncertainty on new machines requires new independent data.

Preserve this first run as an evaluated baseline. Next, investigate operating-condition effects and calibration scope using development data. Predeclare any revision and treat this dataset as exposed development data for that revision; obtain independent confirmation before claiming improved generalization. Do not adjust this run's thresholds until its false alarms disappear.

A dashboard can display these research scores and their limitations, but should not present this version as a validated machine-protection alarm.

## Evidence

- Numerical protocol: docs/model_protocol_v1.md and the immutable model_protocol.md snapshot in the run.
- Configuration/code/input provenance: outputs/runs/model_baseline_v1/pre_evaluation.json and run.json.
- Models: outputs/runs/model_baseline_v1/models_fold_1.json through models_fold_5.json.
- Window scores: predictions.csv; individual results: record_metrics.csv.
- Comparisons: comparison.csv, fold_comparison.csv and condition_comparison.csv.
- Verification: outputs/runs/model_validation_001/validation.json and tests.xml.
