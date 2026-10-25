"""Which emails fire for a decision card. Deterministic, no LLM."""


def events_for(card, phase="morning"):
    if phase == "evening":
        return [("EVENING_RECAP", "info")]
    ev = [("DAILY_DIGEST", "info")]
    gf = set(card.get("gate_failed") or [])
    if card.get("decision") == "TRADE":
        ev.append(("TRADE_APPROVED", "alert"))
    if "redteam_veto" in gf:
        ev.append(("REDTEAM_VETO", "alert"))
    if "vix_stress" in gf:
        ev.append(("VIX_STRESS", "alert"))
    if gf & {"kill_switch", "rate_limit", "data_invalid"}:
        ev.append(("KILL_SWITCH", "critical"))
    return ev
