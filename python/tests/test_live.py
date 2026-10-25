import json

import numpy as np
import pytest
from sklearn.isotonic import IsotonicRegression

from python.backtest import load_setup
from python.daily import decide, load_art, qhat_from
from python.ml.conformal import calibrate
from python.risk_client import ROOT

EXE = ROOT / "cpp" / "build" / "risk_engine"
ART = ROOT / "data" / "models" / "live.joblib"
pytestmark = pytest.mark.skipif(not (EXE.exists() and ART.exists()), reason="needs C++ build and live.joblib")
PRE = {"conformal_ambiguous", "edge_below_cost", "vix_stress", "agent_disagreement"}


@pytest.fixture(scope="module")
def setup():
    return load_setup()


def test_qhat_from_saved_scores_matches_calibrate(setup):
    art = load_art()
    for a in (0.05, 0.10, 0.20):
        assert np.allclose(qhat_from(art["cal_scores"], a), calibrate(setup["p_ca"], setup["y_ca"], a))


def test_saved_isotonic_matches_sklearn(setup):
    art = load_art()
    p = setup["p_ca"][:, 1]
    iso = IsotonicRegression(increasing=True, out_of_bounds="clip").fit(
        np.abs(2 * p - 1), np.where(p >= 0.5, 1, -1) * setup["ret_ca"])
    x = np.abs(2 * setup["p_te"][:, 1] - 1)
    assert np.allclose(iso.predict(x), np.interp(x, art["iso_x"], art["iso_y"]))


def test_live_path_reproduces_backtest_before_the_llm():
    art = load_art()
    cards = [json.loads(l) for l in open(ROOT / "results" / "pipeline_cards.jsonl")][::20]
    assert len(cards) >= 10
    for c in cards:
        live = decide(f"{c['date']} 03:00:00+00:00", use_llm=False, art=art, audit="audit/test_live.jsonl")
        assert live["p_up"] == c["p_up"] and live["conformal_set"] == c["conformal_set"]
        assert live["edge_pct"] == c["edge_pct"] and live["ml_direction"] == c["ml_direction"]
        assert live["cue_score"] == c["cue_score"]
        assert set(live["gate_failed"]) & PRE == set(c["gate_failed"]) & PRE
