"""Glue: agent outputs -> order request for the C++ risk engine (the only thing that can approve a trade)."""
from __future__ import annotations


def severity(red) -> str:
    rank = {"LOW": 0, "MED": 1, "HIGH": 2}
    s = max((rank[o.severity] for o in red.objections), default=0)
    if red.recommend_veto:
        s = 2
    return ["LOW", "MED", "HIGH"][s]


def order_request(proposal, red, her, ml, price, vix, ts_ms, data_valid=True):
    """Returns None when the strategy itself says WAIT."""
    if proposal.action == "WAIT":
        return None
    return {
        "type": "check_order", "symbol": "NIFTYBEES",
        "side": "BUY" if proposal.action == "BUY" else "SELL",
        "price": price, "qty": int(20000 // price),
        "expected_edge_pct": ml["edge_pct"], "data_valid": data_valid,
        "conformal_singleton": ml["singleton"], "disagreement": her["disagreement"],
        "redteam_severity": severity(red), "vix": vix, "ts_ms": ts_ms,
    }
