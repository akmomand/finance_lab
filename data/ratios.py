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


def _ttm_sum(series: pd.Series) -> pd.Series:
    """Trailing four-quarter sum on a chronologically sorted quarterly series."""
    if series is None or series.empty:
        return pd.Series(dtype=float)
    s = series.dropna().sort_index()
    if len(s) < 4:
        return pd.Series(dtype=float)
    return s.rolling(window=4, min_periods=4).sum().dropna()


@cached_data(ttl=TTL_MEDIUM)
def get_key_ratio_trends(ticker: str) -> dict[str, Any]:
    """
    Build up to 8 quarters of key ratios + a current valuation snapshot.

    Historical valuation (P/E, P/S, P/FCF) uses quarter-end price ÷ TTM (sum of
    last 4 quarters). Forward P/E, PEG, EV/EBITDA are point-in-time from Yahoo `.info`.
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

    # Full quarterly series (needed so TTM has 4 quarters of lookback)
    revenue_full = _to_float_series(_row_series(income, _REVENUE))
    net_income_full = _to_float_series(_row_series(income, _NET_INCOME))
    operating_income_full = _to_float_series(_row_series(income, _OPERATING_INCOME))
    eps_full = _to_float_series(_row_series(income, _DILUTED_EPS))
    interest_full = _to_float_series(_row_series(income, _INTEREST_EXP))

    equity_full = _to_float_series(_row_series(balance, _EQUITY))
    assets_full = _to_float_series(_row_series(balance, _TOTAL_ASSETS))
    debt_full = _to_float_series(_row_series(balance, _TOTAL_DEBT))
    cash_full = _to_float_series(_row_series(balance, _CASH))
    current_assets_full = _to_float_series(_row_series(balance, _CURRENT_ASSETS))
    current_liab_full = _to_float_series(_row_series(balance, _CURRENT_LIAB))
    inventory_full = _to_float_series(_row_series(balance, _INVENTORY))
    shares_full = _to_float_series(_row_series(balance, _SHARES))

    ocf_full = _to_float_series(_row_series(cashflow, _OCF))
    capex_full = _to_float_series(_row_series(cashflow, _CAPEX))
    fcf_full = pd.Series(dtype=float)
    if not ocf_full.empty and not capex_full.empty:
        aligned = pd.concat([ocf_full.rename("ocf"), capex_full.rename("capex")], axis=1).dropna()
        fcf_full = aligned.apply(
            lambda r: r["ocf"] + r["capex"] if r["capex"] < 0 else r["ocf"] - r["capex"],
            axis=1,
        ).sort_index()
    elif not ocf_full.empty:
        fcf_full = ocf_full.copy()

    # Display window (last N quarters) for non-TTM ratios
    revenue = _last_n(revenue_full)
    net_income = _last_n(net_income_full)
    operating_income = _last_n(operating_income_full)
    interest = _last_n(interest_full)
    equity = _last_n(equity_full)
    assets = _last_n(assets_full)
    debt = _last_n(debt_full)
    cash = _last_n(cash_full)
    current_assets = _last_n(current_assets_full)
    current_liab = _last_n(current_liab_full)
    inventory = _last_n(inventory_full)

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
        quick_num = current_assets - inventory.reindex(current_assets.index).fillna(0)
    quick_ratio = _safe_div(quick_num, current_liab)

    # Solvency
    debt_to_equity = _safe_div(debt, equity)
    interest_coverage = _last_n(_interest_coverage(operating_income_full, interest_full))

    # Valuation: quarter-end price / TTM fundamentals
    ttm_eps = _ttm_sum(eps_full)
    ttm_revenue = _ttm_sum(revenue_full)
    ttm_fcf = _ttm_sum(fcf_full)
    price_idx = ttm_eps.index.union(ttm_revenue.index).union(ttm_fcf.index).union(shares_full.index)
    prices = _quarter_end_prices(t, price_idx)

    pe = pd.Series(dtype=float)
    if not prices.empty and not ttm_eps.empty:
        aligned = pd.concat([prices.rename("p"), ttm_eps.rename("e")], axis=1).dropna()
        aligned = aligned.loc[aligned["e"] > 0]
        pe = _last_n((aligned["p"] / aligned["e"]).sort_index())

    ps = pd.Series(dtype=float)
    if not prices.empty and not ttm_revenue.empty and not shares_full.empty:
        aligned = pd.concat(
            [prices.rename("p"), shares_full.rename("s"), ttm_revenue.rename("r")],
            axis=1,
        ).dropna()
        aligned = aligned.loc[(aligned["s"] > 0) & (aligned["r"] > 0)]
        ps = _last_n((aligned["p"] * aligned["s"] / aligned["r"]).sort_index())

    price_fcf = pd.Series(dtype=float)
    if not prices.empty and not ttm_fcf.empty and not shares_full.empty:
        aligned = pd.concat(
            [prices.rename("p"), shares_full.rename("s"), ttm_fcf.rename("f")],
            axis=1,
        ).dropna()
        aligned = aligned.loc[(aligned["s"] > 0) & (aligned["f"] > 0)]
        price_fcf = _last_n((aligned["p"] * aligned["s"] / aligned["f"]).sort_index())

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
            "pe": (
                "Historical P/E = quarter-end close ÷ TTM diluted EPS "
                "(sum of that quarter + prior 3 quarters)."
            ),
            "roic": "ROIC approx. operating income × (1 − 21%) / (equity + debt − cash).",
        },
    }
