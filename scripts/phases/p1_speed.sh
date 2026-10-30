#!/usr/bin/env bash
source "$(dirname "$0")/_lib.sh"
say "PHASE 1: lean deps, parallel fetch, 15-min cadence, CI"

[ -f requirements-full.txt ] || cp requirements.txt requirements-full.txt
cat > requirements.txt <<'EOF_REQ'
# Lean runtime + test deps. The full freeze is kept in requirements-full.txt
yfinance==1.7.0
pandas==3.1.0
numpy==2.5.4
pyarrow==26.0.0
scikit-learn==1.9.1
lightgbm==4.7.0
joblib==1.6.0
pydantic==2.14.1
tenacity==9.2.1
PyYAML==6.0.3
groq==1.7.0
feedparser==6.0.14
firebase_admin==7.7.0
pytest==9.1.1
EOF_REQ
pip install --dry-run -q -r requirements.txt >/dev/null 2>&1 && echo "lean deps resolve OK" \
  || echo "WARN: lean deps did not resolve. Restore with: cp requirements-full.txt requirements.txt"
python - <<'PY'
import yfinance, pandas, numpy, pyarrow, sklearn, lightgbm, joblib, pydantic, tenacity, yaml, groq, feedparser, firebase_admin
print("imports ok")
PY

sed -i -E 's|cron: "15,45 4-9 \* \* 1-5".*|cron: "2,17,32,47 4-9 * * 1-5"      # every 15 min in market hours|' .github/workflows/watch.yml
sed -i -E 's|cron: "20,50 4-9 \* \* 1-5".*|cron: "7,22,37,52 4-9 * * 1-5"      # every 15 min in market hours|' .github/workflows/paper.yml
grep -q '2,17,32,47' .github/workflows/watch.yml
grep -q '7,22,37,52' .github/workflows/paper.yml

python - <<'PY'
from _patch import sub
P = "python/watcher.py"
fast = '''# ---------- parallel collectors (fast path) ----------
from concurrent.futures import ThreadPoolExecutor


def _parse_feed(u):
    try:
        return feedparser.parse(u, agent=UA).entries[:15]
    except Exception:
        return []


def fetch_news_parallel(max_age_h=6):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_h)
    urls = [gnews(q) for q in QUERIES] + EXTRA_FEEDS
    with ThreadPoolExecutor(max_workers=len(urls)) as ex:
        feeds = list(ex.map(_parse_feed, urls))
    seen, out = set(), []
    for entries in feeds:
        for e in entries:
            title = " ".join(str(e.get("title", "")).split())
            pp = e.get("published_parsed")
            if not title or not pp:
                continue
            ts = datetime(*pp[:6], tzinfo=timezone.utc)
            if ts < cutoff:
                continue
            hid = hashlib.sha1(title.lower().encode()).hexdigest()[:12]
            if hid in seen:
                continue
            seen.add(hid)
            out.append({"id": hid, "title": title, "link": e.get("link", ""), "ts": ts.isoformat()})
    out.sort(key=lambda x: x["ts"], reverse=True)
    return out


def snapshots_parallel():
    with ThreadPoolExecutor(max_workers=len(WATCH)) as ex:
        res = list(ex.map(snapshot, WATCH.values()))
    return {k: s for k, s in zip(WATCH, res) if s}


'''
sub(P, "# ---------- AI explain ----------", fast + "# ---------- AI explain ----------")
sub(P, """        for k, sym in WATCH.items():
            s = snapshot(sym)
            if s:
                snaps[k] = s
""", "        snaps.update(snapshots_parallel())\n")
sub(P, "    items = fetch_news()\n", "    items = fetch_news_parallel()\n")
PY
python -c "import python.watcher; print('watcher imports ok')"
pytest -q python/tests/test_alerts.py

cat > .github/workflows/ci.yml <<'EOF_CI'
name: ci
on:
  push:
    branches: [main]
    paths: ["python/**", "cpp/**", "requirements.txt", "configs/**"]
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.14"
          cache: pip
      - run: pip install -r requirements.txt
      - name: Build C++ risk engine
        run: |
          sudo apt-get update -y
          sudo apt-get install -y cmake nlohmann-json3-dev libssl-dev
          cmake -S cpp -B cpp/build
          cmake --build cpp/build
      - run: pytest -q
EOF_CI

finish "perf: lean requirements, parallel news/price fetch, 15-min cadence, CI workflow" \
  requirements.txt requirements-full.txt .github/workflows/watch.yml .github/workflows/paper.yml \
  .github/workflows/ci.yml python/watcher.py
say "PHASE 1 DONE"
