"""Dynamic Risk Agent (code only): scales position size DOWN from VIX, drawdown, losing streak.
It can only reduce size. The C++ gate keeps final authority."""


def risk_scale(vix, cards, capital):
    s, why = 1.0, []
    if vix >= 25:
        s *= 0.5; why.append(f"VIX {vix:.1f} >= 25")
    elif vix >= 20:
        s *= 0.75; why.append(f"VIX {vix:.1f} >= 20")
    nets = [c.get("net", 0.0) for c in cards if c.get("decision") == "TRADE" and c.get("settled")]
    eq, peak, dd = 0.0, 0.0, 0.0
    for n in nets:
        eq += n; peak = max(peak, eq); dd = max(dd, peak - eq)
    dd_pct = dd / capital * 100
    if dd_pct >= 4:
        s *= 0.5; why.append(f"drawdown {dd_pct:.2f}% of capital (limit 8%)")
    streak = 0
    for n in reversed(nets):
        if n < 0: streak += 1
        else: break
    if streak >= 3:
        s *= 0.5; why.append(f"{streak} losing trades in a row")
    s = max(0.25, s)
    return {"scale": round(s, 2), "why": why or ["no stress signals"], "drawdown_pct": round(dd_pct, 3), "streak": streak}
