/* QuantForge v10 — views: Strategy Lab, Portfolio Lab, Risk Center, Options Lab */
const PAL = [C.ai, C.cy, C.am, C.up, "#ff8ad8", "#a3e635", "#f97316"];
const HEAT = [[0, "#8a2438"], [.5, "#12151c"], [1, "#1f8a5f"]];

/* =============== STRATEGY LAB =============== */
const STRAT_LABELS = { ma_cross: "MA Crossover", momentum: "Momentum", rsi_reversion: "RSI Reversion", bollinger: "Bollinger Rev.", donchian: "Donchian Breakout", vol_target: "Vol-Target Trend" };
views.strategy = async (root, live) => {
  const cfg = store.get("st", { s: ["ma_cross", "momentum", "donchian", "vol_target"], cost: 5 });
  root.innerHTML = `<section class="panel" style="margin-bottom:12px"><div class="ph"><h3>Strategy Lab</h3><span class="sub">signal at close t → trade at t+1 · costs on every position change</span></div><div class="pb">
    <div class="fgrid" style="grid-template-columns:140px 1fr 110px auto">${tickerInput("stT", state.ticker)}<label class="fld">Strategies${chipsHTML("stS", Object.entries(STRAT_LABELS), cfg.s)}</label>
    <label class="fld">Cost (bps)<input class="inp" id="stC" type="number" value="${cfg.cost}" min="0" max="100"/></label><button class="btn pri" id="stRun">▶ RUN BACKTEST</button></div></div></section><div id="stOut"></div>`;
  bindChips("stS");
  const run = async () => {
    const t = $("#stT").value.trim().toUpperCase() || state.ticker; setTicker(t); const names = chipVals("stS"), cost = +$("#stC").value; store.set("st", { s: names, cost });
    const out = $("#stOut"); busy($("#stRun"), true); out.innerHTML = `<div class="grid g-2">${skel(300)}${skel(300)}</div>`;
    try {
      const body = { ticker: t, strategies: names, cost_bps: cost, days: 756, source: state.source };
      const [d, sf] = await Promise.all([api("/strategies/compare", body), api("/strategies/surface", body)]); if (!live()) return;
      const ids = ["buy_hold", ...names], m = d.metrics, best = names.slice().sort((a, b) => m[b].sharpe - m[a].sharpe)[0];
      out.innerHTML = `<div class="grid" style="gap:12px">
        ${panel("Equity curves · " + esc(d.ticker), `<div class="bar" style="margin-bottom:4px">${seg("lg", [["linear", "Linear"], ["log", "Log"]], "linear")}</div><div id="stEq" class="plot l"></div>`, { sub: d.source === "SIM" ? "simulated data" : d.source })}
        ${panel("Performance", `<div class="scroll"><table class="t"><thead><tr><th>Strategy</th><th>Total</th><th>CAGR</th><th>Vol</th><th>Sharpe</th><th>Sortino</th><th>Max DD</th><th>Calmar</th><th>Win%</th><th>Exposure</th><th>Trades</th></tr></thead><tbody>${ids.map(k => { const x = m[k]; return `<tr class="${k === best ? "best" : ""}"><td><i class="bias-dot" style="background:${k === "buy_hold" ? C.mu : PAL[names.indexOf(k) % PAL.length]}"></i>${d.labels[k]}${k === best ? ' <span class="up">★</span>' : ""}</td><td class="${cls(x.total_return)}">${F.pct(x.total_return, 1, true)}</td><td>${F.pct(x.cagr, 1)}</td><td>${F.pct(x.ann_vol, 1)}</td><td><b>${F.ratio(x.sharpe)}</b></td><td>${F.ratio(x.sortino)}</td><td class="dn">${F.pct(x.max_drawdown, 1)}</td><td>${F.ratio(x.calmar)}</td><td>${F.pct(x.win_rate, 0)}</td><td>${F.pct(x.exposure, 0)}</td><td>${x.trades}</td></tr>`; }).join("")}</tbody></table></div>
          <div class="note" style="margin-top:8px">These are <b>in-sample</b> results on a single path. The heatmaps below test whether a parameter choice survives out-of-sample.</div>`, { sub: "ranked by Sharpe ★" })}
        ${panel("Overfitting detector · MA-cross Sharpe surface", `<div class="grid g-2"><div><div class="mu mono" style="font-size:10px;margin-bottom:4px">IN-SAMPLE (first 60% → ${sf.split_date})</div><div id="hmI" class="plot m"></div></div><div><div class="mu mono" style="font-size:10px;margin-bottom:4px">OUT-OF-SAMPLE (last 40%)</div><div id="hmO" class="plot m"></div></div></div><div id="hmNote" class="note" style="margin-top:8px"></div>`, { sub: "short × long windows", ai: true })}</div>`;
      const draw = lg => plot("stEq", ids.map(k => ({ ...line(d.dates, d.series[k], d.labels[k], k === "buy_hold" ? C.mu : PAL[names.indexOf(k) % PAL.length], { line: { width: k === "buy_hold" ? 1.4 : 1.8, dash: k === "buy_hold" ? "dot" : "solid" } }) })), { yaxis: AX({ type: lg, tickformat: ".2f" }), hovermode: "x unified", margin: { l: 46, r: 10, t: 6, b: 28 } });
      draw("linear"); bindSeg("lg", draw);
      const star = (i, j) => [{ x: String(sf.longs[j]), y: String(sf.shorts[i]), text: "★", showarrow: false, font: { size: 15, color: "#fff" } }], b = sf.best_in_sample;
      const bi = b ? [sf.shorts.indexOf(b.short), sf.longs.indexOf(b.long)] : null;
      const hm = (id, z, ann) => plot(id, [{ type: "heatmap", z, x: sf.longs.map(String), y: sf.shorts.map(String), colorscale: HEAT, zmid: 0, showscale: false, texttemplate: "%{z:.2f}", textfont: { size: 10, color: "#e8ecf3" }, hovertemplate: "short %{y} / long %{x}<br>Sharpe %{z}<extra></extra>", xgap: 2, ygap: 2 }],
        { hovermode: "closest", margin: { l: 36, r: 6, t: 4, b: 34 }, annotations: ann, xaxis: AX({ type: "category", title: { text: "long window", font: { size: 9 } }, showspikes: false }), yaxis: AX({ type: "category", title: { text: "short window", font: { size: 9 } } }) });
      hm("hmI", sf.in_sample, bi ? star(...bi) : []); hm("hmO", sf.out_of_sample, bi ? star(...bi) : []);
      $("#hmNote").innerHTML = b ? `Best in-sample pair <b>${b.short}/${b.long}</b> had Sharpe <b class="up">${b.in_sample_sharpe.toFixed(2)}</b> → out-of-sample <b class="${cls(b.out_of_sample_sharpe)}">${b.out_of_sample_sharpe.toFixed(2)}</b>. ${b.out_of_sample_sharpe < b.in_sample_sharpe * .5 ? '<span class="am">Large decay = the "optimal" parameters were mostly noise-fitting.</span>' : "Reasonable persistence out-of-sample."} Prefer wide, stable green regions over a single hot cell.` : "No valid parameter pair.";
    } catch (e) { if (live()) out.innerHTML = `<div class="panel"><div class="empty">⚠ ${esc(e.message)}</div></div>`; toast(e.message, "err"); } finally { busy($("#stRun"), false); }
  };
  $("#stRun").onclick = run; $("#stT").onkeydown = e => { if (e.key === "Enter") run(); }; await run();
};

/* =============== PORTFOLIO LAB =============== */
const PF_METHODS = [["max_sharpe", "Max Sharpe"], ["min_vol", "Min Vol"], ["risk_parity", "Risk Parity"], ["hrp", "HRP"], ["equal", "Equal"]];
views.portfolio = async (root, live) => {
  const cfg = store.get("pf", { t: ["AAPL", "MSFT", "JPM", "XOM", "GLD", "TLT"], m: "hrp", cap: .5, d: 504 });
  root.innerHTML = `<section class="panel" style="margin-bottom:12px"><div class="ph"><h3>Portfolio Lab</h3><span class="sub">long-only · Ledoit-Wolf covariance · shrunk expected returns</span></div><div class="pb">
    <label class="fld" style="margin-bottom:10px">Universe (pick ≥ 2)${chipsHTML("pfT", allTickers(), cfg.t)}</label>
    <div class="fgrid"><label class="fld">Method${seg("pfM", PF_METHODS, cfg.m)}</label><label class="fld">History${seg("pfD", [[252, "1Y"], [504, "2Y"], [756, "3Y"]], cfg.d)}</label>
      <label class="fld">Max weight <span id="capv" class="ai">${(cfg.cap * 100).toFixed(0)}%</span><input type="range" id="pfCap" min=".2" max="1" step=".05" value="${cfg.cap}"/></label>
      <button class="btn pri" id="pfRun">◆ OPTIMIZE</button><button class="btn" id="pfSave" disabled>SAVE</button></div></div></section><div id="pfOut"></div><div id="pfSaved" style="margin-top:12px"></div>`;
  bindChips("pfT", { min: 2 }); bindSeg("pfM", () => {}); bindSeg("pfD", () => {}); $("#pfCap").oninput = e => $("#capv").textContent = (e.target.value * 100).toFixed(0) + "%";
  let last = null;
  const saved = async () => { try { const r = await (await fetch("/api/portfolios")).json(); if (!live()) return; $("#pfSaved").innerHTML = panel("Saved portfolios", r.length ? `<div class="scroll"><table class="t"><thead><tr><th>Name</th><th>E[ret]</th><th>Vol</th><th>Saved</th></tr></thead><tbody>${r.slice(0, 8).map(p => `<tr><td class="l">${esc(p.name)}</td><td>${F.pct(p.expected_return, 1)}</td><td>${F.pct(p.volatility, 1)}</td><td class="mu">${p.created_at.slice(0, 16).replace("T", " ")}</td></tr>`).join("")}</tbody></table></div>` : '<div class="empty">Nothing saved yet — optimize, then press SAVE.</div>', { sub: "SQLite / Postgres" }); } catch {} };
  const run = async () => {
    const c = { t: chipVals("pfT"), m: segVal("pfM"), cap: +$("#pfCap").value, d: +segVal("pfD") }; store.set("pf", c);
    const out = $("#pfOut"); busy($("#pfRun"), true); out.innerHTML = `<div class="grid g-2">${skel(300)}${skel(300)}</div>`;
    try {
      const d = await api("/portfolio/optimize", { tickers: c.t, method: c.m, cap: c.cap, days: c.d, source: state.source }); if (!live()) return; last = { d, c }; state.pf = { assets: d.assets, weights: d.weights };
      $("#pfSave").disabled = false; const A = d.assets, w = d.weights, o = d.holdout, mn = PF_METHODS.find(x => x[0] === c.m)[1];
      const idx = A.map((_, i) => i).sort((a, b) => w[b] - w[a]);
      out.innerHTML = `<div class="grid" style="gap:12px">
        <div class="kpis">${kpi("Method", mn, "cap " + F.pct(c.cap, 0), "ai")}${kpi("Exp. return", F.pct(d.stats.ret, 1), "shrunk estimate")}${kpi("Volatility", F.pct(d.stats.vol, 1), "annualised")}${kpi("Sharpe (in-sample)", F.ratio(d.stats.sharpe), "optimistic by design")}${kpi("Effective N", F.n(d.effective_n, 1), "of " + A.length + " assets")}${kpi("Diversification", F.n(d.diversification_ratio, 2) + "×", "weighted vol / port vol")}</div>
        <div class="grid g-2">${panel("Allocation vs risk contribution", `<div id="pfW" class="plot m"></div><div class="note">Where the bars differ, capital allocation and risk allocation disagree — risk parity equalises the red bars.</div>`, { sub: mn })}
          ${panel("Efficient frontier", `<div id="pfF" class="plot m"></div>`, { sub: "random portfolios · long-only frontier" })}</div>
        <div class="grid g-2">${panel("Correlation", `<div id="pfC" class="plot m"></div>`, { sub: "Ledoit-Wolf shrunk" })}
          ${panel("Honest test · out-of-sample holdout", `<div id="pfH" class="plot s"></div><div class="scroll"><table class="t"><thead><tr><th>Portfolio</th><th>Return</th><th>Sharpe</th><th>Vol</th></tr></thead><tbody>
            <tr><td class="ai">${mn} (fit ≤ ${o.train_end})</td><td class="${cls(o.optimised_perf.total_return)}">${F.pct(o.optimised_perf.total_return, 1, true)}</td><td><b>${F.ratio(o.optimised_perf.sharpe)}</b></td><td>${F.pct(o.optimised_perf.ann_vol, 1)}</td></tr>
            <tr><td class="mu">Equal weight</td><td class="${cls(o.equal_perf.total_return)}">${F.pct(o.equal_perf.total_return, 1, true)}</td><td><b>${F.ratio(o.equal_perf.sharpe)}</b></td><td>${F.pct(o.equal_perf.ann_vol, 1)}</td></tr></tbody></table></div>
            <div class="note" style="margin-top:6px">Weights were estimated <b>only</b> on data before the split, then held fixed. If the optimizer can't beat 1/N here, its in-sample edge was estimation noise.</div>`, { ai: true, sub: "no look-ahead" })}</div></div>`;
      const nm = idx.map(i => A[i]);
      plot("pfW", [{ type: "bar", name: "Weight", x: nm, y: idx.map(i => w[i]), marker: { color: hexA(C.ai, .85) }, hovertemplate: "%{x}<br>weight %{y:.1%}<extra></extra>" }, { type: "bar", name: "Risk contribution", x: nm, y: idx.map(i => d.risk_contribution[i]), marker: { color: hexA(C.dn, .75) }, hovertemplate: "%{x}<br>risk %{y:.1%}<extra></extra>" }], { barmode: "group", yaxis: AX({ tickformat: ".0%" }), hovermode: "closest" });
      plot("pfF", [{ x: d.random.map(r => r.vol), y: d.random.map(r => r.ret), type: "scatter", mode: "markers", name: "random", marker: { size: 3, color: d.random.map(r => r.ret / r.vol), colorscale: [[0, "#2a3040"], [1, "#4cc9f0"]], opacity: .6 }, hoverinfo: "skip" },
        line(d.frontier.map(r => r.vol), d.frontier.map(r => r.ret), "frontier", C.up, { line: { width: 2.2 } }),
        { x: d.single.map(r => r.vol), y: d.single.map(r => r.ret), type: "scatter", mode: "markers+text", text: d.single.map(r => r.asset), textposition: "top center", textfont: { size: 9, color: C.mu }, name: "assets", marker: { size: 7, color: C.am } },
        { x: [d.stats.vol], y: [d.stats.ret], type: "scatter", mode: "markers", name: mn, marker: { symbol: "star", size: 17, color: C.ai, line: { color: "#fff", width: 1 } } }],
        { hovermode: "closest", xaxis: AX({ title: { text: "volatility", font: { size: 9 } }, tickformat: ".0%" }), yaxis: AX({ title: { text: "expected return", font: { size: 9 } }, tickformat: ".0%" }), margin: { l: 50, r: 10, t: 6, b: 38 } });
      plot("pfC", [{ type: "heatmap", z: d.corr, x: A, y: A, zmin: -1, zmax: 1, colorscale: [[0, "#ff5d73"], [.5, "#12151c"], [1, "#4cc9f0"]], texttemplate: "%{z:.2f}", textfont: { size: 9 }, showscale: false, xgap: 2, ygap: 2, hovertemplate: "%{x}/%{y}: %{z:.2f}<extra></extra>" }], { hovermode: "closest", margin: { l: 56, r: 6, t: 4, b: 40 }, yaxis: AX({ autorange: "reversed" }), xaxis: AX({ showspikes: false }) });
      plot("pfH", [line(o.dates, o.equal_weight, "Equal weight", C.mu, { line: { dash: "dot", width: 1.4 } }), line(o.dates, o.optimised, mn, C.ai, { line: { width: 2 } })], { hovermode: "x unified", margin: { l: 44, r: 8, t: 6, b: 26 }, yaxis: AX({ tickformat: ".2f" }) });
    } catch (e) { if (live()) out.innerHTML = `<div class="panel"><div class="empty">⚠ ${esc(e.message)}</div></div>`; toast(e.message, "err"); } finally { busy($("#pfRun"), false); }
  };
  $("#pfRun").onclick = run;
  $("#pfSave").onclick = async () => { if (!last) return; const { d, c } = last; try { const r = await fetch("/api/portfolios", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: `${PF_METHODS.find(x => x[0] === c.m)[1]} · ${d.assets.join("/")}`, weights: d.weights, expected_return: d.stats.ret, volatility: d.stats.vol }) }); if (!r.ok) throw new Error("save failed"); toast("Portfolio saved", "ok"); saved(); } catch (e) { toast(e.message, "err"); } };
  saved(); await run();
};

/* =============== RISK CENTER =============== */
views.risk = async (root, live) => {
  const pf = state.pf, cfg = store.get("rk", { t: ["SPY", "TLT"], conf: 0.95 });
  root.innerHTML = `<section class="panel" style="margin-bottom:12px"><div class="ph"><h3>Risk Center</h3><span class="sub">VaR · CVaR · drawdowns · scenario stress · Monte Carlo</span></div><div class="pb">
    <label class="fld" style="margin-bottom:10px">Portfolio (equal-weighted unless using optimized)${chipsHTML("rkT", allTickers(), cfg.t)}</label>
    <div class="fgrid"><label class="fld">Confidence${seg("rkC", [[0.95, "95%"], [0.99, "99%"]], cfg.conf)}</label>
      ${pf ? `<label class="fld">Weights<span class="chips"><span class="cchip" id="useOpt">Use last optimized (${pf.assets.length})</span></span></label>` : ""}
      <button class="btn pri" id="rkRun">▲ ANALYSE RISK</button></div></div></section><div id="rkOut"></div>`;
  bindChips("rkT", { min: 1 }); bindSeg("rkC", () => {}); if (pf) $("#useOpt").onclick = e => e.target.classList.toggle("on");
  const run = async () => {
    const use = pf && $("#useOpt")?.classList.contains("on"), t = use ? pf.assets : chipVals("rkT"), w = use ? pf.weights : null, conf = +segVal("rkC"); store.set("rk", { t: chipVals("rkT"), conf });
    const out = $("#rkOut"); busy($("#rkRun"), true); out.innerHTML = `<div class="grid g-2">${skel(260)}${skel(260)}</div>`;
    const base = { tickers: t, weights: w, source: state.source };
    try {
      const [r, st] = await Promise.all([api("/risk/analyze", { ...base, confidence: conf }), api("/stress", { ...base, value: 100000 })]); if (!live()) return;
      const pc = Math.round(conf * 100), v = r.var, cv = r.cvar, m = r.moments, ra = r.ratios, bt = r.var_backtest, sc = st.scenarios, sk = Object.keys(sc);
      out.innerHTML = `<div class="grid" style="gap:12px">
        <div class="kpis">${kpi(pc + "% VaR · historical", F.pct(v.historical, 2), "1-day", "ai")}${kpi("VaR · Normal", F.pct(v.parametric_normal, 2), "underestimates fat tails")}${kpi("VaR · Cornish-Fisher", F.pct(v.cornish_fisher, 2), "skew/kurt adjusted")}${kpi("VaR · Student-t", F.pct(v.student_t_mc, 2), "df " + F.n(m.student_t_df, 1))}${kpi(pc + "% CVaR (ES)", F.pct(cv.historical, 2), "avg loss beyond VaR", "ai")}${kpi("Max drawdown", F.pct(ra.max_drawdown, 1), "calmar " + F.ratio(ra.calmar))}</div>
        <div class="kpis">${kpi("Ann. return", F.pct(m.mean_ann, 1))}${kpi("Ann. vol", F.pct(m.vol_ann, 1))}${kpi("Sharpe", F.ratio(ra.sharpe))}${kpi("Sortino", F.ratio(ra.sortino))}${kpi("Skew", F.n(m.skew, 2), m.skew < -.3 ? "left-tail heavy" : "")}${kpi("Excess kurtosis", F.n(m.excess_kurtosis, 2), "JB p=" + F.n(m.jarque_bera_p, 3))}${kpi("Omega", F.ratio(ra.omega_0))}${kpi("Worst day", F.pct(m.worst_day, 1))}</div>
        <div class="grid g-2">${panel("Return distribution", `<div id="rkH" class="plot m"></div>`, { sub: "daily · VaR lines" })}${panel("Underwater curve", `<div id="rkD" class="plot m"></div>`, { sub: "drawdown from peak" })}</div>
        <div class="grid g-2">${panel("Rolling 21d volatility", `<div id="rkV" class="plot s"></div>`)}${panel("Rolling 63d Sharpe", `<div id="rkS" class="plot s"></div>`)}</div>
        <div class="grid g-2">${panel("VaR model validation · Kupiec POF", `<div class="kpis">${kpi("Exceptions", bt.exceptions, "expected " + bt.expected.toFixed(1))}${kpi("Observations", bt.observations, "rolling " + bt.window + "d window")}${kpi("Kupiec p", F.n(bt.kupiec_p, 3), "", bt.verdict === "calibrated" ? "ai" : "")}</div><div class="verdict ${bt.verdict === "calibrated" ? "EDGE_DETECTED" : "NO_EDGE"}"><b>${bt.verdict.toUpperCase()}</b>${bt.verdict === "calibrated" ? "Historical VaR exception rate is statistically consistent with the stated confidence level." : "Exception frequency differs significantly from the stated level — VaR is mis-stating tail risk."}</div>`, { ai: true })}
          ${panel("Worst drawdown episodes", `<table class="t"><thead><tr><th>Start</th><th>Trough</th><th>Recovered</th><th>Depth</th><th>Days</th></tr></thead><tbody>${r.dd_episodes.map(e => `<tr><td>${e.start}</td><td>${e.trough}</td><td>${e.end}</td><td class="dn">${F.pct(e.depth, 1)}</td><td>${e.days}</td></tr>`).join("")}</tbody></table>`)}</div>
        <div class="grid g-2">${panel("Scenario stress · $100k", `<div id="rkSt" class="plot s"></div><div class="note">Shocks are beta-mapped: each asset's loss = its estimated sensitivity to <b>equities (SPY)</b>, <b>rates (TLT)</b> and <b>commodities (GLD)</b> × the scenario's factor move.</div>`, { sub: "factor-mapped historical shocks" })}
          ${panel("Monte Carlo · 1 year", `<div class="bar" style="margin-bottom:4px">${seg("mcM", [["bootstrap", "Bootstrap"], ["gbm", "GBM"]], "bootstrap")}${seg("mcY", [[1, "1Y"], [3, "3Y"]], 1)}</div><div id="rkMC" class="plot s"></div><div id="mcT"></div>`, { sub: "3,000 paths" })}</div></div>`;
      const x = r.dates;
      const H = r.hist, ctr = H.edges.slice(0, -1).map((e, i) => (e + H.edges[i + 1]) / 2);
      plot("rkH", [{ type: "bar", x: ctr, y: H.counts, marker: { color: ctr.map(c => c < -v.historical ? hexA(C.dn, .8) : hexA(C.cy, .55)) }, hovertemplate: "%{x:.2%}: %{y} days<extra></extra>" }], { bargap: .05, showlegend: false, hovermode: "closest", xaxis: AX({ tickformat: ".1%" }), shapes: [[-v.historical, C.dn, "VaR"], [-cv.historical, "#ff9aa8", "CVaR"]].map(([p, c]) => ({ type: "line", x0: p, x1: p, yref: "paper", y0: 0, y1: 1, line: { color: c, width: 1.5, dash: "dash" } })), annotations: [[-v.historical, "VaR"], [-cv.historical, "CVaR"]].map(([p, tx]) => ({ x: p, yref: "paper", y: 1, text: tx, showarrow: false, font: { size: 9, color: C.dn }, yanchor: "bottom" })) });
      plot("rkD", [{ x, y: r.drawdown, type: "scatter", mode: "lines", fill: "tozeroy", line: { color: C.dn, width: 1.2 }, fillcolor: hexA(C.dn, .22), name: "drawdown" }], { yaxis: AX({ tickformat: ".0%" }), showlegend: false });
      plot("rkV", [line(x, r.rolling_vol, "vol", C.cy)], { yaxis: AX({ tickformat: ".0%" }), showlegend: false, margin: { l: 40, r: 8, t: 6, b: 26 } });
      plot("rkS", [line(x, r.rolling_sharpe, "sharpe", C.ai)], { showlegend: false, margin: { l: 40, r: 8, t: 6, b: 26 }, shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0, y1: 0, line: { color: "rgba(255,255,255,.2)", width: 1 } }] });
      plot("rkSt", [{ type: "bar", x: sk, y: sk.map(k => sc[k].pnl), marker: { color: sk.map(k => sc[k].pnl >= 0 ? hexA(C.up, .8) : hexA(C.dn, .8)) }, text: sk.map(k => F.pct(sc[k].portfolio_return, 1, true)), textposition: "outside", textfont: { size: 9, color: C.mu }, hovertemplate: "%{x}<br>P&L $%{y:,.0f}<extra></extra>" }], { hovermode: "closest", showlegend: false, margin: { l: 56, r: 8, t: 14, b: 50 }, yaxis: AX({ tickprefix: "$", tickformat: ",.0f" }), xaxis: AX({ tickfont: { size: 8.5 }, showspikes: false }) });
      const sim = async () => {
        try { const s = await api("/simulate", { ...base, method: segVal("mcM"), years: +segVal("mcY"), sims: 3000, start: 100000 }); if (!live()) return; const xs = s.bands["50"].map((_, i) => i), b = s.bands;
          plot("rkMC", [...s.sample_paths.slice(0, 14).map(p => ({ x: xs, y: p, type: "scatter", mode: "lines", line: { color: "rgba(139,123,255,.16)", width: 1 }, hoverinfo: "skip", showlegend: false })),
            { x: [...xs, ...xs.slice().reverse()], y: [...b["95"], ...b["5"].slice().reverse()], fill: "toself", fillcolor: hexA(C.ai, .12), line: { width: 0 }, type: "scatter", hoverinfo: "skip", name: "5–95%" },
            { x: [...xs, ...xs.slice().reverse()], y: [...b["75"], ...b["25"].slice().reverse()], fill: "toself", fillcolor: hexA(C.ai, .22), line: { width: 0 }, type: "scatter", hoverinfo: "skip", name: "25–75%" }, line(xs, b["50"], "median", C.cy, { line: { width: 2 } })],
            { showlegend: false, margin: { l: 56, r: 8, t: 6, b: 28 }, yaxis: AX({ tickprefix: "$", tickformat: ",.0f" }), xaxis: AX({ title: { text: "trading days", font: { size: 9 } } }) });
          const T = s.terminal; $("#mcT").innerHTML = `<div class="kpis" style="margin-top:8px">${kpi("Median", F.usd(T.median, 0))}${kpi("5th pct", F.usd(T.p05, 0), "", "")}${kpi("P(loss)", F.pct(T.prob_loss, 0))}${kpi("P(DD>20%)", F.pct(T.prob_dd_20, 0))}</div>`; } catch (e) { toast(e.message, "err"); } };
      bindSeg("mcM", sim); bindSeg("mcY", sim); sim();
    } catch (e) { if (live()) out.innerHTML = `<div class="panel"><div class="empty">⚠ ${esc(e.message)}</div></div>`; toast(e.message, "err"); } finally { busy($("#rkRun"), false); }
  };
  $("#rkRun").onclick = run; await run();
};

/* =============== OPTIONS LAB =============== */
/* is the extreme P&L still growing at the edge of the plotted spot range? (=> unbounded) */
const edgeOpen = (y, sign) => { const n = y.length, ex = sign > 0 ? Math.max(...y) : Math.min(...y), tol = 1e-6;
  return (Math.abs(y[n - 1] - ex) < tol && sign * (y[n - 1] - y[n - 3]) > tol) || (Math.abs(y[0] - ex) < tol && sign * (y[0] - y[2]) > tol); };
const PRESET_LABELS = { long_call: "Long call", long_put: "Long put", covered_call: "Covered call", bull_call_spread: "Bull call spread", bear_put_spread: "Bear put spread", long_straddle: "Long straddle", long_strangle: "Long strangle", iron_condor: "Iron condor", butterfly: "Call butterfly" };
views.options = async (root, live) => {
  const c0 = store.get("op", { S: 100, K: 105, T: .5, r: .04, v: .25, q: 0, type: "call", mp: "", preset: "long_straddle" });
  const f = (id, l, v, step = "any") => `<label class="fld">${l}<input class="inp" id="${id}" type="number" step="${step}" value="${v}"/></label>`;
  root.innerHTML = `<div class="grid" style="grid-template-columns:290px minmax(0,1fr);align-items:start;gap:12px" id="opG">
    <section class="panel"><div class="ph"><h3>Contract</h3><span class="sub">Black-Scholes-Merton + CRR</span></div><div class="pb" style="display:grid;gap:10px">
      ${f("oS", "Spot", c0.S)}${f("oK", "Strike", c0.K)}${f("oT", "Time to expiry (years)", c0.T, .01)}${f("oV", "Volatility (σ)", c0.v, .01)}${f("oR", "Risk-free rate", c0.r, .005)}${f("oQ", "Dividend yield", c0.q, .005)}
      <label class="fld">Type${seg("oTy", [["call", "Call"], ["put", "Put"]], c0.type)}</label>
      <label class="fld">Market price → implied vol<input class="inp" id="oMP" type="number" step="any" value="${c0.mp}" placeholder="optional"/></label>
      <label class="fld">Strategy payoff<select id="oPre" class="inp">${Object.entries(PRESET_LABELS).map(([k, l]) => `<option value="${k}" ${k === c0.preset ? "selected" : ""}>${l}</option>`).join("")}</select></label></div></section>
    <div id="opOut">${skel(400)}</div></div>`;
  bindSeg("oTy", () => sched()); let timer;
  const sched = () => { clearTimeout(timer); timer = setTimeout(run, 260); };
  ["oS", "oK", "oT", "oV", "oR", "oQ", "oMP"].forEach(id => $("#" + id).oninput = sched); $("#oPre").onchange = sched;
  let curveKey = "delta", D = null;
  const drawCurves = () => { if (!D) return; const cv = D.curves; plot("opG1", [line(cv.spots, cv[curveKey], curveKey, C.ai, { line: { width: 2 } })], { margin: { l: 52, r: 8, t: 6, b: 28 }, showlegend: false, shapes: [{ type: "line", x0: +$("#oS").value, x1: +$("#oS").value, yref: "paper", y0: 0, y1: 1, line: { color: C.am, width: 1, dash: "dot" } }] }); };
  async function run() {
    const body = { spot: +$("#oS").value, strike: +$("#oK").value, time_to_maturity: +$("#oT").value, volatility: +$("#oV").value, risk_free_rate: +$("#oR").value, dividend_yield: +$("#oQ").value, option_type: segVal("oTy"), preset: $("#oPre").value, market_price: $("#oMP").value ? +$("#oMP").value : null };
    store.set("op", { S: body.spot, K: body.strike, T: body.time_to_maturity, r: body.risk_free_rate, v: body.volatility, q: body.dividend_yield, type: body.option_type, mp: $("#oMP").value, preset: body.preset });
    try {
      const d = await api("/options/analyze", body); if (!live()) return; D = d; const b = d.bs, s = d.strategy, out = $("#opOut"), fresh = !$("#opG1");
      out.innerHTML = `<div class="grid" style="gap:12px">
        <div class="kpis">${kpi("BS price", F.n(b.price, 4), "European", "ai")}${kpi("American (CRR)", F.n(d.american_crr, 4), "+" + F.n(d.early_exercise_premium, 4) + " early-ex.")}${kpi("Delta", F.n(b.delta, 4))}${kpi("Gamma", F.n(b.gamma, 5))}${kpi("Vega /1%", F.n(b.vega_per_1pct, 4))}${kpi("Theta /day", F.n(b.theta_per_day, 4), "", b.theta_per_day < 0 ? "dn" : "")}${kpi("Rho /1%", F.n(b.rho_per_1pct, 4))}${d.implied_vol != null ? kpi("Implied vol", F.pct(d.implied_vol, 2), "vs σ " + F.pct(body.volatility, 1) + " (" + F.pct(d.iv_vs_input, 1, true) + ")", "ai") : d.implied_vol_error ? kpi("Implied vol", "n/a", d.implied_vol_error) : ""}</div>
        <div class="grid g-2">${panel(PRESET_LABELS[s.preset] + " · P&L", `<div id="opP" class="plot m"></div><div class="kpis" style="margin-top:8px">${kpi("Net " + (s.net_debit >= 0 ? "debit" : "credit"), F.usd(Math.abs(s.net_debit), 2))}${kpi("Max profit", edgeOpen(s.pnl_expiry, 1) ? "Unlimited" : F.usd(s.max_profit, 2), "", "up")}${kpi("Max loss", edgeOpen(s.pnl_expiry, -1) ? "Unlimited" : F.usd(s.max_loss, 2), "", "dn")}${kpi("Breakeven", s.breakevens.length ? s.breakevens.map(x => F.n(x, 1)).join(" / ") : "—")}</div>`, { sub: "expiry vs today (BSM)" })}
          ${panel("Greeks vs spot", `<div class="bar" style="margin-bottom:4px">${seg("gk", [["delta", "Delta"], ["gamma", "Gamma"], ["vega", "Vega"], ["theta", "Theta"], ["price", "Price"]], curveKey)}</div><div id="opG1" class="plot m"></div>`, { sub: "dotted = spot" })}</div>
        <div class="grid g-2">${panel("Time decay", `<div id="opTd" class="plot s"></div>`, { sub: "value vs spot as expiry nears" })}${panel("Price surface · vol × strike", `<div id="opSf" class="plot s"></div>`, { sub: "premium" })}</div>
        ${panel("Strategy legs", `<table class="t"><thead><tr><th>Leg</th><th>Qty</th><th>Strike</th><th>Premium</th></tr></thead><tbody>${s.legs.map(l => `<tr><td class="l">${l.leg}</td><td class="${l.qty > 0 ? "up" : "dn"}">${l.qty > 0 ? "+" : ""}${l.qty}</td><td>${l.strike == null ? "—" : F.n(l.strike, 2)}</td><td>${F.n(l.premium, 3)}</td></tr>`).join("")}</tbody></table>`)}</div>`;
      bindSeg("gk", k => { curveKey = k; drawCurves(); });
      plot("opP", [{ x: s.spots, y: s.pnl_today, name: "Today", type: "scatter", mode: "lines", line: { color: C.cy, width: 1.6, dash: "dot" } }, { x: s.spots, y: s.pnl_expiry, name: "At expiry", type: "scatter", mode: "lines", line: { color: C.ai, width: 2.2 }, fill: "tozeroy", fillcolor: hexA(C.ai, .1) }],
        { margin: { l: 52, r: 8, t: 6, b: 28 }, shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0, y1: 0, line: { color: "rgba(255,255,255,.25)", width: 1 } }, { type: "line", x0: body.spot, x1: body.spot, yref: "paper", y0: 0, y1: 1, line: { color: C.am, width: 1, dash: "dot" } }], hovermode: "x unified" });
      drawCurves();
      plot("opTd", Object.entries(d.decay).map(([k, y], i) => line(d.curves.spots, y, k, PAL[i], { line: { width: 1.6 } })), { margin: { l: 44, r: 8, t: 6, b: 26 } });
      plot("opSf", [{ type: "heatmap", z: d.surface.price, x: d.surface.strike.map(x => +x.toFixed(1)), y: d.surface.vol.map(x => +(x * 100).toFixed(0)), colorscale: [[0, "#12151c"], [1, "#8b7bff"]], showscale: false, hovertemplate: "K %{x} · σ %{y}%<br>premium %{z:.2f}<extra></extra>" }], { hovermode: "closest", margin: { l: 40, r: 6, t: 4, b: 30 }, xaxis: AX({ title: { text: "strike", font: { size: 9 } }, showspikes: false }), yaxis: AX({ title: { text: "σ %", font: { size: 9 } } }) });
    } catch (e) { toast(e.message, "err"); if (live() && !D) $("#opOut").innerHTML = `<div class="panel"><div class="empty">⚠ ${esc(e.message)}</div></div>`; }
  }
  await run();
};
