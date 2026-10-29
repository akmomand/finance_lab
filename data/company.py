"""Company / ticker data via yfinance."""

from __future__ import annotations

import time
from typing import Any

from data.cache import TTL_MEDIUM, cached_data
from data.yf_session import make_ticker


def get_ticker(ticker: str):
    """Return a yfinance Ticker object (shared curl_cffi session when available)."""
    try:
        return make_ticker(ticker)
    except Exception:
        return None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_rate_limit(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    return "ratelimit" in name or "too many requests" in msg or "rate limit" in msg


def _fast_info_dict(ticker_obj) -> dict[str, Any]:
    """Map yfinance fast_info into a partial `.info`-like dict."""
    out: dict[str, Any] = {}
    try:
        fi = ticker_obj.fast_info
    except Exception:
        return out

    def g(*names: str) -> Any:
        for n in names:
            try:
                if hasattr(fi, n):
                    return getattr(fi, n)
                if hasattr(fi, "get"):
                    return fi.get(n)
            except Exception:
                continue
        return None

    price = g("last_price", "lastPrice", "regular_market_price")
    if price is not None:
        out["currentPrice"] = price
        out["regularMarketPrice"] = price
    mcap = g("market_cap", "marketCap")
    if mcap is not None:
        out["marketCap"] = mcap
    high = g("year_high", "fifty_two_week_high")
    low = g("year_low", "fifty_two_week_low")
    if high is not None:
        out["fiftyTwoWeekHigh"] = high
    if low is not None:
        out["fiftyTwoWeekLow"] = low
    prev = g("previous_close", "previousClose")
    if prev is not None:
        out["previousClose"] = prev
    currency = g("currency")
    if currency:
        out["currency"] = currency
    return out


def _history_price(ticker_obj) -> float | None:
    try:
        hist = ticker_obj.history(period="5d", auto_adjust=True)
        if hist is not None and not hist.empty and "Close" in hist.columns:
            return float(hist["Close"].iloc[-1])
    except Exception:
        return None
    return None


def _useful(info: dict[str, Any]) -> bool:
    return any(
        info.get(k) is not None
        for k in (
            "shortName",
            "longName",
            "currentPrice",
            "regularMarketPrice",
            "previousClose",
            "marketCap",
        )
    )


def _fetch_info_once(ticker_obj) -> tuple[dict[str, Any], str | None]:
    """Single attempt: full info, then fast_info / history fallbacks."""
    info: dict[str, Any] = {}
    err: str | None = None

    try:
        raw = ticker_obj.info
        if isinstance(raw, dict) and raw:
            info = dict(raw)
        elif raw:
            try:
                info = dict(raw)
            except Exception:
                info = {}
    except Exception as exc:
        if _is_rate_limit(exc):
            err = (
                "Yahoo Finance rate limit hit. Wait a bit, click **Clear data cache**, then retry. "
                "Also ensure `curl_cffi` is installed (`pip install -U yfinance curl_cffi`)."
            )
        else:
            err = f"Yahoo quote fetch failed: {type(exc).__name__}: {exc}"

    if not _useful(info):
        partial = _fast_info_dict(ticker_obj)
        for k, v in partial.items():
            info.setdefault(k, v)
        if info.get("currentPrice") is None:
            px = _history_price(ticker_obj)
            if px is not None:
                info["currentPrice"] = px
                info["regularMarketPrice"] = px

    if err and _useful(info):
        info["_error"] = err
        info["_partial"] = True
    return info, err


def _fetch_raw_info_uncached(symbol: str) -> dict[str, Any]:
    """Fetch with short retries. Raises on hard failure so Streamlit will not cache it."""
    t = get_ticker(symbol)
    if t is None:
        raise RuntimeError("Could not initialize yfinance ticker.")

    last_err: str | None = None
    for attempt in range(3):
        info, err = _fetch_info_once(t)
        last_err = err
        if _useful(info):
            return info
        if attempt < 2:
            time.sleep(1.5 * (attempt + 1))
            t = get_ticker(symbol) or t

    raise RuntimeError(
        last_err
        or "Could not load company data. Check the ticker, wait if rate-limited, then retry."
    )


@cached_data(ttl=TTL_MEDIUM)
def _get_raw_info_cached(ticker: str) -> dict[str, Any]:
    """Cache successful fetches only (exceptions are not cached by Streamlit)."""
    symbol = (ticker or "").strip().upper()
    if not symbol:
        raise ValueError("Enter a ticker symbol.")
    return _fetch_raw_info_uncached(symbol)


def get_raw_info(ticker: str) -> dict[str, Any]:
    """
    Company quote/fundamentals payload.

    Successes are cached. Failures return ``{_error: ...}`` and are not cached,
    so a later retry can succeed after Yahoo rate limits clear.
    """
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return {"_error": "Enter a ticker symbol."}
    try:
        return _get_raw_info_cached(symbol)
    except Exception as exc:
        return {"_error": str(exc)}


def get_company_overview(ticker: str) -> dict[str, Any]:
    """Normalized company overview for the Overview section."""
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return {"symbol": "", "ok": False, "error": "Enter a ticker symbol."}

    info = get_raw_info(symbol)
    soft_error = info.get("_error")
    if not _useful(info):
        return {
            "symbol": symbol,
            "ok": False,
            "error": soft_error
            or "Could not load company data. Check the ticker or try again.",
        }

    name = info.get("longName") or info.get("shortName")
    price = _safe_float(
        info.get("currentPrice")
        or info.get("regularMarketPrice")
        or info.get("previousClose")
    )
    if not name and price is None:
        return {
            "symbol": symbol,
            "ok": False,
            "error": soft_error or f"No quote data found for '{symbol}'.",
        }

    high_52 = _safe_float(info.get("fiftyTwoWeekHigh"))
    low_52 = _safe_float(info.get("fiftyTwoWeekLow"))
    div_yield = _safe_float(info.get("dividendYield"))
    if div_yield is not None and div_yield > 1:
        div_yield = div_yield / 100.0

    return {
        "symbol": symbol,
        "ok": True,
        "error": None,
        "warning": soft_error if info.get("_partial") else None,
        "name": name or symbol,
        "ticker": symbol,
        "sector": info.get("sector") or "—",
        "industry": info.get("industry") or "—",
        "market_cap": _safe_float(info.get("marketCap")),
        "enterprise_value": _safe_float(info.get("enterpriseValue")),
        "price": price,
        "currency": info.get("currency") or "USD",
        "fifty_two_week_high": high_52,
        "fifty_two_week_low": low_52,
        "beta": _safe_float(info.get("beta")),
        "dividend_yield": div_yield,
        "summary": (info.get("longBusinessSummary") or "").strip(),
        "website": info.get("website"),
        "country": info.get("country"),
        "full_time_employees": info.get("fullTimeEmployees"),
        "exchange": info.get("exchange") or info.get("fullExchangeName"),
        "revenue_segments": _extract_revenue_segments(info),
        "geographic_exposure": _extract_geographic_exposure(info),
    }


def _extract_revenue_segments(info: dict[str, Any]) -> list[dict[str, Any]]:
    _ = info
    return []


def _extract_geographic_exposure(info: dict[str, Any]) -> list[dict[str, Any]]:
    country = info.get("country")
    if country:
        return [{"region": country, "note": "Headquarters / domicile (not revenue mix)"}]
    return []


def get_company_info(ticker: str) -> dict[str, Any]:
    ov = get_company_overview(ticker)
    if not ov.get("ok"):
        return {"symbol": ov.get("symbol", ticker)}
    return {
        "symbol": ov["symbol"],
        "name": ov.get("name"),
        "price": ov.get("price"),
        "currency": ov.get("currency"),
        "sector": ov.get("sector"),
        "industry": ov.get("industry"),
        "market_cap": ov.get("market_cap"),
    }
