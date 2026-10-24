import numpy as np
import pandas as pd

from python.dataclock import DataClock
from python.ml.conformal import calibrate, coverage, prediction_sets
from python.ml.features import SERIES, build_dataset, series_features


def test_dataset_has_no_leakage():
    X, feats = build_dataset()   # asserts internally
    for name in SERIES:
        col = f"avail_{name}"
        assert (X[col] <= X["decision_time"]).all()
    assert len(X) > 500 and len(feats) >= 15


def test_vectorized_features_match_dataclock_truncation():
    """Recompute features from ONLY what DataClock exposes at that moment; must match."""
    X, feats = build_dataset()
    dc = DataClock(SERIES)
    for idx in (200, 600, 900):
        row = X.iloc[idx]
        snap = dc.snapshot(row["decision_time"])
        for name in SERIES:
            f = series_features(name, snap[name]).iloc[-1]
            for col in [c for c in feats if c.startswith(name + "_")]:
                assert np.isclose(f[col], row[col], equal_nan=True), (idx, col)


def test_conformal_coverage_on_exchangeable_data():
    rng = np.random.default_rng(0)

    def make(n):
        z = rng.normal(size=n)
        p1 = 1 / (1 + np.exp(-1.2 * z))
        y = (rng.uniform(size=n) < p1).astype(int)
        p = np.c_[1 - p1, p1]
        return p, y

    p_cal, y_cal = make(4000)
    p_te, y_te = make(4000)
    for a in (0.1, 0.2, 0.3):
        S = prediction_sets(p_te, calibrate(p_cal, y_cal, a))
        assert coverage(S, y_te) >= 1 - a - 0.03


def test_ambiguous_prediction_is_not_singleton():
    p = np.array([[0.5, 0.5]])
    q = np.array([0.6, 0.6])
    S = prediction_sets(p, q)
    assert S.sum() == 2   # both classes plausible => abstain