# Frozen-model longer monitoring protocol — 6 November 2026

Freeze this protocol before scoring the added time intervals.

Question: do the pooled-reference control A and load-centred candidate C retain their short-check performance when the entire reserved check interval is monitored without resets?

Use the saved bank.json from outputs/runs/load_only_experiment_001. No fitting, calibration, feature selection, threshold changes, HP-specific models or new source admissions. Verify every source-run artifact hash and implementation hash. Preserve V1, V2 and load-only run files. Use the identical 28-record supported cohort (17 healthy, 11 fault); retain nine quality exclusions and four unsupported cases.

For a recording of nominal duration T, select all feature windows whose raw sample support lies inside [0.75T+2, T-2] seconds. Continue to exclude fitting/calibration intervals and their guards. Windows are two seconds long at a one-second hop. This produces 70 windows for 300-second records and 25 for 120-second records. The first 25 must reproduce the prior check exactly within numerical tolerance.

Initialize EWMA once at the first check-window distance; alpha=0.2. Retain the first ten warm-up windows, then evaluate every remaining window. Do not reset EWMA or persistence at the old 25-window endpoint or in the added interval. Reset only between source recordings. Compare only A and C; retain raw-distance alarms as a diagnostic beside the primary EWMA result. All thresholds and HI transformations come from the saved bank.

Primary outcomes: healthy records with at least one sustained false alert; fault records with at least one sustained alert; number of distinct confirmed alert events; alarm decision-time occupancy. Report all records, extendable 300-second records separately, and per load. Also report the prior prefix and added extension separately, carrying smoothing/persistence state across their boundary. Prefix and extension are not independent samples.

An exceedance run is a maximal consecutive sequence of eligible windows strictly above threshold. It becomes one confirmed event at its third window; a single below-threshold window ends it. Persistent-alarm occupancy counts the third and subsequent windows only. Time units are one-second decision steps, not sums of overlapping two-second raw windows. A run ending at the final observed window is right-censored. Save exceedance start, confirmation time, last exceedance time, run length and persistent-alarm steps. Fault-onset time is unknown, so report first alert relative to monitoring rather than claiming fault detection latency.

Each 300-second record supplies 60 decision steps instead of 15: 45 extra. A 120-second record supplies no added monitoring. Across this cohort only nine recordings extend (seven healthy and two fault); the other 19 are unchanged. Aggregate total decision exposure is 825 steps: 570 healthy, 255 fault, with 405 new steps in total. The full check raw support spans 71 or 26 seconds including warm-up; actual decision sequences span 60 or 15 one-second steps under the stated convention.

The thresholds were calibrated on shorter episodes. Extending monitoring may increase the chance of an event; that is the intended stress test, not a reason to recalibrate after looking at outcomes. No target false-alarm rate, hours-long validation, independent acquisition or load-transition claim is supported. Previously exposed data and same-acquisition fitting/calibration remain limitations.

Write predictions, record metrics, event details, summaries by duration/load/segment, paired outcomes and a preservation/validation receipt into new output directories. Report unfavourable and favourable findings together. Any subsequent revision requires a separately declared experiment.

