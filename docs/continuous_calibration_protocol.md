# Continuous calibration comparison — 7 November 2026

Freeze this protocol before calculating revised thresholds or check outcomes.

Use the exact fitted references A (pooled) and C (load-centred) from load_only_experiment_001. Preserve the original bank and all prior outputs. No refitting, new feature selection, HP-specific modelling, raw-data cleaning, feature changes or source admission changes. Primary stream is EWMA; report raw scores as a diagnostic.

Replace only the global calibration thresholds. For each of the same 17 healthy recordings, process all two-second windows wholly within the reserved interval [0.5T+2,0.75T-2] seconds. Initialize EWMA once at its first score and discard the first ten decisions for warm-up. Carry state continuously across the rest of the interval. Do not pack short episodes or discard the remaining tail. Reset only between recordings. For each reference and raw/EWMA stream separately, calculate the maximum rolling three-window minimum among eligible calibration scores, then take the maximum over the 17 recordings. Use strict greater-than comparisons, alpha 0.2 and three-window persistence unchanged. This is a maximum-envelope development rule, not a guaranteed false-alarm probability.

Seven 300-second healthy records contribute 70 calibration windows/60 decisions each; ten 120-second records contribute 25/15. Total: 740 calibration windows and 570 decision steps per reference, from 17 acquisitions. The prior episode rule used 24 episodes, 600 windows and 360 decisions. Same-acquisition correlation remains; do not call these independent trials. Removing resets can change scores in either direction, so revised thresholds are not assumed to exceed the original thresholds.

Store the new thresholds with calibration indices, per-record event levels, source bank hash and threshold-supplying recording before checking outcomes. Keep the original fitted-bank file unchanged. Evaluate original versus continuous calibration on exactly the full check intervals used in long_monitoring_001: 28 supported records, 17 healthy and 11 fault. Nine extendable records have 60 decision steps; 19 have 15. No check/fault values select thresholds. These check outcomes have already been exposed; results are development comparisons, not new validation.

Report paired recording/event outcomes, decision-time occupancy, per-load and per-duration breakdowns, threshold changes, and missed/detected fault recordings. Verify that raw and smoothed distances are identical between calibration policies and match the earlier saved predictions. HI values may change because their normalization threshold changes. Record fault alert timing relative to monitoring; fault-onset latency is not identifiable.

No post-result parameter search, margin multiplier, fallback to old thresholds or performance-driven exclusions. A favourable result only justifies carrying the candidate to independent-acquisition checks. If false alarms or missed faults persist, retain and report them. Calibration self-alerts should be zero by construction and must not be presented as validation performance.

