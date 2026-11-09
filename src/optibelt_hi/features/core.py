"""Version 1 candidate moments and broadband spectral summaries."""
import numpy as np
from scipy.signal import periodogram
from optibelt_hi.data.recordings import CHANNELS
from optibelt_hi.preprocessing.signals import window_bounds

FEATURE_NAMES = (
    "mean","rms","ac_rms","peak_to_peak","crest_factor_ac","skewness",
    "kurtosis_pearson","spectral_centroid_hz","power_fraction_0_200",
    "power_fraction_200_1000","power_fraction_1000_5000","power_fraction_5000_12800",
)
BANDS = ((0,200),(200,1000),(1000,5000),(5000,12800))
SCHEMA_VERSION = "candidate_v1"

def channel_features(values, rate=25600):
    raw=np.asarray(values)
    if rate!=25600:
        raise ValueError("Version 1 requires 25600 Hz; band definitions are fixed.")
    if raw.ndim!=1 or len(raw)<4 or raw.dtype.kind not in "fiu" or not np.isfinite(raw).all():
        raise ValueError("Features require at least four finite real samples in one dimension.")
    x=raw.astype(np.float64,copy=False)
    with np.errstate(over="raise",invalid="raise",divide="raise"):
        try:
            mean=x.mean()
            y=x-mean
            ac_rms=np.sqrt(np.mean(y*y))
            if ac_rms==0 or np.ptp(x)==0:
                raise ValueError("Flat window has undefined shape and spectral features.")
            z=y/ac_rms
            z2=z*z
            frequency,psd=periodogram(y,fs=rate,window="hann",detrend=False,
                                      nfft=len(y),return_onesided=True,scaling="density")
            # DC is excluded from the centroid and every fraction denominator.
            frequency,psd=frequency[1:],psd[1:]
            total=psd.sum()
            if total<=0: raise ValueError("Window has no positive-frequency power.")
            result=[mean,np.sqrt(np.mean(x*x)),ac_rms,np.ptp(x),np.max(np.abs(z)),
                    np.mean(z2*z),np.mean(z2*z2),np.sum(frequency*psd)/total]
            for low,high in BANDS:
                mask=(frequency>=low)&((frequency<=high) if high==rate/2 else (frequency<high))
                result.append(psd[mask].sum()/total)
        except FloatingPointError as exc:
            raise ValueError("Numerically undefined feature; no automatic imputation.") from exc
    if not np.isfinite(result).all():
        raise ValueError("Nonfinite feature; no automatic imputation.")
    return dict(zip(FEATURE_NAMES,map(float,result),strict=True))

def extract_windows(values, rate=25600, window_seconds=2., hop_seconds=1.):
    data=np.asarray(values)
    if data.ndim!=2 or data.shape[1]!=len(CHANNELS) or data.dtype.kind not in "fiu":
        raise ValueError("Feature input must be a real N x 5 matrix.")
    bounds=list(window_bounds(len(data),rate,window_seconds,hop_seconds))
    if not bounds: raise ValueError("Recording contains no complete window.")
    columns=[f"{channel}__{name}" for channel in CHANNELS for name in FEATURE_NAMES]
    result=np.empty((len(bounds),len(columns)),dtype=np.float64)
    for row,(start,stop) in enumerate(bounds):
        try:
            result[row]=[value for col in range(len(CHANNELS))
                         for value in channel_features(data[start:stop,col],rate).values()]
        except ValueError as exc:
            raise ValueError(f"Window {row} [{start}:{stop}]: {exc}") from exc
    return result,bounds,columns

