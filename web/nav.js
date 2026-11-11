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
