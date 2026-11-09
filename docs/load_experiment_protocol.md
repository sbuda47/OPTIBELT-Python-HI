# Controlled load-only development experiment

User direction: defer HP modelling and test load awareness first. No HP-specific fitting, feature selection, distance, threshold or inference routing is implemented in these arms. HP remains descriptive metadata and part of the existing evidence-coverage boundary.

Freeze four arms before inspecting outcomes:
A pooled reference + global calibration threshold.
B pooled reference + per-load calibration threshold.
C load-specific healthy feature centres, shared residual covariance + global threshold.
D same load-centred reference as C + per-load threshold.

A/B share the identical fitted model and raw/smoothed distances. C/D also share theirs. Changing A to B or C to D therefore changes only threshold routing; changing A to C or B to D tests the reference adjustment under the same calibration policy. No winner will be tuned after inspecting results.

Use the same 28-record reference-present cohort as V2 (17 normal, 11 fault). The four complete unmatched fault cases remain unsupported for the primary comparison; nine source-quality exclusions remain excluded. This frozen eligibility is an evidence restriction, not HP-specific modelling. Do not broaden claims to missing healthy condition combinations.

Use candidate_v1 features and the existing guarded temporal fit/calibration/check intervals. Only healthy fit blocks supply feature selection, equal-recording moments and covariance. The pooled reference uses all healthy fit records together. The load-centred reference subtracts an equal-recording healthy mean for each of 0/30/60% before fitting one shared residual model. Both use the same existing variance floor, 0.98 correlation pruning and 0.1 shrinkage. No HP/speed centres or interpolation.

Use all COMPLETE 25-window calibration episodes inside the reserved calibration interval, starting every 29 windows. Consecutive episodes have a three-second raw-window gap. This yields more usable calibration coverage for longer recordings; episodes from a recording are correlated, not independent acquisitions. Retain the same first 25 eligible check windows per recording for every arm. Each episode has ten EWMA warm-up windows and fifteen decision windows. Fitting/check intervals and their four-second guards are unchanged.

For raw and EWMA separately, use the maximum three-consecutive-window event level across eligible healthy calibration episodes. Global calibration pools all loads; per-load calibration pools the same episodes within load. This maximum-envelope rule is fixed, not a calibrated rare-event guarantee. The global threshold cannot be lower than a per-load threshold for the same reference. Consequently B cannot reduce alerts compared with A on identical scores; it may recover fault sensitivity at a cost in false alarms. The same applies to D versus C. This structural tradeoff is checked explicitly.

EWMA alpha remains 0.2; persistence is three strictly above-threshold decision windows. HI mapping is unchanged. No adaptive baseline, online load inference, default unknown-load handling or parameter search. Unknown loads return unsupported. State is reset only at the declared episodes; live transitions remain outside scope.

Report all four arms, raw and EWMA, using paired recording outcomes, same denominators, the same episode duration and per-load breakdowns. Report remaining calibration support as distinct records AND correlated episodes. Include false-alert cases and detected/missed faults. Use saved artifact/code hashes and verify the earlier V1 and V2 runs remain unchanged.

This is exposed-data, within-record temporal development. It is neither independent-record validation nor a direct benchmark against the old MATLAB output. It reuses the old pooled-reference/per-load-threshold idea with corrected Python features and healthy-only calibration. Any favourable outcome is a development candidate, not proof of deployment readiness.

