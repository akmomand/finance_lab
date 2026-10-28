"""Key ratio trends (quarterly) from yfinance statements + prices."""

from __future__ import annotations

from typing import Any

import pandas as pd

from data.cache import TTL_MEDIUM, cached_data
from data.company import get_raw_info, get_ticker, _safe_float
from data.trends import (
    QUARTER_COUNT,
    _CAPEX,
    _CASH,
    _EQUITY,
    _NET_INCOME,
    _OCF,
    _OPERATING_INCOME,
    _REVENUE,
    _TOTAL_DEBT,
    _last_n,
    _margin,
    _row_series,
    _to_float_series,
)

_TOTAL_ASSETS = ("Total Assets", "TotalAssets")
_CURRENT_ASSETS = ("Current Assets", "Total Current Assets")
_CURRENT_LIAB = ("Current Liabilities", "Total Current Liabilities")
_INVENTORY = ("Inventory", "Inventories")
_INTEREST_EXP = (
    "Interest Expense",
    "Interest Expense Non Operating",
    "Net Interest Income",
)
_DILUTED_EPS = ("Diluted EPS", "Diluted Continuous Operations", "Basic EPS")
_SHARES = (
    "Ordinary Shares Number",
    "Share Issued",
    "Common Stock Shares Outstanding",
)


def _quarter_end_prices(ticker_obj, index: pd.DatetimeIndex) -> pd.Series:
    """Map each quarter-end date to the nearest prior daily close."""
    if index is None or len(index) == 0:
        return pd.Series(dtype=float)
    try:
        start = (pd.Timestamp(index.min()) - pd.DateOffset(days=14)).strftime("%Y-%m-%d")
        end = (pd.Timestamp(index.max()) + pd.DateOffset(days=7)).strftime("%Y-%m-%d")
        hist = ticker_obj.history(start=start, end=end, auto_adjust=True)
    except Exception:
        return pd.Series(dtype=float)
    if hist is None or hist.empty or "Close" not in hist.columns:
        return pd.Series(dtype=float)

    closes = hist["Close"].copy()
    closes.index = pd.to_datetime(closes.index).tz_localize(None)
    closes = closes.sort_index()

    prices: dict[pd.Timestamp, float] = {}
    for dt in pd.to_datetime(index):
        dt = pd.Timestamp(dt).tz_localize(None)
        prior = closes.loc[:dt]
        if prior.empty:
            continue
        prices[dt] = float(prior.iloc[-1])
    return pd.Series(prices).sort_index()


def _safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    return _margin(a, b)


def _interest_coverage(ebit: pd.Series, interest: pd.Series) -> pd.Series:
    if ebit.empty or interest.empty:
        return pd.Series(dtype=float)
    aligned = pd.concat([ebit.rename("e"), interest.rename("i")], axis=1).dropna()
    if aligned.empty:
        return pd.Series(dtype=float)
    # Interest may be negative on income stmt; use absolute expense
    aligned["i"] = aligned["i"].abs()
    aligned = aligned.loc[aligned["i"] > 0]
    return (aligned["e"] / aligned["i"]).sort_index()


@cached_data(ttl=TTL_MEDIUM)
def get_key_ratio_trends(ticker: str) -> dict[str, Any]:
    """
    Build up to 8 quarters of key ratios + a current valuation snapshot.

    Historical valuation (P/E, P/S, P/FCF) uses quarter-end prices when available.
    Forward P/E, PEG, EV/EBITDA are point-in-time from Yahoo `.info`.
    """
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return {"symbol": "", "ok": False, "error": "Enter a ticker symbol.", "series": {}, "snapshot": {}}

    t = get_ticker(symbol)
    if t is None:
        return {
            "symbol": symbol,
            "ok": False,
            "error": "Could not create ticker object.",
            "series": {},
            "snapshot": {},
        }

    try:
        income = t.quarterly_financials
        if income is None or income.empty:
            income = getattr(t, "quarterly_income_stmt", None)
        balance = t.quarterly_balance_sheet
        cashflow = t.quarterly_cashflow
    except Exception:
        return {
            "symbol": symbol,
            "ok": False,
            "error": "Failed to download quarterly statements for ratios.",
            "series": {},
            "snapshot": {},
        }

    revenue = _last_n(_to_float_series(_row_series(income, _REVENUE)))
    net_income = _last_n(_to_float_series(_row_series(income, _NET_INCOME)))
    operating_income = _last_n(_to_float_series(_row_series(income, _OPERATING_INCOME)))
    eps = _last_n(_to_float_series(_row_series(income, _DILUTED_EPS)))
    interest = _last_n(_to_float_series(_row_series(income, _INTEREST_EXP)))

    equity = _last_n(_to_float_series(_row_series(balance, _EQUITY)))
    assets = _last_n(_to_float_series(_row_series(balance, _TOTAL_ASSETS)))
    debt = _last_n(_to_float_series(_row_series(balance, _TOTAL_DEBT)))
    cash = _last_n(_to_float_series(_row_series(balance, _CASH)))
    current_assets = _last_n(_to_float_series(_row_series(balance, _CURRENT_ASSETS)))
    current_liab = _last_n(_to_float_series(_row_series(balance, _CURRENT_LIAB)))
    inventory = _last_n(_to_float_series(_row_series(balance, _INVENTORY)))

    ocf = _last_n(_to_float_series(_row_series(cashflow, _OCF)))
    capex = _to_float_series(_row_series(cashflow, _CAPEX))
    fcf = pd.Series(dtype=float)
    if not ocf.empty and not capex.empty:
        aligned = pd.concat([ocf.rename("ocf"), capex.rename("capex")], axis=1).dropna()
        fcf = aligned.apply(
            lambda r: r["ocf"] + r["capex"] if r["capex"] < 0 else r["ocf"] - r["capex"],
            axis=1,
        )
        fcf = _last_n(fcf.sort_index())
    elif not ocf.empty:
        fcf = ocf.copy()

    # Profitability
    roe = _safe_div(net_income, equity)
    roa = _safe_div(net_income, assets)
    invested = None
    if not equity.empty:
        d = debt.reindex(equity.index).fillna(0) if not debt.empty else 0
        c = cash.reindex(equity.index).fillna(0) if not cash.empty else 0
        invested = equity + d - c
    roic = _safe_div(operating_income * 0.79, invested) if invested is not None else pd.Series(dtype=float)

    # Liquidity
    current_ratio = _safe_div(current_assets, current_liab)
    quick_num = current_assets
    if not inventory.empty and not current_assets.empty:
        quick_num = (current_assets - inventory.reindex(current_assets.index).fillna(0))
    quick_ratio = _safe_div(quick_num, current_liab)

    # Solvency
    debt_to_equity = _safe_div(debt, equity)
    interest_coverage = _last_n(_interest_coverage(operating_income, interest))

    # Valuation from prices
    all_idx = revenue.index.union(eps.index).union(fcf.index)
    prices = _quarter_end_prices(t, all_idx)
    # Annualize quarterly EPS for P/E (×4) — labeled as such in UI
    pe = pd.Series(dtype=float)
    if not prices.empty and not eps.empty:
        aligned = pd.concat([prices.rename("p"), eps.rename("e")], axis=1).dropna()
        aligned = aligned.loc[aligned["e"] > 0]
        pe = (aligned["p"] / (aligned["e"] * 4)).sort_index()
        pe = _last_n(pe)

    ps = pd.Series(dtype=float)
    if not prices.empty and not revenue.empty:
        # Prefer shares from balance sheet for market cap; else skip P/S level from price alone
        shares = _last_n(_to_float_series(_row_series(balance, _SHARES)))
        if not shares.empty:
            aligned = pd.concat(
                [prices.rename("p"), shares.rename("s"), revenue.rename("r")], axis=1
            ).dropna()
            aligned = aligned.loc[(aligned["s"] > 0) & (aligned["r"] > 0)]
            # Annualize quarterly revenue
            ps = (aligned["p"] * aligned["s"] / (aligned["r"] * 4)).sort_index()
            ps = _last_n(ps)

    price_fcf = pd.Series(dtype=float)
    if not prices.empty and not fcf.empty:
        shares = _last_n(_to_float_series(_row_series(balance, _SHARES)))
        if not shares.empty:
            aligned = pd.concat(
                [prices.rename("p"), shares.rename("s"), fcf.rename("f")], axis=1
            ).dropna()
            aligned = aligned.loc[(aligned["s"] > 0) & (aligned["f"] > 0)]
            price_fcf = (aligned["p"] * aligned["s"] / (aligned["f"] * 4)).sort_index()
            price_fcf = _last_n(price_fcf)

    series = {
        "roe": _last_n(roe),
        "roa": _last_n(roa),
        "roic": _last_n(roic),
        "current_ratio": _last_n(current_ratio),
        "quick_ratio": _last_n(quick_ratio),
        "debt_to_equity": _last_n(debt_to_equity),
        "interest_coverage": interest_coverage,
        "pe": pe,
        "price_to_sales": ps,
        "price_to_fcf": price_fcf,
    }

    info = get_raw_info(symbol) or {}
    snapshot = {
        "trailing_pe": _safe_float(info.get("trailingPE")),
        "forward_pe": _safe_float(info.get("forwardPE")),
        "peg": _safe_float(info.get("pegRatio")),
        "ev_ebitda": _safe_float(info.get("enterpriseToEbitda")),
        "price_to_sales": _safe_float(info.get("priceToSalesTrailing12Months")),
        "price_to_book": _safe_float(info.get("priceToBook")),
    }

    any_data = any(isinstance(s, pd.Series) and not s.empty for s in series.values())
    if not any_data and not any(v is not None for v in snapshot.values()):
        return {
            "symbol": symbol,
            "ok": False,
            "error": "No ratio data available for this ticker.",
            "series": series,
            "snapshot": snapshot,
        }

    return {
        "symbol": symbol,
        "ok": True,
        "error": None,
        "series": series,
        "snapshot": snapshot,
        "notes": {
            "pe": "Historical P/E uses quarter-end price / (quarterly EPS × 4).",
            "roic": "ROIC approx. operating income × (1 − 21%) / (equity + debt − cash).",
        },
    }
