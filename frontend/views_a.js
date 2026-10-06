/* QuantForge v10 — views: Markets, AI Forecast, Screener */
const addBDays = (d, k) => { const x = new Date(d + "T00:00:00Z"); let n = 0; while (n < k) { x.setUTCDate(x.getUTCDate() + 1); if (![0, 6].includes(x.getUTCDay())) n++; } return x.toISOString().slice(0, 10); };

/* =============== MARKETS =============== */
views.terminal = async (root, live) => {
  const t = state.ticker; let range = 252, over = new Set(["sma50", "bb", "vol"]), M = null;
  root.innerHTML = `<div class="grid g-term">
    <section class="panel"><div class="ph"><h3>Watchlist</h3><span class="sub" id="wlN"></span></div><div class="wl" id="wl">${skel(300)}</div></section>
    <div class="stack">
      <section class="panel"><div class="ph"><div class="tick-h" id="tkh"><h2>${esc(t)}</h2><span class="mu mono">loading…</span></div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">${seg("rng", [[63, "3M"], [126, "6M"], [252, "1Y"], [504, "2Y"]], 252)}
        <div class="chips" id="ovl">${[["sma20", "SMA20"], ["sma50", "SMA50"], ["sma200", "SMA200"], ["bb", "BOLL"], ["vol", "VOL"]].map(([k, l]) => `<span class="cchip ${over.has(k) ? "on" : ""}" data-v="${k}">${l}</span>`).join("")}</div></div></div>
        <div class="pb flush"><div id="px" class="plot xl">${skel(520)}</div></div></section>
      <div class="bar" style="margin:0"><button class="btn pri" id="goAI">✦ RUN AI FORECAST ON ${esc(t)}</button><button class="btn" id="goStrat">BACKTEST STRATEGIES</button>
        <label class="fld" style="margin-left:auto;min-width:140px">Jump to ticker<input class="inp" id="jump" list="tl" placeholder="e.g. TSLA ⏎" style="text-transform:uppercase"/></label><datalist id="tl">${allTickers().map(x => `<option value="${x}">`).join("")}</datalist></div>
    </div>
    <div class="stack" id="side">${skel(200)}${skel(220)}${skel(220)}</div></div>`;

  const wl = async () => { await state.qp; if (!live()) return; $("#wlN").textContent = state.quotes.length + " symbols";
    $("#wl").innerHTML = state.quotes.map(q => `<a data-t="${q.ticker}" class="${q.ticker === t ? "on" : ""}"><b>${q.ticker}</b><span class="r mono">${F.px(q.price)}</span><small>${esc(q.name)}</small><span class="r ${cls(q.chg_1d)}">${F.pct(q.chg_1d, 2, true)}</span><span style="grid-column:1/-1">${spark(q.spark, 190, 20)}</span></a>`).join("");
    $("#wl").onclick = e => { const a = e.target.closest("a[data-t]"); if (a) { setTicker(a.dataset.t); go("terminal"); } }; };
  wl();
  $("#goAI").onclick = () => go("forecast"); $("#goStrat").onclick = () => go("strategy");
  $("#jump").onkeydown = e => { if (e.key === "Enter" && e.target.value.trim()) { setTicker(e.target.value); go("terminal"); } };

  const draw = () => {
    if (!M) return; const n = Math.min(range, M.dates.length), sl = a => a.slice(-n), x = sl(M.dates), I = M.indicators, tr = [];
    tr.push({ type: "candlestick", x, open: sl(M.open), high: sl(M.high), low: sl(M.low), close: sl(M.close), name: M.ticker, increasing: { line: { color: C.up, width: 1 }, fillcolor: hexA(C.up, .75) }, decreasing: { line: { color: C.dn, width: 1 }, fillcolor: hexA(C.dn, .75) }, yaxis: "y", hoverinfo: "x+y" });
    if (over.has("bb")) { tr.push(line(x, sl(I.bb_up), "BB↑", "rgba(139,123,255,.55)", { line: { width: 1, dash: "dot" }, hoverinfo: "skip" })); tr.push({ ...line(x, sl(I.bb_lo), "BB↓", "rgba(139,123,255,.55)", { line: { width: 1, dash: "dot" } }), fill: "tonexty", fillcolor: "rgba(139,123,255,.06)", hoverinfo: "skip" }); }
    [["sma20", C.cy], ["sma50", C.am], ["sma200", "#e8ecf3"]].forEach(([k, c]) => over.has(k) && tr.push(line(x, sl(I[k]), k.toUpperCase(), c, { line: { width: 1.2 } })));
    let vmax = 1; if (over.has("vol")) { const v = sl(M.volume); vmax = Math.max(...v); tr.push({ type: "bar", x, y: v, yaxis: "y4", name: "Vol", marker: { color: sl(M.close).map((c, i) => c >= sl(M.open)[i] ? hexA(C.up, .28) : hexA(C.dn, .28)) }, hoverinfo: "skip" }); }
    tr.push(line(x, sl(I.rsi), "RSI 14", C.cy, { yaxis: "y2", line: { width: 1.2 } }));
    tr.push({ type: "bar", x, y: sl(I.macd_hist), yaxis: "y3", name: "MACD hist", marker: { color: sl(I.macd_hist).map(v => v >= 0 ? hexA(C.up, .6) : hexA(C.dn, .6)) } });
    tr.push(line(x, sl(I.macd), "MACD", C.cy, { yaxis: "y3", line: { width: 1 } })); tr.push(line(x, sl(I.macd_signal), "Signal", C.am, { yaxis: "y3", line: { width: 1 } }));
    const rb = /-USD$/.test(M.ticker) ? [] : [{ bounds: ["sat", "mon"] }];
    const sh = [30, 70].map(v => ({ type: "line", xref: "paper", x0: 0, x1: 1, yref: "y2", y0: v, y1: v, line: { color: "rgba(255,255,255,.14)", width: 1, dash: "dot" } }));
    plot("px", tr, { margin: { l: 12, r: 48, t: 6, b: 28 }, showlegend: false, shapes: sh,
      xaxis: AX({ anchor: "y3", rangeslider: { visible: false }, rangebreaks: rb, showspikes: true, spikemode: "across", spikecolor: "#6b7385", spikethickness: 1, spikedash: "dot" }),
      yaxis: AX({ domain: [.34, 1], side: "right" }), yaxis2: AX({ domain: [.185, .30], range: [0, 100], tickvals: [30, 70], side: "right" }), yaxis3: AX({ domain: [0, .14], side: "right", showticklabels: false }),
      yaxis4: { overlaying: "y", side: "left", range: [0, vmax * 3.4], showgrid: false, showticklabels: false, zeroline: false },
      annotations: [{ xref: "paper", yref: "paper", x: 0, y: .31, text: "RSI 14", showarrow: false, font: { size: 9, color: C.mu }, xanchor: "left" }, { xref: "paper", yref: "paper", x: 0, y: .145, text: "MACD", showarrow: false, font: { size: 9, color: C.mu }, xanchor: "left" }] });
  };
  bindSeg("rng", v => { range = +v; draw(); });
  $("#ovl").onclick = e => { const c = e.target.closest(".cchip"); if (!c) return; c.classList.toggle("on"); c.classList.contains("on") ? over.add(c.dataset.v) : over.delete(c.dataset.v); draw(); };

  const pm = api(`/market/${encodeURIComponent(t)}` + Q({ days: 504 })).then(m => {
    if (!live()) return; M = m; const pos = m.change >= 0;
    $("#tkh").innerHTML = `<h2>${esc(m.ticker)}</h2><span class="px">${F.px(m.last)}</span><span class="mono ${pos ? "up" : "dn"}">${pos ? "▲" : "▼"} ${F.pct(Math.abs(m.change))}</span><span class="mu mono" style="font-size:10.5px">52W ${F.px(m.lo_52w)} – ${F.px(m.hi_52w)} · ${m.asof}</span>`; draw();
  }).catch(e => { if (live()) { $("#px").innerHTML = `<div class="empty">⚠ ${esc(e.message)}</div>`; toast(e.message, "err"); } });

  const pa = api(`/analysis/${encodeURIComponent(t)}` + Q({})).then(a => {
    if (!live()) return; const tc = a.technical, g = a.garch, r = a.regime; let html = "";
    html += panel("Technical Consensus", `<div style="display:flex;justify-content:space-between;align-items:baseline"><b class="mono ${tc.bias === "bullish" ? "up" : tc.bias === "bearish" ? "dn" : ""}" style="font-size:22px;text-transform:uppercase">${tc.bias}</b><span class="mono mu">score ${tc.technical_score >= 0 ? "+" : ""}${tc.technical_score.toFixed(2)}</span></div>
      <div class="mbar" style="grid-template-columns:1fr"><i style="--w:${((tc.technical_score + 1) / 2 * 100).toFixed(0)}%"></i></div>
      ${tc.readings.map(x => `<div class="rd"><span><i class="bias-dot ${x.bias}"></i>${x.name}</span><span>${/vs/.test(x.name) ? F.pct(x.value, 1, true) : F.n(x.value, 2)}</span></div>`).join("")}
      <div class="rd"><span class="mu">ATR(14)</span><span>${F.pct(tc.atr_pct)}</span></div><div class="rd"><span class="mu">ADX · trend</span><span>${F.n(tc.adx, 1)} · ${tc.trend_strength}</span></div>`, { sub: "6–7 signals" });
    html += g ? panel("Volatility · GARCH(1,1)", `<div class="kpis"><div class="kpi"><span>Current</span><b>${F.pct(g.current_vol_ann, 1)}</b></div><div class="kpi"><span>Long-run</span><b>${F.pct(g.long_run_vol_ann, 1)}</b></div></div>
      <div id="gp" class="plot s"></div><div class="note">α ${g.alpha.toFixed(3)} · β ${g.beta.toFixed(3)} · persistence ${g.persistence.toFixed(3)}${g.half_life_days ? ` · shock half-life <b>${g.half_life_days.toFixed(1)}d</b>` : ""}. Vol is <b>${g.current_vol_ann > g.long_run_vol_ann ? "above" : "below"}</b> its long-run mean → forecast ${g.current_vol_ann > g.long_run_vol_ann ? "mean-reverts down" : "drifts up"}.</div>`, { sub: "QMLE fit" }) : "";
    html += r ? panel("Regime · Gaussian HMM", `<div style="display:flex;justify-content:space-between;align-items:baseline"><b class="mono" style="font-size:22px;color:${["#3ddc97", "#ffb547", "#ff5d73"][r.current_idx]}">${r.current.toUpperCase()}</b><span class="mono mu">3-state EM</span></div>
      <div style="margin:10px 0" id="reg"></div><table class="t"><thead><tr><th>State</th><th>Vol</th><th>Time</th><th>Dur</th></tr></thead><tbody>${r.states.map((s, i) => `<tr><td style="color:${["#3ddc97", "#ffb547", "#ff5d73"][i]}">${s.name}</td><td>${F.pct(s.ann_vol, 0)}</td><td>${F.pct(s.occupancy, 0)}</td><td>${s.expected_duration_days.toFixed(0)}d</td></tr>`).join("")}</tbody></table>
      <div class="note" style="margin-top:8px">Next-day transition: ${Object.entries(r.next_state_probs).map(([k, v]) => `${k} <b>${F.pct(v, 0)}</b>`).join(" · ")}</div>`, { sub: "vol-ranked" }) : "";
    $("#side").innerHTML = html;
    if (g) { const hist = g.cond_vol_series_ann.slice(-200), fc = g.forecast_vol_ann; plot("gp", [line(hist.map((_, i) => i - 199), hist, "cond. vol", C.cy), line([0, ...fc.map((_, i) => i + 1)].slice(0, fc.length + 1), [hist.at(-1), ...fc], "forecast", C.ai, { line: { dash: "dash", width: 2 } })], { margin: { l: 38, r: 8, t: 6, b: 24 }, showlegend: false, yaxis: AX({ tickformat: ".0%" }), xaxis: AX({ title: { text: "days from today", font: { size: 9 } } }), shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: g.long_run_vol_ann, y1: g.long_run_vol_ann, yref: "y", line: { color: C.am, width: 1, dash: "dot" } }] }); }
    if (r) { const p = r.path, col = ["#3ddc97", "#ffb547", "#ff5d73"]; let runs = "", s = 0; for (let i = 1; i <= p.length; i++) if (i === p.length || p[i] !== p[s]) { runs += `<rect x="${s}" y="0" width="${i - s}" height="1" fill="${col[p[s]]}"/>`; s = i; }
      $("#reg").innerHTML = `<svg class="regstrip" viewBox="0 0 ${p.length} 1" preserveAspectRatio="none">${runs}</svg><div style="display:flex;justify-content:space-between;font:500 9px var(--mono);color:var(--dim);margin-top:3px"><span>${a.dates[r.offset + 1]}</span><span>${a.dates.at(-1)}</span></div>`; }
  }).catch(e => { if (live()) $("#side").innerHTML = panel("Analytics", `<div class="empty">⚠ ${esc(e.message)}</div>`); });
  await Promise.all([pm, pa]);
};

/* =============== AI FORECAST =============== */
function gaugeHTML(p, thr) {
  const L = Math.PI * 80, col = p > .5 + thr ? C.up : p < .5 - thr ? C.dn : C.ai;
  return `<div class="gauge"><svg viewBox="0 0 180 100"><path d="M10 90 A80 80 0 0 1 170 90" fill="none" stroke="#1b2029" stroke-width="11" stroke-linecap="round"/>
    <path id="garc" d="M10 90 A80 80 0 0 1 170 90" fill="none" stroke="${col}" stroke-width="11" stroke-linecap="round" stroke-dasharray="0 ${L}" style="filter:drop-shadow(0 0 7px ${col});transition:stroke-dasharray .9s cubic-bezier(.2,.8,.2,1)" data-to="${(p * L).toFixed(1)} ${L.toFixed(1)}"/>
    <line x1="90" y1="4" x2="90" y2="16" stroke="rgba(255,255,255,.35)" stroke-width="1.5"/></svg><div class="val"><span id="gval">0.0%</span><small>P(UP) · NEXT H DAYS</small></div></div>`;
}
views.forecast = async (root, live) => {
  const cfg = store.get("fc", { h: 5, mode: "long_flat", thr: 0.02, cost: 5 });
  root.innerHTML = `<section class="panel ai-p" style="margin-bottom:12px"><div class="ph"><h3>AI Forecast Engine</h3><span class="sub">purged walk-forward · logit + forest + boosting</span></div>
    <div class="pb"><div class="fgrid">${tickerInput("fcT", state.ticker)}
      <label class="fld">Horizon (days)${seg("fcH", [[1, "1"], [5, "5"], [10, "10"], [21, "21"]], cfg.h)}</label>
      <label class="fld">Positioning${seg("fcM", [["long_flat", "Long/Flat"], ["long_short", "Long/Short"]], cfg.mode)}</label>
      <label class="fld">Entry threshold <span id="thv" class="ai">±${(cfg.thr * 100).toFixed(0)}pp</span><input type="range" id="fcThr" min="0" max="0.1" step="0.01" value="${cfg.thr}"/></label>
      <label class="fld">Cost (bps)<input class="inp" id="fcC" type="number" min="0" max="100" value="${cfg.cost}"/></label>
      <button class="btn pri" id="fcRun">✦ RUN MODEL</button></div></div></section><div id="fcOut"></div>`;
  $("#fcThr").oninput = e => $("#thv").textContent = "±" + (e.target.value * 100).toFixed(0) + "pp";
  bindSeg("fcH", () => {}); bindSeg("fcM", () => {});
  const run = async () => {
    const t = $("#fcT").value.trim().toUpperCase() || state.ticker; setTicker(t);
    const c = { h: +segVal("fcH"), mode: segVal("fcM"), thr: +$("#fcThr").value, cost: +$("#fcC").value }; store.set("fc", c);
    const out = $("#fcOut"); busy($("#fcRun"), true, "FITTING");
    out.innerHTML = `<div class="grid g-fc">${skel(330)}${skel(330)}</div><div class="note" style="text-align:center;margin-top:14px"><span class="spin"></span>&nbsp; Fitting 3 models × 5 purged walk-forward folds, then refitting on all history…</div>`;
    try {
      const d = await api(`/forecast/${encodeURIComponent(t)}` + Q({ horizon: c.h, mode: c.mode, threshold: c.thr, cost_bps: c.cost })); if (!live()) return;
      renderForecast(out, d, c);
    } catch (e) { if (live()) out.innerHTML = `<div class="panel"><div class="empty">⚠ ${esc(e.message)}</div></div>`; toast(e.message, "err"); }
    finally { busy($("#fcRun"), false); }
  };
  $("#fcRun").onclick = run; $("#fcT").onkeydown = e => { if (e.key === "Enter") run(); };
  await run();
};

function renderForecast(out, d, c) {
  const s = d.signal, v = d.validation, o = d.oos_strategy, sp = o.strategy, bp = o.buy_hold_perf, VT = { EDGE_DETECTED: "EDGE DETECTED", WEAK_EDGE: "WEAK / MARGINAL EDGE", NO_EDGE: "NO RELIABLE EDGE" };
  const models = { logit: "Logit", forest: "Forest", boost: "Boost" };
  out.innerHTML = `
  <div class="grid g-fc">
    ${panel("Signal · " + esc(d.ticker), `<div class="hero">${gaugeHTML(s.prob_up, c.thr)}<div>
        <div class="tick-h"><span class="dir ${s.direction}">${s.direction}</span><span class="mu mono" style="font-size:11px">H=${d.horizon}d · ${d.asof} · ${esc(d.source)}</span></div>
        <div style="margin-top:10px">${Object.entries(s.by_model).map(([k, p]) => `<div class="mbar"><span>${models[k] || k}</span><i style="--w:${(p * 100).toFixed(1)}%"></i><span>${F.pct(p, 1)}</span></div>`).join("")}</div>
        <div class="note">Model disagreement σ = <b>${(s.model_disagreement * 100).toFixed(1)}pp</b> ${s.model_disagreement > .08 ? "· <span class='am'>models conflict — low conviction</span>" : "· models broadly agree"}</div></div></div>
      <div class="verdict ${s.verdict}"><b>${VT[s.verdict]}</b>${esc(s.verdict_text)}</div>
      <div class="kpis" style="margin-top:12px">${kpi("P10 target", F.px(s.price_q10), F.pct(s.expected_return_q10, 1, true), "")}${kpi("Median", F.px(s.price_q50), F.pct(s.expected_return_q50, 1, true), "ai")}${kpi("P90 target", F.px(s.price_q90), F.pct(s.expected_return_q90, 1, true), "")}</div>`, { ai: true, sub: "live prediction" })}
    ${panel("Price Projection", `<div id="cone" class="plot l"></div><div class="note">Cone = GARCH(1,1) volatility term-structure around a drift tilted 50% toward the ML median. Bars at the horizon are the model's quantile-regression P10/P50/P90.</div>`, { sub: "30d · 50/90% bands" })}
  </div>
  <div class="grid g-fc" style="margin-top:12px">
    ${panel("Out-of-sample Evidence", `<div class="kpis">
      ${kpi("AUC", F.n(v.auc, 3), `models ${Object.values(v.model_auc).map(x => x.toFixed(2)).join(" / ")}`, v.auc > .53 ? "ai" : "")}
      ${kpi("Rank IC", (v.information_coefficient >= 0 ? "+" : "") + F.n(v.information_coefficient, 3), "p = " + F.n(v.p_value, 3))}
      ${kpi("Accuracy", F.pct(v.accuracy, 1), "base " + F.pct(v.baseline_accuracy, 1))}
      ${kpi("Brier", F.n(v.brier, 4), "naive " + F.n(v.brier_baseline, 4))}
      ${kpi("OOS Sharpe", F.ratio(sp.sharpe), "B&H " + F.ratio(bp.sharpe), sp.sharpe > bp.sharpe ? "ai" : "")}
      ${kpi("OOS Return", F.pct(sp.total_return, 1, true), "B&H " + F.pct(bp.total_return, 1, true))}
      ${kpi("Max DD", F.pct(sp.max_drawdown, 1), "B&H " + F.pct(bp.max_drawdown, 1))}
      ${kpi("Exposure", F.pct(sp.exposure, 0), "turnover " + F.n(sp.turnover_per_year, 0) + "×/yr")}</div>
      <div class="note" style="margin-top:10px"><b>${v.n_oos}</b> out-of-sample bars (≈<b>${v.n_effective}</b> independent after label overlap). ${v.high_conf_accuracy != null ? `High-conviction calls (±5pp) were right <b>${F.pct(v.high_conf_accuracy, 1)}</b> of the time on ${F.pct(v.high_conf_share, 0)} of days.` : ""}</div>`, { sub: "never seen in training" })}
    ${panel("Out-of-sample Equity · net of " + o.cost_bps + "bps", `<div id="oos" class="plot m"></div>`, { sub: o.mode === "long_short" ? "long/short" : "long/flat" })}
  </div>
  <div class="grid g-3" style="margin-top:12px">
    ${panel("Calibration", `<div id="cal" class="plot s"></div><div class="note">Points on the diagonal = probabilities mean what they say.</div>`, { sub: "5 quantile bins" })}
    ${panel("What drives the model", `<div id="imp" class="plot s"></div>`, { sub: "importance · green = ↑ prob" })}
    ${panel("Why this prediction, today", `<div id="drv" class="plot s"></div>`, { sub: "logit contributions" })}
  </div>
  <div style="margin-top:12px">${panel("Walk-forward folds", `<div class="scroll"><table class="t"><thead><tr><th>Test window</th><th>Train rows</th><th>Test rows</th><th>Up-rate</th><th>Accuracy</th><th>AUC</th></tr></thead><tbody>${v.folds.map(f => `<tr><td>${f.start} → ${f.end}</td><td>${f.n_train}</td><td>${f.n_test}</td><td>${F.pct(f.base_rate, 0)}</td><td class="${f.accuracy > f.base_rate ? "up" : ""}">${F.pct(f.accuracy, 1)}</td><td class="${f.auc > .52 ? "up" : f.auc < .48 ? "dn" : ""}">${F.n(f.auc, 3)}</td></tr>`).join("")}</tbody></table></div>
    <div class="note" style="margin-top:8px">${d.meta.features} features · ${d.meta.train_rows} training rows · trained in ${d.meta.seconds}s · embargo gap = horizon (${d.horizon}d) between train and test. <b>Not investment advice.</b> Markets are close to efficient; treat results as research output.</div>`, { sub: "expanding window, refit per fold" })}</div>`;

  // gauge animate
  requestAnimationFrame(() => { const a = $("#garc"); if (a) a.setAttribute("stroke-dasharray", a.dataset.to); countUp($("#gval"), s.prob_up * 100, x => x.toFixed(1) + "%"); });
  // cone
  const cn = d.cone;
  if (cn) { const fx = cn.days.map(k => addBDays(d.asof, k)), hx = cn.hist_dates, last = cn.hist.at(-1), X = [d.asof, ...fx], Y = a => [last, ...a];
    plot("cone", [line(hx, cn.hist, "price", C.tx, { line: { width: 1.4 } }),
      { x: [...X, ...X.slice().reverse()], y: [...Y(cn.p95), ...Y(cn.p05).reverse()], fill: "toself", fillcolor: hexA(C.ai, .13), line: { width: 0 }, name: "90% band", hoverinfo: "skip", type: "scatter" },
      { x: [...X, ...X.slice().reverse()], y: [...Y(cn.p75), ...Y(cn.p25).reverse()], fill: "toself", fillcolor: hexA(C.ai, .24), line: { width: 0 }, name: "50% band", hoverinfo: "skip", type: "scatter" },
      line(X, Y(cn.median), "median", C.ai, { line: { dash: "dash", width: 2 } }),
      { x: [fx[d.horizon - 1]], y: [s.price_q50], type: "scatter", mode: "markers", name: "ML P10–P90", marker: { color: C.cy, size: 9, line: { color: "#000", width: 1 } }, error_y: { type: "data", symmetric: false, array: [s.price_q90 - s.price_q50], arrayminus: [s.price_q50 - s.price_q10], color: C.cy, thickness: 2, width: 6 } }],
      { hovermode: "x unified", margin: { l: 50, r: 10, t: 6, b: 28 } }); }
  // oos equity
  plot("oos", [line(o.dates, o.buy_hold, "Buy & hold", C.mu, { line: { width: 1.3 } }), line(o.dates, o.equity, "AI strategy", C.ai, { line: { width: 2 } })], { yaxis: AX({ tickformat: ".2f" }) });
  // calibration
  plot("cal", [line([0.3, 0.7], [0.3, 0.7], "ideal", "rgba(255,255,255,.25)", { line: { dash: "dot", width: 1 }, hoverinfo: "skip" }),
    { x: d.calibration.map(b => b.pred), y: d.calibration.map(b => b.obs), type: "scatter", mode: "lines+markers", name: "model", line: { color: C.ai, width: 2 }, marker: { color: C.ai, size: d.calibration.map(b => 6 + b.n / 25) }, text: d.calibration.map(b => "n=" + b.n), hovertemplate: "pred %{x:.1%}<br>obs %{y:.1%}<br>%{text}<extra></extra>" }],
    { showlegend: false, margin: { l: 40, r: 8, t: 6, b: 34 }, xaxis: AX({ title: { text: "predicted P(up)", font: { size: 9 } }, tickformat: ".0%" }), yaxis: AX({ title: { text: "observed", font: { size: 9 } }, tickformat: ".0%" }) });
  // importance
  const imp = d.importance.slice(0, 9).reverse();
  plot("imp", [{ type: "bar", orientation: "h", y: imp.map(i => i.feature), x: imp.map(i => i.importance), marker: { color: imp.map(i => i.sign >= 0 ? hexA(C.up, .75) : hexA(C.dn, .75)) }, hovertemplate: "%{y}: %{x:.1%}<extra></extra>" }],
    { margin: { l: 78, r: 8, t: 6, b: 24 }, showlegend: false, hovermode: "closest", xaxis: AX({ tickformat: ".0%" }), yaxis: AX({ tickfont: { size: 9 } }) });
  const dr = d.drivers.slice().reverse();
  plot("drv", [{ type: "bar", orientation: "h", y: dr.map(i => i.feature), x: dr.map(i => i.contribution), marker: { color: dr.map(i => i.contribution >= 0 ? hexA(C.up, .75) : hexA(C.dn, .75)) }, hovertemplate: "%{y}: %{x:+.2f} logit<extra></extra>" }],
    { margin: { l: 78, r: 8, t: 6, b: 24 }, showlegend: false, hovermode: "closest", yaxis: AX({ tickfont: { size: 9 } }) });
}

/* =============== SCREENER =============== */
views.screener = async (root, live) => {
  root.innerHTML = skel(120); await state.qp; if (!live()) return;
  let rows = state.quotes.slice(), key = "rank", dir = 1, f = "";
  const cols = [["rank", "#", x => x], ["ticker", "Symbol", x => `<b>${x}</b>`], ["name", "Name", x => `<span class="mu">${esc(x)}</span>`], ["price", "Price", F.px], ["chg_1d", "1D", x => `<span class="${cls(x)}">${F.pct(x, 2, true)}</span>`],
    ["chg_21d", "1M", x => `<span class="${cls(x)}">${F.pct(x, 1, true)}</span>`], ["chg_126d", "6M", x => `<span class="${cls(x)}">${F.pct(x, 1, true)}</span>`],
    ["rsi", "RSI", x => `<span class="${x > 70 ? "dn" : x < 30 ? "up" : ""}">${x.toFixed(0)}</span>`], ["vol_21d", "Vol 21d", x => F.pct(x, 0)], ["tech_score", "Tech", x => `<span class="${cls(x)}">${x >= 0 ? "+" : ""}${x.toFixed(2)}</span>`],
    ["composite", "Composite", (x, r) => `<span class="${cls(x)}" style="display:inline-block;min-width:50px">${x >= 0 ? "+" : ""}${x.toFixed(2)}</span>`], ["above_200", "Trend", x => x ? '<span class="up">▲ &gt;200d</span>' : '<span class="dn">▼ &lt;200d</span>'], ["spark", "60d", x => spark(x, 80, 20)]];
  const draw = () => {
    const rs = rows.filter(r => !f || (r.ticker + r.name + r.sector).toLowerCase().includes(f)).sort((a, b) => (a[key] > b[key] ? 1 : a[key] < b[key] ? -1 : 0) * dir);
    $("#scT").innerHTML = `<thead><tr>${cols.map(([k, l]) => `<th class="sort ${k === "name" || k === "ticker" ? "l" : ""}" data-k="${k}">${l}${k === key ? (dir > 0 ? " ▲" : " ▼") : ""}</th>`).join("")}</tr></thead><tbody>${rs.map(r => `<tr class="click" data-t="${r.ticker}">${cols.map(([k, , fm], i) => `<td class="${i === 1 || i === 2 ? "l" : ""}">${fm(r[k], r)}</td>`).join("")}</tr>`).join("")}</tbody>`;
  };
  const mx = Math.max(...rows.map(r => Math.abs(r.chg_1d)), .01);
  root.innerHTML = `<div class="grid" style="gap:12px">${panel("Heat · 1-day move", `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(112px,1fr));gap:6px">${rows.map(r => { const a = (.12 + .55 * Math.abs(r.chg_1d) / mx).toFixed(2), c = r.chg_1d >= 0 ? "61,220,151" : "255,93,115"; return `<div class="click" data-t="${r.ticker}" style="padding:10px;border-radius:9px;background:rgba(${c},${a});border:1px solid rgba(${c},.35);cursor:pointer"><b class="mono">${r.ticker}</b><div class="mono" style="font-size:12px">${F.pct(r.chg_1d, 2, true)}</div><small class="mu mono" style="font-size:9.5px">${esc(r.sector)}</small></div>`; }).join("")}</div>`, { sub: "click to open" })}
    ${panel("Universe screener", `<div class="bar"><input class="inp" id="scF" placeholder="Filter by symbol, name or sector…" style="max-width:320px"/><span class="note">Composite = 40% technical score + 40% risk-adjusted 6M momentum + 20% long-term trend (z-scored cross-sectionally). A ranking aid, not a prediction.</span></div><div class="scroll"><table class="t" id="scT"></table></div>`, { sub: rows.length + " symbols · " + (state.lastSource || "") })}</div>`;
  draw();
  root.onclick = e => { const th = e.target.closest("th[data-k]"); if (th) { const k = th.dataset.k; dir = key === k ? -dir : (k === "rank" || k === "ticker" || k === "name" ? 1 : -1); key = k; draw(); return; } const r = e.target.closest("[data-t]"); if (r) { setTicker(r.dataset.t); go("terminal"); } };
  $("#scF").oninput = e => { f = e.target.value.toLowerCase(); draw(); };
};
