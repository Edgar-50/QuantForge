async function post(url,payload){
  const res=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  const data=await res.json();
  if(!res.ok) throw new Error(data.detail||"Request failed");
  return data;
}
const num=id=>parseFloat(document.getElementById(id).value);
const parseReturns=()=>document.getElementById("returns").value.split(",").map(Number).filter(Number.isFinite);
const fmt=x=>Number(x).toFixed(4);

function chartLayout(x,y){
  return {
    paper_bgcolor:"transparent",plot_bgcolor:"transparent",
    font:{color:"#8ca3b3",size:10},margin:{l:50,r:15,t:20,b:45},
    xaxis:{title:x,gridcolor:"#173143",zerolinecolor:"#173143"},
    yaxis:{title:y,gridcolor:"#173143",zerolinecolor:"#173143"},
    legend:{orientation:"h"}
  };
}
function demoPrices(){
  const out=[];let p=100;
  for(let i=0;i<360;i++){p*=1+(Math.sin(i/11)*.0035)+(.0007)+((i%29===0)?-.009:.0004);out.push(p)}
  return out;
}

async function runRisk(){
  const d=await post("/api/risk",{returns:parseReturns(),confidence:.95,risk_free_rate:.03});
  const rows=[["95% VaR",d.var],["95% CVaR",d.cvar],["Max DD",d.max_drawdown],["Sharpe",d.sharpe],["Sortino",d.sortino]];
  document.getElementById("riskCards").innerHTML=rows.map(([k,v])=>`<div class="metric"><span>${k}</span><b>${fmt(v)}</b></div>`).join("");
}
async function priceOption(){
  const d=await post("/api/black-scholes",{spot:num("spot"),strike:num("strike"),time_to_maturity:num("time"),risk_free_rate:num("rate"),volatility:num("vol"),option_type:"call"});
  document.getElementById("optionOut").textContent=`PRICE ${fmt(d.price)}\nDELTA ${fmt(d.delta)}\nGAMMA ${d.gamma.toFixed(6)}\nVEGA ${fmt(d.vega_per_1pct)}\nTHETA ${fmt(d.theta_per_day)}\nRHO ${fmt(d.rho_per_1pct)}`;
}
async function runPortfolio(){
  const mu=[.08,.11,.14,.06];
  const cov=[[.032,.012,.010,.006],[.012,.050,.018,.007],[.010,.018,.082,.008],[.006,.007,.008,.020]];
  const f=await post("/api/portfolio/frontier",{expected_returns:mu,covariance:cov,points:40});
  const mv=await post("/api/portfolio/min-variance",{expected_returns:mu,covariance:cov,points:40});
  const rp=await post("/api/portfolio/risk-parity",{covariance:cov,shrinkage:.25});
  const iv=await post("/api/portfolio/inverse-volatility",{covariance:cov,shrinkage:.25});
  Plotly.newPlot("frontierChart",[
    {x:f.frontier.map(x=>x.volatility),y:f.frontier.map(x=>x.target_return),mode:"lines+markers",name:"Efficient frontier"},
    {x:[mv.volatility],y:[mv.expected_return],mode:"markers",marker:{size:13},name:"Min variance"}
  ],chartLayout("Volatility","Expected Return"),{displayModeBar:false,responsive:true});
  document.getElementById("portfolioOut").textContent=
    `MIN-VAR ${mv.weights.map(x=>(x*100).toFixed(1)+"%").join(" | ")}\n`+
    `RISK PARITY ${rp.weights.map(x=>(x*100).toFixed(1)+"%").join(" | ")}\n`+
    `INVERSE VOL ${iv.weights.map(x=>(x*100).toFixed(1)+"%").join(" | ")}`;
}
async function runStress(){
  const scenarios={
    "Equity Shock":[-.20,-.15,-.10,-.05],
    "Rates Shock":[-.06,-.08,-.12,.03],
    "Risk-Off":[-.14,-.18,-.22,.04],
    "Recovery":[.10,.12,.16,.05]
  };
  const d=await post("/api/stress",{weights:[.25,.25,.25,.25],scenarios,portfolio_value:100000});
  const names=Object.keys(d), pnl=names.map(n=>d[n].pnl);
  Plotly.newPlot("stressChart",[{x:names,y:pnl,type:"bar"}],chartLayout("Scenario","PnL"),{displayModeBar:false,responsive:true});
  document.getElementById("stressOut").textContent=names.map(n=>`${n}: ${d[n].pnl.toFixed(2)}`).join("\n");
}
async function runBacktest(){
  const d=await post("/api/backtest/ma",{prices:demoPrices(),short_window:8,long_window:24,transaction_cost_bps:5});
  document.getElementById("backtestOut").textContent=`Strategy return: ${(d.total_return*100).toFixed(2)}%\nBuy & hold: ${(d.buy_and_hold_return*100).toFixed(2)}%\nSharpe: ${fmt(d.sharpe)}\nMax DD: ${(d.max_drawdown*100).toFixed(2)}%`;
  Plotly.newPlot("equityChart",[{y:d.equity_curve,mode:"lines",name:"Strategy Equity"}],chartLayout("Period","Equity"),{displayModeBar:false,responsive:true});
}
async function runWalkForward(){
  const d=await post("/api/walk-forward",{prices:demoPrices(),train_size:120,test_size:30,transaction_cost_bps:5});
  document.getElementById("wfOut").textContent=`Windows: ${d.windows.length}\nCompounded OOS return: ${(d.compounded_out_of_sample_return*100).toFixed(2)}%`;
  Plotly.newPlot("wfChart",[{x:d.windows.map((_,i)=>i+1),y:d.windows.map(x=>x.test_return),type:"bar",name:"OOS return"}],chartLayout("Window","Return"),{displayModeBar:false,responsive:true});
}
async function runMonte(){
  const d=await post("/api/monte-carlo",{initial_value:num("initial"),annual_return:num("mcReturn"),annual_volatility:num("mcVol"),years:num("years"),simulations:10000,seed:42});
  document.getElementById("monteOut").textContent=`Mean ${d.mean_terminal_value.toFixed(2)}\nMedian ${d.median_terminal_value.toFixed(2)}\nLoss probability ${(d.probability_of_loss*100).toFixed(2)}%`;
  Plotly.newPlot("mcChart",[{x:["P01","P05","P25","P50","P75","P95","P99"],y:[d.p01,d.p05,d.p25,d.p50,d.p75,d.p95,d.p99],type:"bar"}],chartLayout("Percentile","Terminal Value"),{displayModeBar:false,responsive:true});
}
async function runRegime(){
  const d=await post("/api/regime",{returns:parseReturns(),confidence:.95,risk_free_rate:.03});
  document.getElementById("regimeBox").innerHTML=`<span>Detected market state</span><strong>${d.regime.toUpperCase()}</strong><small>Score ${d.score.toFixed(2)} · Confidence ${(d.confidence*100).toFixed(0)}% · Vol ${(d.annualized_volatility*100).toFixed(1)}%</small>`;
}
async function runVolatility(){
  const d=await post("/api/volatility/ewma",{returns:parseReturns(),lambda_:.94});
  Plotly.newPlot("volChart",[{y:d.volatility_series,mode:"lines",name:"EWMA"}],chartLayout("Observation","Annualized Volatility"),{displayModeBar:false,responsive:true});
}
async function runML(){
  const d=await post("/api/ml/direction",{returns:parseReturns(),lookback:5});
  document.getElementById("mlOut").textContent=`Samples: ${d.samples}\nHoldout accuracy: ${(d.accuracy*100).toFixed(2)}%\nLatest P(up): ${(d.latest_probability_up*100).toFixed(2)}%\nCoefficients: ${d.coefficients.map(x=>x.toFixed(3)).join(", ")}`;
}
async function runFactors(){
  const r=parseReturns();
  const asset=r.slice(0,Math.min(r.length,30));
  const factors=asset.map((_,i)=>[
    Math.sin(i/4)*.006 + .001,
    Math.cos(i/6)*.004,
    ((i%5)-2)*.0015
  ]);
  const d=await post("/api/factors",{asset_returns:asset,factors});
  document.getElementById("factorOut").textContent=`Alpha: ${fmt(d.alpha)}\nFactor betas: ${d.factor_betas.map(x=>x.toFixed(4)).join(" | ")}\nR²: ${d.r_squared.toFixed(4)}\nResidual vol: ${d.residual_volatility.toFixed(4)}`;
}

runRisk();priceOption();runPortfolio();runStress();runBacktest();runWalkForward();runMonte();runRegime();runVolatility();runML();runFactors();
