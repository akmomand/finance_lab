"""Macro dashboard — FRED indicators with summary cards and Plotly charts."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data.macro import MACRO_META, get_macro_snapshot
from utils.formatting import format_number, format_percent


def _fmt_level(name: str, value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    if name == "unemployment" or unit == "%":
        return f"{value:.1f}%"
    if name == "gdp":
        return f"${format_number(value, decimals=0)}B"
    return format_number(value, decimals=1)


def _metric_card(st, name: str, m: dict[str, Any]) -> None:
    label = m.get("label", name)
    latest = m.get("latest")
    yoy = m.get("yoy")
    unit = m.get("unit", "")
    date = m.get("latest_date")
    date_str = pd.Timestamp(date).strftime("%b %Y") if date is not None else ""

    st.metric(
        label=label,
        value=_fmt_level(name, latest, unit),
        delta=(f"{yoy:+.1f}% YoY" if yoy is not None else None),
        help=m.get("description", ""),
    )
    if date_str:
        st.caption(f"As of {date_str} · {m.get('series_id', '')}")


def _line_figure(
    df: pd.DataFrame,
    title: str,
    y_title: str,
    yoy: pd.Series | None = None,
    show_yoy: bool = False,
) -> go.Figure:
    if show_yoy and yoy is not None and not yoy.empty:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["value"],
                name="Level",
                mode="lines",
                line=dict(width=2, color="#1f77b4"),
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=yoy.index,
                y=yoy,
                name="YoY %",
                mode="lines",
                line=dict(width=1.5, color="#ff7f0e", dash="dot"),
            ),
            secondary_y=True,
        )
        fig.update_yaxes(title_text=y_title, secondary_y=False)
        fig.update_yaxes(title_text="YoY %", secondary_y=True)
    else:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["value"],
                name=title,
                mode="lines",
                line=dict(width=2, color="#1f77b4"),
                fill="tozeroy",
                fillcolor="rgba(31,119,180,0.08)",
            )
        )
        fig.update_yaxes(title_text=y_title)

    fig.update_layout(
        title=title,
        height=340,
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode="x unified",
        template="plotly_white",
    )
    fig.update_xaxes(title_text="")
    return fig


def _inflation_panel(st, metrics: dict[str, Any]) -> None:
    """Dedicated inflation view: CPI YoY + PCE YoY."""
    st.subheader("Inflation Rate")
    cols = st.columns(2)
    for col, key, color in (
        (cols[0], "cpi", "#d62728"),
        (cols[1], "pce", "#2ca02c"),
    ):
        m = metrics.get(key, {})
        yoy = m.get("yoy_series")
        label = "CPI YoY" if key == "cpi" else "PCE YoY"
        with col:
            if yoy is None or (hasattr(yoy, "empty") and yoy.empty):
                st.warning(f"No {label} data")
                continue
            latest = m.get("yoy")
            st.metric(label, format_percent(latest, decimals=1) if latest is not None else "—")
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=yoy.index,
                    y=yoy,
                    mode="lines",
                    name=label,
                    line=dict(width=2, color=color),
                )
            )
            fig.add_hline(y=2.0, line_dash="dash", line_color="gray", annotation_text="2% target")
            fig.update_layout(
                title=f"{label} Inflation",
                height=320,
                margin=dict(l=40, r=20, t=50, b=40),
                template="plotly_white",
                hovermode="x unified",
                showlegend=False,
            )
            fig.update_yaxes(title_text="%")
            st.plotly_chart(fig, use_container_width=True)


def render_macro_page(st) -> None:
    st.header("Macro Dashboard")
    st.caption(
        "US macro indicators from FRED · Manufacturing cycle uses employment as a free PMI proxy "
        "(ISM PMI is proprietary)."
    )

    with st.spinner("Loading FRED data…"):
        snapshot = get_macro_snapshot()

    status = snapshot.get("status")
    if status == "missing_key":
        st.warning(snapshot.get("message", "Missing FRED_API_KEY"))
        st.markdown(
            "1. Copy `.env.example` → `.env`  \n"
            "2. Add a free key from [FRED API keys](https://fred.stlouisfed.org/docs/api/api_key.html)  \n"
            "3. Restart the app"
        )
        return

    if status == "error":
        st.error(snapshot.get("message", "Failed to load macro data"))
        return

    metrics: dict[str, Any] = snapshot.get("metrics") or {}
    partial = snapshot.get("partial_errors") or []
    if partial:
        st.info(f"Some series failed to load: {', '.join(partial)}")

    # --- Summary cards ---
    st.subheader("Snapshot")
    card_order = ["cpi", "pce", "gdp", "unemployment", "manufacturing_pmi"]
    cols = st.columns(len(card_order))
    for col, name in zip(cols, card_order):
        with col:
            _metric_card(st, name, metrics.get(name, {}))

    st.divider()
    _inflation_panel(st, metrics)

    st.divider()
    st.subheader("Indicator Trends")

    # Lookback selector
    years = st.slider("Chart lookback (years)", min_value=5, max_value=30, value=10, step=5)

    chart_keys = ["gdp", "cpi", "unemployment", "manufacturing_pmi"]
    for i in range(0, len(chart_keys), 2):
        row = st.columns(2)
        for j, key in enumerate(chart_keys[i : i + 2]):
            m = metrics.get(key, {})
            df: pd.DataFrame = m.get("data") if isinstance(m.get("data"), pd.DataFrame) else pd.DataFrame()
            with row[j]:
                if df.empty:
                    st.warning(f"No data for {MACRO_META.get(key, {}).get('label', key)}")
                    continue
                cutoff = df.index.max() - pd.DateOffset(years=years)
                clipped = df.loc[df.index >= cutoff]
                yoy = m.get("yoy_series")
                yoy_clipped = None
                if yoy is not None and not yoy.empty:
                    yoy_clipped = yoy.loc[yoy.index >= cutoff]
                show_yoy = MACRO_META.get(key, {}).get("yoy") == "true" and key != "unemployment"
                fig = _line_figure(
                    clipped,
                    title=m.get("label", key),
                    y_title=m.get("unit", ""),
                    yoy=yoy_clipped,
                    show_yoy=show_yoy,
                )
                st.plotly_chart(fig, use_container_width=True)

    with st.expander("Series reference"):
        for name, series_id in (
            ("CPI", "CPIAUCSL"),
            ("PCE (inflation)", "PCEPI"),
            ("GDP", "GDP"),
            ("Unemployment", "UNRATE"),
            ("Manufacturing employment (PMI proxy)", "MANEMP"),
        ):
            st.markdown(f"- **{name}**: `{series_id}`")
