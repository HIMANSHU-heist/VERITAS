(() => {
const API = window.VERITAS_CHAT_API || null;
const GATE = {conformal_ambiguous:'Model unsure',edge_below_cost:'Edge below cost',vix_stress:'VIX stress',redteam_veto:'AI red-team veto',agent_disagreement:'Agents disagree',kill_switch:'Kill-switch',rate_limit:'Rate limit',data_invalid:'Stale/missing data',invalid_size:'Invalid size',llm_wait:'Strategist chose WAIT',llm_error:'AI error',llm_skipped_trial:'AI skipped'};
const GWHY = {
 conformal_ambiguous:'the model could not pick a side with enough certainty. Both UP and DOWN stayed plausible at the 90% confidence level.',
 edge_below_cost:'the expected profit was smaller than the round-trip trading cost (brokerage, taxes, slippage), so the trade would lose money on average.',
 vix_stress:'India VIX was too high, meaning the market was too jumpy for the system to trade safely.',
 redteam_veto:'the AI red-team reviewer found a serious problem with the proposal and vetoed it.',
 agent_disagreement:'the AI agents pointed in opposite directions, so the system stayed out.',
 kill_switch:'the safety kill-switch was active (daily loss, drawdown or order-rate limit hit).',
 rate_limit:'too many orders in one second, so the safety stop triggered.',
 data_invalid:'market data was stale or missing, and the system never trades on bad data.',
 invalid_size:'the position size came out invalid.',
 llm_wait:'the AI strategist itself decided to WAIT.',
 llm_error:'an AI call failed, and the system fails closed (no trade).',
 llm_skipped_trial:'the AI stage was skipped in a trial run.'};
const GLOSS = [
 [/conformal/,'**Conformal set**: instead of one guess, the model returns the set of outcomes it cannot rule out. If the set is only {UP} or only {DOWN} it is confident. If it is {DOWN, UP} it is unsure, and the system abstains.'],
 [/\bedge\b/,'**Edge**: the average % profit the model expects from this trade, learned from how its past confidence turned into real returns. A trade is allowed only if edge is bigger than the round-trip cost.'],
 [/cost|brokerage|slippage/,'**Cost**: brokerage, exchange fees, STT, stamp duty, GST and slippage for buying and selling. Around 0.146% per round trip here.'],
 [/gate/,'**Gates**: independent safety checks run by the C++ risk engine. Any single failure means no trade. Gates: model certainty, edge vs cost, VIX, agent disagreement, red-team veto, kill-switch, data validity.'],
 [/red.?team/,'**Red-team**: an AI reviewer whose only job is to find reasons the proposed trade is wrong. A HIGH severity finding vetoes it.'],
 [/kill/,'**Kill-switch**: a hard stop in C++ that blocks all trading after a daily loss limit, max drawdown or order flood.'],
 [/vix/,'**India VIX**: the market fear gauge. Above 25 the system refuses to trade.'],
 [/audit|hash/,'**Audit hash**: every decision is written to a hash-chained log. Changing any past line breaks the chain, so tampering is detectable.'],
 [/p\(?up\)?|probability/,'**P(up)**: the model\'s probability that NIFTY closes above its open today. Near 50% means no real view.'],
 [/paper/,'**Paper trading**: simulated trades only. No real money, no real orders.'],
 [/cue/,'**Cue score**: a simple model of overnight global signals (S&P, Nasdaq, Nikkei, crude, gold, USDINR, VIX) pointing to a bullish (+) or bearish (-) bias.'],
 [/llm|agent|gpt|ai\b/,'**AI agents**: a cue agent explains the signals, a strategist proposes, and a red-team challenges. They can only agree with the ML direction or WAIT, and the C++ risk engine has the final say.']];

let today=null,data=null,cards=[],by={},dates=[],latest=null;
const getJ=async u=>{try{const r=await fetch(u+'?t='+Date.now());return r.ok?await r.json():null}catch(e){return null}};
async function load(){
  [today,data]=await Promise.all([getJ('data/today.json'),getJ('data/data.json')]);
  cards=data?data.cards:[];by={};cards.forEach(c=>by[c.date]=c);
  if(today&&today.card)by[today.card.date]=today.card;
  dates=Object.keys(by).sort();latest=dates.length?by[dates[dates.length-1]]:null;
}
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const rich=s=>esc(s).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/\n/g,'<br>');
const f=(n,d=2)=>Number(n).toLocaleString('en-IN',{minimumFractionDigits:d,maximumFractionDigits:d});

function explain(c){
  const g=c.gate_failed||[];
  let t='**'+c.date+': '+c.decision+'**\n';
  if(c.p_up!=null)t+='• Model P(up) '+Math.round(c.p_up*100)+'%, conformal set '+(c.conformal_set||[]).join(' / ')+'\n';
  if(c.edge_pct!=null){const m=((c.counterfactual||'').match(/>\s*([\d.]+)%/)||[])[1];t+='• Expected edge '+f(c.edge_pct,3)+'%'+(m?' vs cost '+m+'%':'')+'\n';}
  if(c.cue_score!=null)t+='• Global cue score '+f(c.cue_score,3)+'\n';
  if(c.decision==='TRADE'){
    t+='\nAll gates passed, so a paper '+(c.side>0?'BUY':'SELL')+' was approved (qty '+c.qty+', cost Rs '+f(c.cost)+').';
    if(c.net!=null)t+=' Result: net Rs '+f(c.net)+'.';
  }else{
    t+='\n**Why no trade:**\n'+(g.length?g.map(x=>'• '+(GATE[x]||x)+': '+(GWHY[x]||'')).join('\n'):'• No action was taken.');
    if(c.counterfactual)t+='\n\n**What would change it:** '+c.counterfactual;
  }
  if(c.proposal)t+='\n\n**Strategist:** '+c.proposal.action+'. '+c.proposal.thesis;
  const ob=(c.red_team&&c.red_team.objections)||[];
  if(ob.length)t+='\n**Red-team:** '+ob.map(o=>o.severity+': '+o.text).join(' | ');
  return t;
}
function perf(){
  if(!data)return 'Backtest numbers are not published yet (data.json missing).';
  const s=data.summary,p=s.pipeline,m=s.ml_gates,e=s.every_day,b=s.buy_hold;
  return '**Backtest '+s.window[0]+' to '+s.window[1]+' ('+s.n_days+' days, paper, after costs)**\n'+
   '• Full pipeline: net Rs '+f(p.net_pnl)+' ('+p.n_trades+' trades, '+Math.round((p.win_rate||0)*100)+'% wins)\n'+
   '• ML + gates only: Rs '+f(m.net_pnl)+' ('+m.n_trades+' trades)\n'+
   '• Trade every day: Rs '+f(e.net_pnl)+' ('+e.n_trades+' trades, costs Rs '+f(e.cost)+')\n'+
   '• Buy & hold: Rs '+f(b.net_pnl)+'\n\n'+
   'Honest reading: the system lost less than the alternatives, mostly by avoiding costly bad trades. It is **not yet profitable**, and this is a research demo.';
}
function gateStats(){
  const n={};cards.forEach(c=>(c.gate_failed||[]).forEach(g=>n[g]=(n[g]||0)+1));
  const a=Object.entries(n).sort((x,y)=>y[1]-x[1]);
  return a.length?'**Most common reasons for no trade**\n'+a.map(([k,v])=>'• '+(GATE[k]||k)+': '+v+' days').join('\n'):'No gate stats yet.';
}
function tradesList(){
  const T=cards.filter(c=>c.decision==='TRADE');
  if(!T.length)return 'No approved trades in the published data.';
  const w=T.filter(c=>c.net>0).length;
  return '**'+T.length+' approved trades, '+w+' winners**\nLast 5:\n'+T.slice(-5).reverse().map(c=>'• '+c.date+' '+(c.side>0?'BUY':'SELL')+' net Rs '+f(c.net)).join('\n');
}
function dateFrom(q){
  const m=q.match(/(20\d\d-\d\d-\d\d)/);if(m)return m[1];
  if(/yesterday|\bkal\b|kaal/.test(q)&&latest){const i=dates.indexOf(latest.date);return i>0?dates[i-1]:null}
  return null;
}
function local(qRaw){
  const q=qRaw.toLowerCase();
  if(/should i (buy|sell)|kharedi|vikri|invest|tip|guarantee/.test(q))
    return 'I can\'t give investment advice, and this is paper trading only. What I can tell you is what the system decided:\n\n'+(latest?explain(latest):'No card yet.');
  const d=dateFrom(q);
  if(d){return by[d]?explain(by[d]):'No decision card for '+d+'. Available range: '+(dates[0]||'-')+' to '+(dates[dates.length-1]||'-')+'.'}
  if(/trade (list|history)|last trade|how many trades|kiti trade|\btrades\b/.test(q))return tradesList();
  if(/pnl|p&l|profit|loss|performance|result|nafa|nuksan|buy.?(and|&)?.?hold|benchmark/.test(q))return perf();
  if(/most|common|stats|how often|kiti vela|gates? stats/.test(q))return gateStats();
  for(const [re,ans] of GLOSS)if(re.test(q)&&/what|mean|explain|kay|mhanje|define|\?/.test(q))return ans;
  if(/how (does|do).*(work|decide)|pipeline|kasa|process/.test(q))
    return '**How a decision is made (every weekday 08:30 IST)**\n1. Fresh data enters through a point-in-time firewall (no future leakage).\n2. LightGBM estimates P(up); conformal prediction says if it is sure.\n3. The C++ risk engine checks edge vs cost, VIX and safety limits.\n4. Only if those pass, AI agents (cue, strategist, red-team) review it. They can agree or WAIT, never flip it.\n5. The risk engine makes the final call and logs it in a hash-chained audit.';
  if(/today|aaj|aajcha|latest|now|decision|why|ka\b|reason|kaaran|trade/.test(q)&&latest)return explain(latest);
  for(const [re,ans] of GLOSS)if(re.test(q))return ans;
  return 'I can explain: **today\'s decision**, **any date** (e.g. "why no trade on 2026-10-01?"), **performance**, **trades**, **most common gates**, **how it works**, and terms like conformal, edge, VIX or red-team.';
}
function ctx(q,facts){
  const d=dateFrom(q.toLowerCase());
  const slim=c=>({date:c.date,decision:c.decision,p_up:c.p_up,set:c.conformal_set,edge:c.edge_pct,gates:c.gate_failed,net:c.net,thesis:c.proposal&&c.proposal.thesis,objections:c.red_team&&c.red_team.objections});
  return {facts:facts,today:latest&&slim(latest),date_card:d&&by[d]?slim(by[d]):null,summary:data&&data.summary,recent:cards.slice(-15).map(slim)};
}
async function answer(q){
  if(!latest&&!data)await load();
  const base=local(q);
  if(!API)return base;
  try{
    const r=await fetch(API,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q,context:ctx(q,base),history:window.__vh||[]})});
    const j=await r.json();const a=j.answer||base;window.__vh=((window.__vh||[]).concat([{q:q.slice(0,300),a:a.slice(0,500)}])).slice(-4);return a;
  }catch(e){return base}
}

/* UI */
const css=document.createElement('style');
css.textContent=
'#vc-b{position:fixed;right:16px;bottom:calc(16px + env(safe-area-inset-bottom));z-index:99;width:56px;height:56px;border-radius:50%;border:0;cursor:pointer;font-size:24px;color:#fff;background:linear-gradient(135deg,#2962ff,#9b7bff);box-shadow:0 8px 28px rgba(41,98,255,.5)}'+
'#vc-p{position:fixed;right:16px;bottom:84px;z-index:99;width:390px;max-width:calc(100vw - 24px);height:540px;max-height:calc(100vh - 110px);display:none;flex-direction:column;background:#1e222d;border:1px solid #2a2e39;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.6);overflow:hidden;font:13px/1.5 Inter,system-ui,sans-serif;color:#d1d4dc}'+
'#vc-p.on{display:flex}'+
'#vc-h{padding:12px 14px;background:#171b26;border-bottom:1px solid #2a2e39;font-weight:700;display:flex;justify-content:space-between;align-items:center}'+
'#vc-h small{color:#8b94a7;font-weight:500}#vc-x{background:none;border:0;color:#8b94a7;font-size:18px;cursor:pointer}'+
'#vc-m{flex:1;overflow:auto;padding:12px;display:flex;flex-direction:column;gap:8px}'+
'.vc-u,.vc-a{max-width:88%;padding:9px 12px;border-radius:12px;word-break:break-word}'+
'.vc-u{align-self:flex-end;background:#2962ff;color:#fff;border-bottom-right-radius:3px}'+
'.vc-a{align-self:flex-start;background:#171b26;border:1px solid #2a2e39;border-bottom-left-radius:3px}'+
'#vc-s{display:flex;gap:6px;flex-wrap:wrap;padding:0 12px 8px}'+
'#vc-s button{background:#171b26;border:1px solid #2a2e39;color:#9aa4b5;border-radius:99px;padding:5px 10px;font:600 11.5px Inter;cursor:pointer}'+
'#vc-f{display:flex;gap:8px;padding:10px;border-top:1px solid #2a2e39;background:#171b26}'+
'#vc-i{flex:1;background:#131722;border:1px solid #2a2e39;border-radius:10px;color:#d1d4dc;padding:10px;font:14px Inter;outline:none;min-width:0}'+
'#vc-g{background:#2962ff;border:0;color:#fff;border-radius:10px;padding:0 14px;font-weight:700;cursor:pointer}'+
'@media(max-width:520px){#vc-p{right:8px;left:8px;width:auto;bottom:80px}}';
document.head.appendChild(css);
const b=document.createElement('button');b.id='vc-b';b.setAttribute('aria-label','Ask VERITAS');b.textContent='\u{1F4AC}';
const p=document.createElement('div');p.id='vc-p';
p.innerHTML='<div id="vc-h"><div>Ask VERITAS <small>· answers from live data</small></div><button id="vc-x">\u2715</button></div><div id="vc-m"></div><div id="vc-s"></div><form id="vc-f"><input id="vc-i" placeholder="Ask why, any date, P&L..." autocomplete="off"><button id="vc-g">Send</button></form>';
document.body.append(b,p);
const m=p.querySelector('#vc-m'),inp=p.querySelector('#vc-i');
const add=(cls,html)=>{const d=document.createElement('div');d.className=cls;d.innerHTML=html;m.appendChild(d);m.scrollTop=m.scrollHeight;return d};
['Why no trade today?','Performance?','Most common gates','How does it work?','What is conformal?'].forEach(t=>{
  const x=document.createElement('button');x.type='button';x.textContent=t;x.onclick=()=>ask(t);p.querySelector('#vc-s').appendChild(x)});
async function ask(q){
  q=q.trim();if(!q)return;add('vc-u',esc(q));inp.value='';
  const w=add('vc-a','<i>thinking...</i>');
  w.innerHTML=rich(await answer(q));m.scrollTop=m.scrollHeight;
}
p.querySelector('#vc-f').onsubmit=e=>{e.preventDefault();ask(inp.value)};
b.onclick=()=>{p.classList.toggle('on');if(p.classList.contains('on')&&!m.children.length)add('vc-a',rich('Hi! Ask me why the system traded or abstained, on **any date**, how it performed, or what a term means. Paper trading only, not investment advice.'));inp.focus()};
p.querySelector('#vc-x').onclick=()=>p.classList.remove('on');
load();
})();
