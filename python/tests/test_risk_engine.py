import pytest
from python.risk_client import RiskEngine


def order(**kw):
    base = dict(type="check_order", symbol="RELIANCE", side="BUY", price=2500.0,
                qty=5, expected_edge_pct=0.8, data_valid=True,
                conformal_singleton=True, disagreement=0.1,
                redteam_severity="LOW", vix=14.0, ts_ms=1000)
    base.update(kw)
    return base


@pytest.fixture
def eng():
    e = RiskEngine(audit_path="audit/test.jsonl")
    yield e
    e.close()


def test_good_trade_passes(eng):
    r = eng.send(order())
    assert r["decision"] == "TRADE" and r["gate_failed"] == []


def test_edge_below_cost_abstains(eng):
    r = eng.send(order(expected_edge_pct=0.05))
    assert r["decision"] == "ABSTAIN" and "edge_below_cost" in r["gate_failed"]
    assert "counterfactual" in r


def test_conformal_ambiguous_abstains(eng):
    r = eng.send(order(conformal_singleton=False))
    assert "conformal_ambiguous" in r["gate_failed"]


def test_redteam_high_vetoes(eng):
    r = eng.send(order(redteam_severity="HIGH"))
    assert r["decision"] == "ABSTAIN" and "redteam_veto" in r["gate_failed"]


def test_disagreement_and_vix_gates(eng):
    r = eng.send(order(disagreement=0.9, vix=40))
    assert "agent_disagreement" in r["gate_failed"] and "vix_stress" in r["gate_failed"]


def test_position_is_clipped(eng):
    r = eng.send(order(qty=100))
    assert r["position_clipped"] and r["qty_approved"] <= 8


def test_order_flood_trips_kill_switch(eng):
    last = None
    for i in range(8):
        last = eng.send(order(ts_ms=5000 + i))
    assert "kill_switch" in last["gate_failed"] and last["killed"]
    assert eng.send({"type": "status"})["killed"]


def test_daily_loss_trips_kill_switch(eng):
    r = eng.send({"type": "update_pnl", "pnl_inr": -25000})
    assert r["killed"] and r["kill_reason"] == "daily_loss_limit"
    assert "kill_switch" in eng.send(order())["gate_failed"]


def test_audit_chain_ok_then_tamper_detected(eng):
    for i in range(3):
        eng.send(order(ts_ms=i * 2000))
    assert eng.verify()["audit"] == "OK"
    txt = eng.audit_path.read_text()
    eng.audit_path.write_text(txt.replace('"RELIANCE"', '"TAMPERED"', 1))
    assert eng.verify()["audit"] == "BROKEN"