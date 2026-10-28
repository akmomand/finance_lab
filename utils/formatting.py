"""Display formatting helpers."""

from __future__ import annotations

from typing import Any


def format_currency(value: Any, currency: str = "USD") -> str:
    if value is None:
        return "—"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "—"
    symbol = "$" if currency == "USD" else f"{currency} "
    return f"{symbol}{num:,.2f}"


def format_percent(value: Any, decimals: int = 2) -> str:
    if value is None:
        return "—"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "—"
    # Accept both ratio (0.05) and already-percent (5.0) heuristically
    if abs(num) <= 1:
        num *= 100
    return f"{num:.{decimals}f}%"


def format_number(value: Any, decimals: int = 2) -> str:
    if value is None:
        return "—"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{num:,.{decimals}f}"


def format_large_number(value: Any) -> str:
    """Market-cap style: 1.2T / 345.6B / 12.3M / 4.5K."""
    if value is None:
        return "—"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "—"

    sign = "-" if num < 0 else ""
    num = abs(num)

    for threshold, suffix in (
        (1e12, "T"),
        (1e9, "B"),
        (1e6, "M"),
        (1e3, "K"),
    ):
        if num >= threshold:
            return f"{sign}{num / threshold:.1f}{suffix}"
    return f"{sign}{num:,.0f}"
