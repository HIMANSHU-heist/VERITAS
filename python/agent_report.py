"""Runs the advisory agents on the latest live card -> web/data/agents.json (dashboard only)."""
import json
from datetime import datetime, timezone

import yaml

from python.agents.dataquality import data_quality
from python.agents.debate import debate
from python.agents.drift import drift
from python.agents.levels import levels
from python.agents.portfolio import portfolio
from python.agents.regime import adjust_p_up, regime
from python.agents.risk_agent import risk_scale
from python.agents.scorecard import scorecard
from python.risk_client import ROOT


def safe(name, fn):
    try:
        return fn()
    except Exception as e:
        print(f"{name} skipped: {type(e).__name__} {e}")
        return None


def _regime(card):
    # uses the row DataClock exposes at decision time (the old code used yesterday's training row)
    from python.daily import live_row
    from python.dataclock import to_utc
    row, _, _ = live_row(to_utc(card["asof"]), None)
    r = regime(row)
    r["adj_p_up"] = adjust_p_up(card["p_up"], r["conf_mult"])
    return r


def _debate(card, reg):
    from python.llm import LLM
    return debate(LLM(), {**card, "regime": (reg or {}).get("label")})


def main():
    cards = [json.loads(l) for l in open(ROOT / "data" / "live_cards.jsonl") if l.strip()]
    card = cards[-1]
    cap = float(yaml.safe_load(open(ROOT / "configs" / "limits.yaml"))["starting_capital_inr"])
    reg = safe("regime", lambda: _regime(card))
    out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "date": card["date"],
           "regime": reg,
           "risk": safe("risk", lambda: risk_scale(card["vix"], cards, cap)),
           "debate": safe("debate", lambda: _debate(card, reg)),
           "portfolio": safe("portfolio", portfolio), "drift": safe("drift", drift),
           "levels": safe("levels", levels),
           "scorecard": safe("scorecard", lambda: scorecard(cards)),
           "dataquality": safe("dataquality", data_quality)}
    p = ROOT / "web" / "data"
    p.mkdir(parents=True, exist_ok=True)
    (p / "agents.json").write_text(json.dumps(out, ensure_ascii=False))
    print({k: ("ok" if v else "skipped") for k, v in out.items() if k not in ("generated_at", "date")})


if __name__ == "__main__":
    main()
