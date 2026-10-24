import json
from types import SimpleNamespace

import pytest

import python.llm as llm
from python.backtest import load_setup, run_backtest
from python.orchestrator import reconcile
from python.pipeline import run_pipeline
from python.risk_client import ROOT
from python.schemas import ProposalOut

EXE = ROOT / "cpp" / "build" / "risk_engine"
pytestmark = pytest.mark.skipif(not EXE.exists(), reason="build the C++ engine first")


class Fake:
    """Agreeing LLM: strategist echoes the ML direction, red-team has no objections."""

    def __init__(self, garbage=False):
        self.calls = 0
        self.garbage = garbage
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls += 1
        system, user = kw["messages"][0]["content"], kw["messages"][1]["content"]
        if self.garbage:
            txt = "not json"
        elif "strategist" in system:
            d = json.loads(user)
            txt = json.dumps({"action": d["ml"]["direction"], "size_pct": 1.0, "thesis": "agree", "evidence_ids": []})
        elif "red-team" in system:
            txt = json.dumps({"objections": [], "recommend_veto": False})
        else:
            txt = json.dumps({"score": 0.0, "confidence": 0.0, "top_drivers": [], "reason": "fake"})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=txt))])


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CACHE", tmp_path)
    monkeypatch.setattr(llm, "MIN_INTERVAL_S", 0.0)


def test_llm_layer_can_only_remove_trades_and_runs_only_on_candidates():
    s = load_setup()
    f = Fake()
    p = run_pipeline(setup=s, llm=llm.LLM(client=f), tag="t_pipe")
    b = run_backtest(alpha=0.10, setup=s, write=False, tag="t_pipe_ref")
    p_dates = {c["date"] for c in p["cards"] if c["decision"] == "TRADE"}
    b_dates = {c["date"] for c in b["cards"] if c["decision"] == "TRADE"}
    assert p_dates <= b_dates
    assert f.calls <= 3 * p["stats"]["candidates"]
    assert len(p["cards"]) == p["n_days"] and p["audit"]["audit"] == "OK"


def test_llm_failure_fails_closed():
    s = load_setup()
    p = run_pipeline(setup=s, llm=llm.LLM(client=Fake(garbage=True)), tag="t_pipe_bad")
    assert p["pipeline"]["n_trades"] == 0
    assert p["stats"]["llm_errors"] == p["stats"]["candidates"] > 0


def test_llm_cannot_flip_direction():
    flipped, was = reconcile(ProposalOut(action="BUY", size_pct=2.0, thesis="x"), "SELL")
    assert was and flipped.action == "WAIT" and flipped.size_pct == 0.0
    same, was = reconcile(ProposalOut(action="SELL", size_pct=1.0, thesis="x"), "SELL")
    assert not was and same.action == "SELL"
