"""Backend -> frontend contract: results/*.json(l) -> web/data/data.json."""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from python.dataclock import load_frozen

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "data"


def _jsonl(p):
    return [json.loads(l) for l in open(p)]


def _cum(cards):
    return np.round(np.cumsum([c.get("net", 0.0) if c["decision"] == "TRADE" else 0.0 for c in cards]), 2).tolist()


def build():
    bt = json.loads((ROOT / "results" / "summary.json").read_text())
    pp = json.loads((ROOT / "results" / "pipeline_summary.json").read_text())
    base = _jsonl(ROOT / "results" / "cards.jsonl")
    cards = _jsonl(ROOT / "results" / "pipeline_cards.jsonl")
    assert [c["date"] for c in base] == [c["date"] for c in cards], "card dates differ"
    dates = [c["date"] for c in cards]
    lim = yaml.safe_load(open(ROOT / "configs" / "limits.yaml"))
    pos = float(lim["starting_capital_inr"]) * float(lim["max_position_pct"]) / 100.0

    nf = load_frozen("NIFTY")
    w = nf[(nf["date"] >= pd.Timestamp(dates[0])) & (nf["date"] <= pd.Timestamp(dates[-1]))]
    closes = w["close"].values.astype(float)
    prev = np.concatenate([[float(w["open"].iloc[0])], closes[:-1]])
    bh_map = dict(zip(w["date"].dt.strftime("%Y-%m-%d"), pos * (closes / prev - 1.0)))
    bh = np.round(np.cumsum([bh_map.get(d, 0.0) for d in dates]), 2).tolist()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": {
            "window": bt["test_window"], "n_days": bt["n_days"], "alpha": bt["alpha"],
            "position_value_inr": bt["position_value_inr"],
            "ml_gates": bt["gated"], "every_day": bt["every_day"], "buy_hold": bt["buy_hold"],
            "pipeline": pp["pipeline"], "agent_stats": pp["stats"], "audit": pp["audit"],
            "edge_stats": bt["edge_stats"],
        },
        "series": {"dates": dates, "ml_gates": _cum(base), "pipeline": _cum(cards), "buy_hold": bh},
        "cards": cards,
    }


def main():
    d = build()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "data.json").write_text(json.dumps(d, ensure_ascii=False))
    s = d["series"]
    print(f"wrote web/data/data.json | {len(d['cards'])} cards | final cumulative: "
          f"ml_gates {s['ml_gates'][-1]}, pipeline {s['pipeline'][-1]}, buy_hold {s['buy_hold'][-1]}")


if __name__ == "__main__":
    main()
