import pandas as pd

from python.agents.dataquality import data_quality
from python.agents.levels import levels
from python.agents.scorecard import scorecard


def bars(n=40, start=100.0):
    d = pd.date_range("2026-01-01", periods=n, freq="B")
    c = pd.Series([start + i * 0.5 for i in range(n)])
    return pd.DataFrame({"date": d, "open": c, "high": c + 1, "low": c - 1, "close": c})


def test_levels_order_and_range():
    r = levels(bars())
    assert r["s2"] < r["s1"] < r["pivot"] < r["r1"] < r["r2"]
    assert r["atr"] > 0 and 0 <= r["range_pos"] <= 1
    assert r["where"] == "near 20-day high"


def test_scorecard_empty_and_basic():
    assert scorecard([])["n_settled"] == 0
    cards = [{"date": f"d{i}", "p_up": 0.7, "ml_direction": "BUY",
              "decision": "TRADE" if i % 2 else "ABSTAIN", "settled": True,
              "ret_oc_pct": 0.5 if i < 8 else -0.5, "net": 10.0 if i % 2 else 0.0} for i in range(10)]
    r = scorecard(cards)
    assert r["n_settled"] == 10 and r["n_trades"] == 5
    assert abs(r["abstain_rate"] - 0.5) < 1e-9
    assert r["shadow_hit_rate"] == 0.8


def test_dataquality_flags_stale_and_jump():
    ok, jump = bars(), bars()
    jump.loc[len(jump) - 1, "close"] = jump["close"].iloc[-2] * 1.2
    today = ok["date"].iloc[-1]
    assert data_quality({"A": ok, "B": jump}, today=today)["status"] == "WARN"
    assert data_quality({"A": ok}, today=today + pd.Timedelta(days=10))["status"] == "BAD"
    assert data_quality({"A": ok}, today=today)["status"] == "OK"
