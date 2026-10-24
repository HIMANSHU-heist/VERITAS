"""Backtester: DataClock-safe features -> LightGBM -> conformal -> C++ risk engine -> paper ledger.

Assumptions (stated, not hidden):
- Tradable proxy = Nifty index / 100 (NIFTYBEES-like ETF).
- Entry at the day's open, exit at the day's close (intraday), long or short.
- Position = max_position_pct of capital. Costs/slippage come from the C++ engine.
- Buy-and-hold is shown with ZERO cost (generous to the benchmark).
"""
from __future__ import annotations

import json
from collections import Counter

import joblib
import numpy as np
import yaml
from sklearn.isotonic import IsotonicRegression

from python.dataclock import load_frozen
from python.ml.conformal import calibrate, prediction_sets
from python.ml.features import build_dataset
from python.risk_client import ROOT, RiskEngine

ETF_DIVISOR = 100.0
CLASS_NAMES = ("DOWN", "UP")


def load_setup():
    X, feats = build_dataset()
    bundle = joblib.load(ROOT / "data" / "models" / "technical.joblib")
    model = bundle["model"]
    n = len(X)
    i1, i2 = int(n * 0.6), int(n * 0.8)          # same split as training
    ca = X.iloc[i1:i2]
    te = X.iloc[i2:].reset_index(drop=True)
    nifty = load_frozen("NIFTY")[["date", "open", "close"]].copy()
    nifty["prev_close"] = nifty["close"].shift(1)
    te = te.merge(nifty[["date", "prev_close"]], on="date", how="left")
    return {
        "te": te, "feats": feats, "nifty": nifty,
        "p_ca": model.predict_proba(ca[feats]), "y_ca": ca["y"].values,
        "p_te": model.predict_proba(te[feats]),
        "ret_ca": ca["ret_oc"].values * 100,
        "avg_move": float(bundle["avg_abs_ret_pct"]),
    }


def summarize(daily_net, trades, capital, pos_val):
    n = len(trades)
    net = float(sum(t["net"] for t in trades))
    gross = float(sum(t["gross"] for t in trades))
    cost = float(sum(t["cost"] for t in trades))
    wins = sum(1 for t in trades if t["net"] > 0)
    cum = np.cumsum(daily_net) if len(daily_net) else np.array([0.0])
    peak = np.maximum.accumulate(np.concatenate([[0.0], cum]))[1:]
    dd = float((peak - cum).max())
    return {
        "n_trades": n,
        "win_rate": (wins / n) if n else None,
        "gross_pnl": round(gross, 2),
        "cost": round(cost, 2),
        "net_pnl": round(net, 2),
        "net_bps_per_trade": round(net / (n * pos_val) * 1e4, 2) if n else None,
        "max_drawdown_inr": round(dd, 2),
        "max_drawdown_pct_capital": round(dd / capital * 100, 3),
    }


def run_backtest(alpha=0.10, setup=None, write=False, tag="main", edge_mode="calibrated"):
    s = setup or load_setup()
    te, p_te = s["te"], s["p_te"]
    q = calibrate(s["p_ca"], s["y_ca"], alpha)
    sets = prediction_sets(p_te, q)

    # Edge calibration: fit ONLY on the calibration window (test window untouched)
    p_ca_up = s["p_ca"][:, 1]
    conf_ca = np.abs(2 * p_ca_up - 1)
    dir_ret_ca = np.where(p_ca_up >= 0.5, 1, -1) * s["ret_ca"]      # realized % return in model's direction
    iso = IsotonicRegression(increasing=True, out_of_bounds="clip").fit(conf_ca, dir_ret_ca)

    limits = yaml.safe_load(open(ROOT / "configs" / "limits.yaml"))
    capital = float(limits["starting_capital_inr"])
    pos_val = capital * float(limits["max_position_pct"]) / 100.0

    eng = RiskEngine(audit_path=f"audit/bt_{tag}.jsonl")
    base = RiskEngine(audit_path=f"audit/bt_{tag}_base.jsonl")

    cards, g_trades, b_trades = [], [], []
    g_daily, b_daily = [], []
    gate_counts = Counter()
    edges, required = [], []

    for i, row in te.iterrows():
        p_up = float(p_te[i, 1])
        conf = abs(2 * p_up - 1)
        if edge_mode == "calibrated":
            edge = float(iso.predict([conf])[0])               # realized-edge estimate (% per trade)
        else:
            edge = conf * s["avg_move"]                        # old naive formula
        single = int(sets[i].sum()) == 1
        side = (1 if sets[i].argmax() == 1 else -1) if single else (1 if p_up >= 0.5 else -1)
        price = float(row["prev_close"]) / ETF_DIVISOR
        qty = int(pos_val // price)
        ret = float(row["ret_oc"])
        ts = int(i) * 86_400_000
        vix = float(row["INDIAVIX_level"])

        eng.send({"type": "new_day"})
        base.send({"type": "new_day"})

        r = eng.send({
            "type": "check_order", "symbol": "NIFTYBEES", "side": "BUY" if side > 0 else "SELL",
            "price": price, "qty": qty, "expected_edge_pct": edge, "data_valid": True,
            "conformal_singleton": single, "disagreement": 0.0,
            "redteam_severity": "LOW", "vix": vix, "ts_ms": ts,
        })
        edges.append(edge)
        required.append(float(r["required_edge_pct"]))

        card = {
            "date": str(row["date"].date()), "p_up": round(p_up, 4),
            "conformal_set": [CLASS_NAMES[k] for k in range(2) if sets[i][k]],
            "edge_pct": round(edge, 4), "decision": r["decision"],
            "gate_failed": r["gate_failed"], "counterfactual": r.get("counterfactual"),
            "audit_hash": r["audit_hash"],
        }
        if r["decision"] == "TRADE":
            q_ap = float(r["qty_approved"])
            gross = side * ret * q_ap * price
            cost = float(r["round_trip_cost_inr"])
            net = gross - cost
            eng.send({"type": "update_pnl", "pnl_inr": net})
            g_trades.append({"gross": gross, "cost": cost, "net": net})
            g_daily.append(net)
            card.update(side=side, qty=q_ap, gross=round(gross, 2), cost=round(cost, 2), net=round(net, 2))
        else:
            g_daily.append(0.0)
            for g in r["gate_failed"]:
                gate_counts[g] += 1
        cards.append(card)

        # Naive baseline: trade every day in the model's direction, no gates
        side_b = 1 if p_up >= 0.5 else -1
        rb = base.send({
            "type": "check_order", "symbol": "NIFTYBEES", "side": "BUY" if side_b > 0 else "SELL",
            "price": price, "qty": qty, "expected_edge_pct": 999.0, "data_valid": True,
            "conformal_singleton": True, "disagreement": 0.0,
            "redteam_severity": "LOW", "vix": 0.0, "ts_ms": ts,
        })
        if rb["decision"] == "TRADE":
            gb = side_b * ret * float(rb["qty_approved"]) * price
            cb = float(rb["round_trip_cost_inr"])
            nb = gb - cb
            base.send({"type": "update_pnl", "pnl_inr": nb})
            b_trades.append({"gross": gb, "cost": cb, "net": nb})
            b_daily.append(nb)
        else:
            b_daily.append(0.0)

    audit = eng.verify()
    eng.close()
    base.close()

    # Buy and hold the same position size (no cost = generous to the benchmark)
    nf = s["nifty"]
    w = nf[(nf["date"] >= te["date"].min()) & (nf["date"] <= te["date"].max())]
    closes = w["close"].values.astype(float)
    prev = np.concatenate([[float(w["open"].iloc[0])], closes[:-1]])
    bh_daily = pos_val * (closes / prev - 1.0)
    bh_total = float(pos_val * (closes[-1] / float(w["open"].iloc[0]) - 1.0))
    bh = summarize(bh_daily, [{"gross": bh_total, "cost": 0.0, "net": bh_total}], capital, pos_val)
    bh["n_trades"] = 1

    n_days = len(te)
    gated = summarize(np.array(g_daily), g_trades, capital, pos_val)
    every = summarize(np.array(b_daily), b_trades, capital, pos_val)

    res = {
        "alpha": alpha, "n_days": n_days, "n_abstain": n_days - gated["n_trades"],
        "test_window": [str(te["date"].min().date()), str(te["date"].max().date())],
        "position_value_inr": pos_val, "gated": gated, "every_day": every, "buy_hold": bh,
        "gate_counts": dict(gate_counts), "audit": audit, "cards": cards,
        "edge_stats": {
            "max_edge_pct": round(max(edges), 4),
            "median_edge_pct": round(float(np.median(edges)), 4),
            "round_trip_cost_pct": round(float(np.median(required)), 4),
            "days_edge_above_cost": int(sum(e > c for e, c in zip(edges, required))),
        },
    }
    if write:
        out = ROOT / "results"
        out.mkdir(exist_ok=True)
        with open(out / "cards.jsonl", "w") as f:
            for c in cards:
                f.write(json.dumps(c) + "\n")
        summary = {k: v for k, v in res.items() if k != "cards"}
        (out / "summary.json").write_text(json.dumps(summary, indent=2))
    return res


def _fmt(v, kind="num"):
    if v is None:
        return "-"
    if kind == "pct":
        return f"{v * 100:.1f}%"
    return f"{v:,.2f}"


def print_report(r):
    print(f"\nTest window: {r['test_window'][0]} -> {r['test_window'][1]}  "
          f"({r['n_days']} days) | position size INR {r['position_value_inr']:,.0f} | alpha={r['alpha']}")
    cols = [("Trade every day", r["every_day"]), (f"VERITAS (alpha={r['alpha']})", r["gated"]),
            ("Buy&Hold (no cost)", r["buy_hold"])]
    print(f"\n{'':26s}" + "".join(f"{n:>24s}" for n, _ in cols))
    for label, key, kind in [
        ("trades", "n_trades", "int"), ("win rate", "win_rate", "pct"),
        ("gross P&L (INR)", "gross_pnl", "num"), ("costs (INR)", "cost", "num"),
        ("NET P&L (INR)", "net_pnl", "num"), ("net bps / trade", "net_bps_per_trade", "num"),
        ("max drawdown (INR)", "max_drawdown_inr", "num"),
    ]:
        vals = []
        for _, m in cols:
            v = m[key]
            vals.append(f"{v:>24d}" if kind == "int" else f"{_fmt(v, kind):>24s}")
        print(f"{label:26s}" + "".join(vals))
    print(f"\nVERITAS abstained on {r['n_abstain']}/{r['n_days']} days "
          f"({r['n_abstain'] / r['n_days'] * 100:.1f}%)")
    print("Gates that blocked trades:", r["gate_counts"])
    e = r["edge_stats"]
    print(f"Edge estimate: median {e['median_edge_pct']}% | max {e['max_edge_pct']}% | "
          f"round-trip cost {e['round_trip_cost_pct']}% | days edge > cost: {e['days_edge_above_cost']}")
    print("Audit chain:", r["audit"])


def main():
    setup = load_setup()
    main_res = run_backtest(0.10, setup=setup, write=True, tag="main")
    print_report(main_res)
    naive = run_backtest(0.10, setup=setup, write=False, tag="naive", edge_mode="naive")
    print(f"\nOld naive edge formula, same alpha: trades={naive['gated']['n_trades']} "
          f"net P&L={naive['gated']['net_pnl']:.2f} INR")
    print("\nSensitivity (same test window; main result above is alpha=0.10, fixed in advance):")
    print(f"{'alpha':>6} {'trades':>7} {'abstain%':>9} {'net P&L INR':>12}")
    for a in (0.05, 0.10, 0.20, 0.30):
        r = main_res if a == 0.10 else run_backtest(a, setup=setup, write=False, tag=f"a{int(a * 100)}")
        print(f"{a:6.2f} {r['gated']['n_trades']:7d} "
              f"{r['n_abstain'] / r['n_days'] * 100:9.1f} {r['gated']['net_pnl']:12.2f}")
    print("\nsaved results/summary.json and results/cards.jsonl")


if __name__ == "__main__":
    main()
