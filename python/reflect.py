"""Reflection Agent (evening): one lesson per settled day -> data/lessons.jsonl.
Fails closed: any error means no lesson, never a crash."""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from python.llm import LLM
from python.risk_client import ROOT

LESSONS = ROOT / "data" / "lessons.jsonl"


class LessonOut(BaseModel):
    verdict: str = Field(max_length=20)
    lesson: str = Field(max_length=300)


SYS = ("You review ONE day of a paper-trading system. Given the decision card and the real outcome, "
       "say whether the decision was right (verdict: GOOD, BAD or NEUTRAL) and write ONE short, "
       "concrete lesson. Use ONLY numbers in the card. Never invent data. "
       "Fields: verdict, lesson.")


def _rows():
    return [json.loads(l) for l in open(LESSONS)] if LESSONS.exists() else []


def recent_lessons(n=5):
    return [r["lesson"] for r in _rows()[-n:]]


def main():
    cards = [json.loads(l) for l in open(ROOT / "data" / "live_cards.jsonl")]
    card = cards[-1]
    if not card.get("settled"):
        print("card not settled, no lesson")
        return
    keep = ("date", "decision", "gate_failed", "p_up", "conformal_set", "edge_pct",
            "ml_direction", "ret_oc_pct", "net", "counterfactual")
    view = {k: card.get(k) for k in keep}
    try:
        out = LLM().call_json("strong", SYS, json.dumps(view, ensure_ascii=False), LessonOut)
    except Exception as e:
        print("reflection skipped:", type(e).__name__, e)
        return
    rows = [r for r in _rows() if r["date"] != card["date"]]
    rows.append({"date": card["date"], "verdict": out.verdict, "lesson": out.lesson})
    LESSONS.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(rows[-1])


if __name__ == "__main__":
    main()
