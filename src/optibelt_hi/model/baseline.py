"""Recording-balanced standardized Mahalanobis baseline."""
from dataclasses import dataclass
import numpy as np
from scipy.linalg import solve_triangular

def matrix(values, width=None):
    x=np.asarray(values)
    if x.ndim!=2 or not len(x) or x.dtype.kind not in "fiu" or not np.isfinite(x).all():
        raise ValueError("Expected a nonempty finite real feature matrix.")
    if width is not None and x.shape[1]!=width:
        raise ValueError("Feature width differs from fitted schema.")
    return x.astype(np.float64,copy=False)

@dataclass
class Model:
    names: list
    indices: np.ndarray
    mean: np.ndarray
    scale: np.ndarray
    covariance: np.ndarray
    diagnostics: dict

    @property
    def selected_names(self):
        return [self.names[i] for i in self.indices]

    def score(self, values):
        x=matrix(values,len(self.names))
        with np.errstate(over="raise",invalid="raise",divide="raise"):
            try:
                z=(x[:,self.indices]-self.mean)/self.scale
                solved=solve_triangular(np.linalg.cholesky(self.covariance),z.T,lower=True)
                distance=np.sqrt(np.sum(solved*solved,axis=0))
            except FloatingPointError as exc:
                raise ValueError("Numerically unrepresentable model input.") from exc
        if not np.isfinite(distance).all(): raise ValueError("Nonfinite model distance.")
        return distance

    def to_dict(self):
        return {"format_version":1,"names":list(self.names),"indices":self.indices.tolist(),
                "mean":self.mean.tolist(),"scale":self.scale.tolist(),
                "covariance":self.covariance.tolist(),"diagnostics":self.diagnostics}

    @classmethod
    def from_dict(cls,state):
        if state["format_version"]!=1: raise ValueError("Unsupported model format.")
        raw_indices=np.asarray(state["indices"])
        if raw_indices.ndim!=1 or raw_indices.dtype.kind not in "iu":
            raise ValueError("Invalid feature indices.")
        indices=raw_indices.astype(int)
        mean=np.asarray(state["mean"],dtype=float); scale=np.asarray(state["scale"],dtype=float)
        covariance=np.asarray(state["covariance"],dtype=float); names=state["names"]; n=len(indices)
        if not n or mean.shape!=(n,) or scale.shape!=(n,) or covariance.shape!=(n,n):
            raise ValueError("Invalid model dimensions.")
        if len(set(names))!=len(names) or len(set(indices))!=n or np.any(indices<0) or np.any(indices>=len(names)):
            raise ValueError("Invalid model schema.")
        if not all(np.isfinite(x).all() for x in (mean,scale,covariance)) or np.any(scale<=0):
            raise ValueError("Invalid model values.")
        if not np.allclose(covariance,covariance.T,rtol=1e-12,atol=1e-12):
            raise ValueError("Covariance must be symmetric.")
        np.linalg.cholesky(covariance)
        return cls(list(names),indices,mean,scale,covariance,state["diagnostics"])

def fit_model(records, names, *, kind="shrinkage", shrinkage=.1, correlation_limit=.98,
              relative_scale_floor=1e-12, drop_suffixes=("rms","power_fraction_5000_12800")):
    if kind not in {"shrinkage","diagonal"} or not 0<shrinkage<=1 or not 0<correlation_limit<=1 or relative_scale_floor<=0:
        raise ValueError("Invalid fitting settings.")
    if not records or not names or len(set(names))!=len(names):
        raise ValueError("Need unique feature names and healthy records.")
    arrays=[matrix(r,len(names)) for r in records]
    x=np.concatenate(arrays)
    weights=np.concatenate([np.full(len(a),1/(len(arrays)*len(a))) for a in arrays])
    weights/=weights.sum()
    with np.errstate(over="raise",invalid="raise",divide="raise"):
        try:
            means=weights@x
            centred=x-means
            scales=np.sqrt(weights@(centred*centred))
            magnitude=np.sqrt(weights@(x*x))
        except FloatingPointError as exc:
            raise ValueError("Numerically invalid fitting values.") from exc
    dropped=[]; candidates=[]
    for i,name in enumerate(names):
        suffix=name.split("__")[-1]
        if suffix in drop_suffixes: reason="defined_redundancy"
        elif scales[i]<=relative_scale_floor*max(1.,magnitude[i]): reason="numerically_constant"
        else:
            candidates.append(i)
            continue
        dropped.append({"name":name,"reason":reason})
    if not candidates: raise ValueError("No nonconstant features remain.")
    z=(x[:,candidates]-means[candidates])/scales[candidates]
    corr=(z*weights[:,None]).T@z
    selected=[]
    for i in range(len(candidates)):
        conflict=next((j for j in selected if abs(corr[i,j])>=correlation_limit),None)
        if conflict is None: selected.append(i)
        else: dropped.append({"name":names[candidates[i]],
            "reason":"correlated_with:"+names[candidates[conflict]],
            "absolute_correlation":float(abs(corr[i,conflict]))})
    indices=np.array([candidates[i] for i in selected],dtype=int)
    covariance=corr[np.ix_(selected,selected)]
    covariance=(covariance+covariance.T)/2
    regularized=(1-shrinkage)*covariance+shrinkage*np.eye(len(indices)) if kind=="shrinkage" else np.eye(len(indices))
    eig=np.linalg.eigvalsh(covariance); regeig=np.linalg.eigvalsh(regularized)
    diagnostics={"recordings":len(arrays),"windows":len(x),"windows_per_recording":[len(a) for a in arrays],
        "recording_weighting":"equal","kind":kind,"shrinkage":shrinkage if kind=="shrinkage" else 1.,
        "correlation_limit":correlation_limit,"relative_scale_floor":relative_scale_floor,
        "input_features":len(names),"selected_features":len(indices),"dropped":dropped,
        "unregularized_rank":int(np.linalg.matrix_rank(covariance)),
        "unregularized_min_eigenvalue":float(eig[0]),"unregularized_max_eigenvalue":float(eig[-1]),
        "unregularized_condition":float(eig[-1]/eig[0]) if eig[0]>0 else None,
        "regularized_min_eigenvalue":float(regeig[0]),"regularized_max_eigenvalue":float(regeig[-1]),
        "regularized_condition":float(regeig[-1]/regeig[0])}
    np.linalg.cholesky(regularized)
    return Model(list(names),indices,means[indices],scales[indices],regularized,diagnostics)

