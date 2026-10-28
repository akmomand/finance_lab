"""Dividend analysis UI."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from data.dividends import get_dividend_analysis
from utils.formatting import format_currency, format_number, format_percent


def render_dividend_analysis(st, ticker: str) -> None:
    symbol = (ticker or "").strip().upper()
    with st.spinner(f"Loading dividends for {symbol}…"):
        data = get_dividend_analysis(symbol)

    if not data.get("ok"):
        st.error(data.get("error") or "Failed to load dividend data.")
        return

    currency = data.get("currency") or "USD"
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Dividend Yield",
        format_percent(data.get("yield"), decimals=2)
        if data.get("yield") is not None
        else "—",
    )
    c2.metric(
        "Payout Ratio",
        format_percent(data.get("payout_ratio"), decimals=1)
        if data.get("payout_ratio") is not None
        else "—",
    )
    c3.metric(
        "5Y Div Growth (CAGR)",
        format_percent(data.get("growth_5y"), decimals=1)
        if data.get("growth_5y") is not None
        else "—",
    )
    c4.metric("Years of Increases", data.get("consecutive_increases", 0))

    rate = data.get("dividend_rate")
    if rate is not None:
        st.caption(f"Indicated annual dividend rate: {format_currency(rate, currency)}")
    if data.get("ex_dividend_date"):
        st.caption(f"Ex-dividend date (Yahoo): {data['ex_dividend_date']}")

    annual = data.get("annual")
    if annual is not None and not getattr(annual, "empty", True):
        st.markdown("##### Annual dividends")
        years = [str(y) for y in annual.index.tolist()]
        vals = annual.astype(float).tolist()
        fig = go.Figure(
            data=[go.Bar(x=years, y=vals, marker_color="#1f77b4", name="Annual DPS")]
        )
        fig.update_layout(
            title="Annual dividends per share",
            height=320,
            template="plotly_white",
            showlegend=False,
            margin=dict(l=40, r=20, t=50, b=40),
            yaxis_title=currency,
        )
        st.plotly_chart(fig, use_container_width=True)

        table = pd.DataFrame(
            {
                "Year": years,
                "Total DPS": [format_number(v, 3) for v in vals],
            }
        )
        st.dataframe(table, use_container_width=True, hide_index=True)

    history = data.get("history")
    if history is not None and not getattr(history, "empty", True):
        st.markdown("##### Recent dividend payments")
        recent = history.sort_index().tail(16)
        recent_df = pd.DataFrame(
            {
                "Date": [d.strftime("%Y-%m-%d") for d in pd.to_datetime(recent.index)],
                "Dividend": [format_number(float(v), 4) for v in recent.values],
            }
        )
        st.dataframe(recent_df, use_container_width=True, hide_index=True)
    else:
        st.caption("No detailed dividend payment history available.")
