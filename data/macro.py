"""FRED macro data fetchers for the dashboard."""

from __future__ import annotations

from typing import Any

import pandas as pd

from config import FRED_API_KEY, FRED_SERIES
from data.cache import TTL_LONG, cached_data

# Display metadata for each indicator (units, preferred chart transform)
MACRO_META: dict[str, dict[str, str]] = {
    "cpi": {
        "label": "CPI (All Urban Consumers)",
        "unit": "Index",
        "description": "Consumer Price Index for All Urban Consumers",
        "yoy": "true",
    },
    "gdp": {
        "label": "US GDP",
        "unit": "Billions USD",
        "description": "Gross Domestic Product (nominal)",
        "yoy": "true",
    },
    "pce": {
        "label": "PCE Price Index",
        "unit": "Index",
        "description": "Personal Consumption Expenditures Price Index (Fed preferred inflation gauge)",
        "yoy": "true",
    },
    "unemployment": {
        "label": "Unemployment Rate",
        "unit": "%",
        "description": "Civilian unemployment rate",
        "yoy": "false",
    },
    "manufacturing_pmi": {
        "label": "Manufacturing Employment",
        "unit": "Thousands",
        "description": "Manufacturing payrolls — free FRED proxy for manufacturing cycle (ISM PMI is proprietary)",
        "yoy": "true",
    },
}


@cached_data(ttl=TTL_LONG)
def get_fred_series(series_id: str) -> pd.DataFrame:
    """Fetch a single FRED series as a DataFrame with DatetimeIndex and column 'value'."""
    if not FRED_API_KEY:
        return pd.DataFrame()

    try:
        from fredapi import Fred

        fred = Fred(api_key=FRED_API_KEY)
        series = fred.get_series(series_id)
        if series is None or (hasattr(series, "empty") and series.empty):
            return pd.DataFrame()

        df = series.to_frame(name="value")
        df.index = pd.to_datetime(df.index)
        df = df.sort_index().dropna()
        df.attrs["series_id"] = series_id
        return df
    except Exception:
        return pd.DataFrame()


def compute_yoy_pct(df: pd.DataFrame, periods: int = 12) -> pd.Series:
    """Year-over-year percent change. Use periods=4 for quarterly GDP."""
    if df.empty or "value" not in df.columns:
        return pd.Series(dtype=float)
    return df["value"].pct_change(periods=periods) * 100


def _latest_metrics(name: str, df: pd.DataFrame) -> dict[str, Any]:
    """Build latest level + YoY (or MoM for rates) for metric cards."""
    meta = MACRO_META.get(name, {})
    if df.empty:
        return {
            "label": meta.get("label", name),
            "series_id": FRED_SERIES.get(name, ""),
            "latest": None,
            "latest_date": None,
            "yoy": None,
            "prior": None,
            "delta": None,
            "unit": meta.get("unit", ""),
            "description": meta.get("description", ""),
        }

    latest = float(df["value"].iloc[-1])
    latest_date = df.index[-1]
    prior = float(df["value"].iloc[-2]) if len(df) > 1 else None
    delta = (latest - prior) if prior is not None else None

    # YoY: monthly series use 12; GDP is quarterly → 4
    is_gdp = name == "gdp"
    yoy_periods = 4 if is_gdp else 12
    yoy = None
    if meta.get("yoy") == "true" and len(df) > yoy_periods:
        yoy_series = compute_yoy_pct(df, periods=yoy_periods)
        if not yoy_series.empty and pd.notna(yoy_series.iloc[-1]):
            yoy = float(yoy_series.iloc[-1])

    return {
        "label": meta.get("label", name),
        "series_id": FRED_SERIES.get(name, ""),
        "latest": latest,
        "latest_date": latest_date,
        "yoy": yoy,
        "prior": prior,
        "delta": delta,
        "unit": meta.get("unit", ""),
        "description": meta.get("description", ""),
        "data": df,
        "yoy_series": compute_yoy_pct(df, periods=yoy_periods) if meta.get("yoy") == "true" else None,
    }


@cached_data(ttl=TTL_LONG)
def get_macro_snapshot() -> dict[str, Any]:
    """
    Load all configured FRED series and compute card metrics.

    Returns status, optional message, and a 'metrics' dict keyed by indicator name.
    """
    if not FRED_API_KEY:
        return {
            "status": "missing_key",
            "message": "Set FRED_API_KEY in .env to load macro data from FRED.",
            "metrics": {},
        }

    metrics: dict[str, Any] = {}
    errors: list[str] = []

    for name, series_id in FRED_SERIES.items():
        df = get_fred_series(series_id)
        if df.empty:
            errors.append(series_id)
            metrics[name] = _latest_metrics(name, df)
        else:
            metrics[name] = _latest_metrics(name, df)

    if errors and len(errors) == len(FRED_SERIES):
        return {
            "status": "error",
            "message": "Could not fetch FRED series. Check your API key and network.",
            "metrics": metrics,
        }

    return {
        "status": "ok",
        "message": None,
        "metrics": metrics,
        "partial_errors": errors,
    }
