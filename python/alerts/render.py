import html
import os

DISCLAIMER = ("VERITAS is a paper-trading research demo. No real orders are placed. "
              "This is not investment advice.")
TITLES = {
    "DAILY_DIGEST": "Daily decision",
    "TRADE_APPROVED": "Paper trade approved",
    "REDTEAM_VETO": "Red-team veto",
    "VIX_STRESS": "VIX stress, trading paused",
    "KILL_SWITCH": "Kill-switch / safety stop",
    "EVENING_RECAP": "Evening recap",
}


def render(kind, card, sub, demo=True):
    d, dec = card["date"], card["decision"]
    gates = ", ".join(card.get("gate_failed") or []) or "none"
    rows = [("Decision", dec), ("Model P(up)", card.get("p_up")),
            ("Conformal set", ", ".join(card.get("conformal_set") or [])),
            ("Edge estimate (%)", card.get("edge_pct")), ("Gates that blocked", gates)]
    if card.get("counterfactual"):
        rows.append(("What would change it", card["counterfactual"]))
    if card.get("proposal"):
        rows.append(("Strategy thesis", card["proposal"]["thesis"]))
    for o in ((card.get("red_team") or {}).get("objections") or [])[:3]:
        rows.append((f"Red-team {o['severity']}", o["text"]))
    if kind == "EVENING_RECAP":
        rows.append(("Paper P&L net of costs (INR)", card.get("net", 0.0)))
    tag = "[DEMO, historical card] " if demo else ""
    subject = f"{tag}[VERITAS paper] {TITLES[kind]}: {dec} ({d})"
    text = "\n".join(f"{k}: {v}" for k, v in rows) + "\n\n" + DISCLAIMER
    trs = "".join(f"<tr><td><b>{html.escape(str(k))}</b></td><td>{html.escape(str(v))}</td></tr>"
                  for k, v in rows)
    body = (f"<h3>{html.escape(TITLES[kind])} - {html.escape(d)}</h3>"
            f"<table cellpadding='6' border='1' style='border-collapse:collapse'>{trs}</table>"
            f"<p style='color:#666;font-size:12px'>{html.escape(DISCLAIMER)}</p>")
    app = os.environ.get("APP_URL", "")
    if app:
        body += f"<p style='font-size:12px'><a href='{html.escape(app)}'>Manage or unsubscribe</a></p>"
    return subject, text, body
