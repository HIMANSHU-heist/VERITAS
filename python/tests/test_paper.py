from datetime import date

from python.paper.engine import apply_fill, classify


def card(**kw):
    base = {"decision": "TRADE", "gate_failed": [], "ml_direction": "BUY", "edge_pct": 0.5, "p_up": 0.7}
    base.update(kw)
    return base


def test_tiers():
    assert classify(card())[0] == "AUTO"
    assert classify(card(edge_pct=0.2))[0] == "ASK"
    assert classify(card(decision="ABSTAIN", gate_failed=["redteam_veto"], edge_pct=0.2))[0] == "ASK"
    assert classify(card(decision="ABSTAIN", gate_failed=["conformal_ambiguous", "edge_below_cost"], edge_pct=-0.05))[0] == "NONE"


def test_hard_gates_never_ask():
    for g in ("vix_stress", "kill_switch", "data_invalid"):
        assert classify(card(decision="ABSTAIN", gate_failed=[g], edge_pct=0.9))[0] == "NONE"


def test_round_trip_loses_only_costs_and_conserves_cash():
    a = {"cash": 100000.0, "realized": 0.0, "holdings": {}}
    u, t = apply_fill(a, "BUY", 100, 200.0, date(2026, 10, 27))
    a2 = {**a, **u}
    assert a2["holdings"]["NIFTYBEES"]["qty"] == 100 and a2["cash"] < 100000 - 20000
    u2, t2 = apply_fill(a2, "SELL", 100, 200.0, date(2026, 10, 28))
    assert "NIFTYBEES" not in u2["holdings"] and t2["pnl"] < 0
    assert abs((100000 + t2["pnl"]) - u2["cash"]) < 0.05
