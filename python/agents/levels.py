"""Levels Agent (code only): classic pivots, ATR and 20-day range from NIFTY daily bars. Advisory."""
import pandas as pd

from python.dataclock import load_frozen


def levels(df=None, n=14):
    if df is None:
        df = load_frozen("NIFTY")
        df = df[df["available_at"] <= pd.Timestamp.now(tz="UTC")]
    df = df.dropna(subset=["high", "low", "close"]).reset_index(drop=True)
    if len(df) < n + 2:
        raise ValueError("not enough bars")
    h, l, c = (df[k].astype(float) for k in ("high", "low", "close"))
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(n).mean().iloc[-1])
    H, L, C = float(h.iloc[-1]), float(l.iloc[-1]), float(c.iloc[-1])
    p = (H + L + C) / 3
    hi20, lo20 = float(h.tail(20).max()), float(l.tail(20).min())
    pos = (C - lo20) / (hi20 - lo20) if hi20 > lo20 else 0.5
    where = "near 20-day high" if pos >= 0.8 else "near 20-day low" if pos <= 0.2 else "mid-range"
    atr_pct = atr / C * 100
    out = {"asof": str(df["date"].iloc[-1].date()), "close": C, "atr": atr, "atr_pct": atr_pct,
           "hi20": hi20, "lo20": lo20, "range_pos": pos, "where": where,
           "pivot": p, "r1": 2 * p - L, "s1": 2 * p - H, "r2": p + (H - L), "s2": p - (H - L),
           "suggested_stop_pct": 1.5 * atr_pct, "suggested_target_pct": 2.5 * atr_pct}
    return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in out.items()}
