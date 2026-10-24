"""Feature builder. Every feature row is joined to a decision time (08:30 IST = 03:00 UTC)
using each series' available_at, so no future data can enter."""
from __future__ import annotations

import numpy as np
import pandas as pd

from python.dataclock import load_frozen

DECISION_HOUR_UTC = 3  # 08:30 IST ~ 03:00 UTC
SERIES = ["NIFTY", "SP500", "NASDAQ", "NIKKEI", "CRUDE", "GOLD", "USDINR", "INDIAVIX"]


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def series_features(name: str, df: pd.DataFrame) -> pd.DataFrame:
    """Causal features only (rolling/pct_change look backwards)."""
    c = df["close"].astype(float)
    out = pd.DataFrame({"available_at": df["available_at"].values})
    r1 = c.pct_change(1)
    if name == "NIFTY":
        out["NIFTY_ret1"] = r1.values
        out["NIFTY_ret5"] = c.pct_change(5).values
        out["NIFTY_ret10"] = c.pct_change(10).values
        out["NIFTY_vol10"] = r1.rolling(10).std().values
        out["NIFTY_vol20"] = r1.rolling(20).std().values
        out["NIFTY_rsi14"] = _rsi(c).values
        out["NIFTY_ma20_ratio"] = (c / c.rolling(20).mean() - 1).values
        out["NIFTY_range1"] = ((df["high"] - df["low"]) / c).values
    elif name == "INDIAVIX":
        out["INDIAVIX_level"] = c.values
        out["INDIAVIX_chg1"] = r1.values
    else:
        out[f"{name}_ret1"] = r1.values
    return out


def _utc_ns(s: pd.Series) -> pd.Series:
    s = pd.to_datetime(s)
    s = s.dt.tz_localize("UTC") if s.dt.tz is None else s.dt.tz_convert("UTC")
    return s.astype("datetime64[ns, UTC]")


def build_dataset():
    nifty = load_frozen("NIFTY")
    dec = pd.DataFrame({
        "date": nifty["date"].values,
        "ret_oc": (nifty["close"] / nifty["open"] - 1).values,
    })
    dec["decision_time"] = _utc_ns(
        (pd.to_datetime(dec["date"]) + pd.Timedelta(hours=DECISION_HOUR_UTC)).dt.tz_localize("UTC")
    )
    X = dec.sort_values("decision_time").reset_index(drop=True)

    for name in SERIES:
        f = series_features(name, load_frozen(name))
        f["available_at"] = _utc_ns(f["available_at"])
        f = f.sort_values("available_at")
        X = pd.merge_asof(X, f, left_on="decision_time", right_on="available_at",
                          direction="backward")
        X = X.rename(columns={"available_at": f"avail_{name}"})

    # Leakage tripwire: every joined row must be available at decision time.
    for name in SERIES:
        col = f"avail_{name}"
        ok = X[col].isna() | (X[col] <= X["decision_time"])
        assert ok.all(), f"LEAK: {name} has rows available after decision time"

    feat_cols = [c for c in X.columns
                 if c not in ("date", "ret_oc", "decision_time") and not c.startswith("avail_")]
    X = X.dropna(subset=feat_cols + ["ret_oc"]).reset_index(drop=True)
    X["y"] = (X["ret_oc"] > 0).astype(int)
    return X, feat_cols