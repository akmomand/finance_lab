"""Historical quarterly trend charts (Plotly)."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go

from data.trends import get_quarterly_trends
from utils.formatting import format_large_number


def _quarter_labels(index: pd.Index) -> list[str]:
    labels: list[str] = []
    for ts in pd.to_datetime(index):
        q = (ts.month - 1) // 3 + 1
        labels.append(f"{ts.year} Q{q}")
    return labels


def _bar_or_line(
    series: pd.Series,
    title: str,
    *,
    as_percent: bool = False,
    as_currency: bool = True,
    chart_type: str = "bar",
) -> go.Figure | None:
    if series is None or series.empty:
        return None

    x = _quarter_labels(series.index)
    y = series.astype(float).tolist()

    fig = go.Figure()
    if chart_type == "line":
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode="lines+markers",
                name=title,
                line=dict(width=2, color="#1f77b4"),
                marker=dict(size=7),
            )
        )
    else:
        colors = ["#2ca02c" if v >= 0 else "#d62728" for v in y]
        fig.add_trace(
            go.Bar(x=x, y=y, name=title, marker_color=colors)
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
        # values stored as ratios → display as percent
        fig.data[0].y = [v * 100 if v is not None else None for v in y]
    elif as_currency:
        fig.update_yaxes(title_text="USD")
    return fig


def _series_table(series_map: dict[str, pd.Series], keys: list[tuple[str, str, str]]) -> pd.DataFrame:
    """Build a display table: Quarter x metrics. kind: money|pct|eps"""
    frames: dict[str, pd.Series] = {}
    for key, label, kind in keys:
        s = series_map.get(key)
        if s is None or s.empty:
            continue
        if kind == "pct":
            frames[label] = (s * 100).round(1)
        elif kind == "eps":
            frames[label] = s.round(2)
        else:
            frames[label] = s
    if not frames:
        return pd.DataFrame()
    df = pd.DataFrame(frames)
    df.index = _quarter_labels(df.index)
    df.index.name = "Quarter"
    return df.reset_index()


def _fmt_money_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].map(
                lambda v: format_large_number(v) if pd.notna(v) else "—"
            )
    return out


def render_historical_trends(st, ticker: str) -> None:
    symbol = (ticker or "").strip().upper()
    with st.spinner(f"Loading quarterly trends for {symbol}…"):
        data = get_quarterly_trends(symbol)

    if not data.get("ok"):
        st.error(data.get("error") or "Failed to load quarterly trends.")
        return

    series: dict[str, Any] = data.get("series") or {}
    st.caption("Last up to 8 reported quarters · source: yfinance quarterly statements")

    tab_growth, tab_margins, tab_bs, tab_cf = st.tabs(
        ["Growth", "Profitability", "Balance Sheet", "Cash Flow"]
    )

    with tab_growth:
        growth_keys = [
            ("revenue", "Revenue", "bar"),
            ("operating_income", "Operating Income", "bar"),
            ("net_income", "Net Income", "bar"),
            ("eps", "EPS (Diluted)", "line"),
        ]
        cols = st.columns(2)
        for i, (key, title, ctype) in enumerate(growth_keys):
            fig = _bar_or_line(
                series.get(key, pd.Series(dtype=float)),
                title,
                as_percent=False,
                as_currency=(key != "eps"),
                chart_type=ctype,
            )
            with cols[i % 2]:
                if fig is None:
                    st.info(f"No data for {title}")
                else:
                    st.plotly_chart(fig, use_container_width=True)

        table = _series_table(
            series,
            [
                ("revenue", "Revenue", "money"),
                ("operating_income", "Op. Income", "money"),
                ("net_income", "Net Income", "money"),
                ("eps", "EPS", "eps"),
            ],
        )
        if not table.empty:
            st.dataframe(
                _fmt_money_cols(table, ["Revenue", "Op. Income", "Net Income"]),
                use_container_width=True,
                hide_index=True,
            )

    with tab_margins:
        margin_keys = [
            ("gross_margin", "Gross Margin"),
            ("operating_margin", "Operating Margin"),
            ("net_margin", "Net Margin"),
        ]
        cols = st.columns(3)
        for i, (key, title) in enumerate(margin_keys):
            fig = _bar_or_line(
                series.get(key, pd.Series(dtype=float)),
                title,
                as_percent=True,
                as_currency=False,
                chart_type="line",
            )
            with cols[i]:
                if fig is None:
                    st.info(f"No data for {title}")
                else:
                    st.plotly_chart(fig, use_container_width=True)

        table = _series_table(
            series,
            [
                ("gross_margin", "Gross %", "pct"),
                ("operating_margin", "Op. %", "pct"),
                ("net_margin", "Net %", "pct"),
            ],
        )
        if not table.empty:
            display = table.copy()
            for c in ["Gross %", "Op. %", "Net %"]:
                if c in display.columns:
                    display[c] = display[c].map(
                        lambda v: f"{v:.1f}%" if pd.notna(v) else "—"
                    )
            st.dataframe(display, use_container_width=True, hide_index=True)

    with tab_bs:
        bs_keys = [
            ("cash", "Cash"),
            ("debt", "Debt"),
            ("equity", "Equity"),
        ]
        cols = st.columns(3)
        for i, (key, title) in enumerate(bs_keys):
            fig = _bar_or_line(
                series.get(key, pd.Series(dtype=float)),
                title,
                chart_type="line",
            )
            with cols[i]:
                if fig is None:
                    st.info(f"No data for {title}")
                else:
                    st.plotly_chart(fig, use_container_width=True)

        table = _series_table(
            series,
            [
                ("cash", "Cash", "money"),
                ("debt", "Debt", "money"),
                ("equity", "Equity", "money"),
            ],
        )
        if not table.empty:
            st.dataframe(
                _fmt_money_cols(table, ["Cash", "Debt", "Equity"]),
                use_container_width=True,
                hide_index=True,
            )

    with tab_cf:
        cf_keys = [
            ("operating_cash_flow", "Operating Cash Flow"),
            ("free_cash_flow", "Free Cash Flow"),
        ]
        cols = st.columns(2)
        for i, (key, title) in enumerate(cf_keys):
            fig = _bar_or_line(
                series.get(key, pd.Series(dtype=float)),
                title,
                chart_type="bar",
            )
            with cols[i]:
                if fig is None:
                    st.info(f"No data for {title}")
                else:
                    st.plotly_chart(fig, use_container_width=True)

        table = _series_table(
            series,
            [
                ("operating_cash_flow", "OCF", "money"),
                ("free_cash_flow", "FCF", "money"),
            ],
        )
        if not table.empty:
            st.dataframe(
                _fmt_money_cols(table, ["OCF", "FCF"]),
                use_container_width=True,
                hide_index=True,
            )
