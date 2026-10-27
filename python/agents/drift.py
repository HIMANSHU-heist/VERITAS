"""Drift Monitor: is the model's recent accuracy / conformal coverage still healthy?"""
import joblib

from python.daily import qhat_from
from python.ml.conformal import coverage, prediction_sets
from python.ml.features import build_dataset
from python.risk_client import ROOT


def drift(n=60, alpha=0.10):
    X, _ = build_dataset()
    art = joblib.load(ROOT / "data" / "models" / "technical.joblib")
    r = X.tail(n)
    p = art["model"].predict_proba(r[art["features"]])
    y = r["y"].values
    acc = float((p.argmax(1) == y).mean())
    cov = coverage(prediction_sets(p, qhat_from(art["cal_scores"], alpha)), y)
    bad = cov < 1 - alpha - 0.10 or acc < 0.45
    return {"status": "DRIFT" if bad else "OK", "accuracy": round(acc, 3), "coverage": round(cov, 3),
            "target_coverage": 1 - alpha, "n": n,
            "action": "Retrain: python -m python.ml.train_technical && python -m python.live_artifacts" if bad else "No action"}
