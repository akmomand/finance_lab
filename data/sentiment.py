"""Analyst sentiment / price targets via yfinance."""

from __future__ import annotations

from typing import Any

import pandas as pd

from data.cache import TTL_MEDIUM, cached_data
from data.company import get_raw_info, get_ticker, _safe_float


def _recommendation_counts(ticker_obj) -> dict[str, int]:
    """Best-effort Strong Buy / Buy / Hold / Sell / Strong Sell tallies."""
    counts = {
        "strong_buy": 0,
        "buy": 0,
        "hold": 0,
        "sell": 0,
        "strong_sell": 0,
    }
    try:
        summary = getattr(ticker_obj, "recommendations_summary", None)
        if summary is not None and not getattr(summary, "empty", True):
            df = summary.copy()
            # Often columns like strongBuy, buy, hold, sell, strongSell on latest period row
            row = df.iloc[0]
            mapping = {
                "strong_buy": ("strongBuy", "strong buy", "Strong Buy"),
                "buy": ("buy", "Buy"),
                "hold": ("hold", "Hold"),
                "sell": ("sell", "Sell"),
                "strong_sell": ("strongSell", "strong sell", "Strong Sell"),
            }
            for key, names in mapping.items():
                for name in names:
                    if name in df.columns:
                        val = _safe_float(row[name])
                        if val is not None:
                            counts[key] = int(val)
                        break
            if sum(counts.values()) > 0:
                return counts
    except Exception:
        pass

    try:
        recs = getattr(ticker_obj, "recommendations", None)
        if recs is None or getattr(recs, "empty", True):
            return counts
        df = recs.copy().tail(40)
        col = None
        for c in df.columns:
            if str(c).lower() in ("to grade", "tograde", "firm"):
                continue
            if "grade" in str(c).lower() or str(c).lower() == "action":
                col = c
        # Prefer To Grade
        for c in df.columns:
            if str(c).lower().replace(" ", "") in ("tograde", "to_grade"):
                col = c
                break
        if col is None:
            # last string-like column
            for c in reversed(list(df.columns)):
                if df[c].dtype == object:
                    col = c
                    break
        if col is None:
            return counts

        for raw in df[col].dropna().astype(str):
            g = raw.strip().lower()
            if "strong buy" in g or g in ("strong_buy", "strongbuy"):
                counts["strong_buy"] += 1
            elif g in ("buy", "outperform", "overweight", "accumulate"):
                counts["buy"] += 1
            elif g in ("hold", "neutral", "equal-weight", "market perform", "peer perform"):
                counts["hold"] += 1
            elif g in ("sell", "underperform", "underweight", "reduce"):
                counts["sell"] += 1
            elif "strong sell" in g:
                counts["strong_sell"] += 1
    except Exception:
        pass
    return counts


@cached_data(ttl=TTL_MEDIUM)
def get_analyst_sentiment(ticker: str) -> dict[str, Any]:
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return {"symbol": "", "ok": False, "error": "Enter a ticker symbol."}

    info = get_raw_info(symbol) or {}
    t = get_ticker(symbol)

    price = _safe_float(
        info.get("currentPrice")
        or info.get("regularMarketPrice")
        or info.get("previousClose")
    )
    target = _safe_float(info.get("targetMeanPrice") or info.get("targetMedianPrice"))
    target_high = _safe_float(info.get("targetHighPrice"))
    target_low = _safe_float(info.get("targetLowPrice"))
    n_analysts = info.get("numberOfAnalystOpinions")
    rec_key = info.get("recommendationKey") or info.get("recommendationMean")

    counts = _recommendation_counts(t) if t is not None else {}
    has_counts = sum(counts.values()) > 0
    has_target = target is not None

    if not has_counts and not has_target and not rec_key:
        return {
            "symbol": symbol,
            "ok": False,
            "error": "No analyst sentiment data available for this ticker.",
        }

    upside = None
    if target is not None and price not in (None, 0):
        upside = (target - price) / price

    return {
        "symbol": symbol,
        "ok": True,
        "error": None,
        "price": price,
        "currency": info.get("currency") or "USD",
        "target_mean": target,
        "target_high": target_high,
        "target_low": target_low,
        "upside": upside,
        "n_analysts": n_analysts,
        "recommendation_key": rec_key,
        "counts": counts,
        "has_counts": has_counts,
    }
