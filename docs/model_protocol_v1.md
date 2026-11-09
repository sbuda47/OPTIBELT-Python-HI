# First Python MD-HI protocol (predeclared before evaluation)

This protocol follows grouped_v1 without changing its 27 primary recordings, five rounds or roles. candidate_v1 features are inputs. Numerical settings in configs/model.yaml are fixed before any evaluation score is inspected. This is a first baseline implementation, not a claim of optimized methodology.

## Healthy fitting

Only healthy fit-role records supply selection, scaling and covariance. Give each of R recordings total weight 1/R, and each of its n_r windows weight 1/(R*n_r). Longer records and overlapping windows do not create extra recording weight. These weights are not an estimate of independent sample size.

Drop total rms and the final band fraction from each channel by definition: rms is algebraically determined by mean and ac_rms, and four fractions sum to one. For remaining columns compute weighted population mean and standard deviation. Drop a column if its standard deviation is at most 1e-12 times max(1, weighted RMS of that column). This is a numerical floor, not a physical relevance threshold.

Standardize using fitting statistics only. Traverse remaining columns in the published schema order; keep a column unless its absolute weighted correlation with an already kept column is at least 0.98. Record every decision, retained name and input index. This deterministic, unsupervised pruning does not measure fault relevance. No feature-count cap is selected from evaluation.

Compute weighted population covariance C of retained standardized features. The primary model uses C_reg = 0.9*C + 0.1*I. This fixed ridge/shrinkage rule is not Ledoit-Wolf or a fitted shrinkage coefficient. Record rank, eigenvalues and conditioning before/after regularization. Use Cholesky solves for d = sqrt(z^T*C_reg^(-1)*z), with no pseudoinverse or explicit matrix inversion.

## Fixed comparisons

Fit independent models for fusion (all five channels), vibration, three-phase current, torque, and a diagonal standardized-distance baseline using fusion's candidate scope and selection rule. The diagonal model uses I after standardization. Use identical recording roles and calibration rules for all comparisons. Do not select a winner or change parameters using held-out performance.

## Calibration, score and monitoring

Healthy calibration-role records set thresholds only; they do not change features, scaling or covariance. Give each calibration recording equal total weight. The threshold q is the smallest observed distance at which the weighted empirical CDF reaches 0.99. No interpolation, Gaussian, chi-square or distribution-free coverage guarantee is assumed. Reject a nonpositive threshold.

Export raw distance, distance/q, and H = 100/(1+(distance/q)^2). H is a bounded anomaly-derived health score: 100 at the fitted centre, 50 at the threshold, decreasing toward zero. It is not calibrated percentage health, wear, remaining life or fault probability. Alarm means distance > q; equality does not alarm. Distances are never clipped.

Also compute a causal EWMA of distance with alpha=0.2, initialized to the first distance of each recording and reset between records: s[0]=d[0]; s[t]=0.2*d[t]+0.8*s[t-1]. Calibrate a separate 99th-percentile threshold from identically smoothed healthy calibration records. Never apply the raw threshold to smoothed distances.

At a one-second hop, a sustained step after initialization takes 11 updates to reach at least 90% of its change. Report this smoothing response separately from the two-second signal window and upstream offline resampling. The existing resampling filter is not a validated online implementation.

A secondary recording alert requires three consecutive above-threshold windows. Export the first qualifying window's stop time as time from recording start, never as fault-onset detection delay: these recordings have no verified onset labels.

## Evaluation and uncertainty

Evaluate each primary record only in its assigned test round. Report both raw and smoothed results with the corresponding calibrated thresholds. For each record report fraction of windows above threshold and whether the three-window alert occurred. Primary aggregate false-alarm fraction is the mean of fractions across healthy test recordings; fault alarm fraction is the corresponding mean across faulty recordings. These are window occupancy summaries, not an independent-window accuracy claim. Report numerator/denominator for recording alerts separately.

Break results down by fold and fault condition; retain per-record output. Report observed min/max per-record fractions to show variability. Do not attach independent-window binomial confidence intervals. Only five operating groups, unknown motor/run identity, correlated overlapping windows and reused historical data prevent strong generalization/uncertainty claims.

A withheld group's healthy alarms can reflect operating/sensor shift. Stationary fault-condition files do not establish a degradation trajectory. Poor results must be reported without moving thresholds or altering this evaluated version. Later changes become documented development iterations and need fresh external confirmation.

## References and evidence

[Mahalanobis distance definition](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.mahalanobis.html).
[EWMA recursion and assumptions](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc324.htm). Our initialization and empirical calibration are specified above; we do not use normal-independent control-chart limit formulas.

Save model JSON (no pickle), configuration snapshot, fit/calibration identifiers, feature-input and split hashes, implementation hashes, per-window predictions, per-record summaries and comparison summaries. Freeze code/configuration provenance before evaluating. Any correction after results become visible must be recorded as such.

