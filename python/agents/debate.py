"""Strategy Debate: Bull vs Bear, then a Judge. Judge may only agree with ml.direction or WAIT."""
import json
from typing import Literal

from pydantic import BaseModel, Field


class Arg(BaseModel):
    argument: str = Field(max_length=300)
    strength: float = Field(ge=0, le=1)


class Judge(BaseModel):
    verdict: Literal["BUY", "SELL", "WAIT"]
    reason: str = Field(max_length=300)


RULES = ("Use ONLY the numbers given. Never invent data. Quote edge exactly as edge_text; never convert units. "
         "This is a PAPER-trading system. ")
BULL = "You argue FOR taking the proposed trade in ml_direction. " + RULES + "Fields: argument, strength (0..1)."
BEAR = "You argue AGAINST taking the proposed trade. " + RULES + "Fields: argument, strength (0..1)."
JUDGE = ("You are a cautious judge. Read the bull and bear arguments. You may only choose ml_direction or WAIT. "
         + RULES + "Fields: verdict (BUY|SELL|WAIT), reason.")


def debate(llm, card):
    ctx = {"ml_direction": card["ml_direction"], "p_up": card["p_up"], "conformal_set": card["conformal_set"],
           "edge_text": f"{card['edge_pct']:.3f}%", "cue_score": card.get("cue_score"),
           "gates_failed": card.get("gate_failed"), "regime": card.get("regime")}
    u = json.dumps(ctx, ensure_ascii=False)
    bull = llm.call_json("fast", BULL, u, Arg)
    bear = llm.call_json("fast", BEAR, u, Arg)
    j = llm.call_json("strong", JUDGE, json.dumps({**ctx, "bull": bull.model_dump(), "bear": bear.model_dump()}), Judge)
    if j.verdict not in ("WAIT", card["ml_direction"]):
        j = Judge(verdict="WAIT", reason="direction_mismatch: " + j.reason[:250])
    return {"bull": bull.model_dump(), "bear": bear.model_dump(), "judge": j.model_dump()}
