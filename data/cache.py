"""Streamlit cache helpers and TTL constants."""

from __future__ import annotations

from typing import Callable, TypeVar

import streamlit as st

T = TypeVar("T")

# Default TTLs (seconds)
TTL_SHORT = 60 * 15       # 15 minutes
TTL_MEDIUM = 60 * 60      # 1 hour
TTL_LONG = 60 * 60 * 6    # 6 hours


def cached_data(ttl: int = TTL_MEDIUM) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator factory wrapping st.cache_data with a shared TTL."""
    return st.cache_data(ttl=ttl)
