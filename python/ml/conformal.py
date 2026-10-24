"""Class-conditional (Mondrian) split conformal classification."""
from __future__ import annotations

import math

import numpy as np


def calibrate(p_cal, y_cal, alpha):
    """Return qhat[k] per class. Score = 1 - p(true class)."""
    n_classes = p_cal.shape[1]
    qhat = np.ones(n_classes)
    for k in range(n_classes):
        s = 1.0 - p_cal[y_cal == k, k]
        n = len(s)
        if n == 0:
            qhat[k] = 1.0
            continue
        level = min(1.0, math.ceil((n + 1) * (1.0 - alpha)) / n)
        qhat[k] = np.quantile(s, level, method="higher")
    return qhat


def prediction_sets(p, qhat):
    """Boolean matrix (n, n_classes): class k is in the set if 1 - p_k <= qhat_k."""
    return (1.0 - p) <= qhat[None, :]


def coverage(sets, y):
    return float(sets[np.arange(len(y)), y].mean())
