"""Core logic for fetching fundamentals, technicals, volatility edge, Greeks, and option yields."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import logging
import math
from typing import List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

from screener.universe import StockTicker

logger = logging.getLogger(__name__)

RISK_FREE_RATE = 0.042  # 4.2% annualized US Treasury benchmark


@dataclass
class OptionYieldResult:
    # Identity
    symbol: str
    name: str
    region: str
    country: str
    index_group: str
    google_finance_code: str
    spot_price: float
    market_cap_b: float

    # 1. Fundamental Quality (Beyond P/E > 0)
    trailing_pe: float
    forward_pe: Optional[float]
    peg_ratio: Optional[float]
    fcf_yield_pct: Optional[float]
    operating_margin_pct: Optional[float]
    analyst_upside_pct: Optional[float]
    dividend_yield_pct: float

    # 2. Technical Regime (RSI-14 & 200-DMA)
    rsi_14: float
    sma200: float
    sma200_dist_pct: float
    tech_regime: str

    # 3. Volatility Edge (HV30, IV, VRP, Vol Rank)
    hv_30d_pct: float
    vol_rank_52w_pct: float
    vrp_pct: float

    # 4. Event Risk Protection
    expiration: str
    dte: int
    earnings_date: Optional[str]
    earnings_before_expiry: bool

    # 5. Cash-Secured Put (CSP) Metrics + Greeks & Liquidity
    csp_strike: float
    csp_otm_pct: float
    csp_premium: float
    csp_iv_pct: float
    csp_delta: float
    csp_pop_pct: float
    csp_spread_pct: float
    csp_open_interest: int
    csp_raw_yield_pct: float
    csp_annualized_yield_pct: float

    # 6. Covered Call (CC) Metrics + Greeks & Liquidity
    cc_strike: float
    cc_otm_pct: float
    cc_premium: float
    cc_iv_pct: float
    cc_delta: float
    cc_pop_pct: float
    cc_spread_pct: float
    cc_open_interest: int
    cc_raw_yield_pct: float
    cc_annualized_yield_pct: float
    cc_total_income_yield_pct: float
    cc_annualized_if_called_pct: float

    # Synthesis & Edge Score
    edge_score: float
    strategy_signal: str

    def to_dict(self) -> dict:
        return asdict(self)


def _resolve_google_finance_code(symbol: str, info: dict) -> str:
    """Resolve `SYMBOL:EXCHANGE` for Google Finance URLs from Yahoo Finance exchange metadata."""
    if symbol.endswith(".KS"):
        return f"{symbol[:-3]}:KRX"
    clean_sym = symbol.replace("-", ".")
    exch_raw = str(info.get("exchange") or "").upper()
    if exch_raw in ("NMS", "NGM", "NCM", "NAS", "NASDAQ"):
        exch = "NASDAQ"
    elif exch_raw in ("PCX", "ASE", "BTS", "NYSEARCA"):
        exch = "NYSEARCA"
    elif exch_raw in ("NYQ", "NYS", "NYSE"):
        exch = "NYSE"
    else:
        exch = "NASDAQ"
    return f"{clean_sym}:{exch}"


# ---------------------------------------------------------------------------
# Black-Scholes Option Pricing, Implied Volatility & Greeks Solver
# ---------------------------------------------------------------------------

def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(
    spot: float,
    strike: float,
    t_years: float,
    iv: float,
    rate: float = RISK_FREE_RATE,
    div_yield: float = 0.0,
    option_type: str = "put",
) -> float:
    """Compute Black-Scholes-Merton European option price."""
    if t_years <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
        if option_type == "call":
            return max(0.0, spot - strike)
        return max(0.0, strike - spot)

    sqrt_t = math.sqrt(t_years)
    d1 = (math.log(spot / strike) + (rate - div_yield + 0.5 * iv * iv) * t_years) / (iv * sqrt_t)
    d2 = d1 - iv * sqrt_t

    disc_q = math.exp(-div_yield * t_years)
    disc_r = math.exp(-rate * t_years)

    if option_type == "call":
        return spot * disc_q * _norm_cdf(d1) - strike * disc_r * _norm_cdf(d2)
    else:
        return strike * disc_r * _norm_cdf(-d2) - spot * disc_q * _norm_cdf(-d1)


def solve_implied_volatility(
    market_price: float,
    spot: float,
    strike: float,
    t_years: float,
    rate: float = RISK_FREE_RATE,
    div_yield: float = 0.0,
    option_type: str = "put",
    fallback_iv: float = 0.25,
) -> float:
    """Invert Black-Scholes via bisection to find true Implied Volatility from option premium."""
    if market_price <= 0 or spot <= 0 or strike <= 0 or t_years <= 0:
        return fallback_iv

    intrinsic = max(0.0, (spot - strike) if option_type == "call" else (strike - spot))
    if market_price <= intrinsic:
        return max(0.05, fallback_iv)

    low, high = 0.03, 3.00
    for _ in range(40):
        mid = 0.5 * (low + high)
        price = bs_price(spot, strike, t_years, mid, rate, div_yield, option_type)
        if abs(price - market_price) < 1e-4:
            return mid
        if price > market_price:
            high = mid
        else:
            low = mid
    solved = 0.5 * (low + high)
    return solved if 0.04 <= solved <= 2.95 else fallback_iv


def compute_option_greeks(
    spot: float,
    strike: float,
    t_years: float,
    iv: float,
    rate: float = RISK_FREE_RATE,
    div_yield: float = 0.0,
    option_type: str = "put",
) -> tuple[float, float]:
    """
    Return (Delta, Probability_of_Profit_Pct).
    - For a short Put (CSP): Delta is negative [-1, 0], PoP = N(d2) * 100 (prob S_T > K).
    - For a short Call (CC): Delta is positive [0, 1], PoP = N(-d2) * 100 (prob S_T < K).
    """
    if t_years <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
        return (0.0, 50.0)

    sqrt_t = math.sqrt(t_years)
    d1 = (math.log(spot / strike) + (rate - div_yield + 0.5 * iv * iv) * t_years) / (iv * sqrt_t)
    d2 = d1 - iv * sqrt_t
    disc_q = math.exp(-div_yield * t_years)

    if option_type == "call":
        delta = disc_q * _norm_cdf(d1)
        pop_pct = _norm_cdf(-d2) * 100.0
    else:
        delta = disc_q * (_norm_cdf(d1) - 1.0)
        pop_pct = _norm_cdf(d2) * 100.0

    return round(delta, 3), round(pop_pct, 1)


# ---------------------------------------------------------------------------
# Technicals & Realized Volatility Engine
# ---------------------------------------------------------------------------

def compute_technicals_and_hv(hist_df: pd.DataFrame) -> dict:
    """
    Compute 14-day RSI, 200-day SMA, 30-day Realized Volatility (HV30),
    and 52-Week Volatility Percentile Rank from 1-year daily close prices.
    """
    default_out = {
        "rsi_14": 50.0,
        "sma200": 0.0,
        "sma200_dist_pct": 0.0,
        "tech_regime": "NEUTRAL",
        "hv_30d_pct": 22.0,
        "vol_rank_52w_pct": 50.0,
    }
    if hist_df is None or hist_df.empty or "Close" not in hist_df.columns:
        return default_out

    closes = hist_df["Close"].dropna()
    if len(closes) < 30:
        return default_out

    spot = float(closes.iloc[-1])

    # 1. 200-Day SMA
    sma200 = float(closes.tail(200).mean())
    sma200_dist_pct = ((spot - sma200) / sma200) * 100.0 if sma200 > 0 else 0.0

    # 2. 14-Day RSI (Wilder's smoothing)
    delta = closes.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / 14.0, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / 14.0, min_periods=14, adjust=False).mean()
    last_gain = float(avg_gain.iloc[-1])
    last_loss = float(avg_loss.iloc[-1])
    if last_loss == 0:
        rsi_14 = 100.0
    else:
        rs = last_gain / last_loss
        rsi_14 = 100.0 - (100.0 / (1.0 + rs))

    if rsi_14 <= 38.0:
        tech_regime = "OVERSOLD (CSP Edge)"
    elif rsi_14 >= 65.0:
        tech_regime = "OVERBOUGHT (CC Edge)"
    else:
        tech_regime = "NEUTRAL"

    # 3. 30-Day Realized Volatility (21 trading days) & 52-Week Rolling Volatility Rank
    log_returns = np.log(closes / closes.shift(1)).dropna()
    rolling_hv = log_returns.rolling(window=21).std() * math.sqrt(252.0) * 100.0
    rolling_hv = rolling_hv.dropna()

    if rolling_hv.empty:
        hv_30d_pct = 22.0
        vol_rank_52w_pct = 50.0
    else:
        hv_30d_pct = float(rolling_hv.iloc[-1])
        hv_min = float(rolling_hv.min())
        hv_max = float(rolling_hv.max())
        if hv_max > hv_min:
            vol_rank_52w_pct = ((hv_30d_pct - hv_min) / (hv_max - hv_min)) * 100.0
        else:
            vol_rank_52w_pct = 50.0

    return {
        "rsi_14": round(rsi_14, 1),
        "sma200": round(sma200, 2),
        "sma200_dist_pct": round(sma200_dist_pct, 2),
        "tech_regime": tech_regime,
        "hv_30d_pct": round(hv_30d_pct, 2),
        "vol_rank_52w_pct": round(vol_rank_52w_pct, 1),
    }


# ---------------------------------------------------------------------------
# Option Chain Selection & Yield Math
# ---------------------------------------------------------------------------

def select_expiration(expirations: tuple[str, ...], target_dte: int = 30, min_dte: int = 7) -> tuple[str, int]:
    """Select the expiration date closest to `target_dte` with at least `min_dte` days remaining."""
    today = date.today()
    best_exp: Optional[str] = None
    best_dte: int = 0
    best_diff: int = 999999

    for exp_str in expirations:
        try:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        dte = (exp_date - today).days
        if dte < min_dte:
            continue
        diff = abs(dte - target_dte)
        if diff < best_diff:
            best_diff = diff
            best_exp = exp_str
            best_dte = dte

    if best_exp is None:
        raise ValueError(f"No valid expiration found with DTE >= {min_dte}")
    return best_exp, best_dte


def _compute_option_premium(row: pd.Series) -> float:
    """Calculate option premium using mid-price when bid/ask are valid, falling back to lastPrice."""
    bid = float(row.get("bid", 0.0) or 0.0)
    ask = float(row.get("ask", 0.0) or 0.0)
    last_price = float(row.get("lastPrice", 0.0) or 0.0)

    if bid > 0 and ask > 0 and ask >= bid:
        return round((bid + ask) / 2.0, 2)
    if bid > 0:
        return round(bid, 2)
    return round(last_price, 2)


def _compute_spread_pct(row: pd.Series, premium: float) -> float:
    """Compute bid-ask spread percentage relative to mid price when live quotes exist."""
    bid = float(row.get("bid", 0.0) or 0.0)
    ask = float(row.get("ask", 0.0) or 0.0)
    if bid > 0 and ask >= bid and premium > 0:
        return round(((ask - bid) / premium) * 100.0, 2)
    return 0.0


def select_otm_put(
    puts_df: pd.DataFrame,
    spot_price: float,
    target_otm_pct: float = 0.05,
    target_delta: Optional[float] = None,
    t_years: float = 30.0 / 365.0,
    fallback_iv: float = 0.25,
) -> pd.Series:
    """Select an Out-Of-The-Money (OTM) Put by target_delta (if specified) or target_otm_pct."""
    df = puts_df.copy()
    df = df[df["strike"] < spot_price].copy()
    if df.empty:
        df = puts_df.copy()

    df["premium"] = df.apply(_compute_option_premium, axis=1)
    df = df[df["premium"] > 0].copy()
    if df.empty:
        raise ValueError("No puts with non-zero premium found.")

    if target_delta is not None and target_delta > 0:
        deltas = []
        for _, r in df.iterrows():
            iv = solve_implied_volatility(
                float(r["premium"]), spot_price, float(r["strike"]), t_years, option_type="put", fallback_iv=fallback_iv
            )
            d, _ = compute_option_greeks(spot_price, float(r["strike"]), t_years, iv, option_type="put")
            deltas.append(abs(d))
        df["abs_delta"] = deltas
        df["score_diff"] = (df["abs_delta"] - abs(target_delta)).abs()
    else:
        target_strike = spot_price * (1.0 - target_otm_pct)
        df["score_diff"] = (df["strike"] - target_strike).abs()

    return df.sort_values("score_diff").iloc[0]


def select_otm_call(
    calls_df: pd.DataFrame,
    spot_price: float,
    target_otm_pct: float = 0.05,
    target_delta: Optional[float] = None,
    t_years: float = 30.0 / 365.0,
    fallback_iv: float = 0.25,
) -> pd.Series:
    """Select an Out-Of-The-Money (OTM) Call by target_delta (if specified) or target_otm_pct."""
    df = calls_df.copy()
    df = df[df["strike"] > spot_price].copy()
    if df.empty:
        df = calls_df.copy()

    df["premium"] = df.apply(_compute_option_premium, axis=1)
    df = df[df["premium"] > 0].copy()
    if df.empty:
        raise ValueError("No calls with non-zero premium found.")

    if target_delta is not None and target_delta > 0:
        deltas = []
        for _, r in df.iterrows():
            iv = solve_implied_volatility(
                float(r["premium"]), spot_price, float(r["strike"]), t_years, option_type="call", fallback_iv=fallback_iv
            )
            d, _ = compute_option_greeks(spot_price, float(r["strike"]), t_years, iv, option_type="call")
            deltas.append(abs(d))
        df["abs_delta"] = deltas
        df["score_diff"] = (df["abs_delta"] - abs(target_delta)).abs()
    else:
        target_strike = spot_price * (1.0 + target_otm_pct)
        df["score_diff"] = (df["strike"] - target_strike).abs()

    return df.sort_values("score_diff").iloc[0]


def calculate_annualized_csp_yield(premium: float, strike: float, dte: int) -> tuple[float, float]:
    """Calculate Cash-Secured Put (CSP) raw and annualized yields."""
    if strike <= 0 or dte <= 0:
        return 0.0, 0.0
    raw_yield_pct = (premium / strike) * 100.0
    annualized_yield_pct = raw_yield_pct * (365.0 / dte)
    return round(raw_yield_pct, 2), round(annualized_yield_pct, 2)


def calculate_annualized_cc_yield(
    premium: float, strike: float, spot_price: float, dte: int
) -> tuple[float, float, float]:
    """Calculate Covered Call (CC) raw, static annualized, and if-called annualized yields."""
    if spot_price <= 0 or dte <= 0:
        return 0.0, 0.0, 0.0
    raw_yield_pct = (premium / spot_price) * 100.0
    annualized_yield_pct = raw_yield_pct * (365.0 / dte)
    upside = max(0.0, strike - spot_price)
    if_called_raw_pct = ((premium + upside) / spot_price) * 100.0
    annualized_if_called_pct = if_called_raw_pct * (365.0 / dte)
    return (
        round(raw_yield_pct, 2),
        round(annualized_yield_pct, 2),
        round(annualized_if_called_pct, 2),
    )


def _extract_earnings_date(info: dict) -> Optional[date]:
    """Extract upcoming earnings date from Yahoo Finance ticker info."""
    for key in ("earningsTimestamp", "earningsTimestampStart", "earningsTimestampEnd"):
        ts = info.get(key)
        if ts and isinstance(ts, (int, float)) and ts > 0:
            try:
                return datetime.fromtimestamp(ts, tz=timezone.utc).date()
            except Exception:
                continue
    return None


def _normalize_dividend_yield(info: dict) -> float:
    """Extract dividend yield as a clean percentage (e.g., 2.45 for 2.45%)."""
    dy = info.get("dividendYield")
    if dy is None:
        return 0.0
    val = float(dy)
    if 0 < val < 0.25:
        return round(val * 100.0, 2)
    return round(val, 2)


def _compute_edge_and_signal(
    csp_ann_yield: float,
    cc_ann_yield: float,
    csp_pop: float,
    vrp_pct: float,
    rsi_14: float,
    trailing_pe: float,
    fcf_yield_pct: Optional[float],
    earnings_before_expiry: bool,
) -> tuple[float, str]:
    """
    Synthesize all 5 pillars into a composite Quantitative Edge Score (0-100)
    and an actionable strategy classification.
    """
    yield_component = min(40.0, csp_ann_yield * 0.85)
    pop_component = max(0.0, (csp_pop - 50.0) * 0.6)
    vrp_component = max(-10.0, min(20.0, vrp_pct * 1.2))

    fund_component = 0.0
    if 0 < trailing_pe <= 35.0:
        fund_component += 10.0
    elif trailing_pe <= 50.0:
        fund_component += 5.0
    if fcf_yield_pct is not None and fcf_yield_pct >= 3.0:
        fund_component += 8.0

    event_penalty = -15.0 if earnings_before_expiry else 5.0

    raw_score = yield_component + pop_component + vrp_component + fund_component + event_penalty
    edge_score = round(max(1.0, min(99.0, raw_score)), 1)

    if earnings_before_expiry:
        signal = "CAUTION: EARNINGS IN WINDOW"
    elif rsi_14 <= 40.0 and vrp_pct >= 0:
        signal = "STRONG CSP (Pullback + Rich IV)"
    elif rsi_14 >= 65.0 and cc_ann_yield >= 15.0:
        signal = "STRONG CC (Overbought Rally)"
    elif vrp_pct >= 5.0 and csp_ann_yield >= 18.0:
        signal = "HIGH VRP EDGE (Overpriced IV)"
    elif trailing_pe <= 28.0 and csp_ann_yield >= 15.0:
        signal = "QUALITY WHEEL CORE"
    else:
        signal = "NEUTRAL / THETA HOLD"

    return edge_score, signal


# ---------------------------------------------------------------------------
# Main Per-Ticker & Parallel Universe Screening Pipeline
# ---------------------------------------------------------------------------

def analyze_ticker(
    ticker_meta: StockTicker,
    target_dte: int = 30,
    target_otm_pct: float = 0.05,
    target_delta: Optional[float] = None,
    min_pe: float = 0.0,
) -> Optional[OptionYieldResult]:
    """Fetch fundamentals, technicals, volatility, and options chain for a single ticker."""
    yf_ticker = yf.Ticker(ticker_meta.symbol)
    info = yf_ticker.info or {}

    spot_price = (
        info.get("currentPrice")
        or info.get("regularMarketPrice")
        or info.get("previousClose")
        or info.get("navPrice")
    )
    if not spot_price or spot_price <= 0:
        logger.warning("Skipping %s: No valid spot price.", ticker_meta.symbol)
        return None
    spot_f = float(spot_price)

    # 1. Fundamental Quality Filter (P/E > min_pe)
    trailing_pe = info.get("trailingPE")
    forward_pe = info.get("forwardPE")
    effective_pe = trailing_pe if trailing_pe is not None else forward_pe
    if effective_pe is None or effective_pe <= min_pe:
        logger.info("Filtered out %s: P/E (%s) <= %.2f", ticker_meta.symbol, effective_pe, min_pe)
        return None

    market_cap = float(info.get("marketCap") or info.get("totalAssets") or 0.0)
    market_cap_b = market_cap / 1e9

    fcf = info.get("freeCashflow")
    fcf_yield_pct = round((float(fcf) / market_cap) * 100.0, 2) if (fcf and market_cap > 0) else None

    op_margin = info.get("operatingMargins")
    op_margin_pct = round(float(op_margin) * 100.0, 1) if op_margin is not None else None

    peg_ratio = info.get("pegRatio") or info.get("trailingPegRatio")
    peg_val = round(float(peg_ratio), 2) if peg_ratio is not None else None

    target_mean = info.get("targetMeanPrice")
    analyst_upside_pct = (
        round(((float(target_mean) - spot_f) / spot_f) * 100.0, 1)
        if (target_mean and float(target_mean) > 0)
        else None
    )

    dividend_yield_pct = _normalize_dividend_yield(info)
    div_decimal = dividend_yield_pct / 100.0
    gf_code = _resolve_google_finance_code(ticker_meta.symbol, info)

    # 2. Technicals & Historical Volatility (1Y daily history)
    try:
        hist_df = yf_ticker.history(period="1y", interval="1d", auto_adjust=True)
    except Exception:
        hist_df = pd.DataFrame()
    tech = compute_technicals_and_hv(hist_df)
    hv_decimal = tech["hv_30d_pct"] / 100.0

    # 3. Options Chain & Expiration Selection (with Black-Scholes synthetic fallback for KRX/non-US listings)
    expirations = yf_ticker.options
    today = date.today()
    earn_date = _extract_earnings_date(info)
    earn_date_str = earn_date.isoformat() if earn_date else None

    if not expirations:
        # Build synthetic 30-DTE 5% OTM option chain from Black-Scholes using 30d Realized Volatility
        dte = target_dte
        exp_date = pd.Timestamp(today) + pd.Timedelta(days=dte)
        exp_str = f"{exp_date.strftime('%Y-%m-%d')} (Synth)"
        t_years = dte / 365.0
        earnings_before_expiry = bool(earn_date and today <= earn_date <= exp_date.date())

        csp_strike = round(spot_f * (1.0 - target_otm_pct), 2)
        cc_strike = round(spot_f * (1.0 + target_otm_pct), 2)
        synth_iv = max(0.15, hv_decimal)
        csp_premium = round(
            bs_price(spot_f, csp_strike, t_years, synth_iv, div_yield=div_decimal, option_type="put"), 2
        )
        cc_premium = round(
            bs_price(spot_f, cc_strike, t_years, synth_iv, div_yield=div_decimal, option_type="call"), 2
        )
        csp_otm_pct = round(((spot_f - csp_strike) / spot_f) * 100.0, 2)
        cc_otm_pct = round(((cc_strike - spot_f) / spot_f) * 100.0, 2)
        csp_iv_pct = round(synth_iv * 100.0, 2)
        cc_iv_pct = round(synth_iv * 100.0, 2)
        csp_delta, csp_pop_pct = compute_option_greeks(
            spot_f, csp_strike, t_years, synth_iv, div_yield=div_decimal, option_type="put"
        )
        cc_delta, cc_pop_pct = compute_option_greeks(
            spot_f, cc_strike, t_years, synth_iv, div_yield=div_decimal, option_type="call"
        )
        csp_spread_pct, cc_spread_pct = 0.0, 0.0
        csp_oi, cc_oi = 0, 0
    else:
        exp_str, dte = select_expiration(expirations, target_dte=target_dte)
        exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
        t_years = max(dte, 1) / 365.0
        earnings_before_expiry = bool(earn_date and today <= earn_date <= exp_date)

        # 5. Select OTM Put & Call (via Delta target or % OTM)
        chain = yf_ticker.option_chain(exp_str)
        put_row = select_otm_put(
            chain.puts,
            spot_f,
            target_otm_pct=target_otm_pct,
            target_delta=target_delta,
            t_years=t_years,
            fallback_iv=hv_decimal,
        )
        call_row = select_otm_call(
            chain.calls,
            spot_f,
            target_otm_pct=target_otm_pct,
            target_delta=target_delta,
            t_years=t_years,
            fallback_iv=hv_decimal,
        )

        # Cash-Secured Put (CSP) Metrics & True Black-Scholes IV/Greeks
        csp_strike = float(put_row["strike"])
        csp_premium = float(put_row["premium"])
        csp_otm_pct = round(((spot_f - csp_strike) / spot_f) * 100.0, 2)
        csp_spread_pct = _compute_spread_pct(put_row, csp_premium)
        csp_iv = solve_implied_volatility(
            csp_premium, spot_f, csp_strike, t_years, div_yield=div_decimal, option_type="put", fallback_iv=hv_decimal
        )
        csp_iv_pct = round(csp_iv * 100.0, 2)
        csp_delta, csp_pop_pct = compute_option_greeks(
            spot_f, csp_strike, t_years, csp_iv, div_yield=div_decimal, option_type="put"
        )
        csp_oi_val = put_row.get("openInterest", 0)
        csp_oi = 0 if pd.isna(csp_oi_val) else int(csp_oi_val)

        # Covered Call (CC) Metrics & True Black-Scholes IV/Greeks
        cc_strike = float(call_row["strike"])
        cc_premium = float(call_row["premium"])
        cc_otm_pct = round(((cc_strike - spot_f) / spot_f) * 100.0, 2)
        cc_spread_pct = _compute_spread_pct(call_row, cc_premium)
        cc_iv = solve_implied_volatility(
            cc_premium, spot_f, cc_strike, t_years, div_yield=div_decimal, option_type="call", fallback_iv=hv_decimal
        )
        cc_iv_pct = round(cc_iv * 100.0, 2)
        cc_delta, cc_pop_pct = compute_option_greeks(
            spot_f, cc_strike, t_years, cc_iv, div_yield=div_decimal, option_type="call"
        )
        cc_oi_val = call_row.get("openInterest", 0)
        cc_oi = 0 if pd.isna(cc_oi_val) else int(cc_oi_val)

    csp_raw, csp_ann = calculate_annualized_csp_yield(csp_premium, csp_strike, dte)
    cc_raw, cc_ann, cc_if_called = calculate_annualized_cc_yield(cc_premium, cc_strike, spot_f, dte)
    cc_total_income_yield_pct = round(cc_ann + dividend_yield_pct, 2)

    # Volatility Risk Premium (Average Option IV minus 30-day Realized HV)
    avg_iv_pct = 0.5 * (csp_iv_pct + cc_iv_pct)
    vrp_pct = round(avg_iv_pct - tech["hv_30d_pct"], 2)

    # Composite Edge Score & Strategy Signal
    edge_score, strategy_signal = _compute_edge_and_signal(
        csp_ann_yield=csp_ann,
        cc_ann_yield=cc_ann,
        csp_pop=csp_pop_pct,
        vrp_pct=vrp_pct,
        rsi_14=tech["rsi_14"],
        trailing_pe=float(effective_pe),
        fcf_yield_pct=fcf_yield_pct,
        earnings_before_expiry=earnings_before_expiry,
    )

    return OptionYieldResult(
        symbol=ticker_meta.symbol,
        name=info.get("shortName") or ticker_meta.name,
        region=ticker_meta.region,
        country=ticker_meta.country,
        index_group=getattr(ticker_meta, "index_group", "NASDAQ-100"),
        google_finance_code=gf_code,
        spot_price=round(spot_f, 2),
        market_cap_b=round(market_cap_b, 1),
        trailing_pe=round(float(effective_pe), 2),
        forward_pe=round(float(forward_pe), 2) if forward_pe is not None else None,
        peg_ratio=peg_val,
        fcf_yield_pct=fcf_yield_pct,
        operating_margin_pct=op_margin_pct,
        analyst_upside_pct=analyst_upside_pct,
        dividend_yield_pct=dividend_yield_pct,
        rsi_14=tech["rsi_14"],
        sma200=tech["sma200"],
        sma200_dist_pct=tech["sma200_dist_pct"],
        tech_regime=tech["tech_regime"],
        hv_30d_pct=tech["hv_30d_pct"],
        vol_rank_52w_pct=tech["vol_rank_52w_pct"],
        vrp_pct=vrp_pct,
        expiration=exp_str,
        dte=dte,
        earnings_date=earn_date_str,
        earnings_before_expiry=earnings_before_expiry,
        csp_strike=csp_strike,
        csp_otm_pct=csp_otm_pct,
        csp_premium=csp_premium,
        csp_iv_pct=csp_iv_pct,
        csp_delta=csp_delta,
        csp_pop_pct=csp_pop_pct,
        csp_spread_pct=csp_spread_pct,
        csp_open_interest=csp_oi,
        csp_raw_yield_pct=csp_raw,
        csp_annualized_yield_pct=csp_ann,
        cc_strike=cc_strike,
        cc_otm_pct=cc_otm_pct,
        cc_premium=cc_premium,
        cc_iv_pct=cc_iv_pct,
        cc_delta=cc_delta,
        cc_pop_pct=cc_pop_pct,
        cc_spread_pct=cc_spread_pct,
        cc_open_interest=cc_oi,
        cc_raw_yield_pct=cc_raw,
        cc_annualized_yield_pct=cc_ann,
        cc_total_income_yield_pct=cc_total_income_yield_pct,
        cc_annualized_if_called_pct=cc_if_called,
        edge_score=edge_score,
        strategy_signal=strategy_signal,
    )


def run_screen(
    universe: List[StockTicker],
    target_dte: int = 30,
    target_otm_pct: float = 0.05,
    target_delta: Optional[float] = None,
    min_pe: float = 0.0,
    max_workers: int = 6,
) -> pd.DataFrame:
    """Screen a list of tickers concurrently and return a sorted pandas DataFrame."""
    results: List[dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {
            executor.submit(
                analyze_ticker,
                item,
                target_dte,
                target_otm_pct,
                target_delta,
                min_pe,
            ): item
            for item in universe
        }
        for future in as_completed(future_to_ticker):
            item = future_to_ticker[future]
            try:
                res = future.result()
                if res is not None:
                    results.append(res.to_dict())
            except Exception as exc:
                logger.warning("Failed to process %s: %s", item.symbol, exc)

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(by="edge_score", ascending=False).reset_index(drop=True)
    return df
