import hashlib
import os
import smtplib
import ssl
import time
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def send(to, subject, text, html_body, dry_run=True):
    if dry_run:
        out = ROOT / "outbox"
        out.mkdir(exist_ok=True)
        h = hashlib.md5(subject.encode()).hexdigest()[:8]
        (out / f"{to.replace('@', '_at_')}_{h}.html").write_text(html_body)
        return "dry-run"
    user, pw = os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"]
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = f"VERITAS Alerts <{user}>", to, subject
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, pw)
        s.send_message(msg)
    time.sleep(1)
    return "sent"
