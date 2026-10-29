"""Shared yfinance session — prefers curl_cffi Chrome impersonation to reduce Yahoo blocks."""

from __future__ import annotations

from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def get_yf_session() -> Any | None:
    """Return a curl_cffi session when available; otherwise None (yfinance default)."""
    try:
        from curl_cffi import requests as curl_requests

        return curl_requests.Session(impersonate="chrome")
    except Exception:
        return None


def make_ticker(symbol: str):
    """Create a yfinance Ticker using the shared session when possible."""
    import yfinance as yf

    sym = (symbol or "").strip().upper()
    session = get_yf_session()
    if session is not None:
        try:
            return yf.Ticker(sym, session=session)
        except TypeError:
            # Older yfinance without session kwarg
            return yf.Ticker(sym)
    return yf.Ticker(sym)
