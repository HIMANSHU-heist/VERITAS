#!/usr/bin/env bash
source "$(dirname "$0")/_lib.sh"
say "PHASE 3: shared navbar, PWA, hosting headers, auto-deploy"

cat > web/shared.css <<'EOF_W'
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:8px;padding:10px 12px;background:#131722;border-bottom:1px solid #2a2e39}
.kg{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px}
.kp{background:#1e222d;border:1px solid #2a2e39;border-radius:8px;padding:8px 12px}
.kp small{display:block;color:#8b94a7;font-size:11px;letter-spacing:.06em;text-transform:uppercase}
.kp b{font-size:18px;font-weight:700}
.kpis .empty{color:#8b94a7;padding:6px}
EOF_W

cat > web/nav.js <<'EOF_W'
(() => {
  const LINKS = [["index.html", "Terminal"], ["agents.html", "Agents"], ["portfolio.html", "Portfolio"],
                 ["flow.html", "How it works"], ["subscribe.html", "Alerts"]];
  const cur = location.pathname.split("/").pop() || "index.html";
  const css = document.createElement("style");
  css.textContent = `
  .vnav{position:sticky;top:0;z-index:1000;display:flex;align-items:center;gap:4px;height:48px;padding:0 12px;background:#0f131d;border-bottom:1px solid #2a2e39;font:600 13px Inter,system-ui,sans-serif;overflow-x:auto;white-space:nowrap;scrollbar-width:none}
  .vnav::-webkit-scrollbar{display:none}
  .vnav .vb{display:flex;align-items:center;gap:8px;margin-right:10px;color:#d1d4dc;font-weight:800;letter-spacing:.14em;text-decoration:none}
  .vnav .vb i{width:20px;height:20px;border-radius:6px;background:linear-gradient(135deg,#2962ff,#9b7bff)}
  .vnav a.vl{color:#8b94a7;text-decoration:none;padding:7px 12px;border-radius:8px}
  .vnav a.vl:hover{color:#d1d4dc;background:#1a1f2c}
  .vnav a.vl.on{color:#fff;background:#2962ff}
  .vnav .vs{margin-left:auto;padding-left:14px;font-weight:500;font-size:12px;color:#8b94a7}
  .vnav .vs b{display:inline-block;width:8px;height:8px;border-radius:50%;background:#26a69a;margin-right:6px}
  .vnav .vs.old b{background:#f5a623}
  .hdr{top:48px!important}`;
  document.head.append(css);

  const lm = document.createElement("link");
  lm.rel = "manifest"; lm.href = "manifest.webmanifest";
  document.head.append(lm);

  const nav = document.createElement("nav");
  nav.className = "vnav";
  nav.setAttribute("aria-label", "Main");
  nav.innerHTML = '<a class="vb" href="index.html"><i></i>VERITAS</a>' +
    LINKS.map(l => `<a class="vl${cur === l[0] ? " on" : ""}" href="${l[0]}">${l[1]}</a>`).join("") +
    '<span class="vs" id="vns"></span>';
  document.body.prepend(nav);

  fetch("data/today.json?t=" + Date.now()).then(r => r.ok ? r.json() : null).then(j => {
    if (!j) return;
    const h = (Date.now() - new Date(j.generated_at)) / 36e5;
    const el = document.getElementById("vns");
    el.className = "vs" + (h > 80 ? " old" : "");
    el.innerHTML = "<b></b>" + (j.card ? j.card.date + " · " + j.card.decision : "no card") + " · " +
      (h < 1 ? "just now" : h < 48 ? Math.round(h) + "h ago" : Math.round(h / 24) + "d ago");
  }).catch(() => {});

  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
})();
EOF_W

cat > web/sw.js <<'EOF_W'
const V = "veritas-v1";
const STATIC = ["./", "index.html", "agents.html", "portfolio.html", "flow.html", "subscribe.html",
                "shared.css", "nav.js", "chat.js", "icon.svg"];
self.addEventListener("install", e => {
  e.waitUntil(caches.open(V).then(c => Promise.allSettled(STATIC.map(u => c.add(u)))).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(k => Promise.all(k.filter(x => x !== V).map(x => caches.delete(x)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const r = e.request;
  if (r.method !== "GET") return;
  const u = new URL(r.url);
  if (u.origin !== location.origin) return;
  if (u.pathname.includes("/data/")) { e.respondWith(fetch(r).catch(() => caches.match(r))); return; }
  e.respondWith(fetch(r).then(res => { const c = res.clone(); caches.open(V).then(x => x.put(r, c)); return res; })
    .catch(() => caches.match(r)));
});
EOF_W

cat > web/manifest.webmanifest <<'EOF_W'
{
  "name": "VERITAS Terminal",
  "short_name": "VERITAS",
  "description": "Paper-trading research: ML proposes, AI agents review, C++ decides.",
  "start_url": "./",
  "display": "standalone",
  "background_color": "#131722",
  "theme_color": "#131722",
  "icons": [{ "src": "icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any" }]
}
EOF_W

cat > web/icon.svg <<'EOF_W'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2962ff"/><stop offset="1" stop-color="#9b7bff"/></linearGradient></defs><rect width="128" height="128" rx="28" fill="url(#g)"/><path d="M30 38l34 56 34-56" fill="none" stroke="#fff" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/></svg>
EOF_W

cat > firebase.json <<'EOF_W'
{
  "hosting": {
    "public": "web",
    "ignore": ["firebase.json", "**/.*"],
    "headers": [
      { "source": "/data/**", "headers": [{ "key": "Cache-Control", "value": "no-cache" }] },
      { "source": "/sw.js", "headers": [{ "key": "Cache-Control", "value": "no-cache" }] },
      { "source": "**/*.@(js|css|html)", "headers": [{ "key": "Cache-Control", "value": "no-cache" }] }
    ]
  },
  "firestore": { "rules": "firestore.rules" }
}
EOF_W

cat > .github/workflows/deploy.yml <<'EOF_W'
name: deploy-web
on:
  push:
    branches: [main]
    paths: ["web/**", "!web/data/**", "firebase.json"]
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: veritas-deploy
  cancel-in-progress: true
jobs:
  deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v5
      - name: Deploy Firebase Hosting
        env:
          SA: ${{ secrets.FIREBASE_SERVICE_ACCOUNT }}
        run: |
          echo "$SA" > "$RUNNER_TEMP/sa.json"
          export GOOGLE_APPLICATION_CREDENTIALS="$RUNNER_TEMP/sa.json"
          npx --yes firebase-tools@15 deploy --only hosting --project veritas-trading --non-interactive
          rm -f "$RUNNER_TEMP/sa.json"
EOF_W

python -m json.tool firebase.json >/dev/null && python -m json.tool web/manifest.webmanifest >/dev/null && echo "json ok"
jscheck web/nav.js
jscheck web/sw.js

finish "feat(web): shared navbar with live status, PWA manifest + service worker, no-cache headers, auto-deploy" \
  web/shared.css web/nav.js web/sw.js web/manifest.webmanifest web/icon.svg firebase.json .github/workflows/deploy.yml
say "PHASE 3 DONE"
