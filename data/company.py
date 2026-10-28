"""Company / ticker data via yfinance."""

from __future__ import annotations

from typing import Any

from data.cache import TTL_SHORT, cached_data


def get_ticker(ticker: str):
    """Return a yfinance Ticker object, or None on failure."""
    try:
        import yfinance as yf

        return yf.Ticker((ticker or "").strip().upper())
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


@cached_data(ttl=TTL_SHORT)
def get_raw_info(ticker: str) -> dict[str, Any]:
    """
    Cached company quote/fundamentals payload.

    Always returns a dict. On failure includes `_error` and optionally partial
    fields from fast_info / history so the UI can still show a quote.
    Empty failures are short-TTL cached to limit Yahoo hammering, but still
    surface a clear `_error` (e.g. rate limit).
    """
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return {"_error": "Enter a ticker symbol."}

    t = get_ticker(symbol)
    if t is None:
        return {"_error": "Could not initialize yfinance ticker."}

    info: dict[str, Any] = {}
    err: str | None = None

    try:
        raw = t.info
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
                "Yahoo Finance rate limit hit. Wait a minute, then use "
                "**Clear data cache** in the sidebar and retry."
            )
        else:
            err = f"Yahoo quote fetch failed: {type(exc).__name__}"

    # Merge fast_info / last close when `.info` is thin or missing
    if not info or not (info.get("shortName") or info.get("longName") or info.get("currentPrice")):
        partial = _fast_info_dict(t)
        for k, v in partial.items():
            info.setdefault(k, v)
        if info.get("currentPrice") is None:
            px = _history_price(t)
            if px is not None:
                info["currentPrice"] = px
                info["regularMarketPrice"] = px

    if not info:
        return {
            "_error": err
            or "Could not load company data. Check the ticker, wait if rate-limited, then retry."
        }

    if err:
        info["_error"] = err
        info["_partial"] = True
    return info


@cached_data(ttl=TTL_SHORT)
def get_company_overview(ticker: str) -> dict[str, Any]:
    """
    Normalized company overview for the Overview section.

    Includes basics, business summary, and best-effort segment / geo notes.
    yfinance does not expose structured revenue-segment or geographic breakdowns
    for most tickers; those fields are filled only when present.
    """
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return {"symbol": "", "ok": False, "error": "Enter a ticker symbol."}

    info = get_raw_info(symbol)
    soft_error = info.get("_error")
    # Treat as hard failure only when we have essentially nothing useful
    useful = any(
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
    if not useful:
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

    overview: dict[str, Any] = {
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
    return overview


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
