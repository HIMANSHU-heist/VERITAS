"""Veto Quality Tracker: how much did the red-team save (or cost) on the days it vetoed?

For every day where ML+gates said TRADE but the red-team vetoed, rebuild the trade that
WOULD have happened and compute its net P&L (real C++ costs). Output: results/veto_report.json
"""
from __future__ import annotations

import json

import pandas as pd
import yaml

from python.backtest import ETF_DIVISOR
from python.dataclock import load_frozen
from python.risk_client import ROOT, RiskEngine


def main():
    cards = [json.loads(l) for l in open(ROOT / "results" / "pipeline_cards.jsonl")]
    vetoed = [c for c in cards if "redteam_veto" in (c.get("gate_failed") or [])]

    nf = load_frozen("NIFTY").set_index("date")
    limits = yaml.safe_load(open(ROOT / "configs" / "limits.yaml"))
    pos_val = float(limits["starting_capital_inr"]) * float(limits["max_position_pct"]) / 100.0

    eng = RiskEngine(audit_path="audit/veto_report.jsonl")
    rows = []
    for c in vetoed:
        d = pd.Timestamp(c["date"])
        if d not in nf.index:
            continue
        i = nf.index.get_loc(d)
        if i == 0:
            continue
        ret = float(nf["close"].iloc[i] / nf["open"].iloc[i] - 1.0)
        price = float(nf["close"].iloc[i - 1]) / ETF_DIVISOR
        qty = float(int(pos_val // price))
        side = 1 if c["ml_direction"] == "BUY" else -1
        gross = side * ret * qty * price
        eng.send({"type": "new_day"})
        r = eng.send({"type": "check_order", "symbol": "NIFTYBEES",
                      "side": "BUY" if side > 0 else "SELL", "price": price, "qty": int(qty),
                      "expected_edge_pct": 1.0, "data_valid": True, "conformal_singleton": True,
                      "disagreement": 0.0, "redteam_severity": "LOW", "vix": 15.0,
                      "ts_ms": 1_000_000 + len(rows) * 100_000})
        cost = float(r["round_trip_cost_inr"])
        net = gross - cost
        rows.append({"date": c["date"], "side": "BUY" if side > 0 else "SELL",
                     "ret_oc_pct": round(ret * 100, 3), "gross": round(gross, 2),
                     "cost": round(cost, 2), "would_be_net": round(net, 2),
                     "veto_was": "GOOD" if net < 0 else "BAD"})
    eng.close()

    saved = -sum(r["would_be_net"] for r in rows if r["would_be_net"] < 0)
    missed = sum(r["would_be_net"] for r in rows if r["would_be_net"] > 0)
    total = sum(r["would_be_net"] for r in rows)
    good = sum(1 for r in rows if r["veto_was"] == "GOOD")
    out = {"n_vetoes": len(rows), "good_vetoes": good,
           "good_veto_rate": round(good / len(rows), 3) if rows else None,
           "loss_avoided_inr": round(saved, 2), "profit_missed_inr": round(missed, 2),
           "net_effect_inr": round(-total, 2),
           "note": "net_effect_inr > 0 means vetoing the trades was better than taking them",
           "days": rows}
    (ROOT / "results" / "veto_report.json").write_text(json.dumps(out, indent=2))
    print(f"vetoes: {out['n_vetoes']} | good: {good} ({out['good_veto_rate']})")
    print(f"loss avoided: INR {out['loss_avoided_inr']} | profit missed: INR {out['profit_missed_inr']}")
    print(f"NET effect of red-team: INR {out['net_effect_inr']:+}")


if __name__ == "__main__":
    main()
