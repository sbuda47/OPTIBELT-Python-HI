# Operator alarm zones and duration experiment — 7 November 2026

User direction: leave HP-specific models out; use a 0–100 operator HI and warnings/critical audible-alarm requests, with a human inspecting and stopping the motor. No automatic motor stop, automatic restart, real audio or hardware command is authorized by this experiment.

Freeze the load-aware C reference and pooled A comparison, their continuous-calibration thresholds, source features and MD/EWMA distances. Introduce a separately versioned operator display/alarm policy. Earlier releases and results are unchanged.

Mapping: H = 100 / (1 + (2/3)(MD/q)^2), with q the frozen stream's calibration threshold. Thus MD=0 maps to 100 and MD=q to 60. This replaces the earlier mapping of q to 50 for this experiment only; it does not make HI a physical percentage of health. Primary input is the smoothed distance. Critical H<25 corresponds to MD/q>sqrt(4.5), a stricter deviation requirement than the previous MD>q alarm. Detection at the old threshold does not guarantee detection here.

Instantaneous zones: normal H>=60; warning 25<=H<60; critical H<25. Warning indication starts immediately on an eligible H<60 reading. Compare two fixed recovery policies: no hysteresis (warning clears at >=60, critical at >=25), and hysteresis (warning clears at >=65, critical at >=30). Critical indication takes priority over warning. The recovery thresholds are experimental hypotheses, not tuned operating settings.

Compare critical confirmation durations of 2, 3 and 5 elapsed seconds. The timer starts at the first eligible H<25 reading, continues only with consecutive one-second updates below 25 and cancels at H>=25, including the critical recovery band 25–30. Hysteresis maintains the displayed state, not the below-25 timer. At a one-second decision interval, two seconds requires three observations; five seconds requires six. Do not confuse counts with elapsed time.

After confirmation, emit and latch an operator/audible-alarm request. Do not call sound/hardware APIs. No automatic stopping. Acknowledgement may clear the latch only with a currently valid score recovered to the configured critical-clear boundary; acknowledgement itself never restarts machinery. No acknowledgement is simulated in dataset replay, so a confirmed request remains latched through the episode. Count new requests separately from latched time.

Missing/nonfinite readings or a timestamp gap cancel an unconfirmed timer and mark data unavailable/gapped. They must never create a healthy reading or clear an existing confirmed request. A fresh sequence is required after the gap. Preserve the source monitor's first ten-window warm-up, during which no zone alarms are initiated. A new source recording gets a fresh policy session.

Replay all 28 supported records over exactly the full reserved check intervals from continuous_calibration_001: 17 healthy, 11 faults; 570 healthy and 255 fault decision steps per policy/reference. Compare 2 references x 2 recovery rules x 3 durations. Report warning/critical zone exposure, state transitions, operator-request events, healthy request records, detected/missed fault records and first confirmation relative to the first eligible decision. Because fault onset is unknown, this is not physical fault-detection latency.

Synthetic tests must cover brief dips, sustained critical scores, boundary fluctuation, hysteresis recovery, a recovery-band timer cancellation, gaps/missing values, warm-up, acknowledgement and latch persistence. A brief raw-signal impulse can still influence multiple overlapping feature windows and EWMA outputs; duration rules confirm sustained scores, not independently proven sustained physical faults.

Freeze the protocol and implementation before dataset replay, and report all policies without selecting durations to optimize these already exposed recordings. Thresholds/HI version must accompany playback outputs. This is simulation/development; realistic confirmation time must later account for windowing, smoothing, communications, operator response and machine stopping.

