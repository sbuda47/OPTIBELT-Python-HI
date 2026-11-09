# Findings from the first dataset milestone

## F001 — Mixed native rates are encoded with NaN padding
The source publication reports 100 kHz current and 25.6 kHz vibration/torque. In complete local variable-speed recordings, the matrix has 12,000,000 rows. Vibration and torque contain 3,072,000 native samples followed by NaN padding, while current contains 12,000,000 samples. Each channel covers 120 seconds when interpreted at its own rate.

The old extraction code downsampled every channel by four and treated the result as 25.6 kHz. That gives a real rate of 25 kHz for current and 6.4 kHz for vibration/torque. Its fillmissing/zero fallback could also extend padding or fabricate a missing channel. The new pipeline changes this behaviour explicitly.

Evidence is recorded per channel in outputs/runs/initial_raw_audit/channels.csv. Source rates appear on page 5 and in Table 3 of Jung et al. (2025).

## F002 — Seven entire vibration channels are missing
All vibration samples are NaN in these seven files
- Coil60%_1HP_30%_58Hz
- Normal_1HP_0%_52Hz
- Normal_1HP_0%_58Hz
- Normal_1HP_30%_52Hz
- Normal_1HP_30%_58Hz
- Normal_1HP_60%_52Hz
- Normal_1HP_60%_58Hz

They remain in the raw collection and are flagged. They cannot enter an initial five-channel feature model as complete measurements. A current/torque-only study, source replacement or explicit missing-modality model would be separate decisions.

## F003 — Two stored durations differ from the nominal source description
Bearing_3HP_30% is in the invariant-speed folder but its matrix has 12,000,000 rows. Its finite channel lengths correspond to 120 seconds, while the publication describes 300-second constant-speed runs.

Coil60%_5HP_30%_58Hz has 3,172,404 stored rows. Its finite sample counts are 809,662 per vibration/torque channel and 3,163,770 per current channel, approximately 31.63 seconds. Exact finite intervals and their relative timing need investigation before admitting a shorter common interval.

Both fail the initial nominal-duration gate. This gate is deliberately conservative; it does not establish that the MAT container is corrupt.

## F004 — Original exported fault labels include healthy mislabelling
Reading segments/Source and segments/FaultType in the preserved AC/scenario_v2.h5 shows
- Bearing_3HP_30% — 116 windows labelled Normal
- Bearing_3HP_30%_58Hz — 116 windows labelled Normal
- Bearing_5HP_30%_58Hz — 116 windows labelled Normal
- Interturn60%_3HP_0% — 291 windows labelled Normal

Total 639 windows. The recovered ProcessFilePro_v2.m defaults to Normal and has no branches for Bearing or Interturn. Build_HI_v2.m selects its healthy baseline using FaultType == Normal. These source and artifact findings demonstrate a route for faulty windows to enter the historical healthy baseline. The exact saved-fit membership needs further artifact tracing if the historical model is investigated.

The new parser preserves each of these labels and rejects unknown names. Its tests cover both fault families.

## F005 — Data availability constrains independent evaluation
The collection contains 41 distinct file hashes and no unreadable MAT files. Under the nominal-duration, five-channel gate, 32 recordings pass, including 17 labelled healthy and 15 labelled faulty. Six healthy variable-speed 1 HP recordings lack vibration.

A random split of overlapping windows would give misleading independence. Splits will remain unassigned until the admitted recording population and the intended operating/motor scope are documented.

