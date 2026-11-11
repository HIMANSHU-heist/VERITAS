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
