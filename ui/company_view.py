"""Company analysis view — section stubs for later steps."""

from __future__ import annotations

from data.company import get_company_info
from utils.formatting import format_currency, format_large_number


SECTION_STUBS = [
    ("1. Overview", "coming in Step 3"),
    ("2. Price & Returns", "coming soon"),
    ("3. Valuation", "coming soon"),
    ("4. Profitability", "coming soon"),
    ("5. Growth", "coming soon"),
    ("6. Balance Sheet", "coming soon"),
    ("7. Cash Flow", "coming soon"),
    ("8. Ownership", "coming soon"),
    ("9. News & Events", "coming soon"),
    ("10. Scorecard", "coming soon"),
]


def render_company_page(st, ticker: str) -> None:
    st.header("Company Analysis")
    symbol = (ticker or "").strip().upper() or "—"
    st.subheader(f"Ticker: {symbol}")

    info = get_company_info(symbol) if symbol and symbol != "—" else {}

    with st.expander("1. Overview", expanded=True):
        st.caption("Overview details coming in Step 3")
        if info:
            name = info.get("name") or symbol
            price = info.get("price")
            currency = info.get("currency") or "USD"
            cols = st.columns(4)
            cols[0].metric("Name", name)
            cols[1].metric("Price", format_currency(price, currency))
            cols[2].metric("Sector", info.get("sector") or "—")
            cols[3].metric("Market Cap", format_large_number(info.get("market_cap")))
        else:
            st.write("Could not load basic quote info. Check the ticker or try again.")

    for title, note in SECTION_STUBS[1:]:
        with st.expander(title, expanded=False):
            st.caption(note)
