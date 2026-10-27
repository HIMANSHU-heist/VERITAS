"""Runs every user's paper account: approved orders, exits, new signals, equity snapshot.
Fake money only. Hard gates are never overridden; users may approve soft-gate trades."""
import argparse
import html
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

from python.agents.risk_agent import risk_scale
from python.alerts.mailer import send
from python.daily import ist_today
from python.paper.engine import SYMBOL, apply_fill, classify, exit_reason, size_qty
from python.risk_client import ROOT

IST = timezone(timedelta(hours=5, minutes=30))
VALID_HOURS = 6


def market_open(now):
    t = now.astimezone(IST)
    return t.weekday() < 5 and (9, 20) <= (t.hour, t.minute) <= (15, 15)


def live_price(card):
    try:
        import yfinance as yf
        h = yf.Ticker("NIFTYBEES.NS").history(period="1d", interval="5m")
        if len(h):
            return float(h["Close"].iloc[-1]), "NIFTYBEES.NS"
    except Exception:
        pass
    return (float(card["price"]), "card price (Nifty/100)") if card else (None, "none")


def init_db():
    import firebase_admin
    from firebase_admin import credentials, firestore
    sa = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if not sa:
        sys.exit("FIREBASE_SERVICE_ACCOUNT missing (run this from GitHub Actions)")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(json.loads(sa)))
    return firestore.client()


def notify(uid, subject, lines, send_mail):
    from firebase_admin import auth
    try:
        u = auth.get_user(uid)
    except Exception:
        return
    if not (u.email and u.email_verified):
        return
    app = os.environ.get("APP_URL", "").replace("subscribe.html", "portfolio.html")
    tail = "Paper money only. Not investment advice."
    text = "\n".join(lines) + (f"\n\nApprove or reject: {app}" if app else "") + "\n\n" + tail
    body = "".join(f"<p>{html.escape(l)}</p>" for l in lines)
    body += (f"<p><a href='{html.escape(app)}'>Approve or reject</a></p>" if app else "")
    body += f"<p style='color:#666;font-size:12px'>{tail}</p>"
    try:
        print(send(u.email, subject, text, body, dry_run=not send_mail), subject, "->", u.email)
    except Exception as e:
        print("mail failed:", type(e).__name__, e)


def run_account(db, doc, card, price, now, today, send_mail, can_trade):
    ref, acct = doc.reference, doc.to_dict()
    p = ref.collection("settings").document("prefs").get()
    prefs = p.to_dict() if p.exists else {}
    mode, size_pct = prefs.get("mode", "auto"), float(prefs.get("sizePct", 5))
    log = []

    def trade(side, qty, reason, conf, src, tid):
        nonlocal acct
        if ref.collection("trades").document(tid).get().exists:
            return True
        upd, tr = apply_fill(acct, side, qty, price, today)
        if not upd:
            return False
        tr.update(ts=now, date=str(today), reason=reason, conf=conf, source=src)
        b = db.batch()
        b.update(ref, upd)
        b.set(ref.collection("trades").document(tid), tr)
        b.commit()
        acct = {**acct, **upd}
        log.append(f"{side} {tr['qty']} @ {tr['price']} ({src}: {reason})")
        return True

    def hold():
        return (acct.get("holdings") or {}).get(SYMBOL)

    def equity():
        return float(acct["cash"]) + sum(h["qty"] * price for h in (acct.get("holdings") or {}).values())

    # 1) approved / expired pending orders
    for pd_ in ref.collection("pending").where("status", "in", ["pending", "approved"]).stream():
        d, exp = pd_.to_dict(), pd_.to_dict()["expiresAt"]
        if d["status"] == "pending" and now > exp:
            pd_.reference.update({"status": "expired"})
        elif d["status"] == "approved":
            if now > exp + timedelta(hours=1):
                pd_.reference.update({"status": "expired"})
            elif can_trade and trade(d["side"], d["qty"], d["reason"], d["conf"], "approved", f"pend-{pd_.id}"):
                pd_.reference.update({"status": "executed"})

    # 2) risk exits run automatically
    exited = False
    if can_trade and hold():
        why = exit_reason(hold(), price, today)
        if why:
            exited = trade("SELL", hold()["qty"], why, 0, "auto", f"{today}-exit")

    # 3) new signal from today's VERITAS card
    fresh = card and card.get("date") == str(today)
    tier, side, why, conf = classify(card) if fresh else ("NONE", "", "no fresh card", 0)
    pos = hold()
    order = None
    if tier != "NONE" and not exited:
        if side == "SELL" and pos:
            order = ("SELL", pos["qty"])
        elif side == "BUY" and not pos and mode != "off":
            q = size_qty(equity(), size_pct, risk_scale(card["vix"], [], 1)["scale"], price)
            order = ("BUY", q) if q >= 1 else None
    if order:
        s, q = order
        if tier == "ASK" or mode == "ask":
            pr = ref.collection("pending").document(f"{card['date']}-{s}")
            if not pr.get().exists:
                pr.set({"status": "pending", "side": s, "symbol": SYMBOL, "qty": q, "price": round(price, 2),
                        "conf": conf, "tier": tier, "reason": why, "createdAt": now,
                        "expiresAt": now + timedelta(hours=VALID_HOURS)})
                notify(doc.id, f"[VERITAS paper] Approval needed: {s} {q} {SYMBOL}",
                       [f"The paper agent wants to {s} {q} {SYMBOL} at about {price:.2f}.",
                        f"Confidence {conf}. Reason: {why}",
                        f"Expires in {VALID_HOURS} hours. No action means no trade."], send_mail)
                log.append(f"asked approval: {s} {q}")
        elif can_trade:
            trade(s, q, why, conf, "auto", f"{today}-{s}")

    # 4) mark to market
    eq = round(equity(), 2)
    ref.update({"equity": eq, "lastPrice": round(price, 3), "lastRun": now})
    ref.collection("equity").document(str(today)).set({"date": str(today), "equity": eq, "cash": acct["cash"]})
    print(doc.id[:8], "equity", eq, "|", "; ".join(log) or "no action")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--force", action="store_true", help="ignore market hours (testing)")
    a = ap.parse_args()
    now = datetime.now(timezone.utc)
    today = date.fromisoformat(str(ist_today())[:10])
    rows = [json.loads(l) for l in open(ROOT / "data" / "live_cards.jsonl")]
    card = rows[-1] if rows else None
    price, src = live_price(card)
    if price is None:
        sys.exit("no price available")
    can = a.force or market_open(now)
    print(f"{today} price {price:.2f} ({src}) | market open: {can} | card: {card and card['date']}")
    db = init_db()
    for doc in db.collection("accounts").stream():
        try:
            run_account(db, doc, card, price, now, today, a.send, can)
        except Exception as e:
            print("account", doc.id[:8], "failed:", type(e).__name__, e)


if __name__ == "__main__":
    main()
