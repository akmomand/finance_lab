"""Key ratio trend charts (Plotly)."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go

from data.ratios import get_key_ratio_trends
from utils.formatting import format_number


def _quarter_labels(index: pd.Index) -> list[str]:
    labels: list[str] = []
    for ts in pd.to_datetime(index):
        q = (ts.month - 1) // 3 + 1
        labels.append(f"{ts.year} Q{q}")
    return labels


def _line_chart(
    series: pd.Series,
    title: str,
    *,
    as_percent: bool = False,
) -> go.Figure | None:
    if series is None or series.empty:
        return None
    y = series.astype(float)
    if as_percent:
        y = y * 100
    fig = go.Figure(
        data=[
            go.Scatter(
                x=_quarter_labels(series.index),
                y=y.tolist(),
                mode="lines+markers",
                line=dict(width=2, color="#1f77b4"),
                marker=dict(size=7),
                name=title,
            )
        ]
    )
    fig.update_layout(
        title=title,
        height=300,
        margin=dict(l=40, r=20, t=50, b=40),
        template="plotly_white",
        showlegend=False,
        hovermode="x unified",
    )
    if as_percent:
        fig.update_yaxes(ticksuffix="%")
    return fig


def _render_group(st, series_map: dict[str, Any], specs: list[tuple[str, str, bool]]) -> None:
    cols = st.columns(min(3, len(specs)) or 1)
    for i, (key, title, as_pct) in enumerate(specs):
        fig = _line_chart(series_map.get(key, pd.Series(dtype=float)), title, as_percent=as_pct)
        with cols[i % len(cols)]:
            if fig is None:
                st.info(f"No data for {title}")
            else:
                st.plotly_chart(fig, use_container_width=True)

    # Compact table
    frames: dict[str, pd.Series] = {}
    for key, title, as_pct in specs:
        s = series_map.get(key)
        if s is None or s.empty:
            continue
        frames[title] = (s * 100).round(1) if as_pct else s.round(2)
    if not frames:
        return
    df = pd.DataFrame(frames)
    df.index = _quarter_labels(df.index)
    df.index.name = "Quarter"
    display = df.reset_index()
    for key, title, as_pct in specs:
        if title in display.columns and as_pct:
            display[title] = display[title].map(
                lambda v: f"{v:.1f}%" if pd.notna(v) else "—"
            )
    st.dataframe(display, use_container_width=True, hide_index=True)


def render_key_ratio_trends(st, ticker: str) -> None:
    symbol = (ticker or "").strip().upper()
    with st.spinner(f"Loading key ratios for {symbol}…"):
        data = get_key_ratio_trends(symbol)

    if not data.get("ok"):
        st.error(data.get("error") or "Failed to load key ratios.")
        return

    series = data.get("series") or {}
    snapshot = data.get("snapshot") or {}
    notes = data.get("notes") or {}

    st.caption(
        "Up to 8 quarters from statements · valuation history uses quarter-end prices when available"
    )

    # Current valuation snapshot strip
    st.markdown("##### Current valuation snapshot")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Trailing P/E", format_number(snapshot.get("trailing_pe"), decimals=1))
    c2.metric("Forward P/E", format_number(snapshot.get("forward_pe"), decimals=1))
    c3.metric("PEG", format_number(snapshot.get("peg"), decimals=2))
    c4.metric("EV / EBITDA", format_number(snapshot.get("ev_ebitda"), decimals=1))
    c5.metric("Price / Sales", format_number(snapshot.get("price_to_sales"), decimals=2))

    tab_prof, tab_liq, tab_solv, tab_val = st.tabs(
        ["Profitability", "Liquidity", "Solvency", "Valuation"]
    )

    with tab_prof:
        _render_group(
            st,
            series,
            [
                ("roe", "ROE", True),
                ("roa", "ROA", True),
                ("roic", "ROIC (approx.)", True),
            ],
        )
        if notes.get("roic"):
            st.caption(notes["roic"])

    with tab_liq:
        _render_group(
            st,
            series,
            [
                ("current_ratio", "Current Ratio", False),
                ("quick_ratio", "Quick Ratio", False),
            ],
        )

    with tab_solv:
        _render_group(
            st,
            series,
            [
                ("debt_to_equity", "Debt / Equity", False),
                ("interest_coverage", "Interest Coverage", False),
            ],
        )

    with tab_val:
        _render_group(
            st,
            series,
            [
                ("pe", "P/E (TTM)", False),
                ("price_to_sales", "Price / Sales (TTM)", False),
                ("price_to_fcf", "Price / FCF (TTM)", False),
            ],
        )
        if notes.get("pe"):
            st.caption(notes["pe"])
        st.caption(
            "P/S and P/FCF still use quarterly statements (Yahoo often only returns ~5 periods). "
            "Forward P/E, PEG, and EV/EBITDA are current Yahoo snapshots only."
        )
