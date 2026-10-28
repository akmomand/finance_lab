"""Finance Lab — Streamlit entry point."""

import streamlit as st

from config import APP_TITLE, DEFAULT_TICKER, PAGE_CONFIG
from ui.company_view import render_company_page
from ui.macro_view import render_macro_page

st.set_page_config(**PAGE_CONFIG)

st.sidebar.title(APP_TITLE)
page = st.sidebar.radio("Navigation", ["Macro", "Company"], index=0)

ticker = DEFAULT_TICKER
if page == "Company":
    ticker = st.sidebar.text_input("Ticker", value=DEFAULT_TICKER).strip().upper()

if page == "Macro":
    render_macro_page(st)
else:
    render_company_page(st, ticker)

st.sidebar.markdown("---")
st.sidebar.caption("Data: yfinance · FRED")
st.caption("Finance Lab · market data via yfinance · macro via FRED")
