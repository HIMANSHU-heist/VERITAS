#!/usr/bin/env bash
source "$(dirname "$0")/_lib.sh"
say "PHASE 2: 3 new code agents + regime fix + tests"

cat > python/agents/levels.py <<'EOF_A'
"""Levels Agent (code only): classic pivots, ATR and 20-day range from NIFTY daily bars. Advisory."""
import pandas as pd

from python.dataclock import load_frozen


def levels(df=None, n=14):
    if df is None:
        df = load_frozen("NIFTY")
        df = df[df["available_at"] <= pd.Timestamp.now(tz="UTC")]
    df = df.dropna(subset=["high", "low", "close"]).reset_index(drop=True)
    if len(df) < n + 2:
        raise ValueError("not enough bars")
    h, l, c = (df[k].astype(float) for k in ("high", "low", "close"))
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(n).mean().iloc[-1])
    H, L, C = float(h.iloc[-1]), float(l.iloc[-1]), float(c.iloc[-1])
    p = (H + L + C) / 3
    hi20, lo20 = float(h.tail(20).max()), float(l.tail(20).min())
    pos = (C - lo20) / (hi20 - lo20) if hi20 > lo20 else 0.5
    where = "near 20-day high" if pos >= 0.8 else "near 20-day low" if pos <= 0.2 else "mid-range"
    atr_pct = atr / C * 100
    out = {"asof": str(df["date"].iloc[-1].date()), "close": C, "atr": atr, "atr_pct": atr_pct,
           "hi20": hi20, "lo20": lo20, "range_pos": pos, "where": where,
           "pivot": p, "r1": 2 * p - L, "s1": 2 * p - H, "r2": p + (H - L), "s2": p - (H - L),
           "suggested_stop_pct": 1.5 * atr_pct, "suggested_target_pct": 2.5 * atr_pct}
    return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in out.items()}
EOF_A

cat > python/agents/scorecard.py <<'EOF_A'
"""Scorecard Agent (code only): grades the LIVE model on settled days. Advisory."""


def scorecard(cards):
    cs = [c for c in cards if c.get("p_up") is not None]
    st = [c for c in cs if c.get("settled") and c.get("ret_oc_pct") is not None]
    tr = [c for c in st if c.get("decision") == "TRADE"]
    n_trade_cards = sum(1 for c in cs if c.get("decision") == "TRADE")
    out = {"n_cards": len(cards), "n_settled": len(st), "n_trades": len(tr),
           "abstain_rate": round(1 - n_trade_cards / len(cs), 3) if cs else None,
           "net_total": round(sum(float(c.get("net") or 0) for c in tr), 2),
           "win_rate": round(sum(1 for c in tr if (c.get("net") or 0) > 0) / len(tr), 3) if tr else None,
           "brier": None, "shadow_hit_rate": None, "status": "COLLECTING"}
    if st:
        brier = sum((c["p_up"] - (1.0 if c["ret_oc_pct"] > 0 else 0.0)) ** 2 for c in st) / len(st)
        hit = sum(1 for c in st if (c.get("ml_direction") == "BUY") == (c["ret_oc_pct"] > 0)) / len(st)
        out.update(brier=round(brier, 4), shadow_hit_rate=round(hit, 3))
    if len(st) >= 20:
        out["status"] = "BETTER_THAN_COIN" if out["brier"] < 0.25 else "NOT_BETTER_THAN_COIN"
    out["note"] = "Brier below 0.25 beats a coin flip. Needs 20+ settled days to mean anything."
    return out
EOF_A

cat > python/agents/dataquality.py <<'EOF_A'
"""Data Quality Agent (code only): stale bars, missing closes, duplicates and suspicious jumps."""
import pandas as pd

from python.dataclock import load_frozen

NAMES = ["NIFTY", "SP500", "NASDAQ", "NIKKEI", "CRUDE", "GOLD", "USDINR", "INDIAVIX",
         "RELIANCE", "TCS", "HDFCBANK", "INFY"]


def data_quality(frames=None, today=None):
    if today is None:
        today = pd.Timestamp.now(tz="UTC").tz_localize(None)
    today = pd.Timestamp(today).normalize()
    if frames is None:
        frames = {n: load_frozen(n) for n in NAMES}
    rows, issues, bad, warn = [], [], False, False
    for name, df in frames.items():
        df = df.sort_values("date").reset_index(drop=True)
        last = pd.Timestamp(df["date"].iloc[-1]).normalize()
        age = int((today - last).days)
        flags = []
        if age > 5:
            flags.append("stale"); bad = True
        c = df["close"].astype(float)
        if pd.isna(c.iloc[-1]):
            flags.append("missing_close"); bad = True
        if len(c) > 1 and c.iloc[-2]:
            jump = abs(c.iloc[-1] / c.iloc[-2] - 1)
            if jump > (0.30 if name == "INDIAVIX" else 0.08):
                flags.append(f"jump_{jump * 100:.1f}pct"); warn = True
        if df["date"].duplicated().any():
            flags.append("duplicate_dates"); bad = True
        rows.append({"name": name, "last": str(last.date()), "age_days": age, "rows": int(len(df)), "flags": flags})
        if flags:
            issues.append(f"{name}: {', '.join(flags)}")
    return {"status": "BAD" if bad else "WARN" if warn else "OK", "series": rows, "issues": issues}
EOF_A

cat > python/tests/test_new_agents.py <<'EOF_T'
import pandas as pd

from python.agents.dataquality import data_quality
from python.agents.levels import levels
from python.agents.scorecard import scorecard


def bars(n=40, start=100.0):
    d = pd.date_range("2026-01-01", periods=n, freq="B")
    c = pd.Series([start + i * 0.5 for i in range(n)])
    return pd.DataFrame({"date": d, "open": c, "high": c + 1, "low": c - 1, "close": c})


def test_levels_order_and_range():
    r = levels(bars())
    assert r["s2"] < r["s1"] < r["pivot"] < r["r1"] < r["r2"]
    assert r["atr"] > 0 and 0 <= r["range_pos"] <= 1
    assert r["where"] == "near 20-day high"


def test_scorecard_empty_and_basic():
    assert scorecard([])["n_settled"] == 0
    cards = [{"date": f"d{i}", "p_up": 0.7, "ml_direction": "BUY",
              "decision": "TRADE" if i % 2 else "ABSTAIN", "settled": True,
              "ret_oc_pct": 0.5 if i < 8 else -0.5, "net": 10.0 if i % 2 else 0.0} for i in range(10)]
    r = scorecard(cards)
    assert r["n_settled"] == 10 and r["n_trades"] == 5
    assert abs(r["abstain_rate"] - 0.5) < 1e-9
    assert r["shadow_hit_rate"] == 0.8


def test_dataquality_flags_stale_and_jump():
    ok, jump = bars(), bars()
    jump.loc[len(jump) - 1, "close"] = jump["close"].iloc[-2] * 1.2
    today = ok["date"].iloc[-1]
    assert data_quality({"A": ok, "B": jump}, today=today)["status"] == "WARN"
    assert data_quality({"A": ok}, today=today + pd.Timedelta(days=10))["status"] == "BAD"
    assert data_quality({"A": ok}, today=today)["status"] == "OK"
EOF_T

cat > python/agent_report.py <<'EOF_R'
"""Runs the advisory agents on the latest live card -> web/data/agents.json (dashboard only)."""
import json
from datetime import datetime, timezone

import yaml

from python.agents.dataquality import data_quality
from python.agents.debate import debate
from python.agents.drift import drift
from python.agents.levels import levels
from python.agents.portfolio import portfolio
from python.agents.regime import adjust_p_up, regime
from python.agents.risk_agent import risk_scale
from python.agents.scorecard import scorecard
from python.risk_client import ROOT


def safe(name, fn):
    try:
        return fn()
    except Exception as e:
        print(f"{name} skipped: {type(e).__name__} {e}")
        return None


def _regime(card):
    # uses the row DataClock exposes at decision time (the old code used yesterday's training row)
    from python.daily import live_row
    from python.dataclock import to_utc
    row, _, _ = live_row(to_utc(card["asof"]), None)
    r = regime(row)
    r["adj_p_up"] = adjust_p_up(card["p_up"], r["conf_mult"])
    return r


def _debate(card, reg):
    from python.llm import LLM
    return debate(LLM(), {**card, "regime": (reg or {}).get("label")})


def main():
    cards = [json.loads(l) for l in open(ROOT / "data" / "live_cards.jsonl") if l.strip()]
    card = cards[-1]
    cap = float(yaml.safe_load(open(ROOT / "configs" / "limits.yaml"))["starting_capital_inr"])
    reg = safe("regime", lambda: _regime(card))
    out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "date": card["date"],
           "regime": reg,
           "risk": safe("risk", lambda: risk_scale(card["vix"], cards, cap)),
           "debate": safe("debate", lambda: _debate(card, reg)),
           "portfolio": safe("portfolio", portfolio), "drift": safe("drift", drift),
           "levels": safe("levels", levels),
           "scorecard": safe("scorecard", lambda: scorecard(cards)),
           "dataquality": safe("dataquality", data_quality)}
    p = ROOT / "web" / "data"
    p.mkdir(parents=True, exist_ok=True)
    (p / "agents.json").write_text(json.dumps(out, ensure_ascii=False))
    print({k: ("ok" if v else "skipped") for k, v in out.items() if k not in ("generated_at", "date")})


if __name__ == "__main__":
    main()
EOF_R

pytest -q python/tests/test_new_agents.py

python - <<'PY'
import json, pathlib
from python.agents.dataquality import data_quality
from python.agents.levels import levels
from python.agents.scorecard import scorecard
p = pathlib.Path("web/data/agents.json")
d = json.loads(p.read_text()) if p.exists() else {}
cp = pathlib.Path("data/live_cards.jsonl")
cards = [json.loads(l) for l in open(cp) if l.strip()] if cp.exists() else []
for k, fn in (("levels", levels), ("scorecard", lambda: scorecard(cards)), ("dataquality", data_quality)):
    try:
        d[k] = fn()
    except Exception as e:
        print(k, "skipped:", type(e).__name__, e)
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(d, ensure_ascii=False))
print("agents.json keys:", sorted(d))
PY

finish "feat(agents): Levels, Scorecard, DataQuality agents; regime now uses decision-time row" \
  python/agents/levels.py python/agents/scorecard.py python/agents/dataquality.py \
  python/agent_report.py python/tests/test_new_agents.py web/data/agents.json
say "PHASE 2 DONE"
