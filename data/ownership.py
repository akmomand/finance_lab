"""Institutional and insider ownership via yfinance."""

from __future__ import annotations

from typing import Any

import pandas as pd

from data.cache import TTL_MEDIUM, cached_data
from data.company import get_raw_info, get_ticker, _safe_float


@cached_data(ttl=TTL_MEDIUM)
def get_ownership(ticker: str) -> dict[str, Any]:
    symbol = (ticker or "").strip().upper()
    if not symbol:
        return {"symbol": "", "ok": False, "error": "Enter a ticker symbol."}

    info = get_raw_info(symbol) or {}
    t = get_ticker(symbol)
    if t is None:
        return {"symbol": symbol, "ok": False, "error": "Could not create ticker object."}

    held_inst = _safe_float(info.get("heldPercentInstitutions"))
    held_insiders = _safe_float(info.get("heldPercentInsiders"))

    institutions = pd.DataFrame()
    try:
        ih = getattr(t, "institutional_holders", None)
        if ih is not None and not getattr(ih, "empty", True):
            institutions = ih.copy().head(15)
    except Exception:
        pass

    major = pd.DataFrame()
    try:
        mh = getattr(t, "major_holders", None)
        if mh is not None and not getattr(mh, "empty", True):
            major = mh.copy()
    except Exception:
        pass

    insiders = pd.DataFrame()
    try:
        it = getattr(t, "insider_transactions", None)
        if it is not None and not getattr(it, "empty", True):
            insiders = it.copy().head(25)
    except Exception:
        pass

    # Summarize buys vs sells from insider transactions when possible
    buys = 0
    sells = 0
    if not insiders.empty:
        text_cols = [c for c in insiders.columns if insiders[c].dtype == object]
        for c in text_cols:
            for val in insiders[c].dropna().astype(str):
                low = val.lower()
                if "purchase" in low or "buy" in low or "acquisition" in low:
                    buys += 1
                elif "sale" in low or "sell" in low or "disposition" in low:
                    sells += 1
            if buys or sells:
                break

    ok = (
        held_inst is not None
        or held_insiders is not None
        or not institutions.empty
        or not insiders.empty
        or not major.empty
    )
    if not ok:
        return {
            "symbol": symbol,
            "ok": False,
            "error": "No ownership data available for this ticker.",
        }

    return {
        "symbol": symbol,
        "ok": True,
        "error": None,
        "held_institutions": held_inst,
        "held_insiders": held_insiders,
        "institutions": institutions,
        "major_holders": major,
        "insider_transactions": insiders,
        "insider_buys": buys,
        "insider_sells": sells,
    }
