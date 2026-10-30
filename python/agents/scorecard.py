"""Scorecard Agent (code only): grades the LIVE model on settled days. Advisory."""


def scorecard(cards):
    cs = [c for c in cards if c.get("p_up") is not None]
    st = [c for c in cs if c.get("settled") and c.get("ret_oc_pct") is not None]
    tr = [c for c in st if c.get("decision") == "TRADE"]
    n_trade_cards = sum(1 for c in cs if c.get("decision") == "TRADE")
    out = {"n_cards": len(cards), "n_settled": len(st), "n_trades": len(tr),
           "abstain_rate": round(1 - n_trade_cards / len(cs), 3) if cs else None,
           "net_total": round(sum(float(c.get("net") or 0) for c in tr), 2),
           "win_rate": round(sum(1 for c in tr if (c.get("net") or 0) > 0) / len(tr), 3) if tr else None,
           "brier": None, "shadow_hit_rate": None, "status": "COLLECTING"}
    if st:
        brier = sum((c["p_up"] - (1.0 if c["ret_oc_pct"] > 0 else 0.0)) ** 2 for c in st) / len(st)
        hit = sum(1 for c in st if (c.get("ml_direction") == "BUY") == (c["ret_oc_pct"] > 0)) / len(st)
        out.update(brier=round(brier, 4), shadow_hit_rate=round(hit, 3))
    if len(st) >= 20:
        out["status"] = "BETTER_THAN_COIN" if out["brier"] < 0.25 else "NOT_BETTER_THAN_COIN"
    out["note"] = "Brier below 0.25 beats a coin flip. Needs 20+ settled days to mean anything."
    return out
