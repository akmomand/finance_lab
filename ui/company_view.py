"""Company analysis view — section navigator loads one section at a time."""

from __future__ import annotations

from typing import Any

from data.company import get_company_overview
from data.scorecard import get_fundamental_scorecard
from ui.dividends_view import render_dividend_analysis
from ui.earnings_view import render_earnings_analysis
from ui.fair_value_view import render_fair_value
from ui.ownership_view import render_ownership
from ui.peers_view import render_peer_comparison
from ui.ratios_view import render_key_ratio_trends
from ui.sentiment_view import render_analyst_sentiment
from ui.trends_view import render_historical_trends
from utils.formatting import (
    format_currency,
    format_large_number,
    format_number,
    format_percent,
)

SECTIONS = [
    "1. Company Overview",
    "2. Fundamental Scorecard",
    "3. Historical Trend Analysis",
    "4. Key Ratio Trends",
    "5. Fair Value",
    "6. Competitor / Industry Comparison",
    "7. Earnings Analysis",
    "8. Analyst Sentiment",
    "9. Ownership",
    "10. Dividend Analysis",
]

_HEALTH_STYLE = {
    "strong": ("Strong", "#0f7b3a", "#e6f6ec"),
    "watch": ("Watch", "#a15c00", "#fff6e5"),
    "concern": ("Concern", "#b42318", "#fdeceb"),
    "na": ("N/A", "#667085", "#f2f4f7"),
}


def _metric(st, label: str, value: str) -> None:
    st.metric(label, value)


def _format_score_value(value: Any, fmt: str) -> str:
    if value is None:
        return "—"
    if fmt == "percent":
        return format_percent(value, decimals=1)
    return format_number(value, decimals=2)


def _health_badge(label: str, color: str, bg: str) -> str:
    return (
        f'<span style="display:inline-block;padding:0.15rem 0.55rem;border-radius:999px;'
        f'font-size:0.85rem;font-weight:600;color:{color};background:{bg};">{label}</span>'
    )


def _render_overview(st, ov: dict[str, Any]) -> None:
    if ov.get("warning"):
        st.warning(ov["warning"])

    currency = ov.get("currency") or "USD"
    name = ov.get("name") or ov.get("symbol")
    symbol = ov.get("symbol")

    st.markdown(f"### {name}")
    st.caption(
        f"{symbol}"
        + (f" · {ov['exchange']}" if ov.get("exchange") else "")
        + (f" · {ov['country']}" if ov.get("country") else "")
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _metric(st, "Ticker", symbol or "—")
    with c2:
        _metric(st, "Sector", str(ov.get("sector") or "—"))
    with c3:
        _metric(st, "Industry", str(ov.get("industry") or "—"))
    with c4:
        employees = ov.get("full_time_employees")
        _metric(
            st,
            "Employees",
            format_large_number(employees) if employees else "—",
        )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _metric(st, "Current Price", format_currency(ov.get("price"), currency))
    with c2:
        _metric(st, "Market Cap", format_large_number(ov.get("market_cap")))
    with c3:
        _metric(st, "Enterprise Value", format_large_number(ov.get("enterprise_value")))
    with c4:
        _metric(st, "Beta", format_number(ov.get("beta"), decimals=2))

    high = ov.get("fifty_two_week_high")
    low = ov.get("fifty_two_week_low")
    range_str = "—"
    if high is not None and low is not None:
        range_str = f"{format_currency(low, currency)} – {format_currency(high, currency)}"

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _metric(st, "52-Week Range", range_str)
    with c2:
        _metric(st, "52-Week High", format_currency(high, currency))
    with c3:
        _metric(st, "52-Week Low", format_currency(low, currency))
    with c4:
        _metric(st, "Dividend Yield", format_percent(ov.get("dividend_yield"), decimals=2))

    price = ov.get("price")
    if price is not None and high is not None and low is not None and high > low:
        pct = (float(price) - float(low)) / (float(high) - float(low))
        pct = max(0.0, min(1.0, pct))
        st.progress(pct, text=f"Price position in 52-week range · {pct * 100:.0f}%")

    if ov.get("website"):
        st.markdown(f"Website: [{ov['website']}]({ov['website']})")

    st.divider()
    st.markdown("#### Business Summary")
    summary = ov.get("summary") or ""
    if summary:
        st.write(summary)
    else:
        st.info("No business summary available for this ticker.")

    st.markdown("#### Revenue Segments")
    segments = ov.get("revenue_segments") or []
    if segments:
        st.dataframe(segments, use_container_width=True, hide_index=True)
    else:
        st.caption(
            "Structured product / revenue segment breakdown is not available via free "
            "yfinance for most tickers. Summary above is the primary description source."
        )

    st.markdown("#### Geographic Exposure")
    geo = ov.get("geographic_exposure") or []
    if geo:
        for row in geo:
            note = f" — {row['note']}" if row.get("note") else ""
            st.write(f"- **{row.get('region', '—')}**{note}")
    else:
        st.caption(
            "Geographic revenue mix is not available via free yfinance for this ticker."
        )


def _render_scorecard(st, card: dict[str, Any]) -> None:
    tallies = card.get("tallies") or {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Strong", tallies.get("strong", 0))
    c2.metric("Watch", tallies.get("watch", 0))
    c3.metric("Concern", tallies.get("concern", 0))
    c4.metric("N/A", tallies.get("na", 0))

    st.caption(
        "Bands are general quality screens (not industry-adjusted). "
        "Green = strong · Yellow = watch · Red = concern. "
        "ROIC is approximated from annual statements when available."
    )

    h1, h2, h3 = st.columns([2, 1, 1])
    h1.markdown("**Metric**")
    h2.markdown("**Current**")
    h3.markdown("**Health**")

    for row in card.get("rows") or []:
        health = row.get("health", "na")
        label, color, bg = _HEALTH_STYLE.get(health, _HEALTH_STYLE["na"])
        m1, m2, m3 = st.columns([2, 1, 1])
        with m1:
            st.markdown(f"**{row.get('metric', '')}**")
            if row.get("help"):
                st.caption(row["help"])
        with m2:
            st.markdown(_format_score_value(row.get("value"), row.get("format", "ratio")))
        with m3:
            st.markdown(_health_badge(label, color, bg), unsafe_allow_html=True)

    st.markdown("##### Threshold reference")
    for row in card.get("rows") or []:
        direction = "≥" if row.get("higher_is_better", True) else "≤"
        g = row.get("green")
        y = row.get("yellow")
        if row.get("format") == "percent":
            g_s = format_percent(g, decimals=0)
            y_s = format_percent(y, decimals=0)
        else:
            g_s = format_number(g, decimals=2)
            y_s = format_number(y, decimals=2)
        st.caption(
            f"{row.get('metric')}: strong {direction} {g_s}, "
            f"watch {direction} {y_s}, else concern"
        )


def render_company_page(st, ticker: str) -> None:
    st.header("Company Analysis")
    symbol = (ticker or "").strip().upper()
    if not symbol:
        st.warning("Enter a ticker in the sidebar.")
        return

    section = st.selectbox(
        "Section",
        SECTIONS,
        index=0,
        key=f"company_section_{symbol}",
        help="Only the selected section loads data — reduces Yahoo rate limits.",
    )
    st.caption(f"Ticker **{symbol}** · loading: {section}")

    if section.startswith("1."):
        with st.spinner(f"Loading overview for {symbol}…"):
            ov = get_company_overview(symbol)
        if not ov.get("ok"):
            st.error(ov.get("error") or "Failed to load overview.")
        else:
            _render_overview(st, ov)

    elif section.startswith("2."):
        with st.spinner(f"Loading scorecard for {symbol}…"):
            card = get_fundamental_scorecard(symbol)
        if not card.get("ok"):
            st.error(card.get("error") or "Failed to load scorecard.")
        else:
            _render_scorecard(st, card)

    elif section.startswith("3."):
        render_historical_trends(st, symbol)

    elif section.startswith("4."):
        render_key_ratio_trends(st, symbol)

    elif section.startswith("5."):
        render_fair_value(st, symbol)

    elif section.startswith("6."):
        render_peer_comparison(st, symbol)

    elif section.startswith("7."):
        render_earnings_analysis(st, symbol)

    elif section.startswith("8."):
        render_analyst_sentiment(st, symbol)

    elif section.startswith("9."):
        render_ownership(st, symbol)

    elif section.startswith("10."):
        render_dividend_analysis(st, symbol)
