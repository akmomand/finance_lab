"""Fundamental quality scorecard from yfinance."""

from __future__ import annotations

from typing import Any, Literal

import pandas as pd

from config import SCORECARD_METRICS
from data.cache import TTL_MEDIUM, cached_data
from data.company import get_raw_info, get_ticker, _safe_float

Health = Literal["strong", "watch", "concern", "na"]


def _normalize_ratio(value: float | None) -> float | None:
    """Normalize Yahoo ratios that may be percent-like (e.g. 28 → 0.28)."""
    if value is None:
        return None
    # ROE / margins often arrive as 0.28; sometimes as 28
    if abs(value) > 1.5:
        return value / 100.0
    return value


def _normalize_debt_equity(value: float | None) -> float | None:
    """Yahoo debtToEquity is commonly expressed as percent (e.g. 150 → 1.50)."""
    if value is None:
        return None
    if abs(value) > 10:
        return value / 100.0
    return value


def _first_col(df: pd.DataFrame) -> pd.Series | None:
    if df is None or df.empty:
        return None
    return df.iloc[:, 0]


def _row_value(series: pd.Series | None, names: tuple[str, ...]) -> float | None:
    if series is None:
        return None
    index_map = {str(i).strip().lower(): i for i in series.index}
    for name in names:
        key = name.lower()
        if key in index_map:
            return _safe_float(series[index_map[key]])
    # fuzzy contains
    for name in names:
        key = name.lower()
        for label, original in index_map.items():
            if key in label:
                return _safe_float(series[original])
    return None


def _compute_roic(ticker_obj) -> float | None:
    """Approximate ROIC = NOPAT / (equity + debt − cash) from latest annual statements."""
    try:
        income = ticker_obj.financials
        balance = ticker_obj.balance_sheet
    except Exception:
        return None

    inc = _first_col(income)
    bal = _first_col(balance)
    if inc is None or bal is None:
        return None

    ebit = _row_value(
        inc,
        (
            "EBIT",
            "Operating Income",
            "Operating Income or Loss",
        ),
    )
    tax_provision = _row_value(inc, ("Tax Provision", "Income Tax Expense"))
    pretax = _row_value(
        inc,
        (
            "Pretax Income",
            "Income Before Tax",
            "EBT",
        ),
    )

    tax_rate = None
    if tax_provision is not None and pretax not in (None, 0):
        tax_rate = max(0.0, min(0.40, abs(tax_provision / pretax)))
    if tax_rate is None:
        tax_rate = 0.21

    if ebit is None:
        return None
    nopat = ebit * (1.0 - tax_rate)

    equity = _row_value(
        bal,
        (
            "Stockholders Equity",
            "Total Stockholder Equity",
            "Common Stock Equity",
            "Total Equity Gross Minority Interest",
        ),
    )
    total_debt = _row_value(
        bal,
        (
            "Total Debt",
            "Net Debt",
            "Long Term Debt",
        ),
    )
    # If Net Debt was picked, prefer Total Debt when both exist — already ordered
    cash = _row_value(
        bal,
        (
            "Cash Cash Equivalents And Short Term Investments",
            "Cash And Cash Equivalents",
            "Cash Financial",
        ),
    )

    if equity is None:
        return None
    debt = total_debt or 0.0
    cash_val = cash or 0.0
    invested = equity + debt - cash_val
    if invested is None or invested <= 0:
        return None
    return nopat / invested


def grade_metric(key: str, value: float | None) -> Health:
    spec = SCORECARD_METRICS.get(key)
    if not spec or value is None:
        return "na"
    green = float(spec["green"])
    yellow = float(spec["yellow"])
    if spec.get("higher_is_better", True):
        if value >= green:
            return "strong"
        if value >= yellow:
            return "watch"
        return "concern"
    # lower is better
    if value <= green:
        return "strong"
    if value <= yellow:
        return "watch"
    return "concern"


@cached_data(ttl=TTL_MEDIUM)
def get_fundamental_scorecard(ticker: str) -> dict[str, Any]:
    """
    Build the color-coded fundamental scorecard.

    Returns ok flag, per-metric rows, and a simple tallies summary.
    """
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return {"symbol": "", "ok": False, "error": "Enter a ticker symbol.", "rows": []}

    info = get_raw_info(symbol)
    if not info:
        return {
            "symbol": symbol,
            "ok": False,
            "error": "Could not load fundamentals for scorecard.",
            "rows": [],
        }

    t = get_ticker(symbol)

    roe = _normalize_ratio(_safe_float(info.get("returnOnEquity")))
    gross_margin = _normalize_ratio(_safe_float(info.get("grossMargins")))
    debt_to_equity = _normalize_debt_equity(_safe_float(info.get("debtToEquity")))
    current_ratio = _safe_float(info.get("currentRatio"))

    fcf = _safe_float(info.get("freeCashflow"))
    revenue = _safe_float(info.get("totalRevenue"))
    fcf_margin = (fcf / revenue) if fcf is not None and revenue not in (None, 0) else None

    roic = _compute_roic(t) if t is not None else None
    if roic is None:
        # Soft fallback: ROA as a weaker invested-capital proxy is misleading —
        # leave None rather than fake ROIC.
        roic = None

    values: dict[str, float | None] = {
        "roe": roe,
        "roic": roic,
        "gross_margin": gross_margin,
        "debt_to_equity": debt_to_equity,
        "current_ratio": current_ratio,
        "fcf_margin": fcf_margin,
    }

    rows: list[dict[str, Any]] = []
    tallies = {"strong": 0, "watch": 0, "concern": 0, "na": 0}

    for key, spec in SCORECARD_METRICS.items():
        value = values.get(key)
        health = grade_metric(key, value)
        tallies[health] = tallies.get(health, 0) + 1
        rows.append(
            {
                "key": key,
                "metric": spec["label"],
                "value": value,
                "format": spec["format"],
                "health": health,
                "help": spec.get("help", ""),
                "green": spec["green"],
                "yellow": spec["yellow"],
                "higher_is_better": spec.get("higher_is_better", True),
            }
        )

    return {
        "symbol": symbol,
        "ok": True,
        "error": None,
        "rows": rows,
        "tallies": tallies,
    }
