# Investigation of the Normal_1HP_0% false alerts — 6 November 2026

The observed alerts have a traceable mathematical explanation: an unusually impulsive torque signal gives this healthy-labelled recording a high background distance, vibration spectral content shifts later in the recording, and causal smoothing carries recent excursions across three decision points. There is also a concrete calibration-coverage mismatch: continuous replay of an unused tail of this recording's reserved calibration interval already produces a sustained alert. No fitted model, threshold, signal or completed experiment was changed.

Evidence directory: outputs/runs/normal_1hp0_investigation_001. Source experiment: long_monitoring_001, using the saved load_only_experiment_001 bank. Target: dataset/raw/invariant_speed/Normal_1HP_0%.mat. Controls inspected natively: Normal_1HP_30%.mat and Normal_5HP_0%.mat. Feature comparisons include all 17 complete healthy recordings.

## 1. The main positive score contributions come from torque

At the first alert confirmation (263 seconds), the largest positive allocations to the smoothed score are torque skewness and crest factor, followed by torque/vibration spectral measures. At 295 seconds, torque crest factor and spectral centroid dominate the positive allocations. Both model variants show this pattern.

| At 263 s | A: pooled reference | C: load-centred reference |
|---|---:|---:|
| Smoothed MD | 5.7073 | 5.7148 |
| Frozen threshold | 5.6221 | 5.6864 |
| Signed torque allocation | 5.2445 | 4.9093 |
| Signed vibration allocation | 1.2447 | 1.7511 |
| Signed allocation from all currents together | -0.7818 | -0.9456 |

These signed allocations sum to the actual smoothed distance. They are not percentages of physical damage or independent causal effects. Negative contributions reflect covariance interactions; they do not prove that a sensor is irrelevant. A separate conditional-feature/group calculation also finds the largest channel-level conditional squared-distance term for torque at 263 s. Conditional terms overlap and cannot be added into percentages.

The first event includes especially negative torque skewness (median -0.903 across decision endpoints 261–263 s). The second includes large torque crest factors (median 20.85 across 293–295 s). Both occur within the range already seen in this recording's fit block: skewness -1.261 to 0.023 and crest factor 11.74 to 23.58. The event pattern is not simply a previously unseen single-feature maximum.

Raw distances at the confirmation endpoints are already below their raw thresholds: at 263 s, A is about 5.247 and C about 5.155; at 295 s, A is about 4.686 and C about 4.631. The EWMA retains the effect of preceding higher scores. This is intended smoothing behaviour, not look-ahead or a computation error.

## 2. Impulsive torque is present throughout the target recording

The target's median two-second torque crest factor is 15.95 during fit, 16.11 in the used calibration windows and 16.48 in the later check extension. A crest factor describes the largest centred excursion relative to the window's AC RMS. It can be high for an impulsive or noise-affected low-amplitude signal, not only for a machine fault.

Native one-second screening found samples beyond eight local AC RMS in every one of the target's 300 seconds (5,870 samples out of 7,680,000 torque samples, about 0.0764%). The two selected controls had none under this descriptive rule. Their median two-second fitting crest factors are about 2.93 (1 HP/30%) and 2.90 (5 HP/0%). The eight-RMS rule is a diagnostic count, not an exclusion policy.

Torque spectral centroid in the target is also different: about 5.48 kHz during fit, versus about 111 Hz and 127 Hz in these two controls. The pattern exists before the false-alert intervals, so removing the late alert windows would not resolve the underlying heterogeneity.

This supports inspecting acquisition/sensor behaviour and how low-load torque features are represented. It does not establish sensor failure, incorrect healthy labelling or an HP-dependent physical cause. The controls differ in load or rating, and physical motor/acquisition identity and signal units remain insufficiently established.

## 3. Vibration changes in spectral shape, with nearly stable amplitude

| Target median feature | Fit block | Used calibration windows | Later check extension |
|---|---:|---:|---:|
| Vibration spectral centroid | 7,151 Hz | 7,340 Hz | 7,734 Hz |
| Vibration power fraction, 1–5 kHz | 20.74% | 16.15% | 6.68% |
| Vibration power fraction, 5–12.8 kHz | 78.77% | 83.36% | 92.88% |
| Vibration AC RMS, stored units | 0.47957 | 0.48166 | 0.47965 |
| Torque AC RMS, stored units | 0.14095 | 0.14434 | 0.14202 |

The vibration centroid rises about 8.15% from fit to the late extension; its amplitude stays nearly constant. This is redistribution of measured spectral power, not evidence of a general increase in vibration magnitude. The 5–12.8 kHz fraction is descriptive here; it is excluded from the fitted feature set by the existing redundancy rule.

The target's full late-extension raw-distance median rises from the fit median 4.911 to 5.291 for A, and 4.868 to 5.303 for C. This is consistent with a changed joint feature pattern plus recurring torque excursions; it is not a causal partition of the increase. Warming, changing machine behaviour, sensor response or acquisition effects remain hypotheses, not verified mechanisms.

## 4. The longer monitoring rule was not fully represented during calibration

For a 300-second record, the reserved calibration interval contains 70 two-second feature windows. The declared fixed-episode calibration used two groups of 25 windows:

- Starts 152–176 seconds (raw support through 178 s).
- Starts 181–205 seconds (raw support through 207 s).

Each group discards its first ten decisions for warm-up. Therefore only 30 decision windows contribute to the calibration event statistic. Four start positions between episodes and sixteen in the remaining tail are not in either episode. The unused tail has window starts 206–221 s, ending at 223 s.

Replaying the entire reserved calibration interval continuously, with the unchanged detector, produces an event in the target at 218 s for A and 219 s for C. Both occur in that unused tail. A is persistent at 218–219 s and C at 219 s. No other healthy recording produces a sustained event in this continuous calibration diagnostic.

This is stronger evidence than merely observing later check alarms: relevant healthy variation was already present in the reserved calibration data but outside the fixed complete episodes. The implementation followed its declared protocol; the problem is the coverage and duration of that protocol relative to the longer monitoring task.

The original global thresholds came from Normal_5HP_0%_58Hz, not from the target: 5.6221 for A and 5.6864 for C. No threshold was recomputed in this investigation, and no improved detection/false-alarm result is claimed.

## 5. Raw integrity and reconstruction checks

All five native channels were screened for each of the three records. There were no missing/nonfinite native samples, all storage padding matched the expected NaN layout, and no one-second segment had zero variance. The longest identical-value run across the 15 screened channels was 80 microseconds. Each channel's observed minimum and maximum appeared once; this provides no repeated-rail evidence of clipping, but unknown hardware limits prevent ruling out all sensor artifacts.

All 299 windows x 60 features for the target were re-extracted directly from the raw recording, including the fixed current resampling. All 17,940 saved values reproduced exactly. Source SHA-256 hashes matched admission records before and after screening. The torque and vibration channels are already at the common native rate and are not resampled by this pipeline.

The signed smoothed allocations reconstruct the saved score, and 720 feature allocations and their conditional squared-distance calculations were cross-checked through separate Cholesky/conditional-residual arithmetic. Continuous calibration replay was independently reproduced. V1, V2, load-only and longer-monitoring outputs remain hash-identical.

These checks rule out the specific missingness, padding, flat-segment and reconstruction errors tested. They do not establish physical sensor calibration, machine health, hardware synchrony or label correctness.

## Recommended next controlled experiment

Keep HP modelling deferred. The most directly supported next change is to align healthy calibration with the continuous monitoring policy:

1. Preserve the current fitted A/C reference models and all existing results.
2. Declare a separate experiment that processes the full reserved healthy calibration interval continuously, with one warm-up and no artificial episode resets or discarded tail. Keep smoothing, persistence and the remaining model settings fixed initially.
3. Freeze the resulting thresholds before evaluating and report both healthy events and missed fault detections. These same exposed records can provide development comparisons only; fresh recordings are needed for confirmation.
4. In a separate feature study, investigate robust torque shape measures and low-load signal quality across healthy AND fault recordings. Do not silently drop torque, erase spikes or add a filter simply because they drive these false alerts: that could remove useful fault evidence.
5. Seek repeated healthy acquisitions for the 1 HP/0% condition and acquisition/sensor metadata to distinguish a repeatable operating pattern from recording-specific behaviour.

The available evidence supports a calibration-coverage change before adding HP model banks. It does not yet establish that this change will solve the false alarms, that smoothing parameters should change, or that the target should be excluded from healthy training.

## Evidence map

- healthy_phase_distances.csv: fit/calibration/check distributions for all 17 healthy records.
- target_feature_phases.csv and healthy_feature_comparison.csv: feature levels and temporal/control comparisons.
- signed_feature_allocations.csv and channel_diagnostics.csv: exact score allocations and conditional terms.
- target_check_timeline.csv: frozen A/C score and threshold timeline.
- continuous_calibration_diagnostic.csv, calibration_tail_replay.csv and calibration_threshold_sources.csv: calibration coverage evidence.
- native_channel_profiles.csv, native_second_metrics.csv and torque_peak_neighbours.csv: native sample screening and inspectable peak neighbourhoods.
- raw_feature_reproduction.csv: reconstruction checks.
- investigation.json: verification findings, source preservation and artifact hashes.
- scripts/: exact scripts used, retained with their original project/staging paths for audit; use a fresh output path for a rerun.

Review status: share with the stated scope and physical-cause limitations. This investigation is diagnostic, not an additional independent validation set.

