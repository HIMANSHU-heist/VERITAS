"""Live News Agent: fresh headlines -> sanitize (injection filter) -> LLM sentiment -> NewsOut.
Fails closed: any problem means neutral news (score 0), never a fake signal."""
from __future__ import annotations

import json

import feedparser

from python.agents import news_agent
from python.risk_client import ROOT
from python.schemas import NewsOut

NO_NEWS = NewsOut(score=0.0, confidence=0.0, evidence_ids=[])
FEEDS = [
    "https://news.google.com/rss/search?q=Nifty+OR+Sensex+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=RBI+OR+%22Indian+stock+market%22+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
]
feedparser.USER_AGENT = "Mozilla/5.0 (VERITAS paper-trading research)"


def fetch_headlines(limit=12):
    """Returns [(int_id, title)]. Ids are ints because NewsOut.evidence_ids is list[int]."""
    titles, seen = [], set()
    for url in FEEDS:
        try:
            for e in feedparser.parse(url).entries:
                t = str(e.get("title", "")).strip()
                if t and t.lower() not in seen:
                    seen.add(t.lower())
                    titles.append(t)
        except Exception:
            continue
    if not titles:  # fallback: whatever the watcher saved last
        try:
            w = json.loads((ROOT / "web" / "data" / "watch.json").read_text())
            titles = [h["title"] for h in w.get("headlines", [])]
        except Exception:
            titles = []
    return list(enumerate(titles[:limit], start=1))


def live_news(llm, as_of):
    """Returns (NewsOut, flagged_ids, items). Neutral on any failure."""
    try:
        items = fetch_headlines()
        if not items:
            return NO_NEWS, [], []
        news, flagged = news_agent(llm, items, as_of=as_of)
        return news, flagged, items
    except Exception:
        return NO_NEWS, [], []


if __name__ == "__main__":
    import pandas as pd

    from python.llm import LLM

    llm = LLM()
    news, flagged, items = live_news(llm, pd.Timestamp.now(tz="UTC"))
    print("headlines:", len(items), "| flagged as injection:", flagged)
    for i, t in items:
        print(f"  [{i}] {t}")
    print("NEWS:", news.model_dump())
