"""Live paper decision for ONE day: fresh data -> DataClock -> ML+conformal -> C++ gates -> AI agents -> card."""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timedelta, timezone

import joblib
import numpy as np
import pandas as pd

from python.agents import cue_agent, herding, redteam_agent, strategy_agent
from python.dataclock import DataClock, load_frozen, to_utc
from python.llm import LLM
from python.reflect import recent_lessons
from python.news import NO_NEWS, live_news
from python.ml.features import SERIES, _utc_ns, series_features
from python.orchestrator import order_request, reconcile
from python.risk_client import ROOT, RiskEngine
from python.schemas import NewsOut, ProposalOut, RedTeamOut

CLASS_NAMES = ("DOWN", "UP")
CALM = RedTeamOut(objections=[], recommend_veto=False)
ETF_DIVISOR = 100.0


def ist_today():
    return (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).date()


def load_art():
    art = joblib.load(ROOT / "data" / "models" / "live.joblib")
    art["model"] = joblib.load(ROOT / "data" / "models" / "technical.joblib")["model"]
    return art


def qhat_from(cal_scores, alpha):
    q = np.ones(2)
    for k in (0, 1):
        s = np.asarray(cal_scores[k])
        n = len(s)
        if n:
            level = min(1.0, math.ceil((n + 1) * (1.0 - alpha)) / n)
            q[k] = np.quantile(s, level, method="higher")
    return q


def live_row(t, feats):
    """Features at decision time t from ONLY the rows DataClock would expose."""
    X = pd.DataFrame({"decision_time": _utc_ns(pd.Series([t]))})
    last = {}
    for name in SERIES:
        df = load_frozen(name)
        vis = df[df["available_at"] <= t].reset_index(drop=True)
        last[name] = vis["date"].iloc[-1]
        f = series_features(name, vis)
        f["available_at"] = _utc_ns(f["available_at"])
        X = pd.merge_asof(X, f.sort_values("available_at"), left_on="decision_time",
                          right_on="available_at", direction="backward")
        X = X.rename(columns={"available_at": f"avail_{name}"})
    nf = load_frozen("NIFTY")
    close = float(nf[nf["available_at"] <= t]["close"].iloc[-1])
    return X.iloc[0], last, close


def decide(as_of, llm=None, use_llm=True, art=None, alpha=0.10, audit=None):
    art = art or load_art()
    t = to_utc(as_of)
    feats = art["features"]
    row, last, close = live_row(t, feats)
    price = close / ETF_DIVISOR
    vix = float(row["INDIAVIX_level"])
    vix = 0.0 if math.isnan(vix) else vix
    ts = int(t.timestamp() * 1000)
    stale = [n for n, d in last.items() if (t.date() - d.date()).days > 6]
    bad = bool(row[feats].isna().any())
    card = {"date": str(t.date()), "asof": t.isoformat(), "mode": "live", "price": round(price, 4),
            "vix": round(vix, 2), "data_asof": {n: str(d.date()) for n, d in last.items()}}
    eng = RiskEngine(audit_path=audit or f"data/live_audit/{card['date']}.jsonl")
    side = 0
    try:
        eng.send({"type": "new_day"})
        if stale or bad:
            req = order_request(ProposalOut(action="BUY", size_pct=0, thesis="data check"), CALM,
                                {"disagreement": 0.0}, {"edge_pct": 0.0, "singleton": False},
                                price, vix, ts, data_valid=False)
            final = eng.send(req)
            card["note"] = "stale_or_missing_data: " + ",".join(stale or ["nan_features"])
        else:
            p = art["model"].predict_proba(row[feats].astype(float).to_frame().T)[0]
            p_up = float(p[1])
            sets = (1.0 - p) <= qhat_from(art["cal_scores"], alpha)
            single = int(sets.sum()) == 1
            side = (1 if sets.argmax() == 1 else -1) if single else (1 if p_up >= 0.5 else -1)
            action = "BUY" if side > 0 else "SELL"
            edge = float(np.interp(abs(2 * p_up - 1), art["iso_x"], art["iso_y"]))
            score, drivers = art["cue_model"].predict(row)
            her = herding([score, 2 * p_up - 1])
            ml = {"p_up": p_up, "conformal_set": [CLASS_NAMES[k] for k in range(2) if sets[k]],
                  "edge_pct": edge, "singleton": single, "direction": action}
            card.update(p_up=round(p_up, 4), conformal_set=ml["conformal_set"], edge_pct=round(edge, 4),
                        cue_score=round(score, 3), ml_direction=action)
            news, news_flagged, heads = NO_NEWS, [], []
            if use_llm and card['date'] == str(ist_today()):   # never fetch live news for a past date (leakage)
                llm = llm or LLM(clock=DataClock(['NIFTY']))
                news, news_flagged, heads = live_news(llm, t)
            her2 = herding([score, 2 * p_up - 1, news.score])
            if heads:
                used = set(news.evidence_ids)
                card['news'] = {'score': news.score, 'confidence': news.confidence,
                                'flagged_injection': news_flagged,
                                'headlines': [{'id': i, 'text': x} for i, x in heads if i in used]}
            pre = eng.send(order_request(ProposalOut(action=action, size_pct=2.0, thesis="ml"),
                                         CALM, her, ml, price, vix, ts))
            final = pre
            if pre["decision"] == "TRADE":
                if not use_llm:
                    final = {**pre, "decision": "CANDIDATE", "gate_failed": ["llm_not_run"]}
                else:
                    try:
                        llm = llm or LLM(clock=DataClock(["NIFTY"]))
                        ml_llm = {k: v for k, v in ml.items() if k != "edge_pct"}
                        ml_llm.update(p_up=round(p_up, 3),
                                      edge_text=f"{edge:.3f}% of position value ({edge * 100:.0f} basis points)")
                        cue = cue_agent(llm, score, drivers, as_of=t)
                        prop, _ = reconcile(strategy_agent(llm, cue, news, ml_llm, her2, as_of=t, lessons=recent_lessons()), action)
                        red = redteam_agent(llm, prop, cue, NO_NEWS, ml_llm, as_of=t)
                        card.update(cue_reason=cue.reason, proposal=prop.model_dump(), red_team=red.model_dump())
                        req = order_request(prop, red, her2, ml, price, vix, ts + 1)
                        final = eng.send(req) if req else {**pre, "decision": "WAIT", "gate_failed": ["llm_wait"]}
                    except Exception as e:      # fail closed: any AI problem means no trade
                        card["llm_error"] = f"{type(e).__name__}: {e}"[:200]
                        final = {**pre, "decision": "WAIT", "gate_failed": ["llm_error"]}
        card.update(decision=final["decision"], gate_failed=final["gate_failed"],
                    counterfactual=final.get("counterfactual"), audit_hash=final["audit_hash"])
        if final["decision"] == "TRADE":
            card.update(side=side, qty=float(final["qty_approved"]),
                        cost=round(float(final["round_trip_cost_inr"]), 2))
        card["audit_ok"] = eng.verify()["audit"] == "OK"
    finally:
        eng.close()
    return card


def save_card(card):
    p = ROOT / "data" / "live_cards.jsonl"
    cards = [json.loads(l) for l in open(p)] if p.exists() else []
    cards = [c for c in cards if c["date"] != card["date"]] + [card]
    p.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cards))
    out = ROOT / "web" / "data"
    out.mkdir(parents=True, exist_ok=True)
    (out / "today.json").write_text(json.dumps(
        {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "card": card},
        ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="IST date YYYY-MM-DD (default: today)")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args()
    card = decide(f"{a.date or ist_today()} 03:00:00+00:00", use_llm=not a.no_llm)
    if not a.no_save:
        save_card(card)
    keys = ("date", "decision", "gate_failed", "p_up", "conformal_set", "edge_pct", "cue_score",
            "ml_direction", "llm_error", "note", "audit_ok")
    print(json.dumps({k: card.get(k) for k in keys if card.get(k) is not None}, indent=1))


if __name__ == "__main__":
    main()
