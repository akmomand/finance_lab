"""Company analysis view — Overview (Step 3) + stubs for later sections."""

from __future__ import annotations

from typing import Any

from data.company import get_company_overview
from utils.formatting import (
    format_currency,
    format_large_number,
    format_number,
    format_percent,
)


# Remaining roadmap sections (Overview rendered fully below)
SECTION_STUBS = [
    ("2. Fundamental Scorecard", "coming in Step 4"),
    ("3. Historical Trend Analysis", "coming in Step 5"),
    ("4. Key Ratio Trends", "coming in Step 6"),
    ("5. Fair Value", "coming in Step 7"),
    ("6. Competitor / Industry Comparison", "coming in Step 8"),
    ("7. Earnings Analysis", "coming in Step 8"),
    ("8. Analyst Sentiment", "coming in Step 9"),
    ("9. Ownership", "coming in Step 9"),
    ("10. Dividend Analysis", "coming in Step 9"),
]


def _metric(st, label: str, value: str) -> None:
    st.metric(label, value)


def _render_overview(st, ov: dict[str, Any]) -> None:
    currency = ov.get("currency") or "USD"
    name = ov.get("name") or ov.get("symbol")
    symbol = ov.get("symbol")

    st.markdown(f"### {name}")
    st.caption(
        f"{symbol}"
        + (f" · {ov['exchange']}" if ov.get("exchange") else "")
        + (f" · {ov['country']}" if ov.get("country") else "")
    )

    # Row 1 — identity & size
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

    # Row 2 — valuation / quote
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _metric(st, "Current Price", format_currency(ov.get("price"), currency))
    with c2:
        _metric(st, "Market Cap", format_large_number(ov.get("market_cap")))
    with c3:
        _metric(st, "Enterprise Value", format_large_number(ov.get("enterprise_value")))
    with c4:
        _metric(st, "Beta", format_number(ov.get("beta"), decimals=2))

    # Row 3 — range & yield
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

    # Price vs 52w range bar
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
        st.caption(
            "Full regional revenue mix is rarely exposed by free Yahoo data; "
            "showing domicile when available."
        )
    else:
        st.caption(
            "Geographic revenue mix is not available via free yfinance for this ticker."
        )


def render_company_page(st, ticker: str) -> None:
    st.header("Company Analysis")
    symbol = (ticker or "").strip().upper()
    if not symbol:
        st.warning("Enter a ticker in the sidebar.")
        return

    with st.spinner(f"Loading {symbol}…"):
        ov = get_company_overview(symbol)

    with st.expander("1. Company Overview", expanded=True):
        if not ov.get("ok"):
            st.error(ov.get("error") or "Failed to load overview.")
        else:
            _render_overview(st, ov)

    for title, note in SECTION_STUBS:
        with st.expander(title, expanded=False):
            st.caption(note)
