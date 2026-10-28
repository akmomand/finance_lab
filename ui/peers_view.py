"""Competitor / industry comparison UI."""

from __future__ import annotations

import pandas as pd

from data.company import get_raw_info
from data.peers import get_peer_comparison, parse_peer_input, suggest_peers
from utils.formatting import format_large_number, format_number, format_percent


def render_peer_comparison(st, ticker: str) -> None:
    symbol = (ticker or "").strip().upper()
    info = get_raw_info(symbol) or {}
    sector = info.get("sector")
    defaults = suggest_peers(symbol, sector=sector)
    default_text = ", ".join(defaults)

    st.caption(
        "Peers are **not** auto-discovered from the market. "
        "Suggestions come from a small fixed list (or sector defaults); edit freely."
    )

    peer_text = st.text_input(
        "Peer tickers (comma-separated)",
        value=default_text,
        key=f"peers_input_{symbol}",
        help="Example: MSFT, GOOGL, AMZN",
    )
    peers = parse_peer_input(peer_text, symbol)

    if not peers:
        st.info("Add at least one peer ticker to compare.")
        return

    with st.spinner("Loading peer metrics…"):
        data = get_peer_comparison(symbol, tuple(peers))

    if not data.get("ok"):
        st.error(data.get("error") or "Failed to load peer comparison.")
        return

    rows = data.get("rows") or []
    records = []
    for r in rows:
        if not r.get("ok"):
            records.append(
                {
                    "Ticker": r.get("symbol"),
                    "Name": "—",
                    "P/E": "—",
                    "Fwd P/E": "—",
                    "ROE": "—",
                    "Gross Margin": "—",
                    "FCF Margin": "—",
                    "Debt/Equity": "—",
                    "Market Cap": "—",
                }
            )
            continue
        records.append(
            {
                "Ticker": r.get("symbol"),
                "Name": r.get("name"),
                "P/E": format_number(r.get("pe"), decimals=1),
                "Fwd P/E": format_number(r.get("forward_pe"), decimals=1),
                "ROE": format_percent(r.get("roe"), decimals=1),
                "Gross Margin": format_percent(r.get("gross_margin"), decimals=1),
                "FCF Margin": format_percent(r.get("fcf_margin"), decimals=1),
                "Debt/Equity": format_number(r.get("debt_to_equity"), decimals=2),
                "Market Cap": format_large_number(r.get("market_cap")),
            }
        )

    df = pd.DataFrame(records)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Highlight primary row note
    st.caption(f"Primary ticker **{symbol}** is the first row. Failed peer loads show as —.")
