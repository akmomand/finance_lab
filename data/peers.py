"""Peer comparison metrics via yfinance (user-selected peers + defaults)."""

from __future__ import annotations

from typing import Any

from data.cache import TTL_MEDIUM, cached_data
from data.company import get_raw_info, _safe_float

# Starter suggestions only — not a live peer search. User can edit freely.
DEFAULT_PEERS: dict[str, list[str]] = {
    "AAPL": ["MSFT", "GOOGL", "AMZN", "META"],
    "MSFT": ["AAPL", "GOOGL", "AMZN", "ORCL"],
    "GOOGL": ["META", "MSFT", "AMZN", "AAPL"],
    "AMZN": ["WMT", "MSFT", "GOOGL", "SHOP"],
    "META": ["GOOGL", "SNAP", "PINS", "MSFT"],
    "NVDA": ["AMD", "INTC", "AVGO", "TSM"],
    "AMD": ["NVDA", "INTC", "AVGO", "QCOM"],
    "TSLA": ["F", "GM", "RIVN", "LCID"],
    "JPM": ["BAC", "WFC", "C", "GS"],
    "XOM": ["CVX", "COP", "BP", "SHEL"],
    "JNJ": ["PFE", "MRK", "ABBV", "LLY"],
    "KO": ["PEP", "MNST", "KDP"],
    "DIS": ["NFLX", "CMCSA", "WBD", "PARA"],
}

SECTOR_DEFAULTS: dict[str, list[str]] = {
    "Technology": ["AAPL", "MSFT", "GOOGL", "NVDA"],
    "Communication Services": ["META", "GOOGL", "NFLX", "DIS"],
    "Consumer Cyclical": ["AMZN", "TSLA", "HD", "NKE"],
    "Financial Services": ["JPM", "BAC", "V", "MA"],
    "Healthcare": ["JNJ", "UNH", "LLY", "PFE"],
    "Energy": ["XOM", "CVX", "COP", "SLB"],
    "Consumer Defensive": ["PG", "KO", "PEP", "WMT"],
    "Industrials": ["CAT", "HON", "GE", "UNP"],
}


def suggest_peers(ticker: str, sector: str | None = None, limit: int = 4) -> list[str]:
    """Return suggested peer tickers (fixed map / sector fallback)."""
    symbol = (ticker or "").strip().upper()
    if symbol in DEFAULT_PEERS:
        return [p for p in DEFAULT_PEERS[symbol] if p != symbol][:limit]
    if sector and sector in SECTOR_DEFAULTS:
        return [p for p in SECTOR_DEFAULTS[sector] if p != symbol][:limit]
    return ["MSFT", "GOOGL", "AMZN"][:limit]


def parse_peer_input(text: str, primary: str, max_peers: int = 6) -> list[str]:
    """Parse comma/space-separated tickers; exclude primary; dedupe."""
    symbol = (primary or "").strip().upper()
    raw = (text or "").replace(";", ",").replace(" ", ",")
    parts = [p.strip().upper() for p in raw.split(",") if p.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if p == symbol or p in seen:
            continue
        seen.add(p)
        out.append(p)
        if len(out) >= max_peers:
            break
    return out


def _normalize_ratio(value: float | None) -> float | None:
    if value is None:
        return None
    if abs(value) > 1.5:
        return value / 100.0
    return value


def _normalize_debt_equity(value: float | None) -> float | None:
    if value is None:
        return None
    if abs(value) > 10:
        return value / 100.0
    return value


def _peer_metrics(symbol: str) -> dict[str, Any]:
    info = get_raw_info(symbol) or {}
    if not info or (info.get("_error") and not info.get("shortName") and not info.get("trailingPE")):
        return {"symbol": symbol, "ok": False, "error": info.get("_error")}

    fcf = _safe_float(info.get("freeCashflow"))
    revenue = _safe_float(info.get("totalRevenue"))
    fcf_margin = (fcf / revenue) if fcf is not None and revenue not in (None, 0) else None

    name = info.get("shortName") or info.get("longName") or symbol
    return {
        "symbol": symbol,
        "ok": True,
        "name": name,
        "pe": _safe_float(info.get("trailingPE")),
        "forward_pe": _safe_float(info.get("forwardPE")),
        "roe": _normalize_ratio(_safe_float(info.get("returnOnEquity"))),
        "gross_margin": _normalize_ratio(_safe_float(info.get("grossMargins"))),
        "fcf_margin": fcf_margin,
        "debt_to_equity": _normalize_debt_equity(_safe_float(info.get("debtToEquity"))),
        "market_cap": _safe_float(info.get("marketCap")),
        "price": _safe_float(
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        ),
    }


@cached_data(ttl=TTL_MEDIUM)
def get_peer_comparison(primary: str, peers: tuple[str, ...]) -> dict[str, Any]:
    """
    Compare primary ticker vs peers on key multiples / quality metrics.

    `peers` is a tuple so Streamlit cache hashing stays stable.
    """
    symbol = (primary or "").strip().upper()
    if not symbol:
        return {"ok": False, "error": "Enter a ticker symbol.", "rows": []}

    tickers = [symbol] + [p for p in peers if p and p.upper() != symbol]
    rows: list[dict[str, Any]] = []
    for t in tickers:
        rows.append(_peer_metrics(t.upper()))

    if not any(r.get("ok") for r in rows):
        return {
            "ok": False,
            "error": "Could not load peer metrics. Yahoo may be rate-limiting requests.",
            "rows": rows,
            "primary": symbol,
        }

    return {"ok": True, "error": None, "rows": rows, "primary": symbol}
