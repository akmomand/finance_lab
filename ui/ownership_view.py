"""Ownership section UI — institutions + insiders."""

from __future__ import annotations

from data.ownership import get_ownership
from utils.formatting import format_percent


def render_ownership(st, ticker: str) -> None:
    symbol = (ticker or "").strip().upper()
    with st.spinner(f"Loading ownership for {symbol}…"):
        data = get_ownership(symbol)

    if not data.get("ok"):
        st.error(data.get("error") or "Failed to load ownership data.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Institutional Ownership",
        format_percent(data.get("held_institutions"), decimals=1)
        if data.get("held_institutions") is not None
        else "—",
    )
    c2.metric(
        "Insider Ownership",
        format_percent(data.get("held_insiders"), decimals=1)
        if data.get("held_insiders") is not None
        else "—",
    )
    c3.metric("Recent Insider Buys*", data.get("insider_buys", 0))
    c4.metric("Recent Insider Sells*", data.get("insider_sells", 0))
    st.caption("*Buy/sell counts are approximate keyword tallies from recent insider transaction text.")

    major = data.get("major_holders")
    if major is not None and not getattr(major, "empty", True):
        st.markdown("##### Major holders summary")
        st.dataframe(major, use_container_width=True, hide_index=True)

    inst = data.get("institutions")
    if inst is not None and not getattr(inst, "empty", True):
        st.markdown("##### Top institutional holders")
        st.dataframe(inst, use_container_width=True, hide_index=True)
    else:
        st.caption("Top institutional holder table not available for this ticker.")

    insiders = data.get("insider_transactions")
    if insiders is not None and not getattr(insiders, "empty", True):
        st.markdown("##### Recent insider transactions")
        st.dataframe(insiders, use_container_width=True, hide_index=True)
    else:
        st.caption("Insider transaction detail not available via free Yahoo data for this ticker.")
