#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
[ -f .venv/bin/activate ] && source .venv/bin/activate || true
export PYTHONPATH="$ROOT/scripts/phases:$ROOT${PYTHONPATH:+:$PYTHONPATH}"

say() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }

finish() {  # finish "commit message" path...
  local msg="$1"; shift
  git add -A -- "$@"
  if git diff --cached --quiet; then echo "nothing to commit"; return 0; fi
  git commit -q -m "$msg"
  echo "committed: $msg"
  if git pull --rebase --autostash -q origin main && git push -q origin HEAD:main; then
    echo "pushed to origin/main"
  else
    echo "WARN: push failed. Commit is saved locally. Run: git pull --rebase origin main && git push"
  fi
}

jscheck() {  # jscheck file.html|file.js
  command -v node >/dev/null || { echo "node not found, skipping JS syntax check"; return 0; }
  python - "$1" <<'PY'
import re, subprocess, sys, tempfile
p = sys.argv[1]
t = open(p, encoding="utf-8").read()
parts = [t] if p.endswith(".js") else re.findall(r"<script(?![^>]*src)[^>]*>(.*?)</script>", t, re.S)
for m in parts:
    ext = ".mjs" if "import " in m[:600] else ".js"
    f = tempfile.NamedTemporaryFile("w", suffix=ext, delete=False, encoding="utf-8")
    f.write(m); f.close()
    r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
    if r.returncode:
        print(r.stderr); sys.exit(1)
print("js ok:", p)
PY
}
