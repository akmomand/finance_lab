"""Earnings history / surprise data via yfinance."""

from __future__ import annotations

from typing import Any

import pandas as pd

from data.cache import TTL_MEDIUM, cached_data
from data.company import get_ticker, _safe_float

QUARTER_COUNT = 8
# Yahoo earnings_dates often has years of history — pull enough for charts
EARNINGS_DATES_LIMIT = 24


def _from_earnings_dates(ticker_obj) -> pd.DataFrame:
    """Parse get_earnings_dates / earnings_dates into a clean frame."""
    df = None
    try:
        if hasattr(ticker_obj, "get_earnings_dates"):
            df = ticker_obj.get_earnings_dates(limit=EARNINGS_DATES_LIMIT)
        if (df is None or df.empty) and hasattr(ticker_obj, "earnings_dates"):
            df = ticker_obj.earnings_dates
    except Exception:
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    # Normalize column names
    colmap = {c: str(c).strip() for c in out.columns}
    out = out.rename(columns=colmap)

    # Common columns: EPS Estimate, Reported EPS, Surprise(%)
    rename = {}
    for c in out.columns:
        cl = c.lower()
        if "estimate" in cl and "eps" in cl:
            rename[c] = "estimate"
        elif "reported" in cl or (cl == "eps" or "actual" in cl):
            rename[c] = "actual"
        elif "surprise" in cl:
            rename[c] = "surprise_pct"
    out = out.rename(columns=rename)

    if "estimate" not in out.columns and "actual" not in out.columns:
        return pd.DataFrame()

    out = out.reset_index()
    date_col = out.columns[0]
    out = out.rename(columns={date_col: "date"})
    out["date"] = pd.to_datetime(out["date"], errors="coerce", utc=True)
    out["date"] = out["date"].dt.tz_localize(None)

    for col in ("estimate", "actual", "surprise_pct"):
        if col in out.columns:
            out[col] = out[col].map(_safe_float)

    if "surprise_pct" not in out.columns and "estimate" in out.columns and "actual" in out.columns:
        out["surprise_pct"] = out.apply(
            lambda r: (
                ((r["actual"] - r["estimate"]) / abs(r["estimate"]) * 100.0)
                if r.get("estimate") not in (None, 0) and r.get("actual") is not None
                else None
            ),
            axis=1,
        )

    out = out.dropna(subset=["date"]).sort_values("date")
    # Prefer rows that have at least an actual or estimate
    keep = [c for c in ("estimate", "actual") if c in out.columns]
    if keep:
        out = out.dropna(subset=keep, how="all")
    return out.tail(QUARTER_COUNT)


def _from_earnings_history(ticker_obj) -> pd.DataFrame:
    """Fallback: earnings_history DataFrame."""
    try:
        hist = getattr(ticker_obj, "earnings_history", None)
        if hist is None or (hasattr(hist, "empty") and hist.empty):
            return pd.DataFrame()
        df = hist.copy().reset_index()
    except Exception:
        return pd.DataFrame()

    rename = {}
    for c in df.columns:
        cl = str(c).lower()
        if "quarter" in cl or cl in ("index", "date", "earnings date"):
            rename[c] = "date"
        elif "eps estimate" in cl or cl == "epsestimated":
            rename[c] = "estimate"
        elif "eps actual" in cl or "reported" in cl:
            rename[c] = "actual"
        elif "surprise" in cl:
            rename[c] = "surprise_pct"
    df = df.rename(columns=rename)
    if "date" not in df.columns:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ("estimate", "actual", "surprise_pct"):
        if col in df.columns:
            df[col] = df[col].map(_safe_float)
    df = df.dropna(subset=["date"]).sort_values("date")
    return df.tail(QUARTER_COUNT)


@cached_data(ttl=TTL_MEDIUM)
def get_earnings_analysis(ticker: str) -> dict[str, Any]:
    """Last ~8 quarters of EPS estimate / actual / surprise."""
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return {"symbol": "", "ok": False, "error": "Enter a ticker symbol.", "table": None}

    t = get_ticker(symbol)
    if t is None:
        return {
            "symbol": symbol,
            "ok": False,
            "error": "Could not create ticker object.",
            "table": None,
        }

    df = _from_earnings_dates(t)
    if df.empty:
        df = _from_earnings_history(t)

    if df.empty:
        return {
            "symbol": symbol,
            "ok": False,
            "error": "No earnings estimate/actual history available for this ticker.",
            "table": None,
        }

    # Quarter labels
    labels = []
    for ts in df["date"]:
        q = (ts.month - 1) // 3 + 1
        labels.append(f"{ts.year} Q{q}")
    df = df.copy()
    df["quarter"] = labels

    beats = 0
    misses = 0
    if "surprise_pct" in df.columns:
        for v in df["surprise_pct"]:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                continue
            if v > 0:
                beats += 1
            elif v < 0:
                misses += 1

    return {
        "symbol": symbol,
        "ok": True,
        "error": None,
        "table": df,
        "beats": beats,
        "misses": misses,
        "avg_surprise": (
            float(df["surprise_pct"].dropna().mean())
            if "surprise_pct" in df.columns and not df["surprise_pct"].dropna().empty
            else None
        ),
    }
