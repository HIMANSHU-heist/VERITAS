"""Stage 7: full decision pipeline on the held-out window.
ML + conformal + C++ gates run first. LLM agents run only on days that pass, and may only agree or WAIT.
No historical news exists, so the news agent is neutral here (price-only backtest)."""
from __future__ import annotations

import argparse
import json

import numpy as np
import yaml
from sklearn.isotonic import IsotonicRegression

from python.agents import CueModel, cue_agent, herding, redteam_agent, strategy_agent
from python.backtest import CLASS_NAMES, ETF_DIVISOR, load_setup, summarize
from python.dataclock import DataClock
from python.llm import LLM, LLMError, ReplayMiss
from python.ml.conformal import calibrate, prediction_sets
from python.orchestrator import order_request, reconcile
from python.risk_client import ROOT, RiskEngine
from python.schemas import NewsOut, ProposalOut, RedTeamOut

CALM = RedTeamOut(objections=[], recommend_veto=False)
NO_NEWS = NewsOut(score=0.0, confidence=0.0, evidence_ids=[])


def run_pipeline(alpha=0.10, setup=None, llm=None, max_llm_days=None, write=False, tag="pipe"):
    s = setup or load_setup()
    te, p_te = s["te"], s["p_te"]
    sets = prediction_sets(p_te, calibrate(s["p_ca"], s["y_ca"], alpha))
    p_ca = s["p_ca"][:, 1]
    iso = IsotonicRegression(increasing=True, out_of_bounds="clip").fit(
        np.abs(2 * p_ca - 1), np.where(p_ca >= 0.5, 1, -1) * s["ret_ca"])
    cue_model = CueModel().fit()
    llm = llm or LLM(clock=DataClock(["NIFTY"]))
    limits = yaml.safe_load(open(ROOT / "configs" / "limits.yaml"))
    capital = float(limits["starting_capital_inr"])
    pos_val = capital * float(limits["max_position_pct"]) / 100.0
    eng = RiskEngine(audit_path=f"audit/{tag}.jsonl")
    cards, trades, daily = [], [], []
    st = dict(candidates=0, llm_wait=0, direction_mismatch=0, redteam_veto=0, llm_errors=0, llm_skipped=0)

    for i, row in te.iterrows():
        p_up = float(p_te[i, 1])
        edge = float(iso.predict([abs(2 * p_up - 1)])[0])
        single = int(sets[i].sum()) == 1
        side = (1 if sets[i].argmax() == 1 else -1) if single else (1 if p_up >= 0.5 else -1)
        action = "BUY" if side > 0 else "SELL"
        price = float(row["prev_close"]) / ETF_DIVISOR
        ts = int(i) * 86_400_000
        vix = float(row["INDIAVIX_level"])
        score, drivers = cue_model.predict(row)
        her = herding([score, 2 * p_up - 1])
        ml = {"p_up": p_up, "conformal_set": [CLASS_NAMES[k] for k in range(2) if sets[i][k]],
              "edge_pct": edge, "singleton": single, "direction": action}
        ml_llm = {k: v for k, v in ml.items() if k != "edge_pct"}
        ml_llm.update(p_up=round(p_up, 3),
                      edge_text=f"{edge:.3f}% of position value ({edge * 100:.0f} basis points)")

        eng.send({"type": "new_day"})
        pre = eng.send(order_request(ProposalOut(action=action, size_pct=2.0, thesis="ml"),
                                     CALM, her, ml, price, vix, ts))
        card = {"date": str(row["date"].date()), "p_up": round(p_up, 4), "conformal_set": ml["conformal_set"],
                "edge_pct": round(edge, 4), "cue_score": round(score, 3), "ml_direction": action}
        final = pre
        if pre["decision"] == "TRADE":
            st["candidates"] += 1
            if max_llm_days is not None and st["candidates"] > max_llm_days:
                st["llm_skipped"] += 1
                final = {**pre, "decision": "WAIT", "gate_failed": ["llm_skipped_trial"]}
            else:
                try:
                    as_of = row["decision_time"]
                    cue = cue_agent(llm, score, drivers, as_of=as_of)
                    prop, flipped = reconcile(
                        strategy_agent(llm, cue, NO_NEWS, ml_llm, her, as_of=as_of), action)
                    red = redteam_agent(llm, prop, cue, NO_NEWS, ml_llm, as_of=as_of)
                    st["direction_mismatch"] += int(flipped)
                    card.update(cue_reason=cue.reason, proposal=prop.model_dump(), red_team=red.model_dump())
                    req = order_request(prop, red, her, ml, price, vix, ts + 1)
                    if req is None:
                        st["llm_wait"] += 1
                        final = {**pre, "decision": "WAIT", "gate_failed": ["llm_wait"]}
                    else:
                        final = eng.send(req)
                        st["redteam_veto"] += int("redteam_veto" in final["gate_failed"])
                except (LLMError, ReplayMiss) as e:
                    st["llm_errors"] += 1
                    card["llm_error"] = str(e)[:200]
                    final = {**pre, "decision": "WAIT", "gate_failed": ["llm_error"]}
                print(f"  candidate {st['candidates']:3d} {card['date']} -> "
                      f"{final['decision']} {final['gate_failed']}", flush=True)

        net = 0.0
        if final["decision"] == "TRADE":
            q = float(final["qty_approved"])
            gross = side * float(row["ret_oc"]) * q * price
            cost = float(final["round_trip_cost_inr"])
            net = gross - cost
            eng.send({"type": "update_pnl", "pnl_inr": net})
            trades.append({"gross": gross, "cost": cost, "net": net})
            card.update(side=side, qty=q, gross=round(gross, 2), cost=round(cost, 2), net=round(net, 2))
        daily.append(net)
        card.update(decision=final["decision"], gate_failed=final["gate_failed"],
                    counterfactual=final.get("counterfactual"), audit_hash=final["audit_hash"])
        cards.append(card)

    audit = eng.verify()
    eng.close()
    res = {"alpha": alpha, "n_days": len(te), "pipeline": summarize(np.array(daily), trades, capital, pos_val),
           "stats": st, "audit": audit, "cards": cards}
    if write:
        out = ROOT / "results"
        out.mkdir(exist_ok=True)
        with open(out / "pipeline_cards.jsonl", "w") as f:
            for c in cards:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        (out / "pipeline_summary.json").write_text(
            json.dumps({k: v for k, v in res.items() if k != "cards"}, indent=2))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-llm-days", type=int, default=None)
    a = ap.parse_args()
    r = run_pipeline(max_llm_days=a.max_llm_days, write=True)
    ref = json.loads((ROOT / "results" / "summary.json").read_text())["gated"]
    p = r["pipeline"]
    print(f"\nFull pipeline (alpha=0.10, {r['n_days']} days, price-only agents)")
    print(f"{'':24s}{'ML+gates only':>16s}{'Full pipeline':>16s}")
    for label, k in [("trades", "n_trades"), ("gross P&L (INR)", "gross_pnl"), ("costs (INR)", "cost"),
                     ("NET P&L (INR)", "net_pnl"), ("max drawdown (INR)", "max_drawdown_inr")]:
        print(f"{label:24s}{ref[k]:>16,.2f}{p[k]:>16,.2f}")
    print("Agent stats:", r["stats"])
    print("Audit chain:", r["audit"])
    if a.max_llm_days is not None:
        print("TRIAL RUN: later candidate days were skipped, do not read the P&L.")


if __name__ == "__main__":
    main()
