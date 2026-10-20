"""HTML Dashboard and CSV exporter for enriched option yield screening results."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import pandas as pd


def export_to_csv(df: pd.DataFrame, output_path: str | Path) -> Path:
    """Save the screening DataFrame to a clean CSV file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" style="color-scheme: dark;">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="color-scheme" content="dark" />
  <title>NASDAQ-100 &amp; STOXX 50 Options Edge Dashboard</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b1120;
      --panel: #151f32;
      --border: #26354d;
      --text: #f8fafc;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --green: #4ade80;
      --amber: #fbbf24;
      --red: #f87171;
      --purple: #c084fc;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 1.5rem 1.75rem;
      line-height: 1.45;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      flex-wrap: wrap;
      gap: 1rem;
      margin-bottom: 1.25rem;
      border-bottom: 1px solid var(--border);
      padding-bottom: 0.9rem;
    }
    .header h1 { font-size: 1.5rem; font-weight: 700; color: var(--text); }
    .header p { color: var(--muted); font-size: 0.84rem; margin-top: 0.25rem; }
    .dte-bar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      background: linear-gradient(90deg, #151f32 0%, #1a2740 100%);
      border: 1px solid var(--border);
      border-radius: 0.75rem;
      padding: 0.85rem 1.15rem;
      margin-bottom: 1.15rem;
    }
    .dte-group {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-wrap: wrap;
    }
    .dte-label {
      font-size: 0.78rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--accent);
      margin-right: 0.35rem;
    }
    .dte-btn, .otm-btn {
      background: var(--bg);
      color: var(--muted);
      border: 1px solid var(--border);
      padding: 0.42rem 0.85rem;
      border-radius: 0.5rem;
      font-size: 0.82rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .dte-btn:hover, .otm-btn:hover {
      color: var(--text);
      border-color: var(--accent);
    }
    .dte-btn.active {
      background: #0284c7;
      color: #ffffff;
      border-color: #38bdf8;
      box-shadow: 0 0 12px #0284c766;
    }
    .otm-btn.active {
      background: #7e22ce;
      color: #ffffff;
      border-color: #c084fc;
      box-shadow: 0 0 12px #7e22ce66;
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
      gap: 0.85rem;
      margin-bottom: 1.15rem;
    }
    .kpi-card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 0.75rem;
      padding: 0.95rem 1.15rem;
    }
    .kpi-label { font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); }
    .kpi-value { font-size: 1.45rem; font-weight: 700; margin-top: 0.2rem; }
    .kpi-sub { font-size: 0.74rem; color: var(--muted); margin-top: 0.15rem; }
    .controls {
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
      margin-bottom: 1rem;
      align-items: center;
      background: var(--panel);
      padding: 0.8rem 1rem;
      border-radius: 0.75rem;
      border: 1px solid var(--border);
    }
    .controls input, .controls select {
      background: var(--bg);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 0.48rem 0.75rem;
      border-radius: 0.5rem;
      font-size: 0.84rem;
    }
    .controls label {
      display: flex;
      align-items: center;
      gap: 0.4rem;
      font-size: 0.84rem;
      color: var(--muted);
      cursor: pointer;
    }
    .table-wrap {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 0.75rem;
      overflow-x: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.81rem;
      text-align: right;
    }
    th, td {
      padding: 0.62rem 0.72rem;
      border-bottom: 1px solid var(--border);
      white-space: nowrap;
    }
    th {
      background: #0f172a90;
      color: var(--muted);
      font-weight: 600;
      cursor: pointer;
      user-select: none;
      font-size: 0.74rem;
      text-transform: uppercase;
    }
    th:hover { color: var(--accent); }
    th:first-child, td:first-child,
    th:nth-child(2), td:nth-child(2),
    th:nth-child(3), td:nth-child(3) {
      text-align: left;
    }
    tr:hover td { background: #26354d45; }
    .ticker-link {
      color: var(--accent);
      font-weight: 700;
      text-decoration: none;
      border-bottom: 1px dashed #38bdf866;
      padding-bottom: 1px;
      transition: all 0.15s ease;
    }
    .ticker-link:hover {
      color: #7dd3fc;
      border-bottom-style: solid;
      border-bottom-color: #7dd3fc;
    }
    .badge {
      display: inline-block;
      padding: 0.15rem 0.45rem;
      border-radius: 999px;
      font-size: 0.71rem;
      font-weight: 600;
    }
    .badge-us { background: #0284c733; color: #38bdf8; border: 1px solid #0284c7; }
    .badge-eu { background: #7e22ce33; color: #c084fc; border: 1px solid #7e22ce; }
    .sig-csp { background: #16a34a33; color: #4ade80; border: 1px solid #16a34a; }
    .sig-cc { background: #d9770633; color: #fbbf24; border: 1px solid #d97706; }
    .sig-warn { background: #dc262633; color: #f87171; border: 1px solid #dc2626; }
    .sig-neutral { background: #33415555; color: #cbd5e1; border: 1px solid #475569; }
    .pos { color: var(--green); font-weight: 600; }
    .neg { color: var(--red); }
    .warn { color: var(--amber); font-weight: 600; }
    .formula-box {
      margin-top: 1.25rem;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 0.75rem;
      padding: 1rem 1.25rem;
      font-size: 0.8rem;
      color: var(--muted);
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 0.75rem;
    }
    .formula-box strong { color: var(--text); }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>NASDAQ-100 &amp; STOXX Europe 50 Options Quantitative Edge Dashboard</h1>
      <p id="subHeader">5-Pillar Institutional Screener &bull; Active Horizon: 30 Days (Monthly) &bull; Target Strike: 5.0% OTM</p>
    </div>
    <div style="color: var(--muted); font-size: 0.8rem;">
      Generated: __GENERATED_AT__
    </div>
  </div>

  <!-- Interactive Option Horizon (DTE) & Strike OTM Selector Bar -->
  <div class="dte-bar">
    <div class="dte-group">
      <span class="dte-label">&#9201; Option Expiration Horizon:</span>
      <button class="dte-btn" data-dte="7">7 Days (Weekly)</button>
      <button class="dte-btn" data-dte="14">14 Days (2-Wk)</button>
      <button class="dte-btn active" data-dte="30">30 Days (Monthly)</button>
      <button class="dte-btn" data-dte="90">90 Days (Quarterly)</button>
      <button class="dte-btn" data-dte="180">180 Days (6-Mo)</button>
      <button class="dte-btn" data-dte="360">360 Days (1-Yr LEAPS)</button>
    </div>
    <div class="dte-group">
      <span class="dte-label" style="color: var(--purple);">&#127919; Strike Cushion (% OTM):</span>
      <button class="otm-btn" data-otm="0.025">2.5% OTM</button>
      <button class="otm-btn active" data-otm="0.05">5.0% OTM</button>
      <button class="otm-btn" data-otm="0.075">7.5% OTM</button>
      <button class="otm-btn" data-otm="0.10">10.0% OTM</button>
    </div>
  </div>

  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-label">Screened Stocks (P/E &gt; 0)</div>
      <div class="kpi-value" id="kpiCount">__TOTAL_COUNT__</div>
      <div class="kpi-sub">__US_COUNT__ US / __EU_COUNT__ Europe &amp; Global</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Avg Volatility Risk Prem</div>
      <div class="kpi-value" id="kpiVrp" style="color: var(--accent);">__AVG_VRP__%</div>
      <div class="kpi-sub">Implied Vol minus 30d Realized HV</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label" id="kpiCspLabel">Avg CSP Ann. Yield (30d)</div>
      <div class="kpi-value" id="kpiCsp" style="color: var(--green);">__AVG_CSP__%</div>
      <div class="kpi-sub" id="kpiCspSub">With Black-Scholes PoP &amp; &Delta;</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label" id="kpiCcLabel">Avg CC + Div Yield (30d)</div>
      <div class="kpi-value" id="kpiCc" style="color: var(--amber);">__AVG_CC__%</div>
      <div class="kpi-sub">Covered Call + Annual Dividend</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Earnings-Safe in Window</div>
      <div class="kpi-value" id="kpiSafe" style="color: var(--purple);">__SAFE_COUNT__</div>
      <div class="kpi-sub" id="kpiSafeSub">No earnings before selected expiry</div>
    </div>
  </div>

  <div class="controls">
    <input type="text" id="searchInput" placeholder="Search symbol, company, signal..." />
    <select id="indexFilter">
      <option value="ALL">All Indexes (NASDAQ-100 + STOXX 50 + Mega-Caps + Custom)</option>
      <option value="NASDAQ-100">NASDAQ-100 Only</option>
      <option value="STOXX-50 / EU">STOXX 50 / Europe Only</option>
      <option value="US Mega-Cap">S&amp;P 100 Non-NASDAQ Titans</option>
      <option value="Custom / Global">Custom / Global (BABA, SK Hynix, EWY)</option>
    </select>
    <select id="regionFilter">
      <option value="ALL">All Regions</option>
      <option value="US">United States (US)</option>
      <option value="EU">Europe (EU)</option>
      <option value="GLOBAL">Asia / Global</option>
    </select>
    <select id="maxPeFilter">
      <option value="9999">Any P/E &gt; 0</option>
      <option value="45">P/E &le; 45x</option>
      <option value="30">P/E &le; 30x (GARP)</option>
      <option value="20">P/E &le; 20x (Value)</option>
    </select>
    <select id="linkMode" title="Choose how ticker links open">
      <option value="GF_QUOTE">Ticker Link: Google Finance Quote</option>
      <option value="GF_DARK">Ticker Link: Google Finance (Forced Dark View)</option>
    </select>
    <label>
      <input type="checkbox" id="hideEarnings" />
      Exclude Earnings in Window
    </label>
    <label>
      <input type="checkbox" id="posVrpOnly" />
      Positive VRP Only (IV &gt; HV30)
    </label>
  </div>

  <div class="table-wrap">
    <table id="screenerTable">
      <thead>
        <tr>
          <th data-key="symbol">Ticker (Google Finance &#8599;)</th>
          <th data-key="index_group">Index</th>
          <th data-key="strategy_signal">Action Signal</th>
          <th data-key="edge_score">Edge Score</th>
          <th data-key="spot_price">Spot ($)</th>
          <th data-key="trailing_pe">P/E (Fwd)</th>
          <th data-key="fcf_yield_pct">FCF Yld</th>
          <th data-key="dividend_yield_pct">Div Yld</th>
          <th data-key="rsi_14">RSI(14)</th>
          <th data-key="hv_30d_pct">HV30</th>
          <th data-key="csp_iv_pct">Opt IV</th>
          <th data-key="vrp_pct">VRP (IV-HV)</th>
          <th data-key="earnings_date">Next Earnings</th>
          <th data-key="csp_strike">CSP Strike (&Delta;)</th>
          <th data-key="csp_premium">CSP Prem ($)</th>
          <th data-key="csp_pop_pct">CSP PoP</th>
          <th data-key="csp_annualized_yield_pct">CSP Ann. Yld</th>
          <th data-key="cc_strike">CC Strike (&Delta;)</th>
          <th data-key="cc_premium">CC Prem ($)</th>
          <th data-key="cc_pop_pct">CC PoP</th>
          <th data-key="cc_total_income_yield_pct">CC+Div Yld</th>
        </tr>
      </thead>
      <tbody id="tableBody"></tbody>
    </table>
  </div>

  <div class="formula-box">
    <div>
      <strong>1. Dynamic Option Horizon (7d / 14d / 30d / 90d / 180d / 360d):</strong><br/>
      Switching DTE buttons recalculates option premiums, Black-Scholes &Delta;, PoP, annualized yields, and checks if <code>Next Earnings</code> falls inside your selected DTE window.
    </div>
    <div>
      <strong>2. Volatility Edge (VRP):</strong><br/>
      <code>VRP = Implied Vol (IV) - 30d Realized Vol (HV30)</code>. Positive VRP means option premiums are overpriced relative to actual historical stock movement.
    </div>
    <div>
      <strong>3. Black-Scholes Greeks (&Delta; &amp; PoP):</strong><br/>
      <code>PoP = N(d2)</code> for CSPs (probability stock stays above strike at expiry). Higher Edge Score = Higher reward relative to risk.
    </div>
  </div>

  <script>
    const baseData = __RECORDS_JSON__;
    let selectedDte = 30;
    let selectedOtm = 0.05;
    let sortKey = "edge_score";
    let sortAsc = false;
    const RISK_FREE = 0.042;

    // Standard Normal CDF (Abramowitz & Stegun approximation, accurate to 1e-7)
    function normCdf(x) {
      const a1 =  0.254829592, a2 = -0.284496736, a3 =  1.421413741;
      const a4 = -1.453152027, a5 =  1.061405429, p  =  0.3275911;
      const sign = x < 0 ? -1 : 1;
      const absX = Math.abs(x) / Math.sqrt(2.0);
      const t = 1.0 / (1.0 + p * absX);
      const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-absX * absX);
      return 0.5 * (1.0 + sign * y);
    }

    function bsPriceAndGreeks(spot, strike, tYears, iv, rate, divYield, isCall) {
      if (tYears <= 0 || iv <= 0 || spot <= 0 || strike <= 0) {
        return { price: 0, delta: 0, pop: 50 };
      }
      const sqrtT = Math.sqrt(tYears);
      const d1 = (Math.log(spot / strike) + (rate - divYield + 0.5 * iv * iv) * tYears) / (iv * sqrtT);
      const d2 = d1 - iv * sqrtT;
      const discQ = Math.exp(-divYield * tYears);
      const discR = Math.exp(-rate * tYears);

      if (isCall) {
        const price = spot * discQ * normCdf(d1) - strike * discR * normCdf(d2);
        const delta = discQ * normCdf(d1);
        const pop = normCdf(-d2) * 100.0;
        return { price: Math.max(0.01, price), delta, pop };
      } else {
        const price = strike * discR * normCdf(-d2) - spot * discQ * normCdf(-d1);
        const delta = discQ * (normCdf(d1) - 1.0);
        const pop = normCdf(d2) * 100.0;
        return { price: Math.max(0.01, price), delta, pop };
      }
    }

    function roundStrike(rawStrike, spot) {
      if (spot >= 500) return Math.round(rawStrike / 5) * 5;
      if (spot >= 100) return Math.round(rawStrike / 2.5) * 2.5;
      if (spot >= 25) return Math.round(rawStrike);
      return Math.round(rawStrike * 2) / 2;
    }

    // Recompute a row dynamically for the chosen DTE (7, 14, 30, 90, 180, 360) and OTM %
    function computeRowForHorizon(r) {
      const today = new Date("2026-10-20T00:00:00Z");
      const targetExp = new Date(today.getTime() + selectedDte * 86400000);

      let earnInWindow = false;
      if (r.earnings_date) {
        const earnDt = new Date(r.earnings_date + "T00:00:00Z");
        earnInWindow = (earnDt >= today && earnDt <= targetExp);
      }

      // If exact baseline 30d & 5% OTM, preserve exact exchange strikes/premiums
      if (selectedDte === 30 && Math.abs(selectedOtm - 0.05) < 0.001) {
        return { ...r, earnings_before_expiry: earnInWindow };
      }

      const spot = r.spot_price;
      const tYears = selectedDte / 365.0;
      const divDec = (r.dividend_yield_pct || 0) / 100.0;

      // Volatility term structure: short-dated options have slightly higher event vol if earnings in window,
      // longer-dated options (90-360d) mean-revert toward long-term realized volatility (HV30)
      const basePutIv = (r.csp_iv_pct || 25) / 100.0;
      const baseCallIv = (r.cc_iv_pct || basePutIv * 100) / 100.0;
      const hvDec = (r.hv_30d_pct || 22) / 100.0;

      const weightBase = Math.min(1.0, Math.pow(30.0 / Math.max(selectedDte, 7), 0.18));
      const putIv = Math.max(0.08, weightBase * basePutIv + (1.0 - weightBase) * hvDec);
      const callIv = Math.max(0.08, weightBase * baseCallIv + (1.0 - weightBase) * hvDec);

      const cspStrike = roundStrike(spot * (1.0 - selectedOtm), spot);
      const ccStrike = roundStrike(spot * (1.0 + selectedOtm), spot);

      const putRes = bsPriceAndGreeks(spot, cspStrike, tYears, putIv, RISK_FREE, divDec, false);
      const callRes = bsPriceAndGreeks(spot, ccStrike, tYears, callIv, RISK_FREE, divDec, true);

      const cspRawYld = (putRes.price / cspStrike) * 100.0;
      const cspAnnYld = cspRawYld * (365.0 / selectedDte);

      const ccRawYld = (callRes.price / spot) * 100.0;
      const ccAnnYld = ccRawYld * (365.0 / selectedDte);
      const ccTotalYld = ccAnnYld + (r.dividend_yield_pct || 0);

      const putIvPct = putIv * 100.0;
      const vrpPct = 0.5 * (putIvPct + callIv * 100.0) - r.hv_30d_pct;

      // Recompute Edge Score & Action Signal for this horizon
      const yieldComp = Math.min(40.0, cspAnnYld * 0.85);
      const popComp = Math.max(0.0, (putRes.pop - 50.0) * 0.6);
      const vrpComp = Math.max(-10.0, Math.min(20.0, vrpPct * 1.2));
      let fundComp = 0.0;
      if (r.trailing_pe > 0 && r.trailing_pe <= 35.0) fundComp += 10.0;
      else if (r.trailing_pe <= 50.0) fundComp += 5.0;
      if (r.fcf_yield_pct !== null && r.fcf_yield_pct >= 3.0) fundComp += 8.0;
      const eventPen = earnInWindow ? -15.0 : 5.0;
      const edgeScore = Math.max(1.0, Math.min(99.0, yieldComp + popComp + vrpComp + fundComp + eventPen));

      let signal = "NEUTRAL / THETA HOLD";
      if (earnInWindow) signal = "CAUTION: EARNINGS IN WINDOW";
      else if (r.rsi_14 <= 40.0 && vrpPct >= 0) signal = "STRONG CSP (Pullback + Rich IV)";
      else if (r.rsi_14 >= 65.0 && ccAnnYld >= 15.0) signal = "STRONG CC (Overbought Rally)";
      else if (vrpPct >= 5.0 && cspAnnYld >= 18.0) signal = "HIGH VRP EDGE (Overpriced IV)";
      else if (r.trailing_pe <= 28.0 && cspAnnYld >= 15.0) signal = "QUALITY WHEEL CORE";

      return {
        ...r,
        dte: selectedDte,
        earnings_before_expiry: earnInWindow,
        csp_strike: cspStrike,
        csp_premium: putRes.price,
        csp_iv_pct: putIvPct,
        csp_delta: putRes.delta,
        csp_pop_pct: putRes.pop,
        csp_annualized_yield_pct: cspAnnYld,
        cc_strike: ccStrike,
        cc_premium: callRes.price,
        cc_delta: callRes.delta,
        cc_pop_pct: callRes.pop,
        cc_annualized_yield_pct: ccAnnYld,
        cc_total_income_yield_pct: ccTotalYld,
        vrp_pct: vrpPct,
        edge_score: edgeScore,
        strategy_signal: signal
      };
    }

    const tbody = document.getElementById("tableBody");
    const searchInput = document.getElementById("searchInput");
    const indexFilter = document.getElementById("indexFilter");
    const regionFilter = document.getElementById("regionFilter");
    const maxPeFilter = document.getElementById("maxPeFilter");
    const linkMode = document.getElementById("linkMode");
    const hideEarnings = document.getElementById("hideEarnings");
    const posVrpOnly = document.getElementById("posVrpOnly");

    function getGoogleFinanceUrl(row) {
      const code = row.google_finance_code || `${row.symbol}:NASDAQ`;
      if (linkMode && linkMode.value === "GF_DARK") {
        const parts = code.split(":");
        const query = parts.length === 2 ? `${parts[1]}:${parts[0]} stock` : `${row.symbol} stock`;
        return `https://www.google.com/search?q=${encodeURIComponent(query)}&cs=1`;
      }
      return `https://www.google.com/finance/quote/${encodeURIComponent(code)}?cs=1`;
    }

    function badgeClassForSignal(sig) {
      if (sig.includes("CAUTION")) return "sig-warn";
      if (sig.includes("CSP") || sig.includes("VRP") || sig.includes("WHEEL")) return "sig-csp";
      if (sig.includes("CC")) return "sig-cc";
      return "sig-neutral";
    }

    function fmtOpt(val, suffix = "%") {
      return val !== null && val !== undefined ? val.toFixed(1) + suffix : "N/A";
    }

    function renderTable() {
      const query = searchInput.value.toLowerCase();
      const idxGroup = indexFilter.value;
      const region = regionFilter.value;
      const maxPe = parseFloat(maxPeFilter.value);
      const noEarn = hideEarnings.checked;
      const vrpPos = posVrpOnly.checked;

      document.getElementById("subHeader").innerHTML =
        `5-Pillar Institutional Screener &bull; Active Horizon: <strong>${selectedDte} Days</strong> &bull; Target Strike: <strong>${(selectedOtm * 100).toFixed(1)}% OTM</strong>`;
      document.getElementById("kpiCspLabel").textContent = `Avg CSP Ann. Yield (${selectedDte}d)`;
      document.getElementById("kpiCcLabel").textContent = `Avg CC + Div Yield (${selectedDte}d)`;

      const horizonData = baseData.map(computeRowForHorizon);

      const filtered = horizonData.filter(r => {
        const matchesIndex = idxGroup === "ALL" || r.index_group === idxGroup;
        const matchesRegion = region === "ALL" || r.region === region;
        const matchesPe = r.trailing_pe <= maxPe;
        const matchesEarn = !noEarn || !r.earnings_before_expiry;
        const matchesVrp = !vrpPos || r.vrp_pct > 0;
        const matchesQuery =
          r.symbol.toLowerCase().includes(query) ||
          (r.name && r.name.toLowerCase().includes(query)) ||
          r.strategy_signal.toLowerCase().includes(query) ||
          (r.country && r.country.toLowerCase().includes(query));
        return matchesIndex && matchesRegion && matchesPe && matchesEarn && matchesVrp && matchesQuery;
      });

      filtered.sort((a, b) => {
        const va = a[sortKey] ?? -9999;
        const vb = b[sortKey] ?? -9999;
        if (typeof va === "string") {
          return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
        }
        return sortAsc ? va - vb : vb - va;
      });

      document.getElementById("kpiCount").textContent = filtered.length;
      if (filtered.length > 0) {
        const avgVrp = filtered.reduce((s, r) => s + r.vrp_pct, 0) / filtered.length;
        const avgCsp = filtered.reduce((s, r) => s + r.csp_annualized_yield_pct, 0) / filtered.length;
        const avgCc = filtered.reduce((s, r) => s + r.cc_total_income_yield_pct, 0) / filtered.length;
        const safeCnt = filtered.filter(r => !r.earnings_before_expiry).length;
        document.getElementById("kpiVrp").textContent = (avgVrp >= 0 ? "+" : "") + avgVrp.toFixed(1) + "%";
        document.getElementById("kpiCsp").textContent = avgCsp.toFixed(2) + "%";
        document.getElementById("kpiCc").textContent = avgCc.toFixed(2) + "%";
        document.getElementById("kpiSafe").textContent = safeCnt + " / " + filtered.length;
      }

      tbody.innerHTML = filtered.map(r => {
        const vrpCls = r.vrp_pct >= 0 ? "pos" : "neg";
        const rsiCls = r.rsi_14 <= 38 ? "pos" : (r.rsi_14 >= 65 ? "warn" : "");
        const earnText = r.earnings_date
          ? (r.earnings_before_expiry ? `<span class="neg">&#9888; ${r.earnings_date}</span>` : `<span style="color:var(--muted)">${r.earnings_date}</span>`)
          : `<span style="color:var(--muted)">None</span>`;
        const fwdPeStr = r.forward_pe ? ` <span style="color:var(--muted);font-size:0.72rem;">(${r.forward_pe.toFixed(1)}x)</span>` : "";
        const gfUrl = getGoogleFinanceUrl(r);

        return `
        <tr>
          <td>
            <a href="${gfUrl}" target="_blank" rel="noopener noreferrer" class="ticker-link" title="View ${r.symbol} on Google Finance">
              ${r.symbol} &#8599;
            </a>
            <span style="color:var(--muted);font-size:0.72rem;margin-left:0.25rem;">${(r.name || "").slice(0, 14)}</span>
          </td>
          <td><span class="badge ${r.region === 'US' ? 'badge-us' : 'badge-eu'}">${r.index_group || r.region}</span></td>
          <td><span class="badge ${badgeClassForSignal(r.strategy_signal)}">${r.strategy_signal}</span></td>
          <td><strong>${r.edge_score.toFixed(1)}</strong></td>
          <td>$${r.spot_price.toFixed(2)}</td>
          <td>${r.trailing_pe.toFixed(1)}x${fwdPeStr}</td>
          <td>${fmtOpt(r.fcf_yield_pct)}</td>
          <td>${r.dividend_yield_pct.toFixed(2)}%</td>
          <td class="${rsiCls}">${r.rsi_14.toFixed(1)}</td>
          <td>${r.hv_30d_pct.toFixed(1)}%</td>
          <td>${r.csp_iv_pct.toFixed(1)}%</td>
          <td class="${vrpCls}">${r.vrp_pct >= 0 ? '+' : ''}${r.vrp_pct.toFixed(1)}%</td>
          <td>${earnText}</td>
          <td>$${r.csp_strike.toFixed(1)} <span style="color:var(--muted);font-size:0.72rem;">(${r.csp_delta.toFixed(2)}&Delta;)</span></td>
          <td>$${r.csp_premium.toFixed(2)}</td>
          <td>${r.csp_pop_pct.toFixed(0)}%</td>
          <td class="pos">${r.csp_annualized_yield_pct.toFixed(2)}%</td>
          <td>$${r.cc_strike.toFixed(1)} <span style="color:var(--muted);font-size:0.72rem;">(${r.cc_delta.toFixed(2)}&Delta;)</span></td>
          <td>$${r.cc_premium.toFixed(2)}</td>
          <td>${r.cc_pop_pct.toFixed(0)}%</td>
          <td class="warn">${r.cc_total_income_yield_pct.toFixed(2)}%</td>
        </tr>
      `}).join("");
    }

    document.querySelectorAll(".dte-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".dte-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        selectedDte = parseInt(btn.getAttribute("data-dte"), 10);
        renderTable();
      });
    });

    document.querySelectorAll(".otm-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".otm-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        selectedOtm = parseFloat(btn.getAttribute("data-otm"));
        renderTable();
      });
    });

    document.querySelectorAll("th[data-key]").forEach(th => {
      th.addEventListener("click", () => {
        const key = th.getAttribute("data-key");
        if (sortKey === key) {
          sortAsc = !sortAsc;
        } else {
          sortKey = key;
          sortAsc = false;
        }
        renderTable();
      });
    });

    searchInput.addEventListener("input", renderTable);
    indexFilter.addEventListener("change", renderTable);
    regionFilter.addEventListener("change", renderTable);
    maxPeFilter.addEventListener("change", renderTable);
    linkMode.addEventListener("change", renderTable);
    hideEarnings.addEventListener("change", renderTable);
    posVrpOnly.addEventListener("change", renderTable);
    renderTable();
  </script>
</body>
</html>
"""


def generate_html_dashboard(
    df: pd.DataFrame,
    output_path: str | Path,
    target_dte: int = 30,
    target_otm_pct: float = 0.05,
) -> Path:
    """Generate a self-contained, interactive HTML dashboard with all 5 quantitative pillars."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    clean_df = df.where(pd.notnull(df), None)
    records = clean_df.to_dict(orient="records") if not df.empty else []
    records_json = json.dumps(records)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    avg_vrp = round(float(df["vrp_pct"].mean()), 1) if not df.empty else 0.0
    avg_csp = round(float(df["csp_annualized_yield_pct"].mean()), 2) if not df.empty else 0.0
    avg_cc = round(float(df["cc_total_income_yield_pct"].mean()), 2) if not df.empty else 0.0
    us_count = int((df["region"] == "US").sum()) if not df.empty else 0
    eu_count = int((df["region"] != "US").sum()) if not df.empty else 0
    safe_count = int((~df["earnings_before_expiry"]).sum()) if not df.empty else 0

    html = (
        HTML_TEMPLATE.replace("__GENERATED_AT__", generated_at)
        .replace("__TOTAL_COUNT__", str(len(records)))
        .replace("__US_COUNT__", str(us_count))
        .replace("__EU_COUNT__", str(eu_count))
        .replace("__AVG_VRP__", f"{avg_vrp:+.1f}")
        .replace("__AVG_CSP__", str(avg_csp))
        .replace("__AVG_CC__", str(avg_cc))
        .replace("__SAFE_COUNT__", f"{safe_count} / {len(records)}")
        .replace("__RECORDS_JSON__", records_json)
    )
    path.write_text(html, encoding="utf-8")
    index_copy = path.parent / "index.html"
    if index_copy != path:
        index_copy.write_text(html, encoding="utf-8")
    return path
