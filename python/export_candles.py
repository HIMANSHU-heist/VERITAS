"""NIFTY daily candles -> web/data/candles.json (dashboard chart)."""
import json

from python.dataclock import load_frozen
from python.risk_client import ROOT


def main():
    df = load_frozen("NIFTY").tail(420)
    has_vol = "volume" in df.columns
    out = []
    for _, r in df.iterrows():
        v = float(r["volume"]) if has_vol and r["volume"] == r["volume"] else None
        out.append({"time": str(r["date"].date()), "open": round(float(r["open"]), 2),
                    "high": round(float(r["high"]), 2), "low": round(float(r["low"]), 2),
                    "close": round(float(r["close"]), 2), "volume": v})
    p = ROOT / "web" / "data"
    p.mkdir(parents=True, exist_ok=True)
    (p / "candles.json").write_text(json.dumps(out))
    print(f"wrote web/data/candles.json | {len(out)} candles")


if __name__ == "__main__":
    main()
