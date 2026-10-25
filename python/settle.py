"""After the close: attach the real NIFTY outcome to today's live card (paper P&L)."""
import json
import sys

import pandas as pd

from python.daily import ist_today, save_card
from python.dataclock import load_frozen
from python.risk_client import ROOT


def main():
    p = ROOT / "data" / "live_cards.jsonl"
    cards = [json.loads(l) for l in open(p)] if p.exists() else []
    today = str(ist_today())
    if not cards or cards[-1]["date"] != today:
        sys.exit(f"no live card for {today}; refusing to settle an older card")
    card = cards[-1]
    nf = load_frozen("NIFTY")
    r = nf[nf["date"] == pd.Timestamp(today)]
    if r.empty:
        card.update(settled=False, net=0.0, outcome="No NIFTY bar for this date (market closed or data missing)")
    else:
        ret = float(r["close"].iloc[0]) / float(r["open"].iloc[0]) - 1.0
        card.update(settled=True, ret_oc_pct=round(ret * 100, 3))
        if card["decision"] == "TRADE":
            gross = card["side"] * ret * card["qty"] * card["price"]
            card.update(gross=round(gross, 2), net=round(gross - card["cost"], 2))
        else:
            card["net"] = 0.0
    save_card(card)
    print({k: card.get(k) for k in ("date", "decision", "settled", "ret_oc_pct", "net", "outcome")})


if __name__ == "__main__":
    main()
