"""Regime Agent (code only): trending / sideways / volatile -> confidence multiplier."""
MULT = {"TRENDING": 1.0, "SIDEWAYS": 0.8, "VOLATILE": 0.6}


def regime(row):
    vix, v10 = float(row["INDIAVIX_level"]), float(row["NIFTY_vol10"])
    ma, r10 = float(row["NIFTY_ma20_ratio"]), float(row["NIFTY_ret10"])
    if vix >= 22 or v10 >= 0.012:
        lab, why = "VOLATILE", f"VIX {vix:.1f}, 10-day vol {v10 * 100:.2f}%"
    elif abs(ma) >= 0.02 and ma * r10 > 0:
        lab, why = "TRENDING", f"{ma * 100:+.1f}% vs 20-day average, 10-day return {r10 * 100:+.1f}%"
    else:
        lab, why = "SIDEWAYS", f"{ma * 100:+.1f}% vs 20-day average, no clear trend"
    return {"label": lab, "conf_mult": MULT[lab], "why": why}


def adjust_p_up(p_up, mult):
    return round(0.5 + (p_up - 0.5) * mult, 4)
