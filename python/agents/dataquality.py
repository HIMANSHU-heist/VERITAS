"""Data Quality Agent (code only): stale bars, missing closes, duplicates and suspicious jumps."""
import pandas as pd

from python.dataclock import load_frozen

NAMES = ["NIFTY", "SP500", "NASDAQ", "NIKKEI", "CRUDE", "GOLD", "USDINR", "INDIAVIX",
         "RELIANCE", "TCS", "HDFCBANK", "INFY"]


def data_quality(frames=None, today=None):
    if today is None:
        today = pd.Timestamp.now(tz="UTC").tz_localize(None)
    today = pd.Timestamp(today).normalize()
    if frames is None:
        frames = {n: load_frozen(n) for n in NAMES}
    rows, issues, bad, warn = [], [], False, False
    for name, df in frames.items():
        df = df.sort_values("date").reset_index(drop=True)
        last = pd.Timestamp(df["date"].iloc[-1]).normalize()
        age = int((today - last).days)
        flags = []
        if age > 5:
            flags.append("stale"); bad = True
        c = df["close"].astype(float)
        if pd.isna(c.iloc[-1]):
            flags.append("missing_close"); bad = True
        if len(c) > 1 and c.iloc[-2]:
            jump = abs(c.iloc[-1] / c.iloc[-2] - 1)
            if jump > (0.30 if name == "INDIAVIX" else 0.08):
                flags.append(f"jump_{jump * 100:.1f}pct"); warn = True
        if df["date"].duplicated().any():
            flags.append("duplicate_dates"); bad = True
        rows.append({"name": name, "last": str(last.date()), "age_days": age, "rows": int(len(df)), "flags": flags})
        if flags:
            issues.append(f"{name}: {', '.join(flags)}")
    return {"status": "BAD" if bad else "WARN" if warn else "OK", "series": rows, "issues": issues}
