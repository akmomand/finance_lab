"""Analyst sentiment UI."""

from __future__ import annotations

import plotly.graph_objects as go

from data.sentiment import get_analyst_sentiment
from utils.formatting import format_currency, format_percent


def render_analyst_sentiment(st, ticker: str) -> None:
    symbol = (ticker or "").strip().upper()
    with st.spinner(f"Loading analyst data for {symbol}…"):
        data = get_analyst_sentiment(symbol)

    if not data.get("ok"):
        st.error(data.get("error") or "Failed to load analyst sentiment.")
        return

    currency = data.get("currency") or "USD"
    price = data.get("price")
    target = data.get("target_mean")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Price", format_currency(price, currency))
    c2.metric("Avg Target", format_currency(target, currency))
    upside = data.get("upside")
    c3.metric("Upside to Target", format_percent(upside, decimals=1) if upside is not None else "—")
    c4.metric("Analysts", str(data.get("n_analysts") or "—"))

    if data.get("recommendation_key"):
        st.caption(f"Yahoo recommendation key: **{data['recommendation_key']}**")

    lo, hi = data.get("target_low"), data.get("target_high")
    if lo is not None or hi is not None:
        st.caption(
            f"Target range: {format_currency(lo, currency)} – {format_currency(hi, currency)}"
        )

    counts = data.get("counts") or {}
    if data.get("has_counts"):
        labels = ["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"]
        keys = ["strong_buy", "buy", "hold", "sell", "strong_sell"]
        values = [counts.get(k, 0) for k in keys]

        cols = st.columns(5)
        for col, lab, val in zip(cols, labels, values):
            col.metric(lab, val)

        fig = go.Figure(
            data=[
                go.Bar(
                    x=labels,
                    y=values,
                    marker_color=["#0f7b3a", "#2ca02c", "#f0ad4e", "#d9534f", "#a94442"],
                )
            ]
        )
        fig.update_layout(
            title="Analyst ratings",
            height=300,
            template="plotly_white",
            showlegend=False,
            margin=dict(l=40, r=20, t=50, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Detailed Strong Buy / Buy / Hold / Sell counts not available; showing targets only.")
