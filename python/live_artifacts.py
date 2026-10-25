"""One-time freeze of everything the live path needs, from the SAME data and split as the backtest."""
import joblib
import numpy as np
from sklearn.isotonic import IsotonicRegression

from python.agents import CueModel
from python.backtest import load_setup
from python.risk_client import ROOT


def main():
    s = load_setup()
    p = s["p_ca"][:, 1]
    iso = IsotonicRegression(increasing=True, out_of_bounds="clip").fit(
        np.abs(2 * p - 1), np.where(p >= 0.5, 1, -1) * s["ret_ca"])
    tech = joblib.load(ROOT / "data" / "models" / "technical.joblib")
    out = {"iso_x": iso.X_thresholds_.tolist(), "iso_y": iso.y_thresholds_.tolist(),
           "cue_model": CueModel().fit(), "features": tech["features"],
           "cal_scores": tech["cal_scores"]}
    joblib.dump(out, ROOT / "data" / "models" / "live.joblib")
    print("saved data/models/live.joblib | iso knots:", len(out["iso_x"]), "| features:", len(out["features"]))


if __name__ == "__main__":
    main()
