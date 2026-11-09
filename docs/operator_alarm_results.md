# Operator HI zones, hysteresis and duration — 7 November 2026

The operator-zone experiment is complete. With the load-aware C reference, all three confirmation durations (2, 3 and 5 seconds) produce zero critical operator-alarm requests on the 17 healthy recordings and critical requests on 10/11 fault recordings. All 11 faults reach at least warning. Two healthy recordings also show warnings. The distinction between a warning and a confirmed critical request must be retained when reporting these results.

Run: outputs/runs/operator_zones_001. Verification: outputs/runs/operator_zones_validation_001. Protocol: operator_alarm_protocol.md.

No HP-specific model was added. No sound was played, no motor command was issued and no existing fitted model, calibration, release or experiment result was changed. All output actions are logged shadow requests.

## The 0–100 operator score

We retain MD as the underlying deviation measure and the existing healthy calibration threshold q. The separately versioned operator mapping is:

H = 100 / (1 + (2/3)(MD/q)^2).

The calibrated boundary now maps to 60 instead of 50. MD=0 maps to 100 and larger distances reduce HI towards zero. This is a nonlinear normalized deviation score, not measured percentage health or remaining life. No dataset minimum/maximum or fault/test label is used to choose the mapping.

The primary signal is EWMA-smoothed MD. Zone boundaries are:

| Instantaneous zone | Operator HI |
|---|---|
| Normal | 60–100 inclusive at 60 |
| Warning | 25 up to, but not including, 60 |
| Critical | Below 25 |

Critical requires MD/q > sqrt(4.5), approximately 2.12. This is more demanding than the previously tested alarm condition MD>q. Therefore the previous 11/11 sustained detections cannot be transferred to critical-zone claims.

The legacy hi_candidate_v1 bundle and playback output retain their original HI mapping. The new operator_zones_v1 simulation explicitly saves both legacy_hi and operator_hi. A later dashboard must name its mapping/policy version; old and new values must not be mixed silently.

## Hysteresis in plain language

An alarm enters at one boundary and clears at a different recovery boundary. With the experimental hysteresis settings:

- Enter warning below 60; clear warning only at 65 or higher.
- Enter critical below 25; clear critical indication only at 30 or higher.

For HI readings 70, 59, 61, 59, 64, 65:
without hysteresis the display is normal, warning, normal, warning, normal, normal;
with hysteresis it is normal, warning, warning, warning, warning, normal.

This avoids repeated switching near 60. Its cost is that a warning remains visible longer after a small recovery. Hysteresis does not prove the motor remains unhealthy, and 65/30 are experimental recovery values.

The below-25 confirmation timer is separate from the displayed state. HI rising to 27 cancels an unconfirmed timer, although the hysteretic display can remain critical until HI reaches 30. That distinction prevents the 25–30 recovery band from counting as continuously below 25.

## Confirmation, acknowledgement and missing data

The timer starts at the first eligible score below 25. Two elapsed seconds require three consecutive one-second readings; five seconds require six. A reading >=25 or a missing/gapped reading cancels the unconfirmed timer. Warm-up readings cannot initiate an alarm.

After confirmation, the operator/audible-alarm request latches. There is no automatic motor stop or restart. The code permits acknowledgement to clear a confirmed request only after a valid score has recovered to the configured critical-clear boundary. Missing data cannot clear it. Acknowledgement does not command machinery. Dataset playback includes no simulated acknowledgement, so a request remains latched to the end of its recording.

No real audio interface has been added. The audible_alarm_requested field is a software signal for future dashboard integration. Missing readings produce data_unavailable instead of an invented healthy score; timing restarts from valid fresh data.

## Recorded-data results

Every policy uses the same full check intervals, with 570 healthy and 255 fault decision steps. Ten warm-up windows are unchanged. Only nine records have longer 60-step checks; 19 have 15-step checks.

For C, results are identical in request counts with and without hysteresis:

| Confirmation duration | Healthy critical requests | Fault critical requests | Faults reaching warning or critical | Request time after first eligible decision |
|---|---:|---:|---:|---|
| 2 s | 0/17 | 10/11 | 11/11 | 2–3 s |
| 3 s | 0/17 | 10/11 | 11/11 | 3–4 s |
| 5 s | 0/17 | 10/11 | 11/11 | 5–6 s |

These timing offsets describe the observed playback; they are not latency from physical fault onset. Windowing, EWMA, communications, human response and actual motor stopping are additional considerations. The present recordings do not identify a universally appropriate duration.

The warning-only C fault is Coil10%_3HP_60%_58Hz.mat. Its minimum operator HI is 25.5369; it never enters critical during the eligible check. Shortening the timer cannot make a score above 25 trigger this critical rule. It is flagged for operator attention, but not as a confirmed critical event. This does not establish that operating it is safe or that the proposed zones correspond to physical fault severity.

For the pooled A comparison, 9/11 fault records generate critical requests, while all 11 reach at least warning. Besides the coil recording (minimum 27.6175), Misalign0p3mm_3HP_0%_52Hz.mat remains warning (minimum 26.2926). The difference is local evidence from this fixed policy and these exposed records, not proof of general load-aware superiority.

## What hysteresis changed

For C, the two healthy recordings with warnings are Normal_1HP_0%.mat and Normal_5HP_0%_58Hz.mat. Neither enters critical.

| Healthy C result | No hysteresis | Hysteresis |
|---|---:|---:|
| Records showing warning | 2/17 | 2/17 |
| Warning decision steps | 7/570 | 16/570 |
| Zone-state transitions within eligible checks | 9 | 2 |
| Critical operator requests | 0 | 0 |

The hysteretic warning in Normal_1HP_0% persists from decision times 294–298 s, ending with HI 62.46. This is above the entry threshold but below the recovery threshold 65. The warning in Normal_5HP_0%_58Hz persists from 108–118 s. Both remain active at the end of the check, so the observed warning lengths are right-censored; actual clearance time is unknown.

For A, healthy warning steps rise from 8 to 28 and transitions fall from 11 to 4. This illustrates the same trade-off. Hysteresis reduces state switching; it does not reduce the number of healthy records entering warning here.

Healthy scores never enter critical under these policies. Therefore zero healthy critical requests does not demonstrate that a particular duration suppressed real-data critical transients: there were no such healthy critical excursions to test. Synthetic brief-dip tests verify timer behaviour, but do not establish physical false-alarm performance.

## Verification

All 108 tests passed. New tests cover the mapping, elapsed time versus sample counts, short dips, sustained critical values, warning oscillation, timer cancellation in the recovery band, missing data/gaps, warm-up, acknowledgement and rejection of invalid timestamps.

Independent replay verified all 13,260 prediction rows and 336 record-policy metrics. The score conversion was independently checked using the legacy HI identity H_operator = 300 H_legacy / (200 + H_legacy). Elapsed timers, hysteretic states, latches, summaries and synthetic brief/sustained scenarios reproduced. No motor_stop_command is true in any recorded or synthetic output. Prior experiment and release hashes match.

This is a software simulation on already exposed same-acquisition checks. It is not a severity calibration, an independent validation set, or an implementation of live sound/motor control.

## Recommendation

Retain the 60/25 zone policy and 65/30 recovery values as documented experiment settings, not finalized physical operating limits. Hysteresis is useful for avoiding a flickering operator display, provided the retained warning/recovery state is explained clearly.

No tested duration improved the number of detected critical records or reduced healthy critical requests; increasing duration simply delayed the same ten C requests. Keep duration configurable for simulation rather than declaring a winner from this dataset. Establish acceptable operator response and total system delay before choosing a real setting.

Do not raise the critical boundary solely to capture the warning-only example. First decide, using fault severity and operating-risk evidence, which conditions should be warnings and which require urgent inspection. New acquisitions with weaker faults, transient disturbances and known event timing are needed to validate that distinction.

The next software step can be a dashboard that clearly separates current zone, pending critical timer, latched operator-alarm request, data quality and acknowledgement. It should show no automatic stop control. HP-specific modelling remains excluded.

