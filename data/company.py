"""Company / ticker data via yfinance."""

from __future__ import annotations

from typing import Any

from data.cache import TTL_MEDIUM, cached_data


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


@cached_data(ttl=TTL_MEDIUM)
def get_raw_info(ticker: str) -> dict[str, Any]:
    """Cached raw yfinance `.info` dict (empty on failure)."""
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return {}
    try:
        t = get_ticker(symbol)
        if t is None:
            return {}
        info = t.info or {}
        return dict(info) if isinstance(info, dict) else {}
    except Exception:
        return {}


@cached_data(ttl=TTL_MEDIUM)
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
    if not info:
        return {
            "symbol": symbol,
            "ok": False,
            "error": "Could not load company data. Check the ticker or try again.",
        }

    # Reject obvious non-equity misses (empty name + no price)
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
            "error": f"No quote data found for '{symbol}'.",
        }

    high_52 = _safe_float(info.get("fiftyTwoWeekHigh"))
    low_52 = _safe_float(info.get("fiftyTwoWeekLow"))
    div_yield = _safe_float(info.get("dividendYield"))
    # yfinance sometimes returns yield already as ratio (0.005) or percent-like
    if div_yield is not None and div_yield > 1:
        div_yield = div_yield / 100.0

    overview: dict[str, Any] = {
        "symbol": symbol,
        "ok": True,
        "error": None,
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
        # Structured segment / geo rarely available via free yfinance
        "revenue_segments": _extract_revenue_segments(info),
        "geographic_exposure": _extract_geographic_exposure(info),
    }
    return overview


def _extract_revenue_segments(info: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Best-effort segment list.

    Yahoo/yfinance generally does not provide product-segment tables in `.info`.
    Returns [] when unavailable so the UI can show an honest empty state.
    """
    # Future hook: plug another free source here if one becomes available.
    _ = info
    return []


def _extract_geographic_exposure(info: dict[str, Any]) -> list[dict[str, Any]]:
    """Best-effort geography list; usually empty on free yfinance."""
    country = info.get("country")
    if country:
        return [{"region": country, "note": "Headquarters / domicile (not revenue mix)"}]
    return []


# Back-compat for earlier steps / smoke tests
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
