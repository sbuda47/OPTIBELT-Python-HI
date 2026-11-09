# Version 2: operating-aware development results

Version 2 implements exact condition routing, healthy condition-specific means and shared residual covariance within each motor rating. Version 1 code, configuration and evaluated run files are preserved. The reference bank contains three rating models and 17 healthy condition centres. Reference presence is labelled supported_development; it is not evidence of validated operational performance.

## Implemented coverage

| HP | Load | Invariant 50 Hz | Variable 50–52 Hz | Variable 50–58 Hz |
|---|---|---|---|---|
| 1 | 0% | reference present | unsupported | unsupported |
| 1 | 30% | reference present | unsupported | unsupported |
| 1 | 60% | reference present | unsupported | unsupported |
| 3 | 0% | unsupported | reference present | reference present |
| 3 | 30% | reference present | reference present | reference present |
| 3 | 60% | reference present | reference present | reference present |
| 5 | 0% | reference present | reference present | reference present |
| 5 | 30% | reference present | reference present | reference present |
| 5 | 60% | unsupported | unsupported | unsupported |

Missing-state records receive no numeric HI or healthy/fault verdict. Nine original quality exclusions remain excluded. Four complete fault records are unsupported:

- Interturn60%_3HP_0%: 3HP_0pct_invariant_speed_50to50Hz
- misalign0p5mm_3HP_0%: 3HP_0pct_invariant_speed_50to50Hz
- Journal0p85um_7p5HP_0%_52Hz: 7.5HP_0pct_varying_speed_50to52Hz
- Misalign0p1mm_1HP_0%_58Hz: 1HP_0pct_varying_speed_50to58Hz

The three 1 HP constant-speed references have healthy-only development evidence and no supported fault examples. The 7.5 HP journal case is outside the 1/3/5 HP target and has no healthy reference.

## Design and evidence limits

Only healthy fitting blocks determine state means, feature selection, scaling and covariance. Calibration blocks set state-specific event thresholds; later blocks check behaviour. Four-second sample gaps separate the roles. Every calibration/check episode has 25 windows: ten warm-up windows followed by 15 eligible decisions. Supported fault checks use the same episode length.

The calibration statistic is the maximum minimum of each consecutive score triplet, calculated after EWMA for the smoothed stream. Its threshold comes from healthy calibration episodes only. This directly calibrates the three-window event for that observed episode. One episode per state is insufficient for a population false-alarm guarantee. Zero events on calibration data are by construction. The bank field independent_calibration_acquisitions counts distinct calibration source recordings; these are the SAME acquisitions used in fitting and are not independent of fitting.

This exact-state design deliberately does not interpolate loads or infer instantaneous speed. The profile labels are acquisition regimes/bounds. Windows within a variable-speed file can still have different instantaneous operating conditions. The metadata are supplied from known filenames for playback; live estimation and state-transition handling are not implemented.

## Development outcome

| Stream | Healthy episodes with sustained alert | Fault episodes with sustained alert | Mean healthy alarm-window fraction |
|---|---:|---:|---:|
| raw | 14/17 | 11/11 | 67.1% |
| ewma | 13/17 | 11/11 | 72.5% |

The false-alarm outcome is poor. Capacity/load/profile routing alone has not made the scores stable. The model is not ready for operational alarm use. Possible remaining explanations include variation within the broad speed/load profiles, changes over time within recordings, and insufficient calibration episode coverage; this run does not establish their relative causes. No threshold, feature selection rule or model parameter was tuned after viewing these results.

These numbers must NOT be presented as a direct improvement or deterioration relative to version 1. V1 tested withheld operating groups on 14 healthy/13 fault recordings; V2 uses later segments of familiar healthy recordings, includes 1 HP constant-speed normals and abstains on four unmatched fault cases, leaving 17 healthy/11 fault episodes. The cohorts, exposure and monitoring horizons differ. Both result sets are retained.

## Verification and use

All 80 software tests passed. The saved reference bank was reconstructed exactly from the declared healthy fit/calibration blocks. All 700 saved prediction rows and 56 per-record/stream metrics were reproduced. Guard gaps, schema routing, unsupported states and unchanged V1 artifacts/code were checked.

Primary artifacts: outputs/runs/operating_v2_development_001/{condition_coverage.csv,record_routing.csv,temporal_blocks.csv,bank.json,predictions.csv,record_metrics.csv,summary.csv,pre_fit.json,run.json}. Verification: outputs/runs/v2_validation_001/validation.json. Protocol: docs/v2_protocol.md.

Rerun with a NEW output name:

~~~powershell
uv run python -B -m optibelt_hi.evaluation.operating_v2_run --project . --name operating_v2_development_repeat
~~~

For stable-episode scoring, use model.operating_v2.score_episode with the bank, ordered feature matrix, exact declared condition key and feature names. Inspect status and eligible before using flags. Unknown conditions return unsupported; the first ten windows are warm-up.

## Next development work

Investigate within-record score drift and how well the single calibration episode represents later healthy data, without retroactively modifying this result. Then predeclare a bounded temporal-stability/calibration revision using the existing data and label its results as development. Additional independent recordings remain necessary for independent-acquisition claims, but are not required to continue clearly scoped software development.
