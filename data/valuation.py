"""Fair value helpers: DCF, Graham number, multiples."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from data.cache import TTL_MEDIUM, cached_data
from data.company import get_raw_info, get_ticker, _safe_float
from data.trends import (
    QUARTER_COUNT,
    _REVENUE,
    _last_n,
    _row_series,
    _to_float_series,
)


def graham_number(eps: float | None, bvps: float | None) -> float | None:
    """Benjamin Graham: sqrt(22.5 * EPS * Book Value Per Share)."""
    if eps is None or bvps is None:
        return None
    if eps <= 0 or bvps <= 0:
        return None
    return math.sqrt(22.5 * eps * bvps)


def run_dcf(
    *,
    fcf0: float,
    shares: float,
    net_debt: float,
    growth: float,
    wacc: float,
    terminal_growth: float,
    years: int = 5,
) -> dict[str, Any] | None:
    """
    Simple 5-year FCF DCF → equity value per share.

    fcf0: latest annual (or TTM) free cash flow
    growth / wacc / terminal_growth: decimals (e.g. 0.08)
    net_debt: total debt − cash (subtracted from enterprise value)
    """
    if fcf0 is None or shares is None or shares <= 0:
        return None
    if wacc <= terminal_growth:
        return None
    if wacc <= 0:
        return None

    projected: list[float] = []
    fcf = float(fcf0)
    for _ in range(years):
        fcf = fcf * (1.0 + growth)
        projected.append(fcf)

    discount_factors = [(1.0 + wacc) ** (i + 1) for i in range(years)]
    pv_fcfs = [cf / df for cf, df in zip(projected, discount_factors)]

    terminal_fcf = projected[-1] * (1.0 + terminal_growth)
    terminal_value = terminal_fcf / (wacc - terminal_growth)
    pv_terminal = terminal_value / discount_factors[-1]

    enterprise_value = sum(pv_fcfs) + pv_terminal
    equity_value = enterprise_value - float(net_debt or 0.0)
    intrinsic = equity_value / shares

    return {
        "projected_fcf": projected,
        "pv_fcfs": pv_fcfs,
        "terminal_value": terminal_value,
        "pv_terminal": pv_terminal,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "intrinsic_per_share": intrinsic,
        "years": years,
    }


def _ttm_from_quarterly(series: pd.Series) -> float | None:
    if series is None or series.empty:
        return None
    s = series.dropna().sort_index().tail(4)
    if s.empty:
        return None
    return float(s.sum())


@cached_data(ttl=TTL_MEDIUM)
def get_valuation_inputs(ticker: str) -> dict[str, Any]:
    """Pull baseline inputs for fair-value models from yfinance."""
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return {"symbol": "", "ok": False, "error": "Enter a ticker symbol."}

    info = get_raw_info(symbol) or {}
    t = get_ticker(symbol)

    price = _safe_float(
        info.get("currentPrice")
        or info.get("regularMarketPrice")
        or info.get("previousClose")
    )
    eps = _safe_float(info.get("trailingEps") or info.get("epsTrailingTwelveMonths"))
    bvps = _safe_float(info.get("bookValue"))
    shares = _safe_float(info.get("sharesOutstanding"))
    total_debt = _safe_float(info.get("totalDebt"))
    total_cash = _safe_float(info.get("totalCash"))
    fcf = _safe_float(info.get("freeCashflow"))
    trailing_pe = _safe_float(info.get("trailingPE"))
    forward_pe = _safe_float(info.get("forwardPE"))

    # Revenue growth default from quarterly YoY if possible
    default_growth = 0.08
    hist_pe_avg = None
    try:
        if t is not None:
            income = t.quarterly_financials
            if income is None or income.empty:
                income = getattr(t, "quarterly_income_stmt", None)
            rev = _last_n(_to_float_series(_row_series(income, _REVENUE)), QUARTER_COUNT)
            if len(rev) >= 5:
                latest_ttm = float(rev.tail(4).sum())
                prior_ttm = float(rev.iloc[-5:-1].sum()) if len(rev) >= 5 else None
                # Better: compare last 4 vs previous 4
                if len(rev) >= 8:
                    latest_ttm = float(rev.tail(4).sum())
                    prior_ttm = float(rev.iloc[-8:-4].sum())
                if prior_ttm and prior_ttm != 0:
                    default_growth = max(-0.2, min(0.35, (latest_ttm / prior_ttm) - 1.0))

            # Historical P/E avg from annual earnings + prices (coarse)
            annual = t.financials
            eps_row = _row_series(annual, ("Diluted EPS", "Basic EPS"))
            if eps_row is not None:
                eps_s = _to_float_series(eps_row).tail(5)
                if not eps_s.empty:
                    try:
                        hist = t.history(
                            start=(eps_s.index.min() - pd.DateOffset(days=5)).strftime("%Y-%m-%d"),
                            end=(eps_s.index.max() + pd.DateOffset(days=5)).strftime("%Y-%m-%d"),
                            auto_adjust=True,
                        )
                    except Exception:
                        hist = None
                    if hist is not None and not hist.empty:
                        closes = hist["Close"].copy()
                        closes.index = pd.to_datetime(closes.index).tz_localize(None)
                        pes = []
                        for dt, e in eps_s.items():
                            if e is None or e <= 0:
                                continue
                            dt = pd.Timestamp(dt).tz_localize(None)
                            prior = closes.loc[:dt]
                            if prior.empty:
                                continue
                            pes.append(float(prior.iloc[-1]) / float(e))
                        if pes:
                            hist_pe_avg = sum(pes) / len(pes)
    except Exception:
        pass

    if fcf is None and t is not None:
        try:
            cf = t.quarterly_cashflow
            ocf = _to_float_series(
                _row_series(
                    cf,
                    (
                        "Operating Cash Flow",
                        "Cash Flow From Continuing Operating Activities",
                    ),
                )
            )
            capex = _to_float_series(
                _row_series(cf, ("Capital Expenditure", "Purchase Of PPE"))
            )
            if not ocf.empty and not capex.empty:
                aligned = pd.concat([ocf.rename("o"), capex.rename("c")], axis=1).dropna()
                fcf_q = aligned.apply(
                    lambda r: r["o"] + r["c"] if r["c"] < 0 else r["o"] - r["c"],
                    axis=1,
                )
                fcf = _ttm_from_quarterly(fcf_q)
        except Exception:
            pass

    net_debt = None
    if total_debt is not None or total_cash is not None:
        net_debt = (total_debt or 0.0) - (total_cash or 0.0)

    graham = graham_number(eps, bvps)

    ok = price is not None or eps is not None or fcf is not None
    return {
        "symbol": symbol,
        "ok": ok,
        "error": None if ok else "Could not load valuation inputs for this ticker.",
        "price": price,
        "currency": (info.get("currency") or "USD"),
        "eps": eps,
        "bvps": bvps,
        "shares": shares,
        "fcf": fcf,
        "net_debt": net_debt,
        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe,
        "hist_pe_avg": hist_pe_avg,
        "default_growth": default_growth,
        "graham": graham,
        "name": info.get("shortName") or info.get("longName") or symbol,
    }
