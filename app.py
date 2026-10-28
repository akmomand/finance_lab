"""Finance Lab — Streamlit entry point."""

import streamlit as st

from config import APP_TITLE, DEFAULT_TICKER, PAGE_CONFIG
from ui.company_view import render_company_page
from ui.macro_view import render_macro_page

st.set_page_config(**PAGE_CONFIG)

st.sidebar.title(APP_TITLE)
st.sidebar.caption("Macro indicators + public-company research")

page = st.sidebar.radio("Navigation", ["Macro", "Company"], index=0)

ticker = DEFAULT_TICKER
if page == "Company":
    ticker = (
        st.sidebar.text_input(
            "Ticker",
            value=DEFAULT_TICKER,
            help="US ticker symbol, e.g. AAPL or MSFT",
        )
        .strip()
        .upper()
    )

st.sidebar.markdown("---")
if st.sidebar.button("Clear data cache", help="Clears Streamlit cached Yahoo/FRED responses"):
    st.cache_data.clear()
    st.sidebar.success("Cache cleared — rerunning…")
    st.rerun()

st.sidebar.caption("Data: yfinance · FRED")
st.sidebar.caption(
    "If company data fails for every ticker, Yahoo may be rate-limiting. "
    "Wait ~1 minute, clear cache, then retry."
)

if page == "Macro":
    render_macro_page(st)
else:
    render_company_page(st, ticker)

st.caption("Finance Lab · market data via yfinance · macro via FRED · not investment advice")
