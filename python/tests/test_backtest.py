import pytest

from python.backtest import load_setup, run_backtest


@pytest.fixture(scope="module")
def res():
    s = load_setup()
    return run_backtest(alpha=0.10, setup=s, write=False, tag="test"), s


def test_every_day_is_accounted_for(res):
    r, _ = res
    assert r["gated"]["n_trades"] + r["n_abstain"] == r["n_days"]
    assert len(r["cards"]) == r["n_days"]


def test_gated_never_trades_more_than_naive(res):
    r, _ = res
    assert r["gated"]["n_trades"] <= r["every_day"]["n_trades"]


def test_pnl_identity_gross_minus_cost_is_net(res):
    r, _ = res
    for k in ("gated", "every_day"):
        assert abs(r[k]["gross_pnl"] - r[k]["cost"] - r[k]["net_pnl"]) < 0.05


def test_every_trade_pays_costs(res):
    r, _ = res
    for c in r["cards"]:
        if c["decision"] == "TRADE":
            assert c["cost"] > 0


def test_cards_are_only_in_test_window(res):
    r, s = res
    start = str(s["te"]["date"].min().date())
    assert all(c["date"] >= start for c in r["cards"])


def test_abstain_cards_have_reasons(res):
    r, _ = res
    for c in r["cards"]:
        if c["decision"] == "ABSTAIN":
            assert len(c["gate_failed"]) >= 1


def test_audit_chain_verifies(res):
    r, _ = res
    assert r["audit"]["audit"] == "OK"
    assert r["audit"]["lines"] >= r["n_days"]


def test_deterministic(res):
    r, s = res
    r2 = run_backtest(alpha=0.10, setup=s, write=False, tag="test2")
    assert r2["gated"]["net_pnl"] == r["gated"]["net_pnl"]
    assert r2["every_day"]["n_trades"] == r["every_day"]["n_trades"]
