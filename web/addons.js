(async () => {
  const J = u => fetch(u + "?t=" + Date.now()).then(r => r.ok ? r.json() : null).catch(() => null);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const inr = n => (n < 0 ? "-" : "") + "₹" + Math.abs(Math.round(n)).toLocaleString("en-IN");
  const cl = n => n >= 0 ? "p" : "n";
  const [d, v, les, w] = await Promise.all([J("data/data.json"), J("data/veto.json"), J("data/lessons.json"), J("data/watch.json")]);

  const css = `#vx{position:fixed;left:0;right:0;bottom:0;z-index:99999;display:flex;flex-direction:column-reverse;font:14px system-ui,sans-serif;color:inherit;border-top:1px solid rgba(128,128,128,.4);box-shadow:0 -4px 16px rgba(0,0,0,.35)}#vx .bar{padding:8px 10px}#vx .pn{max-height:55vh;overflow:auto;padding:12px 14px;border-bottom:1px solid rgba(128,128,128,.3)}
  #vx .bar{display:flex;flex-wrap:wrap;gap:8px}
  #vx .bar button{font:inherit;color:inherit;cursor:pointer;padding:9px 14px;border-radius:8px;border:1px solid rgba(128,128,128,.4);background:rgba(128,128,128,.08)}
  #vx .bar button:hover{background:rgba(128,128,128,.18)}
  #vx .bar button[aria-expanded=true]{background:rgba(128,128,128,.25);border-color:rgba(128,128,128,.8);font-weight:600}
  #vx .bar button:focus-visible{outline:2px solid #2962ff;outline-offset:2px}
  #vx .pn{display:none}#vx .pn.open{display:block}
  #vx p.s{opacity:.7;margin:0 0 10px}
  #vx .g{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(170px,1fr))}
  #vx .c{border:1px solid rgba(128,128,128,.3);background:rgba(128,128,128,.07);border-radius:8px;padding:12px}
  #vx .k{font-size:24px;font-weight:700}#vx small{opacity:.7;display:block;font-weight:400;font-size:13px}
  #vx .p{color:#26a69a}#vx .n{color:#ef5350}
  #vx table{width:100%;border-collapse:collapse;font-size:14px}#vx td,#vx th{text-align:left;padding:6px;border-bottom:1px solid rgba(128,128,128,.25)}
  #vx .t{display:flex;flex-wrap:wrap;gap:3px;margin:8px 0}#vx .t i{width:10px;height:10px;border-radius:2px;background:rgba(128,128,128,.45)}
  #vx .t i.w{background:#26a69a}#vx .t i.l{background:#ef5350}#vx .t i.v{background:#f5a623}
  #vx .x{overflow-x:auto}#vx li{padding:6px 0;border-bottom:1px solid rgba(128,128,128,.25);list-style:none}#vx ul{margin:0;padding:0}`;

  const tabs = [];
  if (d && d.cards) {
    const off = d.cards.filter(c => c.decision !== "TRADE").length;
    tabs.push(["Day tape", `<p class="s">Sat out ${off} of ${d.cards.length} days. Green = profit, red = loss, amber = red-team veto, grey = sat out. Hover a square for the reason.</p><div class="t">` +
      d.cards.map(c => {
        const k = c.decision === "TRADE" ? (c.net >= 0 ? "w" : "l") : ((c.gate_failed || []).includes("redteam_veto") ? "v" : "");
        return `<i class="${k}" title="${esc(c.date)}: ${esc(c.decision)} ${esc((c.gate_failed || []).join(", "))}"></i>`;
      }).join("") + "</div>"]);
  }
  if (v) {
    tabs.push(["Veto Tracker", `<p class="s">Trades the red-team blocked, rebuilt and priced with real costs.</p><div class="g">
      <div class="c"><div class="k">${v.good_vetoes}/${v.n_vetoes}</div><small>Vetoes that were right (${Math.round(v.good_veto_rate * 100)}%)</small></div>
      <div class="c"><div class="k p">${inr(v.loss_avoided_inr)}</div><small>Losses avoided</small></div>
      <div class="c"><div class="k n">${inr(-v.profit_missed_inr)}</div><small>Profit missed</small></div>
      <div class="c"><div class="k ${cl(v.net_effect_inr)}">${inr(v.net_effect_inr)}</div><small>Net effect of red-team</small></div></div>
      <div class="x" style="margin-top:10px"><table><tr><th>Date<th>Side<th>Move<th>Would have made<th>Veto</tr>` +
      v.days.slice(-10).reverse().map(r => `<tr><td>${esc(r.date)}<td>${esc(r.side)}<td>${r.ret_oc_pct}%<td class="${cl(r.would_be_net)}">${inr(r.would_be_net)}<td>${r.veto_was === "GOOD" ? "Right" : "Wrong"}</tr>`).join("") + "</table></div>"]);
  }
  if (les && les.length) {
    tabs.push(["Agent memory", `<p class="s">One lesson per settled day. The last five feed tomorrow's strategy prompt.</p><div class="c">` +
      les.slice(-6).reverse().map(r => `<div style="padding:8px 0"><div>${esc(r.lesson)}</div><small>${esc(r.date)} · ${esc(r.verdict)}</small></div>`).join("") + "</div>"]);
  }
  const hs = (w && (w.headlines || w.items)) || [];
  if (hs.length) {
    tabs.push(["Headlines", `<p class="s">Injection-filtered before any model sees them.</p><div class="c"><ul>` +
      hs.slice(0, 8).map(x => `<li>${esc(x.title)}</li>`).join("") + "</ul></div>"]);
  }
  const ag = (await J("data/agents.json")) || {}, tc = await J("data/today.json");
  const A = (n, ty, role, out) => `<div class="c"><b>${esc(n)}</b> <small style="display:inline">· ${esc(ty)}</small><div style="margin:4px 0">${esc(role)}</div><small>${esc(out || "Waiting for first run")}</small></div>`;
  const rg = ag.regime, rk = ag.risk, db = ag.debate, pf = ag.portfolio, dr = ag.drift;
  tabs.unshift(["Agents", `<p class="s">Ten agents, one hard C++ gate, and the Ask VERITAS chatbot. Language models only explain or say no. They can never flip a trade.</p><div class="g">` + [
    A("Cue Agent", "AI", "Explains the macro signal in plain words", tc && tc.card ? "Today's cue score " + tc.card.cue_score : ""),
    A("News Agent", "AI", "Scores headlines, injection-filtered", hs.length ? hs.length + " headlines read" : ""),
    A("Strategy Agent", "AI", "Proposes the model's direction or WAIT", ""),
    A("Red-team Agent", "AI", "Tries to falsify the trade and can veto", v ? v.n_vetoes + " vetoes, " + v.good_vetoes + " right" : ""),
    A("Reflection Agent", "AI", "Writes one lesson per settled day", les && les.length ? les.length + " lessons stored" : ""),
    A("Bull, Bear and Judge", "AI", "Debate the trade, judge picks agree or WAIT", db ? "Judge: " + db.judge.verdict + ". " + db.judge.reason : ""),
    A("Regime Agent", "Code", "Trending, sideways or volatile; scales confidence", rg ? rg.label + " (x" + rg.conf_mult + "). " + rg.why : ""),
    A("Dynamic Risk Agent", "Code", "Shrinks position size under stress, never grows it", rk ? "Size x" + rk.scale + ". " + rk.why.join("; ") : ""),
    A("Portfolio Agent", "Code", "Inverse-volatility weights across 4 stocks", pf ? Object.entries(pf.weights).map(e => e[0] + " " + Math.round(e[1] * 100) + "%").join(", ") + ". " + pf.flag : ""),
    A("Drift Monitor", "ML", "Checks accuracy and conformal coverage", dr ? dr.status + ": accuracy " + dr.accuracy + ", coverage " + dr.coverage + " (target " + dr.target_coverage + ")" : ""),
    A("C++ Risk Gate", "Hard rules", "Final authority. Costs, limits, kill-switch, audit chain", "Cannot be overridden by any agent"),
    A("Ask VERITAS", "AI", "The chatbot. Answers from this page's data", "Open the chat window")
  ].join("") + "</div>"]);
  if (!tabs.length) return;

  const st = document.createElement("style"); st.textContent = css; document.head.append(st);
  const box = document.createElement("section"); box.id = "vx";
  box.innerHTML = `<div class="bar">${tabs.map((t, i) => `<button type="button" aria-expanded="false" aria-controls="vx${i}" data-i="${i}">▸ ${esc(t[0])}</button>`).join("")}</div>` +
    tabs.map((t, i) => `<div class="pn" id="vx${i}">${t[1]}</div>`).join("");
  box.querySelector(".bar").onclick = e => {
    const b = e.target.closest("button"); if (!b) return;
    const was = b.getAttribute("aria-expanded") === "true";
    box.querySelectorAll(".bar button").forEach((x, i) => {
      const on = !was && x === b;
      x.setAttribute("aria-expanded", on);
      x.textContent = (on ? "▾ " : "▸ ") + tabs[i][0];
      box.querySelector("#vx" + i).classList.toggle("open", on);
    });
    if (!was) b.scrollIntoView({block: "nearest", behavior: "smooth"});
  };
  document.body.append(box);
  const st2 = document.createElement("style");
  st2.textContent = `
  #vx{position:fixed!important;top:0!important;right:0!important;bottom:auto!important;left:auto!important;display:block!important;border:0!important;box-shadow:none!important;background:transparent!important;width:0!important;height:0!important}
  #vx .bar{position:fixed;right:10px;top:90px;display:flex;flex-direction:column;align-items:stretch;gap:6px;width:150px;padding:0}
  #vx .bar button{background:var(--vb,#131722)!important;color:inherit;text-align:left;box-shadow:0 2px 10px rgba(0,0,0,.4)}
  #vx .pn{position:fixed;top:60px;right:172px;width:min(540px,calc(100vw - 196px));max-height:calc(100vh - 80px);overflow:auto;padding:14px;border:1px solid rgba(128,128,128,.45);border-radius:10px;background:var(--vb,#131722);box-shadow:0 8px 30px rgba(0,0,0,.5)}
  @media (max-width:640px){#vx .bar{width:auto;top:auto;bottom:70px;flex-direction:row;flex-wrap:wrap;left:10px;right:10px}#vx .pn{right:8px;left:8px;width:auto;top:auto;bottom:120px;max-height:55vh}}`;
  document.head.append(st2);

  const cs = getComputedStyle(document.body), bg = cs.backgroundColor;
  box.style.background = (!bg || bg === "rgba(0, 0, 0, 0)") ? "#131722" : bg;
  box.style.color = cs.color;
  box.style.setProperty("--vb", box.style.backgroundColor);

  (() => {
    const b = document.getElementById("vx"); if (!b) return;
    document.documentElement.append(b);
    const o = document.createElement("style");
    o.textContent = `#vx{position:fixed!important;top:0!important;left:0!important;right:auto!important;bottom:auto!important;width:100vw!important;height:0!important;z-index:2147483647!important;pointer-events:none}
    #vx .bar{position:fixed!important;top:8px!important;left:50%!important;right:auto!important;bottom:auto!important;transform:translateX(-50%);flex-direction:row!important;flex-wrap:wrap;justify-content:center;width:auto!important;max-width:96vw;pointer-events:auto;gap:6px}
    #vx .bar button{white-space:nowrap}
    #vx .pn{position:fixed!important;top:56px!important;left:50%!important;right:auto!important;bottom:auto!important;transform:translateX(-50%);width:min(640px,94vw)!important;max-height:calc(100vh - 80px)!important;pointer-events:auto}`;
    document.head.append(o);
    console.log("VERITAS addons mounted", b.querySelector(".bar").getBoundingClientRect());
  })();
})();
