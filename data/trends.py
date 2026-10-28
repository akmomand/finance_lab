"""Quarterly historical trend series from yfinance."""

from __future__ import annotations

from typing import Any

import pandas as pd

from data.cache import TTL_MEDIUM, cached_data
from data.company import get_ticker, _safe_float

QUARTER_COUNT = 8

# Candidate row labels (yfinance naming varies by ticker / version)
_REVENUE = ("Total Revenue", "Operating Revenue", "Revenue")
_NET_INCOME = (
    "Net Income",
    "Net Income Common Stockholders",
    "Net Income Continuous Operations",
)
_OPERATING_INCOME = ("Operating Income", "EBIT", "Operating Income or Loss")
_GROSS_PROFIT = ("Gross Profit",)
_DILUTED_EPS = ("Diluted EPS", "Diluted Continuous Operations", "Basic EPS")
_TOTAL_DEBT = ("Total Debt", "Long Term Debt", "Net Debt")
_CASH = (
    "Cash Cash Equivalents And Short Term Investments",
    "Cash And Cash Equivalents",
    "Cash Financial",
)
_EQUITY = (
    "Stockholders Equity",
    "Total Stockholder Equity",
    "Common Stock Equity",
    "Total Equity Gross Minority Interest",
)
_OCF = (
    "Operating Cash Flow",
    "Cash Flow From Continuing Operating Activities",
    "Total Cash From Operating Activities",
)
_CAPEX = (
    "Capital Expenditure",
    "Purchase Of PPE",
    "Net PPE Purchase And Sale",
)


def _row_series(df: pd.DataFrame, names: tuple[str, ...]) -> pd.Series | None:
    """Extract a row as a Series indexed by period columns."""
    if df is None or df.empty:
        return None
    index_map = {str(i).strip().lower(): i for i in df.index}
    for name in names:
        key = name.lower()
        if key in index_map:
            return df.loc[index_map[key]]
    for name in names:
        key = name.lower()
        for label, original in index_map.items():
            if key in label:
                return df.loc[original]
    return None


def _to_float_series(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype=float)
    out = series.map(_safe_float)
    out.index = pd.to_datetime(out.index)
    return out.dropna().sort_index()


def _last_n(series: pd.Series, n: int = QUARTER_COUNT) -> pd.Series:
    if series.empty:
        return series
    return series.tail(n)


def _margin(numer: pd.Series, denom: pd.Series) -> pd.Series:
    if numer.empty or denom.empty:
        return pd.Series(dtype=float)
    aligned = pd.concat([numer.rename("n"), denom.rename("d")], axis=1).dropna()
    if aligned.empty:
        return pd.Series(dtype=float)
    mask = aligned["d"] != 0
    aligned = aligned.loc[mask]
    return (aligned["n"] / aligned["d"]).sort_index()


@cached_data(ttl=TTL_MEDIUM)
def get_quarterly_trends(ticker: str) -> dict[str, Any]:
    """
    Last ~8 quarters of growth, profitability, balance sheet, and cash flow.

    Returns chronologically ordered Series under keys used by the UI.
    """
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return {"symbol": "", "ok": False, "error": "Enter a ticker symbol.", "series": {}}

    t = get_ticker(symbol)
    if t is None:
        return {
            "symbol": symbol,
            "ok": False,
            "error": "Could not create ticker object.",
            "series": {},
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
            "error": "Failed to download quarterly statements.",
            "series": {},
        }

    revenue = _last_n(_to_float_series(_row_series(income, _REVENUE)))
    net_income = _last_n(_to_float_series(_row_series(income, _NET_INCOME)))
    operating_income = _last_n(_to_float_series(_row_series(income, _OPERATING_INCOME)))
    gross_profit = _last_n(_to_float_series(_row_series(income, _GROSS_PROFIT)))
    eps = _last_n(_to_float_series(_row_series(income, _DILUTED_EPS)))

    debt = _last_n(_to_float_series(_row_series(balance, _TOTAL_DEBT)))
    cash = _last_n(_to_float_series(_row_series(balance, _CASH)))
    equity = _last_n(_to_float_series(_row_series(balance, _EQUITY)))

    ocf = _last_n(_to_float_series(_row_series(cashflow, _OCF)))
    capex = _to_float_series(_row_series(cashflow, _CAPEX))
    # CapEx often negative in Yahoo; FCF = OCF - |CapEx| when CapEx is negative
    fcf = pd.Series(dtype=float)
    if not ocf.empty:
        if not capex.empty:
            aligned = pd.concat([ocf.rename("ocf"), capex.rename("capex")], axis=1).dropna()
            # CapEx reported as negative outflow → add; if positive spend → subtract
            fcf = aligned.apply(
                lambda r: r["ocf"] + r["capex"]
                if r["capex"] < 0
                else r["ocf"] - r["capex"],
                axis=1,
            )
            fcf = _last_n(fcf.sort_index())
        else:
            fcf = ocf.copy()

    gross_margin = _last_n(_margin(gross_profit, revenue))
    operating_margin = _last_n(_margin(operating_income, revenue))
    net_margin = _last_n(_margin(net_income, revenue))

    series = {
        "revenue": revenue,
        "net_income": net_income,
        "eps": eps,
        "operating_income": operating_income,
        "gross_margin": gross_margin,
        "operating_margin": operating_margin,
        "net_margin": net_margin,
        "debt": debt,
        "cash": cash,
        "equity": equity,
        "operating_cash_flow": ocf,
        "free_cash_flow": fcf,
    }

    any_data = any(isinstance(s, pd.Series) and not s.empty for s in series.values())
    if not any_data:
        return {
            "symbol": symbol,
            "ok": False,
            "error": "No quarterly financial rows found for this ticker.",
            "series": series,
        }

    return {"symbol": symbol, "ok": True, "error": None, "series": series}
