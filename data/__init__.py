"""Data access layer (macro + company)."""

from data.company import get_company_info, get_ticker
from data.macro import get_fred_series, get_macro_snapshot

__all__ = [
    "get_company_info",
    "get_fred_series",
    "get_macro_snapshot",
    "get_ticker",
]
