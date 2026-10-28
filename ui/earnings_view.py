"""Earnings analysis UI — estimates, actuals, surprises."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from data.earnings import get_earnings_analysis
from utils.formatting import format_number


def render_earnings_analysis(st, ticker: str) -> None:
    symbol = (ticker or "").strip().upper()
    with st.spinner(f"Loading earnings history for {symbol}…"):
        data = get_earnings_analysis(symbol)

    if not data.get("ok"):
        st.error(data.get("error") or "Failed to load earnings data.")
        return

    df: pd.DataFrame = data["table"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Beats (in window)", data.get("beats", 0))
    c2.metric("Misses (in window)", data.get("misses", 0))
    avg = data.get("avg_surprise")
    c3.metric("Avg Surprise", f"{avg:+.1f}%" if avg is not None else "—")

    # Table
    display = pd.DataFrame(
        {
            "Quarter": df["quarter"],
            "Estimate": df["estimate"].map(lambda v: format_number(v, 2)) if "estimate" in df else "—",
            "Actual": df["actual"].map(lambda v: format_number(v, 2)) if "actual" in df else "—",
            "Surprise %": (
                df["surprise_pct"].map(lambda v: f"{v:+.1f}%" if pd.notna(v) else "—")
                if "surprise_pct" in df
                else "—"
            ),
        }
    )
    st.dataframe(display, use_container_width=True, hide_index=True)

    # Charts
    tab_eps, tab_surprise = st.tabs(["EPS trend", "Surprise trend"])

    with tab_eps:
        fig = go.Figure()
        x = df["quarter"].tolist()
        if "estimate" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=df["estimate"],
                    mode="lines+markers",
                    name="Estimate",
                    line=dict(dash="dot", color="#ff7f0e"),
                )
            )
        if "actual" in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=df["actual"],
                    mode="lines+markers",
                    name="Actual",
                    line=dict(color="#1f77b4", width=2),
                )
            )
        fig.update_layout(
            title="EPS Estimate vs Actual",
            height=340,
            template="plotly_white",
            hovermode="x unified",
            margin=dict(l=40, r=20, t=50, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab_surprise:
        if "surprise_pct" not in df.columns or df["surprise_pct"].dropna().empty:
            st.info("No surprise % series available.")
        else:
            vals = df["surprise_pct"].tolist()
            colors = ["#2ca02c" if (v is not None and v >= 0) else "#d62728" for v in vals]
            fig = go.Figure(
                data=[go.Bar(x=df["quarter"].tolist(), y=vals, marker_color=colors, name="Surprise %")]
            )
            fig.add_hline(y=0, line_dash="dash", line_color="gray")
            fig.update_layout(
                title="EPS Surprise %",
                height=340,
                template="plotly_white",
                showlegend=False,
                margin=dict(l=40, r=20, t=50, b=40),
                yaxis_ticksuffix="%",
            )
            st.plotly_chart(fig, use_container_width=True)

    st.caption("Source: Yahoo Finance earnings dates / history via yfinance (coverage varies by ticker).")
