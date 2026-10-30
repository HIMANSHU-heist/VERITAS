#!/usr/bin/env bash
source "$(dirname "$0")/_lib.sh"
say "PHASE 6: README + full test run"

cat > scripts/phases/_readme.md <<'EOF_M'
## v2 upgrade notes

- **Faster live jobs.** The watcher and paper trader run every 15 minutes in market hours, with a lean `requirements.txt` (full freeze kept in `requirements-full.txt`) and parallel news and price fetching.
- **Three new code-only agents.** Levels (pivots, ATR, range), Scorecard (live Brier score and hit rate) and Data Quality (stale bars, jumps). All advisory: only the C++ engine can approve a trade.
- **Regime fix.** The Regime agent now reads the decision-time row from DataClock instead of the last training row.
- **New UI.** Shared navbar with a live status badge, a six-tab Agents page, a KPI strip on the Terminal, a dark Alerts page, and an installable PWA.
- **CI and deploy.** `ci.yml` runs pytest on every push touching Python or C++. `deploy.yml` redeploys Firebase Hosting when `web/` changes.

EOF_M
python - <<'PY'
from _patch import sub
sec = open("scripts/phases/_readme.md", encoding="utf-8").read()
sub("README.md", "## 19. Disclaimer", sec + "## 19. Disclaimer")
PY
rm -f scripts/phases/_readme.md

pytest -q || echo "WARN: some tests failed (read the output above). Docs are still committed."

finish "docs: README v2 upgrade notes" README.md
say "ALL PHASES DONE"
echo "Next: GitHub -> Actions: run ci, deploy-web, paper-trader and market-watch once with workflow_dispatch."
