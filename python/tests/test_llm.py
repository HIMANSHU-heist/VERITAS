import json
from types import SimpleNamespace

import pytest

import python.llm as llm
from python.dataclock import DataClock, LeakageError
from python.schemas import CueOut

GOOD = json.dumps({"score": 0.3, "confidence": 0.6, "top_drivers": ["SP500_ret1"], "reason": "US up"})
BAD_RANGE = json.dumps({"score": 5, "confidence": 0.6, "top_drivers": [], "reason": "x"})
AS_OF = "2024-03-12 03:00:00+00:00"


class Fake:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls += 1
        txt = self.replies.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=txt))])


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CACHE", tmp_path)
    monkeypatch.setattr(llm, "MIN_INTERVAL_S", 0.0)


def test_second_identical_call_hits_cache():
    f = Fake([GOOD])
    m = llm.LLM(client=f)
    a = m.call_json("fast", "sys", "usr", CueOut)
    b = m.call_json("fast", "sys", "usr", CueOut)
    assert a == b and f.calls == 1 and m.stats["cache_hit"] == 1


def test_fenced_json_is_extracted():
    m = llm.LLM(client=Fake(["```json\n" + GOOD + "\n```"]))
    assert m.call_json("fast", "s", "u", CueOut).score == 0.3


def test_invalid_then_valid_retries_once():
    f = Fake(["not json at all", GOOD])
    out = llm.LLM(client=f).call_json("fast", "s", "u", CueOut)
    assert out.confidence == 0.6 and f.calls == 2


def test_schema_violation_twice_raises():
    with pytest.raises(llm.LLMError):
        llm.LLM(client=Fake([BAD_RANGE, BAD_RANGE])).call_json("fast", "s", "u", CueOut)


def test_replay_mode_uses_cache_and_never_calls_api():
    llm.LLM(client=Fake([GOOD])).call_json("fast", "s", "u", CueOut)
    f2 = Fake([])
    out = llm.LLM(client=f2, mode="replay").call_json("fast", "s", "u", CueOut)
    assert out.score == 0.3 and f2.calls == 0


def test_replay_miss_raises():
    with pytest.raises(llm.ReplayMiss):
        llm.LLM(client=Fake([]), mode="replay").call_json("fast", "s", "new prompt", CueOut)


def test_leakage_tripwire_blocks_future_dates():
    m = llm.LLM(client=Fake([GOOD]), clock=DataClock(["NIFTY"]))
    with pytest.raises(LeakageError):
        m.call_json("fast", "s", "Nifty closed on 2024-03-14", CueOut, as_of=AS_OF)
