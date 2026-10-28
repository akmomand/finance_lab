"""FRED macro data stubs — implemented in Step 2."""

from __future__ import annotations

import pandas as pd

from config import FRED_API_KEY, FRED_SERIES


def get_fred_series(series_id: str) -> pd.DataFrame:
    """Fetch a single FRED series. Returns empty DataFrame on failure or missing key."""
    if not FRED_API_KEY:
        return pd.DataFrame()

    try:
        from fredapi import Fred

        fred = Fred(api_key=FRED_API_KEY)
        series = fred.get_series(series_id)
        if series is None or series.empty:
            return pd.DataFrame()
        return series.to_frame(name=series_id)
    except Exception:
        return pd.DataFrame()


def get_macro_snapshot() -> dict:
    """
    Placeholder macro snapshot for the dashboard.

    Step 2 will populate each series. Keys align with config.FRED_SERIES.
    """
    snapshot: dict = {
        "status": "not_implemented",
        "message": "Macro data fetch coming in Step 2",
        "series": {},
    }

    if not FRED_API_KEY:
        snapshot["message"] = "Set FRED_API_KEY in .env to enable FRED data"
        return snapshot

    for name, series_id in FRED_SERIES.items():
        snapshot["series"][name] = {
            "id": series_id,
            "data": pd.DataFrame(),  # filled in Step 2
        }

    return snapshot
