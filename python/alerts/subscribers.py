"""Subscribers from Firebase (Spark plan, free) or a local test file.
Only users whose email is VERIFIED in Firebase Auth and who opted in get mail."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_subscribers():
    sa = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if not sa:
        p = ROOT / "configs" / "subscribers.json"
        return json.loads(p.read_text()) if p.exists() else []
    import firebase_admin
    from firebase_admin import auth, credentials, firestore
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(json.loads(sa)))
    db, out = firestore.client(), []
    for d in db.collection("users").where("optIn", "==", True).stream():
        try:
            u = auth.get_user(d.id)
        except Exception:
            continue
        if not u.email_verified or not u.email:      # never trust a client-written flag
            continue
        x = d.to_dict()
        out.append({"uid": d.id, "email": u.email,
                    "digest": x.get("digest", True), "instant": x.get("instant", True)})
    return out
