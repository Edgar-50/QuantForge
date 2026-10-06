/* QuantForge v10 — core: state, api, formatting, charts, ui kit, router, palette */
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const store = { get(k, d) { try { const v = localStorage.getItem("qf." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
                set(k, v) { try { localStorage.setItem("qf." + k, JSON.stringify(v)); } catch {} } };
const state = { view: "terminal", ticker: store.get("ticker", "NVDA"), source: store.get("source", "auto"), quotes: [], universe: [],
                tok: 0, pf: null, lastSource: null, watchTickers: [] };
const C = { up: "#3ddc97", dn: "#ff5d73", ai: "#8b7bff", cy: "#4cc9f0", am: "#ffb547", tx: "#e8ecf3", mu: "#8590a2", ln: "rgba(255,255,255,.06)" };
const VIEW_NAMES = { terminal: "Markets", forecast: "AI Forecast", screener: "Screener", strategy: "Strategy Lab", portfolio: "Portfolio Lab", risk: "Risk Center", options: "Options Lab" };

/* ---------- formatting ---------- */
const isn = x => typeof x === "number" && isFinite(x);
const F = {
  n: (x, d = 2) => isn(x) ? x.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }) : "—",
  pct: (x, d = 2, sign = false) => isn(x) ? (sign && x > 0 ? "+" : "") + (x * 100).toFixed(d) + "%" : "—",
  usd: (x, d = 2) => isn(x) ? (x < 0 ? "-$" : "$") + F.n(Math.abs(x), d) : "—",
  k: x => !isn(x) ? "—" : Math.abs(x) >= 1e9 ? (x / 1e9).toFixed(2) + "B" : Math.abs(x) >= 1e6 ? (x / 1e6).toFixed(2) + "M" : Math.abs(x) >= 1e3 ? (x / 1e3).toFixed(1) + "K" : x.toFixed(0),
  px: x => !isn(x) ? "—" : x >= 1000 ? F.n(x, 0) : F.n(x, 2),
  sgn: x => isn(x) ? (x > 0 ? "up" : x < 0 ? "dn" : "") : "",
  ratio: x => isn(x) ? x.toFixed(2) : "—",
};
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const cls = x => F.sgn(x);

/* ---------- api ---------- */
async function api(path, body) {
  const t0 = performance.now();
  let res;
  try {
    res = await fetch("/api/v2" + path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : undefined);
  } catch (e) { setApi(false); throw new Error("Network error — is the server running?"); }
  let data = null; try { data = await res.json(); } catch {}
  if (!res.ok) { setApi(res.status < 500); const d = data && data.detail; throw new Error(typeof d === "string" ? d : d ? d.map?.(x => x.msg).join("; ") || "Request failed" : res.statusText); }
  setApi(true, Math.round(performance.now() - t0));
  if (data && data.source) setSourceLabel(data.source);
  return data;
}
const Q = o => "?" + new URLSearchParams({ ...o, source: state.source }).toString();
function setApi(ok, ms) { const d = $("#apiDot"); if (!d) return; d.className = "dot " + (ok ? "ok" : "bad"); if (ms != null) $("#latency").textContent = ms + " ms"; }
function setSourceLabel(s) {
  state.lastSource = s; const el = $("#srcLabel"); if (!el) return;
  el.textContent = s === "SIM" ? "SIMULATED DATA" : "LIVE · " + s; el.className = "pill " + (s === "SIM" ? "sim" : "live");
}
function toast(msg, kind = "") { const t = document.createElement("div"); t.className = "toast " + kind; t.textContent = msg; $("#toasts").append(t); setTimeout(() => t.remove(), kind === "err" ? 6000 : 3000); }
const fail = (root, e) => { toast(e.message, "err"); if (root) root.innerHTML = `<div class="empty">⚠ ${esc(e.message)}</div>`; };

/* ---------- plotly helpers ---------- */
const merge = (a, b) => { for (const k in b) { if (b[k] && typeof b[k] === "object" && !Array.isArray(b[k])) a[k] = merge(a[k] && typeof a[k] === "object" ? a[k] : {}, b[k]); else a[k] = b[k]; } return a; };
const AX = (o = {}) => merge({ gridcolor: C.ln, zerolinecolor: "rgba(255,255,255,.12)", linecolor: C.ln, tickfont: { size: 9 }, automargin: true }, o);
function layout(o = {}) {
  return merge({
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: { family: "JetBrains Mono, ui-monospace, monospace", size: 10, color: C.mu },
    margin: { l: 46, r: 12, t: 12, b: 30 }, xaxis: AX({ showspikes: true, spikecolor: "#6b7385", spikethickness: 1, spikedash: "dot", spikemode: "across" }), yaxis: AX(),
    legend: { orientation: "h", y: 1.1, x: 0, font: { size: 10 } }, hovermode: "x",
    hoverlabel: { bgcolor: "#12151c", bordercolor: "#2a3040", font: { family: "JetBrains Mono, monospace", size: 11, color: C.tx } },
  }, o);
}
function plot(id, data, lay, cfg) { const el = typeof id === "string" ? document.getElementById(id) : id; if (!el) return; if (!window.Plotly) { el.innerHTML = '<div class="empty">Plotly failed to load (check network / CDN)</div>'; return; } return Plotly.react(el, data, layout(lay), { displayModeBar: false, responsive: true, ...cfg }); }
const line = (x, y, name, color, o = {}) => ({ x, y, name, type: "scatter", mode: "lines", line: { color, width: 1.6, ...(o.line || {}) }, ...o, line: { color, width: 1.6, ...(o.line || {}) } });
const hexA = (hex, a) => { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; };

/* ---------- ui kit ---------- */
const panel = (title, body, { sub = "", ai = false, actions = "", cls: c = "" } = {}) =>
  `<section class="panel ${ai ? "ai-p" : ""} ${c}"><div class="ph"><h3>${title}</h3><div style="display:flex;gap:10px;align-items:center">${sub ? `<span class="sub">${sub}</span>` : ""}${actions}</div></div><div class="pb">${body}</div></section>`;
const kpi = (label, value, sub = "", c = "") => `<div class="kpi ${c}"><span>${label}</span><b>${value}</b>${sub ? `<small>${sub}</small>` : ""}</div>`;
const skel = (h = 200) => `<div class="skel" style="height:${h}px"></div>`;
const seg = (id, opts, cur) => `<div class="seg" id="${id}">${opts.map(([v, l]) => `<button data-v="${v}" class="${v == cur ? "on" : ""}">${l}</button>`).join("")}</div>`;
function bindSeg(id, fn) { const el = document.getElementById(id); if (!el) return; el.onclick = e => { const b = e.target.closest("button"); if (!b) return; $$("button", el).forEach(x => x.classList.toggle("on", x === b)); fn(b.dataset.v); }; }
const segVal = id => $(`#${id} button.on`)?.dataset.v;
function chipsHTML(id, items, sel) { return `<div class="chips" id="${id}">${items.map(it => { const [v, l] = Array.isArray(it) ? it : [it, it]; return `<span class="cchip ${sel.includes(v) ? "on" : ""}" data-v="${v}">${l}</span>`; }).join("")}</div>`; }
function bindChips(id, { multi = true, min = 1 } = {}) { const el = document.getElementById(id); if (!el) return; el.onclick = e => { const c = e.target.closest(".cchip"); if (!c) return; if (!multi) { $$(".cchip", el).forEach(x => x.classList.remove("on")); c.classList.add("on"); return; } if (c.classList.contains("on") && $$(".cchip.on", el).length <= min) return; c.classList.toggle("on"); }; }
const chipVals = id => $$(`#${id} .cchip.on`).map(c => c.dataset.v);
function busy(btn, on, label) { if (!btn) return; if (on) { btn.dataset.l = btn.innerHTML; btn.disabled = true; btn.innerHTML = `<span class="spin"></span> ${label || "RUNNING"}`; } else { btn.disabled = false; btn.innerHTML = btn.dataset.l || btn.innerHTML; } }
function spark(vals, w = 70, h = 22) {
  if (!vals || vals.length < 2) return ""; const mn = Math.min(...vals), mx = Math.max(...vals), r = mx - mn || 1, up = vals.at(-1) >= vals[0], col = up ? C.up : C.dn;
  const pts = vals.map((v, i) => `${(i / (vals.length - 1) * w).toFixed(1)},${(h - 2 - (v - mn) / r * (h - 4)).toFixed(1)}`).join(" ");
  return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline points="${pts}" fill="none" stroke="${col}" stroke-width="1.4" stroke-linejoin="round"/></svg>`;
}
function countUp(el, to, fmt, ms = 700) { if (!el || !isn(to)) { if (el) el.textContent = fmt(to); return; } const t0 = performance.now(); (function f(t) { const k = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - k, 3); el.textContent = fmt(to * e); if (k < 1) requestAnimationFrame(f); })(t0); }

/* ---------- ticker lists ---------- */
const allTickers = () => state.universe.map(u => u.ticker);
const tickerInput = (id, val) => `<label class="fld">Ticker<input class="inp" id="${id}" list="tl" value="${esc(val)}" spellcheck="false" autocomplete="off" style="text-transform:uppercase"/></label><datalist id="tl">${allTickers().map(t => `<option value="${t}">`).join("")}</datalist>`;
function setTicker(t) { state.ticker = t.toUpperCase().trim(); store.set("ticker", state.ticker); }

/* ---------- router ---------- */
const views = {};
async function go(name, opts = {}) {
  if (!views[name]) name = "terminal"; state.view = name; const tok = ++state.tok;
  $$("#rail a[data-view]").forEach(a => a.classList.toggle("on", a.dataset.view === name));
  const root = $("#view"); root.innerHTML = ""; root.onclick = null; root.onkeydown = null; root.scrollTop = 0; window.scrollTo({ top: 0 });
  document.title = `${VIEW_NAMES[name]} · QuantForge`; history.replaceState(null, "", "#" + name);
  try { await views[name](root, () => tok === state.tok, opts); } catch (e) { if (tok === state.tok) fail(root, e); }
}

/* ---------- status bar ---------- */
function tickClock() {
  const d = new Date(); $("#clock").textContent = d.toISOString().slice(11, 19) + " UTC";
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", weekday: "short", hour: "numeric", minute: "numeric", hour12: false }).formatToParts(d).map(x => [x.type, x.value]));
  const m = (+p.hour % 24) * 60 + +p.minute, open = !["Sat", "Sun"].includes(p.weekday) && m >= 570 && m < 960;
  const el = $("#mktState"); el.textContent = open ? "● NYSE OPEN" : "○ NYSE CLOSED"; el.className = "pill mkt " + (open ? "open" : "closed");
}
function renderTape() {
  const items = state.quotes.map(q => `<span data-t="${q.ticker}"><b>${q.ticker}</b><i class="mono" style="font-style:normal">${F.px(q.price)}</i><i class="${cls(q.chg_1d)}" style="font-style:normal">${q.chg_1d >= 0 ? "▲" : "▼"} ${F.pct(Math.abs(q.chg_1d))}</i></span>`).join("");
  $("#tape").innerHTML = items + items;
  $("#tape").onclick = e => { const s = e.target.closest("span[data-t]"); if (s) { setTicker(s.dataset.t); go("terminal"); } };
}
function loadQuotes() { return (state.qp = api("/screener" + Q({})).then(q => { state.quotes = q; renderTape(); }).catch(e => toast("Quotes unavailable: " + e.message, "err"))); }

/* ---------- command palette ---------- */
const pal = { open: false, items: [], idx: 0 };
function palItems(q) {
  q = q.trim().toLowerCase(); const out = [];
  Object.entries(VIEW_NAMES).forEach(([k, v], i) => { if (!q || v.toLowerCase().includes(q) || k.includes(q)) out.push({ t: "view", k, label: v, hint: "view · " + (i + 1) }); });
  state.universe.forEach(u => { if (!q || u.ticker.toLowerCase().includes(q) || u.name.toLowerCase().includes(q)) out.push({ t: "tick", k: u.ticker, label: u.ticker, hint: u.name + " · " + u.sector }); });
  if (/^[a-z.\-]{1,10}$/.test(q) && !state.universe.some(u => u.ticker.toLowerCase() === q)) out.push({ t: "tick", k: q.toUpperCase(), label: q.toUpperCase(), hint: "open custom symbol" });
  return out.slice(0, 12);
}
function palRender() { $("#palList").innerHTML = pal.items.map((it, i) => `<li data-i="${i}" class="${i === pal.idx ? "on" : ""}"><span>${it.t === "view" ? "↗ " : ""}${esc(it.label)}</span><small>${esc(it.hint)}</small></li>`).join("") || '<li class="mu">No matches</li>'; }
function palOpen(v = true) { pal.open = v; $("#palette").hidden = !v; if (v) { $("#palInput").value = ""; pal.items = palItems(""); pal.idx = 0; palRender(); setTimeout(() => $("#palInput").focus(), 0); } }
function palRun(i) { const it = pal.items[i]; if (!it) return; palOpen(false); if (it.t === "view") go(it.k); else { setTicker(it.k); go(["forecast", "terminal"].includes(state.view) ? state.view : "terminal"); } }
function initPalette() {
  $("#cmdBtn").onclick = () => palOpen(true);
  $("#palInput").oninput = e => { pal.items = palItems(e.target.value); pal.idx = 0; palRender(); };
  $("#palInput").onkeydown = e => { if (e.key === "ArrowDown") { pal.idx = Math.min(pal.idx + 1, pal.items.length - 1); palRender(); e.preventDefault(); } else if (e.key === "ArrowUp") { pal.idx = Math.max(0, pal.idx - 1); palRender(); e.preventDefault(); } else if (e.key === "Enter") palRun(pal.idx); };
  $("#palList").onclick = e => { const li = e.target.closest("li[data-i]"); if (li) palRun(+li.dataset.i); };
  $("#palette").onclick = e => { if (e.target.id === "palette") palOpen(false); };
  document.addEventListener("keydown", e => {
    const typing = /INPUT|SELECT|TEXTAREA/.test(document.activeElement?.tagName || "");
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); palOpen(!pal.open); }
    else if (e.key === "Escape" && pal.open) palOpen(false);
    else if (!typing && !pal.open && e.key === "/") { e.preventDefault(); palOpen(true); }
    else if (!typing && !pal.open && /^[1-7]$/.test(e.key)) go(Object.keys(VIEW_NAMES)[+e.key - 1]);
  });
}

/* ---------- boot ---------- */
async function boot() {
  $("#srcMode").textContent = state.source.toUpperCase();
  $("#srcBtn").onclick = () => { state.source = state.source === "auto" ? "sim" : "auto"; store.set("source", state.source); $("#srcMode").textContent = state.source.toUpperCase(); toast("Data mode: " + state.source.toUpperCase()); loadQuotes(); go(state.view); };
  $("#rail").onclick = e => { const a = e.target.closest("a[data-view]"); if (a) go(a.dataset.view); };
  initPalette(); tickClock(); setInterval(tickClock, 1000);
  try { state.universe = await (await fetch("/api/v2/universe")).json(); setApi(true); } catch { setApi(false); }
  loadQuotes();
  const h = location.hash.slice(1); go(views[h] ? h : "terminal");
}
window.addEventListener("DOMContentLoaded", () => setTimeout(boot, 0));
