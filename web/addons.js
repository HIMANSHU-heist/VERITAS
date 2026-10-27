(async () => {
  const J = u => fetch(u + "?t=" + Date.now()).then(r => r.ok ? r.json() : null).catch(() => null);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const inr = n => (n < 0 ? "-" : "") + "₹" + Math.abs(Math.round(n)).toLocaleString("en-IN");
  const cl = n => n >= 0 ? "p" : "n";
  const [d, v, les, w, ag, t] = await Promise.all(["data/data.json","data/veto.json","data/lessons.json","data/watch.json","data/agents.json","data/today.json"].map(J));
  const a = ag || {}, c = t && t.card, rg = a.regime, rk = a.risk, db = a.debate, pf = a.portfolio, dr = a.drift;
  let hs = (w && (w.headlines || w.items)) || [];
  if (!hs.length && c && c.news) hs = c.news.headlines.map(h => ({title: h.text}));

  const A = (n, ty, role, o) => `<div class="cd"><b>${esc(n)}</b> <small>${esc(ty)}</small><p>${esc(role)}</p><small>${esc(o || "Waiting for first run")}</small></div>`;
  const none = cmd => `<div class="cd">No data yet. Run <code>${esc(cmd)}</code></div>`;
  const tabs = [
    ["Agents", `<p class="sb">Ten agents, one hard C++ gate and the chatbot. Language models only explain or say no. They never flip a trade.</p><div class="gr">` + [
      A("Cue Agent", "AI", "Explains the macro signal in plain words", c ? "Cue score " + c.cue_score : ""),
      A("News Agent", "AI", "Scores headlines, injection-filtered", c && c.news ? "Score " + c.news.score + ", confidence " + c.news.confidence + ", " + c.news.headlines.length + " headlines" : ""),
      A("Strategy Agent", "AI", "Proposes the model's direction or WAIT", ""),
      A("Red-team Agent", "AI", "Tries to falsify the trade and can veto", v ? v.n_vetoes + " vetoes, " + v.good_vetoes + " right" : ""),
      A("Reflection Agent", "AI", "Writes one lesson per settled day", les && les.length ? les.length + " lessons stored" : ""),
      A("Bull, Bear and Judge", "AI", "Debate the trade, judge agrees or says WAIT", db ? "Judge: " + db.judge.verdict + ". " + db.judge.reason : ""),
      A("Regime Agent", "Code", "Trending, sideways or volatile; scales confidence", rg ? rg.label + " (x" + rg.conf_mult + "). " + rg.why : ""),
      A("Dynamic Risk Agent", "Code", "Shrinks size under stress, never grows it", rk ? "Size x" + rk.scale + ". " + rk.why.join("; ") : ""),
      A("Portfolio Agent", "Code", "Inverse-volatility weights across 4 stocks", pf ? Object.entries(pf.weights).map(e => e[0] + " " + Math.round(e[1] * 100) + "%").join(", ") + ". " + pf.flag : ""),
      A("Drift Monitor", "ML", "Checks accuracy and conformal coverage", dr ? dr.status + ": accuracy " + dr.accuracy + ", coverage " + dr.coverage + " (target " + dr.target_coverage + ")" : ""),
      A("C++ Risk Gate", "Hard rules", "Final authority: costs, limits, kill-switch, audit chain", "No agent can override it"),
      A("Ask VERITAS", "AI", "The chat button, bottom right", "Answers from dashboard data")
    ].join("") + "</div>"],
    ["Day tape", d && d.cards ? `<p class="sb">Sat out ${d.cards.filter(x => x.decision !== "TRADE").length} of ${d.cards.length} days. Green profit, red loss, amber red-team veto, grey sat out.</p><div class="tp">` +
      d.cards.map(x => { const k = x.decision === "TRADE" ? (x.net >= 0 ? "w" : "l") : ((x.gate_failed || []).includes("redteam_veto") ? "v" : ""); return `<i class="${k}" title="${esc(x.date)}: ${esc(x.decision)} ${esc((x.gate_failed || []).join(", "))}"></i>`; }).join("") + "</div>" : none("python -m python.export_web")],
    ["Veto Tracker", v ? `<p class="sb">Trades the red-team blocked, rebuilt and priced with real costs.</p><div class="gr"><div class="cd"><div class="kk">${v.good_vetoes}/${v.n_vetoes}</div><small>Vetoes that were right (${Math.round(v.good_veto_rate * 100)}%)</small></div><div class="cd"><div class="kk p">${inr(v.loss_avoided_inr)}</div><small>Losses avoided</small></div><div class="cd"><div class="kk n">${inr(-v.profit_missed_inr)}</div><small>Profit missed</small></div><div class="cd"><div class="kk ${cl(v.net_effect_inr)}">${inr(v.net_effect_inr)}</div><small>Net effect of red-team</small></div></div><div class="cd xs" style="margin-top:10px"><table><tr><th>Date<th>Side<th>Move<th>Would have made<th>Veto</tr>` +
      v.days.slice().reverse().map(r => `<tr><td>${esc(r.date)}<td>${esc(r.side)}<td>${r.ret_oc_pct}%<td class="${cl(r.would_be_net)}">${inr(r.would_be_net)}<td>${r.veto_was === "GOOD" ? "Right" : "Wrong"}</tr>`).join("") + "</table></div>" : none("python -m python.export_extras")],
    ["Agent memory", les && les.length ? `<p class="sb">One lesson per settled day. The last five feed tomorrow's strategy prompt.</p><div class="cd">` + les.slice().reverse().map(r => `<p>${esc(r.lesson)}<br><small>${esc(r.date)} · ${esc(r.verdict)}</small></p>`).join("") + "</div>" : none("python -m python.export_extras")],
    ["Headlines", hs.length ? `<p class="sb">Injection-filtered before any model sees them.</p><div class="cd"><ul>` + hs.slice(0, 10).map(h => `<li>${esc(h.title)}</li>`).join("") + "</ul></div>" : none("python -m python.watcher")]
  ];

  const st = document.createElement("style");
  st.textContent = `#vxm{position:fixed;inset:0;z-index:2147483000;display:none}#vxm.on{display:block}
  #vxm .bk{position:absolute;inset:0;background:rgba(0,0,0,.6)}
  #vxm .pn{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:min(780px,94vw);max-height:86vh;display:flex;flex-direction:column;background:#171b26;color:#d1d4dc;border:1px solid #2a2e39;border-radius:12px;box-shadow:0 20px 60px rgba(0,0,0,.6);font:14px/1.5 system-ui,sans-serif}
  #vxm .hd{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid #2a2e39}
  #vxm .hd button{background:none;border:0;color:#d1d4dc;font-size:18px;cursor:pointer;padding:2px 8px;border-radius:6px}
  #vxm .tb{display:flex;gap:6px;padding:10px 16px;overflow-x:auto;border-bottom:1px solid #2a2e39}
  #vxm .tb button{flex:none;font:inherit;color:#d1d4dc;background:#1e222d;border:1px solid #2a2e39;border-radius:6px;padding:6px 12px;cursor:pointer}
  #vxm .tb button.on{background:#2962ff;border-color:#2962ff;color:#fff;font-weight:600}
  #vxm .ct{overflow:auto;padding:14px 16px}#vxm .sb{color:#787b86;margin:0 0 12px}
  #vxm .gr{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(210px,1fr))}
  #vxm .cd{background:#1e222d;border:1px solid #2a2e39;border-radius:8px;padding:10px 12px}#vxm .cd p{margin:4px 0}
  #vxm small{color:#787b86}#vxm .kk{font-size:22px;font-weight:700}#vxm .p{color:#26a69a}#vxm .n{color:#ef5350}
  #vxm table{width:100%;border-collapse:collapse;font-size:13px}#vxm td,#vxm th{text-align:left;padding:6px;border-bottom:1px solid #2a2e39}#vxm .xs{overflow-x:auto}
  #vxm .tp{display:flex;flex-wrap:wrap;gap:3px}#vxm .tp i{width:11px;height:11px;border-radius:2px;background:#434651}#vxm .tp i.w{background:#26a69a}#vxm .tp i.l{background:#ef5350}#vxm .tp i.v{background:#f5a623}
  #vxm ul{margin:0;padding:0}#vxm li{list-style:none;padding:7px 0;border-bottom:1px solid #2a2e39}
  #vxm button:focus-visible{outline:2px solid #6d9bff;outline-offset:2px}
  #vxl{position:fixed;left:14px;bottom:14px;z-index:99998;background:#2962ff;color:#fff;border:0;border-radius:99px;padding:9px 16px;font:600 14px system-ui,sans-serif;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.4)}`;
  document.head.append(st);

  const m = document.createElement("div");
  m.id = "vxm";
  m.innerHTML = `<div class="bk"></div><div class="pn" role="dialog" aria-modal="true" aria-label="VERITAS agents"><div class="hd"><b>VERITAS · Agents</b><button type="button" aria-label="Close">✕</button></div><div class="tb"></div><div class="ct"></div></div>`;
  document.body.append(m);
  const tb = m.querySelector(".tb"), ct = m.querySelector(".ct"), xb = m.querySelector(".hd button");
  const show = i => { ct.innerHTML = tabs[i][1]; ct.scrollTop = 0; [...tb.children].forEach((b, j) => b.classList.toggle("on", i === j)); };
  tabs.forEach((x, i) => { const b = document.createElement("button"); b.type = "button"; b.textContent = x[0]; b.onclick = () => show(i); tb.append(b); });
  const open = (i = 0) => { show(i); m.classList.add("on"); xb.focus(); };
  const close = () => m.classList.remove("on");
  xb.onclick = close; m.querySelector(".bk").onclick = close;
  document.addEventListener("keydown", e => { if (e.key === "Escape") close(); });

  const anchor = document.querySelector('a.lnk[href="subscribe.html"]');
  if (anchor) {
    const l = document.createElement("a");
    l.className = anchor.className; l.href = "#agents"; l.textContent = "Agents";
    l.onclick = e => { e.preventDefault(); open(0); };
    anchor.before(l);
  } else {
    const f = document.createElement("button");
    f.id = "vxl"; f.type = "button"; f.textContent = "Agents"; f.onclick = () => open(0);
    document.body.append(f);
  }
})();
