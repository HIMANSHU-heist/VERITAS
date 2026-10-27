"""Runs the extra agents on the latest live card -> web/data/agents.json (advisory, dashboard)."""
import json
from datetime import datetime, timezone

import yaml

from python.agents.debate import debate
from python.agents.drift import drift
from python.agents.portfolio import portfolio
from python.agents.regime import adjust_p_up, regime
from python.agents.risk_agent import risk_scale
from python.llm import LLM
from python.ml.features import build_dataset
from python.risk_client import ROOT


def safe(name, fn):
    try:
        return fn()
    except Exception as e:
        print(f"{name} skipped: {type(e).__name__} {e}")
        return None


def main():
    cards = [json.loads(l) for l in open(ROOT / "data" / "live_cards.jsonl")]
    card = cards[-1]
    cap = float(yaml.safe_load(open(ROOT / "configs" / "limits.yaml"))["starting_capital_inr"])

    def _reg():
        X, _ = build_dataset()
        r = regime(X.iloc[-1])
        r["adj_p_up"] = adjust_p_up(card["p_up"], r["conf_mult"])
        return r

    reg = safe("regime", _reg)
    out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "date": card["date"],
           "regime": reg, "risk": safe("risk", lambda: risk_scale(card["vix"], cards, cap)),
           "debate": safe("debate", lambda: debate(LLM(), {**card, "regime": (reg or {}).get("label")})),
           "portfolio": safe("portfolio", portfolio), "drift": safe("drift", drift)}
    p = ROOT / "web" / "data"
    p.mkdir(parents=True, exist_ok=True)
    (p / "agents.json").write_text(json.dumps(out, ensure_ascii=False))
    print({k: (v if not isinstance(v, dict) else list(v)[:3]) for k, v in out.items() if k != "generated_at"})


if __name__ == "__main__":
    main()
