"""Empirical thresholds, bounded health score and causal EWMA."""
import numpy as np

def vector(values, nonnegative=False):
    x=np.asarray(values)
    if x.ndim!=1 or not len(x) or x.dtype.kind not in "fiu" or not np.isfinite(x).all():
        raise ValueError("Expected nonempty finite real scores.")
    x=x.astype(np.float64,copy=False)
    if nonnegative and np.any(x<0): raise ValueError("Distance must be nonnegative.")
    return x

def calibrate(records, quantile=.99):
    if not records or not 0<quantile<=1: raise ValueError("Invalid calibration population or quantile.")
    values=[vector(r,nonnegative=True) for r in records]
    x=np.concatenate(values)
    w=np.concatenate([np.full(len(r),1/(len(values)*len(r))) for r in values])
    order=np.argsort(x,kind="stable")
    cdf=np.cumsum(w[order]); cdf/=cdf[-1]
    index=min(int(np.searchsorted(cdf,quantile,side="left")),len(x)-1)
    threshold=float(x[order[index]])
    if threshold<=0: raise ValueError("Calibration threshold must be positive.")
    return threshold

def health_index(distance, threshold):
    x=vector(distance,nonnegative=True)
    if not np.isfinite(threshold) or threshold<=0: raise ValueError("Threshold must be finite and positive.")
    # Stable equivalent of 100/(1+(d/q)^2), even for very large d.
    return 100*(threshold/np.hypot(x,threshold))**2

def ewma(distance, alpha=.2):
    x=vector(distance)
    if not 0<alpha<=1: raise ValueError("EWMA alpha must be in (0,1].")
    result=np.empty_like(x); result[0]=x[0]
    for i in range(1,len(x)):
        result[i]=alpha*x[i]+(1-alpha)*result[i-1]
    return result

def persistent_alarm(above, count=3):
    flags=np.asarray(above)
    if flags.ndim!=1 or flags.dtype.kind!="b" or isinstance(count,bool) or not isinstance(count,int) or count<1:
        raise ValueError("Expected boolean flags and positive integer persistence.")
    result=np.zeros(len(flags),dtype=bool); streak=0
    for i,flag in enumerate(flags):
        streak=streak+1 if flag else 0
        result[i]=streak>=count
    return result

