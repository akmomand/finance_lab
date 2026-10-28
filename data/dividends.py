"""Dividend metrics and history via yfinance."""

from __future__ import annotations

from typing import Any

import pandas as pd

from data.cache import TTL_MEDIUM, cached_data
from data.company import get_raw_info, get_ticker, _safe_float


def _annual_dividends(div_series: pd.Series) -> pd.Series:
    if div_series is None or div_series.empty:
        return pd.Series(dtype=float)
    s = div_series.copy()
    s.index = pd.to_datetime(s.index).tz_localize(None)
    annual = s.groupby(s.index.year).sum().sort_index()
    annual.index = annual.index.astype(int)
    return annual


def _consecutive_increases(annual: pd.Series) -> int:
    """Count consecutive years of dividend increases ending at the latest full-ish year."""
    if annual is None or len(annual) < 2:
        return 0
    years = list(annual.index)
    values = list(annual.values)
    # Skip current calendar year if it looks incomplete (< 50% of prior)
    if len(values) >= 2 and values[-1] < 0.5 * values[-2]:
        years = years[:-1]
        values = values[:-1]
    streak = 0
    for i in range(len(values) - 1, 0, -1):
        if values[i] > values[i - 1]:
            streak += 1
        else:
            break
    return streak


def _cagr(annual: pd.Series, years: int = 5) -> float | None:
    if annual is None or annual.empty:
        return None
    s = annual.dropna()
    if len(s) < 2:
        return None
    # Use last N+1 points for N-year CAGR
    window = s.tail(years + 1)
    if len(window) < 2:
        window = s
    start = float(window.iloc[0])
    end = float(window.iloc[-1])
    n = len(window) - 1
    if start <= 0 or end <= 0 or n <= 0:
        return None
    return (end / start) ** (1.0 / n) - 1.0


@cached_data(ttl=TTL_MEDIUM)
def get_dividend_analysis(ticker: str) -> dict[str, Any]:
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return {"symbol": "", "ok": False, "error": "Enter a ticker symbol."}

    info = get_raw_info(symbol) or {}
    t = get_ticker(symbol)

    div_yield = _safe_float(info.get("dividendYield"))
    if div_yield is not None and div_yield > 1:
        div_yield = div_yield / 100.0
    payout = _safe_float(info.get("payoutRatio"))
    if payout is not None and payout > 1.5:
        payout = payout / 100.0
    rate = _safe_float(info.get("dividendRate"))
    ex_date = info.get("exDividendDate")

    history = pd.Series(dtype=float)
    try:
        if t is not None:
            d = getattr(t, "dividends", None)
            if d is not None and not getattr(d, "empty", True):
                history = d.copy()
                history.index = pd.to_datetime(history.index)
    except Exception:
        pass

    annual = _annual_dividends(history)
    growth = _cagr(annual, years=5)
    streak = _consecutive_increases(annual)

    ok = (
        div_yield is not None
        or rate is not None
        or not history.empty
        or payout is not None
    )
    if not ok:
        return {
            "symbol": symbol,
            "ok": False,
            "error": "No dividend data for this ticker (may not pay a dividend).",
        }

    return {
        "symbol": symbol,
        "ok": True,
        "error": None,
        "yield": div_yield,
        "payout_ratio": payout,
        "dividend_rate": rate,
        "ex_dividend_date": ex_date,
        "history": history,
        "annual": annual,
        "growth_5y": growth,
        "consecutive_increases": streak,
        "currency": info.get("currency") or "USD",
    }
