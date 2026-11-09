# Candidate feature catalog: candidate_v1

This version computes 12 measurements for each of vibration, torque, current_r, current_s and current_t, producing 60 candidate columns. Feature selection and model fitting have not occurred. No values, selected columns or fitted parameters are imported from MATLAB.

## Input and conventions

Input is a finite five-channel matrix at 25,600 Hz from the validated offline preprocessing. Each window has 51,200 samples (2 seconds); the hop is 25,600 samples (1 second). No window crosses a recording boundary; incomplete final windows are omitted. No amplitude normalization is applied before extraction. Original sensor scaling is preserved; physical calibration and units still need corroboration, so amplitude features are reported in stored channel units rather than assumed A, g or N m.

For a window x with N samples, define m = sum(x)/N, y = x-m, s = sqrt(sum(y*y)/N), and z = y/s. Mean removal is local to each window for shape and spectral features; the stored mean and total RMS retain the original offset. There is no linear detrending or whole-recording mean subtraction.

| Suffix (prefix is channel__) | Definition | Unit |
|---|---|---|
| mean | m | stored channel unit |
| rms | sqrt(sum(x*x)/N) | stored channel unit |
| ac_rms | s (population standard deviation, denominator N) | stored channel unit |
| peak_to_peak | max(x)-min(x) | stored channel unit |
| crest_factor_ac | max(abs(y))/s | dimensionless |
| skewness | sum(z^3)/N; uncorrected standardized third central moment | dimensionless |
| kurtosis_pearson | sum(z^4)/N; uncorrected Pearson fourth moment, no subtraction of 3 | dimensionless |
| spectral_centroid_hz | sum(f[k]*P[k])/sum(P[k]), over k>0 | Hz |
| power_fraction_0_200 | positive-frequency power for 0<f<200 Hz / total positive-frequency power | dimensionless |
| power_fraction_200_1000 | power for 200<=f<1000 Hz / total positive-frequency power | dimensionless |
| power_fraction_1000_5000 | power for 1000<=f<5000 Hz / total positive-frequency power | dimensionless |
| power_fraction_5000_12800 | power for 5000<=f<=12800 Hz / total positive-frequency power | dimensionless |

P is the one-sided density periodogram of y, using a periodic Hann window, N-point FFT, no zero padding and no additional detrending. Positive and negative frequency power are combined using SciPy's real one-sided convention. DC is excluded from both numerator and denominator. The frequency spacing is 0.5 Hz at the default window length. Band integration uses a rectangular bin sum; the common bin width cancels in each fraction. A tone on a band boundary spreads into neighbouring bins under the Hann window; these are broadband summaries, not exact harmonic amplitudes.

Documentation: [SciPy periodogram](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.periodogram.html), [skewness definition](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.skew.html), [Pearson kurtosis](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.kurtosis.html). Installed SciPy remains pinned to 1.17.1 in uv.lock; browsing current documentation does not change dependencies.

## Validation and exclusions

Analytic tests cover offset sine-wave statistics, power allocation between two known tones, centroid, amplitude scaling, finite inputs and complete-window bounds. Missing, infinite, complex, too-short and flat signals are rejected when statistics are undefined. No epsilon substitution or imputation is used. A failed window fails its recording/run and is identified in run.json.

Capacity, load, speed-profile labels, condition and severity remain separate metadata in windows.csv. They are never appended to the 60-column predictor matrix.

## Interpretation and later selection

These features provide a transparent first candidate set. All four band fractions sum to one, and rms^2 = mean^2 + ac_rms^2; therefore this set contains known redundancy and must not be directly inverted as a covariance matrix. Feature pruning, scaling, conditioning and regularization must be fit using the healthy fitting population within each fold. No retained-feature count is predetermined.

The historical MATLAB extractor also contained envelope, harmonic and sideband measurements. Those are not implemented or claimed here. Variable-speed harmonic extraction needs a tested in-window frequency estimator and explicit tracking assumptions. Future additions require a new schema and an evaluation protocol amendment before consulting test performance.

Preprocessing uses an offline two-sided FIR for resampling. Its endpoint behaviour can affect boundary windows; streaming equivalence and sensitivity to boundary-window exclusion remain future checks.


## Current-bandwidth limitation
The common 25.6 kHz time base cannot represent current content above 12.8 kHz, and its resampling filter attenuates frequencies around the transition band. This first feature set therefore does not preserve all information in the original 100 kHz current recordings. Feature-level fusion could instead use equal-duration windows at each native rate; that is a separately testable alternative, since equal sample rates are not mathematically required to combine window-level statistics. Raw recordings are retained for that comparison.
