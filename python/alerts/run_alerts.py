import argparse
import json
from pathlib import Path

from python.alerts.mailer import send
from python.alerts.render import render
from python.alerts.rules import events_for
from python.alerts.subscribers import load_subscribers

ROOT = Path(__file__).resolve().parents[2]
SENT = ROOT / "data" / "alerts_sent.jsonl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", default="results/pipeline_cards.jsonl")
    ap.add_argument("--index", type=int, default=-1)
    ap.add_argument("--phase", default="morning", choices=["morning", "evening"])
    ap.add_argument("--to", default=None)
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--live", action="store_true", help="remove the [DEMO] label")
    a = ap.parse_args()
    cards = [json.loads(l) for l in open(ROOT / a.cards)]
    card = cards[a.index]
    subs = [{"email": a.to}] if a.to else load_subscribers()
    sent = {json.loads(l)["key"] for l in open(SENT)} if SENT.exists() else set()
    n = 0
    for sub in subs:
        for kind, _ in events_for(card, a.phase):
            digest_kind = kind in ("DAILY_DIGEST", "EVENING_RECAP")
            wants = sub.get("digest", True) if digest_kind else sub.get("instant", True)
            key = f"{sub['email']}|{card['date']}|{kind}"
            if not wants or key in sent:
                continue
            subject, text, body = render(kind, card, sub, demo=not a.live)
            status = send(sub["email"], subject, text, body, dry_run=not a.send)
            if a.send:
                SENT.parent.mkdir(exist_ok=True)
                with open(SENT, "a") as f:
                    f.write(json.dumps({"key": key}) + "\n")
            n += 1
            print(status, kind, "->", sub["email"])
    print("mails:", n, "| mode:", "SEND" if a.send else "DRY-RUN (see outbox/)")


if __name__ == "__main__":
    main()
