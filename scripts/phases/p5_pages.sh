#!/usr/bin/env bash
source "$(dirname "$0")/_lib.sh"
say "PHASE 5: clean up Terminal, Portfolio, Flow, Alerts; remove old modal"

cat > scripts/phases/_kpi.js <<'EOF_K'
(function(){const k=$('#kpis');if(!k)return;const L=live,s=data&&data.summary;
const tile=(a,b,c)=>'<div class="kp"><small>'+a+'</small><b class="'+(c||'')+'">'+b+'</b></div>';
let h='';
if(L)h+=tile('Today',esc(L.decision),L.decision==='TRADE'?'pos':'')+tile('P(up)',Math.round((L.p_up||0)*100)+'%')+tile('Edge',f(L.edge_pct,3)+'%')+tile('VIX',f(L.vix));
if(s){const p=s.pipeline;h+=tile('Pipeline net','₹'+f(p.net_pnl),col(p.net_pnl))+tile('Buy&Hold','₹'+f(s.buy_hold.net_pnl),col(s.buy_hold.net_pnl))+tile('Sat out',Math.round(100*(s.n_days-p.n_trades)/s.n_days)+'%')+tile('Trades',p.n_trades);}
k.innerHTML=h||'<div class="empty">No data yet.</div>';})();
EOF_K

python - <<'PY'
import re
from _patch import sub

# ---- Terminal
P = "web/index.html"
kpi = open("scripts/phases/_kpi.js", encoding="utf-8").read().strip()
sub(P, "<style>", '<link rel="stylesheet" href="shared.css">\n<style>')
sub(P, '<div class="brand"><i></i>VERITAS</div>', "")
sub(P, '<a class="lnk" href="portfolio.html">Portfolio</a><a class="lnk" href="flow.html">How it works</a><a class="lnk" href="subscribe.html">Get email alerts</a>', "")
sub(P, '<div class="term">', '<div id="kpis" class="kpis"></div>\n<div class="term">')
old = "if(data)$('#hwin').textContent='backtest '+data.summary.window[0]+' → '+data.summary.window[1];"
sub(P, old, old + "\n" + kpi)
sub(P, '<script src="addons.js" defer></script>', '<script src="nav.js"></script>')

# ---- Portfolio
P = "web/portfolio.html"
t = open(P, encoding="utf-8").read()
t = re.sub(r"<header>.*?</header>\s*", "", t, count=1, flags=re.S)
open(P, "w", encoding="utf-8").write(t)
sub(P, '<h3>Agents</h3><div class="gr">` + boxes.join("") + `</div>',
    '<p class="mu" style="margin-top:10px"><a href="agents.html" style="color:#6d9bff">All agents and their latest output &rarr;</a></p>')
sub(P, "</body></html>", '<script src="nav.js"></script></body></html>')

# ---- How it works
P = "web/flow.html"
sub(P, '<div class="top"><a href="./">&larr; Dashboard</a><a href="subscribe.html">Email alerts</a></div>', "")
sub(P, "every 30 min · 09:45-15:15", "every 15 min · market hours")
paper = ("{id:'n_p',i:'🧪',n:'Paper trader',s:'every 15 min · market hours',f:'paper.yml',"
         "d:'Runs every user paper account: executes approved orders, applies stop-loss, target and time exits, "
         "and asks for approval when a signal is unsure. Fake money only.',p:['Firestore','cron']},\n ")
sub(P, "{id:'n_e',i:'🌆'", paper + "{id:'n_e',i:'🌆'")
adv = """{k:'adv',c:'#22d3ee',t:'Advisory agents',s:'dashboard only, they never place trades',n:[
 {id:'v_reg',i:'🧭',n:'Regime',s:'trending, sideways, volatile',f:'agents/regime.py',d:'Classifies the market and scales confidence down in sideways or volatile regimes.',p:['code only']},
 {id:'v_risk',i:'🎚️',n:'Dynamic risk',s:'size can only shrink',f:'agents/risk_agent.py',d:'Cuts position size under high VIX, drawdown or a losing streak. Never grows it.',p:['code only']},
 {id:'v_lvl',i:'📐',n:'Levels',s:'pivots, ATR, range',f:'agents/levels.py',d:'Classic pivot levels, ATR and the 20-day range, with a volatility-based stop and target suggestion.',p:['code only']},
 {id:'v_sc',i:'🎓',n:'Scorecard',s:'grades the live model',f:'agents/scorecard.py',d:'Brier score, shadow hit rate, abstain rate and net P&L over settled live days.',p:['Brier score']},
 {id:'v_dq',i:'🩺',n:'Data quality',s:'12 series checked',f:'agents/dataquality.py',d:'Flags stale bars, missing closes, duplicate dates and suspicious jumps.',p:['fail early']},
 {id:'v_dr',i:'📉',n:'Drift monitor',s:'accuracy and coverage',f:'agents/drift.py',d:'Warns when recent accuracy or conformal coverage degrades.',p:['conformal coverage']},
 {id:'v_deb',i:'⚔️',n:'Bull, Bear, Judge',s:'debate',f:'agents/debate.py',d:'Two LLMs argue for and against; a judge may only agree or WAIT.',p:['gpt-oss']}]},
"""
sub(P, "{k:'o',c:'#5aa9ff',t:'Outputs'", adv + "{k:'o',c:'#5aa9ff',t:'Outputs'")
sub(P, "</body>", '<script src="nav.js"></script>\n</body>')
PY

cat > web/subscribe.html <<'EOF_S'
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#131722">
<title>VERITAS · Email alerts</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{--bg:#131722;--pn:#1e222d;--bd:#2a2e39;--tx:#d1d4dc;--mu:#8b94a7;--g:#26a69a;--b:#2962ff}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx);font:15px/1.55 Inter,system-ui,sans-serif;min-height:100vh}
.wrap{max-width:540px;margin:0 auto;padding:24px 16px 80px}
h1{font-size:24px;font-weight:800}h3{margin:20px 0 8px;font-size:15px}
.note{color:var(--mu);font-size:13px;margin:6px 0 16px}
.card{background:var(--pn);border:1px solid var(--bd);border-radius:12px;padding:16px}
input[type=email],input[type=password]{width:100%;padding:11px 12px;margin:6px 0;background:var(--bg);color:var(--tx);border:1px solid var(--bd);border-radius:8px;font:inherit}
button{padding:10px 16px;margin:8px 8px 0 0;background:var(--pn);color:var(--tx);border:1px solid var(--bd);border-radius:8px;font:600 14px Inter;cursor:pointer}
button#signup,button#save{background:var(--b);border-color:var(--b);color:#fff}
label{display:flex;gap:10px;align-items:flex-start;margin:10px 0;color:var(--tx)}
label input{margin-top:5px}
.msg{margin:12px 0;padding:10px 12px;background:#2a2e39;border-left:3px solid var(--g);border-radius:6px;font-size:13.5px}
</style>
</head>
<body>
<main class="wrap">
<h1>Email alerts</h1>
<p class="note">Educational paper-trading demo. No real orders are placed. Not investment advice. Emails describe what a software model decided and why, including when it chose NOT to trade.</p>
<div id="msg" class="msg" hidden></div>

<div id="authBox" class="card">
  <input id="email" type="email" placeholder="Email" autocomplete="email">
  <input id="pw" type="password" placeholder="Password (min 6 chars)" autocomplete="current-password">
  <button id="signup">Sign up</button><button id="login">Log in</button>
</div>

<div id="appBox" class="card" hidden>
  <p>Signed in as <b id="who"></b> &middot; email verified: <b id="ver"></b></p>
  <button id="resend" hidden>Resend verification email</button>
  <button id="refresh">I verified, refresh</button>
  <h3>Email preferences</h3>
  <label><input type="checkbox" id="optIn"><span>I agree to receive VERITAS paper-trading emails (untick any time)</span></label>
  <label><input type="checkbox" id="digest" checked><span>Daily decision digest and evening recap</span></label>
  <label><input type="checkbox" id="instant" checked><span>Instant alerts: trade approved, red-team veto, VIX stress, safety stop</span></label>
  <button id="save">Save preferences</button><button id="logout">Log out</button>
</div>
</main>

<script type="module">
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.14.1/firebase-app.js";
import { getAuth, createUserWithEmailAndPassword, signInWithEmailAndPassword,
         sendEmailVerification, onAuthStateChanged, signOut }
  from "https://www.gstatic.com/firebasejs/10.14.1/firebase-auth.js";
import { getFirestore, doc, getDoc, setDoc, serverTimestamp }
  from "https://www.gstatic.com/firebasejs/10.14.1/firebase-firestore.js";
import { firebaseConfig } from "./firebase-config.js";

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
const $ = (id) => document.getElementById(id);
const say = (t) => { $("msg").textContent = t; $("msg").hidden = !t; };
const fail = (e) => say(e.code ? e.code.replace("auth/", "").replaceAll("-", " ") : String(e));

$("signup").onclick = async () => {
  try {
    const c = await createUserWithEmailAndPassword(auth, $("email").value.trim(), $("pw").value);
    await sendEmailVerification(c.user);
    say("Account created. Verification email sent. Check inbox and spam, then click 'I verified, refresh'.");
  } catch (e) { fail(e); }
};
$("login").onclick = async () => {
  try { await signInWithEmailAndPassword(auth, $("email").value.trim(), $("pw").value); say(""); }
  catch (e) { fail(e); }
};
$("logout").onclick = () => signOut(auth);
$("resend").onclick = async () => {
  try { await sendEmailVerification(auth.currentUser); say("Verification email sent again."); }
  catch (e) { fail(e); }
};
$("refresh").onclick = async () => { await auth.currentUser.reload(); await render(auth.currentUser); };
$("save").onclick = async () => {
  const u = auth.currentUser;
  if (!u.emailVerified && $("optIn").checked) { say("Verify your email first, then opt in."); return; }
  try {
    await setDoc(doc(db, "users", u.uid), {
      optIn: $("optIn").checked, digest: $("digest").checked,
      instant: $("instant").checked, updatedAt: serverTimestamp(),
    });
    say($("optIn").checked ? "Saved. You will receive VERITAS paper-trading emails." : "Saved. You are unsubscribed.");
  } catch (e) { fail(e); }
};

async function render(u) {
  $("authBox").hidden = !!u; $("appBox").hidden = !u;
  if (!u) return;
  $("who").textContent = u.email;
  $("ver").textContent = u.emailVerified ? "yes" : "no";
  $("resend").hidden = u.emailVerified;
  const s = await getDoc(doc(db, "users", u.uid));
  const d = s.exists() ? s.data() : { optIn: false, digest: true, instant: true };
  $("optIn").checked = !!d.optIn; $("digest").checked = d.digest !== false; $("instant").checked = d.instant !== false;
}
onAuthStateChanged(auth, render);
</script>
<script src="nav.js"></script>
</body>
</html>
EOF_S

rm -f scripts/phases/_kpi.js
[ -f web/addons.js ] && git rm -q -f web/addons.js || true

for f in web/index.html web/portfolio.html web/flow.html web/subscribe.html web/agents.html; do jscheck "$f"; done

finish "feat(web): unified navbar everywhere, KPI strip on Terminal, dark Alerts page, new flow layers, remove old agents modal" \
  web/index.html web/portfolio.html web/flow.html web/subscribe.html web/addons.js
say "PHASE 5 DONE"
