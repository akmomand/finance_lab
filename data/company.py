"""Company / ticker data via yfinance — light stubs for Step 1."""

from __future__ import annotations

from typing import Any


def get_ticker(ticker: str):
    """Return a yfinance Ticker object, or None on failure."""
    try:
        import yfinance as yf

        return yf.Ticker(ticker.strip().upper())
    except Exception:
        return None


def get_company_info(ticker: str) -> dict[str, Any]:
    """
    Fetch basic company info for Overview smoke tests.

    Returns a small dict with name/price fields, or empty on failure.
    """
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return {}

    try:
        t = get_ticker(symbol)
        if t is None:
            return {}

        info = t.info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        return {
            "symbol": symbol,
            "name": info.get("shortName") or info.get("longName") or symbol,
            "price": price,
            "currency": info.get("currency"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
        }
    except Exception:
        return {"symbol": symbol}
