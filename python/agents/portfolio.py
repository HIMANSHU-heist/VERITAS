"""Portfolio Agent (code only): inverse-volatility weights across 4 stocks + correlation warning."""
import pandas as pd

from python.dataclock import load_frozen

NAMES = ["RELIANCE", "TCS", "HDFCBANK", "INFY"]


def portfolio(n=60):
    R = pd.DataFrame({k: load_frozen(k).set_index("date")["close"].pct_change() for k in NAMES}).dropna().tail(n)
    inv = 1 / R.std()
    w = inv / inv.sum()
    c = R.corr()
    pairs = [(a, b, round(float(c.loc[a, b]), 2)) for i, a in enumerate(NAMES) for b in NAMES[i + 1:]]
    avg = round(sum(p[2] for p in pairs) / len(pairs), 2)
    return {"weights": {k: round(float(v), 3) for k, v in w.items()}, "avg_corr": avg, "pairs": pairs,
            "flag": "HIGH_CORRELATION: treat as one bet" if avg > 0.6 else "diversified enough", "window_days": n}
