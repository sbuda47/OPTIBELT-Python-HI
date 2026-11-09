import json
import numpy as np
import pytest

def fit_api():
    from optibelt_hi.model.baseline import fit_model, Model
    return fit_model, Model

def test_equal_record_weights_and_repeated_windows():
    fit,_=fit_api()
    records=[np.array([[0.],[2.]]),np.array([[10.]])]
    a=fit(records,["value"]); b=fit([np.repeat(records[0],9,axis=0),records[1]],["value"])
    assert a.mean[0]==pytest.approx(5.5)
    assert a.scale[0]==pytest.approx(np.sqrt(20.75))
    np.testing.assert_allclose(a.score(np.array([[4.],[20.]])),b.score(np.array([[4.],[20.]])))
    assert a.diagnostics["recordings"]==2

def test_selection_removes_defined_redundancy_constant_and_correlated():
    fit,_=fit_api()
    t=np.arange(10,dtype=float)
    x=np.column_stack([t,t+2,2*t,np.ones(10),(-1.)**t])
    model=fit([x],["vibration__ac_rms","vibration__rms","duplicate","flat","independent"])
    assert model.selected_names==["vibration__ac_rms","independent"]
    reasons={r["name"]:r["reason"] for r in model.diagnostics["dropped"]}
    assert reasons["vibration__rms"]=="defined_redundancy"
    assert reasons["flat"]=="numerically_constant"
    assert reasons["duplicate"].startswith("correlated_with")

def test_distance_matches_direct_quadratic_form_and_roundtrip():
    fit,Model=fit_api()
    rng=np.random.default_rng(13)
    x=rng.normal(size=(300,4)); x[:,1]+=.5*x[:,0]
    model=fit([x],["a","b","c","d"])
    query=rng.normal(size=(8,4))
    z=(query[:,model.indices]-model.mean)/model.scale
    expected=np.sqrt(np.einsum("ij,ij->i",z,np.linalg.solve(model.covariance,z.T).T))
    np.testing.assert_allclose(model.score(query),expected,rtol=1e-12)
    loaded=Model.from_dict(json.loads(json.dumps(model.to_dict(),allow_nan=False)))
    np.testing.assert_allclose(loaded.score(query),expected)
    assert model.diagnostics["regularized_min_eigenvalue"]>=.1-1e-12

def test_centre_is_zero_and_diagonal_is_standardized_euclidean():
    fit,_=fit_api()
    x=np.array([[0.,1.],[2.,0.],[4.,3.],[6.,2.]])
    model=fit([x],["a","b"],kind="diagonal")
    assert model.score(x.mean(axis=0,keepdims=True))[0]==pytest.approx(0)
    z=(x[:,model.indices]-model.mean)/model.scale
    np.testing.assert_allclose(model.score(x),np.linalg.norm(z,axis=1))

@pytest.mark.parametrize("records", [[],[np.ones((3,2))],[np.array([[1.,np.nan],[2.,3.]])],[np.empty((0,2))],[np.ones((3,2)),np.ones((3,3))]])
def test_bad_training_inputs_fail(records):
    fit,_=fit_api()
    with pytest.raises(ValueError): fit(records,["a","b"])

def test_test_scoring_does_not_change_fitted_state():
    fit,_=fit_api()
    rng=np.random.default_rng(5); model=fit([rng.normal(size=(20,3))],["a","b","c"])
    before=json.dumps(model.to_dict(),sort_keys=True)
    model.score(np.ones((5,3))*100000)
    assert json.dumps(model.to_dict(),sort_keys=True)==before
    with pytest.raises(ValueError): model.score(np.ones((5,2)))

