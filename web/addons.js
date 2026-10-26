(async () => {
  const J = u => fetch(u + "?t=" + Date.now()).then(r => r.ok ? r.json() : null).catch(() => null);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const inr = n => (n < 0 ? "-" : "") + "₹" + Math.abs(Math.round(n)).toLocaleString("en-IN");
  const cl = n => n >= 0 ? "p" : "n";
  const [d, v, les, w] = await Promise.all([J("data/data.json"), J("data/veto.json"), J("data/lessons.json"), J("data/watch.json")]);

  const css = `#vx{margin:24px 0;font:inherit;color:inherit}#vx h3{margin:26px 0 6px}#vx p.s{opacity:.7;margin:0 0 10px}
  #vx .g{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(170px,1fr))}
  #vx .c{border:1px solid rgba(128,128,128,.3);background:rgba(128,128,128,.07);border-radius:8px;padding:12px}
  #vx .k{font-size:24px;font-weight:700}#vx small{opacity:.7;display:block;font-weight:400;font-size:13px}
  #vx .p{color:#26a69a}#vx .n{color:#ef5350}
  #vx table{width:100%;border-collapse:collapse;font-size:14px}#vx td,#vx th{text-align:left;padding:6px;border-bottom:1px solid rgba(128,128,128,.25)}
  #vx .t{display:flex;flex-wrap:wrap;gap:3px;margin:8px 0}#vx .t i{width:10px;height:10px;border-radius:2px;background:rgba(128,128,128,.45)}
  #vx .t i.w{background:#26a69a}#vx .t i.l{background:#ef5350}#vx .t i.v{background:#f5a623}
  #vx .x{overflow-x:auto}#vx li{padding:6px 0;border-bottom:1px solid rgba(128,128,128,.25);list-style:none}#vx ul{margin:0;padding:0}`;

  let h = "";
  if (d && d.cards) {
    const off = d.cards.filter(c => c.decision !== "TRADE").length;
    h += `<h3>Day tape</h3><p class="s">Sat out ${off} of ${d.cards.length} days. Green = profit, red = loss, amber = red-team veto, grey = sat out.</p><div class="t">` +
      d.cards.map(c => {
        let k = c.decision === "TRADE" ? (c.net >= 0 ? "w" : "l") : ((c.gate_failed || []).includes("redteam_veto") ? "v" : "");
        return `<i class="${k}" title="${esc(c.date)}: ${esc(c.decision)} ${esc((c.gate_failed || []).join(", "))}"></i>`;
      }).join("") + "</div>";
  }
  if (v) {
    h += `<h3>Veto Tracker</h3><p class="s">Trades the red-team blocked, rebuilt and priced with real costs.</p><div class="g">
      <div class="c"><div class="k">${v.good_vetoes}/${v.n_vetoes}</div><small>Vetoes that were right (${Math.round(v.good_veto_rate * 100)}%)</small></div>
      <div class="c"><div class="k p">${inr(v.loss_avoided_inr)}</div><small>Losses avoided</small></div>
      <div class="c"><div class="k n">${inr(-v.profit_missed_inr)}</div><small>Profit missed</small></div>
      <div class="c"><div class="k ${cl(v.net_effect_inr)}">${inr(v.net_effect_inr)}</div><small>Net effect of red-team</small></div></div>
      <div class="x" style="margin-top:10px"><table><tr><th>Date<th>Side<th>Move<th>Would have made<th>Veto</tr>` +
      v.days.slice(-10).reverse().map(r => `<tr><td>${esc(r.date)}<td>${esc(r.side)}<td>${r.ret_oc_pct}%<td class="${cl(r.would_be_net)}">${inr(r.would_be_net)}<td>${r.veto_was === "GOOD" ? "Right" : "Wrong"}</tr>`).join("") + "</table></div>";
  }
  if (les && les.length) {
    h += `<h3>Agent memory</h3><p class="s">One lesson per settled day. The last five feed tomorrow's strategy prompt.</p><div class="c">` +
      les.slice(-6).reverse().map(r => `<div style="padding:8px 0"><div>${esc(r.lesson)}</div><small>${esc(r.date)} · ${esc(r.verdict)}</small></div>`).join("") + "</div>";
  }
  const hs = (w && (w.headlines || w.items)) || [];
  if (hs.length) {
    h += `<h3>Headlines being watched</h3><p class="s">Injection-filtered before any model sees them.</p><div class="c"><ul>` +
      hs.slice(0, 8).map(x => `<li>${esc(x.title)}</li>`).join("") + "</ul></div>";
  }
  if (!h) return;
  const st = document.createElement("style"); st.textContent = css; document.head.append(st);
  const box = document.createElement("section"); box.id = "vx"; box.innerHTML = h;
  (document.querySelector("main") || document.body).append(box);
})();
