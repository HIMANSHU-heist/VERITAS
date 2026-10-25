from python.alerts.render import render
from python.alerts.rules import events_for


def card(**kw):
    base = {"date": "2026-10-13", "decision": "ABSTAIN", "gate_failed": ["redteam_veto"],
            "p_up": 0.7, "conformal_set": ["UP"], "edge_pct": 0.15, "counterfactual": None}
    base.update(kw)
    return base


def test_veto_fires_digest_and_veto():
    assert [k for k, _ in events_for(card())] == ["DAILY_DIGEST", "REDTEAM_VETO"]


def test_trade_alert():
    assert "TRADE_APPROVED" in [k for k, _ in events_for(card(decision="TRADE", gate_failed=[]))]


def test_kill_switch_critical():
    assert ("KILL_SWITCH", "critical") in events_for(card(gate_failed=["kill_switch"]))


def test_evening_only_recap():
    assert events_for(card(), "evening") == [("EVENING_RECAP", "info")]


def test_html_escaped_and_disclaimer():
    s, t, h = render("DAILY_DIGEST", card(counterfactual="<script>alert(1)</script>"), {})
    assert "<script>" not in h and "not investment advice" in t and "[DEMO" in s
