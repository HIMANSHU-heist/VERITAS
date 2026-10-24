"""DataClock: point-in-time data firewall.

Every bar gets an `available_at` (UTC). Agents only ever see rows where
available_at <= decision time. Simplified conservative assumptions:
  - Indian assets: bar available 15:45 IST (10:15 UTC) on the bar's date.
  - Everything else (US, Asia, commodities, FX): available at 00:00 UTC
    on the NEXT calendar day (so the bar has surely closed).
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

FROZEN = Path(__file__).resolve().parent.parent / "data" / "frozen"

INDIA = {"NIFTY", "RELIANCE", "TCS", "HDFCBANK", "INFY", "INDIAVIX"}
INDIA_LAG = pd.Timedelta(hours=10, minutes=15)
OTHER_LAG = pd.Timedelta(days=1)


class LeakageError(Exception):
    pass


def to_utc(ts) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def load_frozen(name: str) -> pd.DataFrame:
    df = pd.read_parquet(FROZEN / f"{name}.parquet")
    d = pd.to_datetime(df["date"])
    if getattr(d.dt, "tz", None) is not None:
        d = d.dt.tz_localize(None)
    df["date"] = d.dt.normalize()
    lag = INDIA_LAG if name in INDIA else OTHER_LAG
    df["available_at"] = (df["date"] + lag).dt.tz_localize("UTC")
    return df.sort_values("date").reset_index(drop=True)


class DataClock:
    def __init__(self, names):
        self.frames = {n: load_frozen(n) for n in names}
        self.log: list[dict] = []   # audit trail of every data request

    def get(self, name: str, as_of) -> pd.DataFrame:
        t = to_utc(as_of)
        df = self.frames[name]
        visible = df[df["available_at"] <= t]
        self.log.append({
            "series": name,
            "as_of": t.isoformat(),
            "rows_visible": int(len(visible)),
            "rows_hidden_future": int(len(df) - len(visible)),
        })
        return visible.copy()

    def snapshot(self, as_of) -> dict[str, pd.DataFrame]:
        return {n: self.get(n, as_of) for n in self.frames}

    def check_text(self, text: str, as_of) -> bool:
        """Tripwire: reject any prompt/text that mentions a date after as_of."""
        t = to_utc(as_of)
        for m in re.findall(r"\d{4}-\d{2}-\d{2}", text):
            if pd.Timestamp(m, tz="UTC") > t:
                raise LeakageError(f"Future date {m} found in text, as_of={t.date()}")
        return True
