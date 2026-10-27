"""Pure paper-trading rules (no I/O). Fake money. LLMs never decide money."""
from __future__ import annotations

from datetime import date

import yaml

from python.risk_client import ROOT

COSTS = yaml.safe_load(open(ROOT / "configs" / "costs.yaml"))
SYMBOL = "NIFTYBEES"
STOP, TARGET, MAX_HOLD_DAYS = -0.02, 0.03, 5
REQUIRED_EDGE, AUTO_EDGE = 0.146, 0.292          # percent; auto = 2x round-trip cost
HARD = {"kill_switch", "vix_stress", "data_invalid", "rate_limit"}
SOFT = {"redteam_veto", "agent_disagreement", "conformal_ambiguous"}


def charges(side, value):
    c = COSTS
    brk = min(c["brokerage"]["pct"] * value, c["brokerage"]["max_per_order_inr"])
    exch, sebi = c["exchange_txn_pct"] * value, c["sebi_pct"] * value
    gst = c["gst_pct"] * (brk + exch + sebi)
    stt = c["stt_sell_pct"] * value if side == "SELL" else 0.0
    stamp = c["stamp_buy_pct"] * value if side == "BUY" else 0.0
    return round(brk + exch + sebi + gst + stt + stamp, 2)


def classify(card):
    """-> (tier AUTO|ASK|NONE, side, why, confidence). Hard gates can never be overridden."""
    gf = set(card.get("gate_failed") or [])
    side, edge = card["ml_direction"], float(card["edge_pct"])
    conf = round(abs(2 * float(card["p_up"]) - 1), 3)
    if gf & HARD:
        return "NONE", side, "hard gate: " + ", ".join(sorted(gf & HARD)), conf
    if card["decision"] == "TRADE":
        tier = "AUTO" if edge >= AUTO_EDGE else "ASK"
        return tier, side, f"all gates passed, edge {edge:.3f}% vs cost {REQUIRED_EDGE}%", conf
    if edge >= REQUIRED_EDGE and gf <= SOFT:
        return "ASK", side, "blocked only by " + ", ".join(sorted(gf)) + ". Your call.", conf
    return "NONE", side, f"no edge after costs ({edge:.3f}%)", conf


def exit_reason(pos, price, today):
    ret = price / pos["avg"] - 1
    if ret <= STOP:
        return f"stop-loss at {ret * 100:.2f}%"
    if ret >= TARGET:
        return f"take-profit at {ret * 100:.2f}%"
    d = (today - date.fromisoformat(pos["since"])).days
    if d >= MAX_HOLD_DAYS:
        return f"held {d} days (max {MAX_HOLD_DAYS})"
    return None


def size_qty(equity, size_pct, scale, price):
    return int(equity * size_pct / 100.0 * scale // price)


def apply_fill(acct, side, qty, px, today):
    """Pure. Returns (account_fields, trade) or (None, None) when the order cannot fill."""
    slip = COSTS["slippage_bps"] / 1e4
    fp = px * (1 + slip) if side == "BUY" else px * (1 - slip)
    h = {k: dict(v) for k, v in (acct.get("holdings") or {}).items()}
    pos = h.get(SYMBOL)
    cash, realized, pnl = float(acct["cash"]), float(acct.get("realized", 0.0)), None
    if side == "BUY":
        while qty > 0 and qty * fp + charges("BUY", qty * fp) > cash:
            qty -= 1
        if qty < 1:
            return None, None
        val = qty * fp
        fee = charges("BUY", val)
        oq, oa = (pos["qty"], pos["avg"]) if pos else (0, 0.0)
        nq = oq + qty
        h[SYMBOL] = {"qty": nq, "avg": round((oa * oq + val + fee) / nq, 4),
                     "since": pos["since"] if pos else today.isoformat()}
        cash -= val + fee
    else:
        if not pos:
            return None, None
        qty = min(qty, pos["qty"])
        val = qty * fp
        fee = charges("SELL", val)
        pnl = val - fee - pos["avg"] * qty
        cash += val - fee
        realized += pnl
        if pos["qty"] - qty > 0:
            h[SYMBOL] = {**pos, "qty": pos["qty"] - qty}
        else:
            h.pop(SYMBOL)
    trade = {"side": side, "symbol": SYMBOL, "qty": qty, "price": round(fp, 3), "fee": fee,
             "pnl": None if pnl is None else round(pnl, 2)}
    return {"cash": round(cash, 2), "realized": round(realized, 2), "holdings": h}, trade
