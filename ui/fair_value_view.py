"""Fair value section: DCF, Graham number, multiples."""

from __future__ import annotations

from data.valuation import get_valuation_inputs, graham_number, run_dcf
from utils.formatting import format_currency, format_large_number, format_number, format_percent


def _upsert_vs_price(st, label: str, value: float | None, price: float | None, currency: str) -> None:
    if value is None or price is None or price == 0:
        st.metric(label, format_currency(value, currency) if value is not None else "—")
        return
    pct = (value - price) / price
    st.metric(
        label,
        format_currency(value, currency),
        delta=f"{pct * 100:+.1f}% vs price",
    )


def render_fair_value(st, ticker: str) -> None:
    symbol = (ticker or "").strip().upper()
    with st.spinner(f"Loading valuation inputs for {symbol}…"):
        base = get_valuation_inputs(symbol)

    if not base.get("ok"):
        st.error(base.get("error") or "Failed to load valuation inputs.")
        return

    currency = base.get("currency") or "USD"
    price = base.get("price")

    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", format_currency(price, currency))
    c2.metric("TTM FCF", format_large_number(base.get("fcf")))
    c3.metric("Shares Out", format_large_number(base.get("shares")))

    st.caption(
        "Models are educational simplifications — not investment advice. "
        "DCF is highly sensitive to growth, WACC, and terminal growth."
    )

    tab_dcf, tab_graham, tab_multiples = st.tabs(
        ["Discounted Cash Flow", "Graham Value", "Multiples"]
    )

    # ----- DCF -----
    with tab_dcf:
        st.markdown("##### Assumptions")
        default_g = float(base.get("default_growth") or 0.08)
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            growth_pct = st.number_input(
                "Revenue / FCF growth %",
                min_value=-20.0,
                max_value=40.0,
                value=round(default_g * 100, 1),
                step=0.5,
                key=f"dcf_growth_{symbol}",
                help="Applied to FCF each year for the explicit forecast period.",
            )
        with col_b:
            wacc_pct = st.number_input(
                "WACC %",
                min_value=1.0,
                max_value=25.0,
                value=9.0,
                step=0.25,
                key=f"dcf_wacc_{symbol}",
            )
        with col_c:
            term_pct = st.number_input(
                "Terminal growth %",
                min_value=0.0,
                max_value=5.0,
                value=2.5,
                step=0.25,
                key=f"dcf_term_{symbol}",
            )

        growth = growth_pct / 100.0
        wacc = wacc_pct / 100.0
        terminal_growth = term_pct / 100.0

        fcf0 = base.get("fcf")
        shares = base.get("shares")
        net_debt = base.get("net_debt") or 0.0

        if fcf0 is None or shares is None:
            st.warning("Need free cash flow and shares outstanding to run DCF.")
        elif wacc <= terminal_growth:
            st.error("WACC must be greater than terminal growth.")
        else:
            result = run_dcf(
                fcf0=float(fcf0),
                shares=float(shares),
                net_debt=float(net_debt),
                growth=growth,
                wacc=wacc,
                terminal_growth=terminal_growth,
            )
            if result is None:
                st.error("Could not compute DCF with the current inputs.")
            else:
                intrinsic = result["intrinsic_per_share"]
                m1, m2, m3 = st.columns(3)
                with m1:
                    _upsert_vs_price(st, "Intrinsic Value", intrinsic, price, currency)
                with m2:
                    m2.metric("Current Price", format_currency(price, currency))
                with m3:
                    if price and intrinsic:
                        gap = (intrinsic - price) / price
                        label = "Undervalued" if gap > 0 else "Overvalued"
                        m3.metric(label, f"{abs(gap) * 100:.1f}%")

                st.markdown("##### DCF bridge")
                b1, b2, b3, b4 = st.columns(4)
                b1.metric("PV of FCFs", format_large_number(sum(result["pv_fcfs"])))
                b2.metric("PV Terminal", format_large_number(result["pv_terminal"]))
                b3.metric("Enterprise Value", format_large_number(result["enterprise_value"]))
                b4.metric("Equity Value", format_large_number(result["equity_value"]))

                years = list(range(1, result["years"] + 1))
                st.dataframe(
                    {
                        "Year": years,
                        "Projected FCF": [format_large_number(v) for v in result["projected_fcf"]],
                        "PV of FCF": [format_large_number(v) for v in result["pv_fcfs"]],
                    },
                    use_container_width=True,
                    hide_index=True,
                )

    # ----- Graham -----
    with tab_graham:
        st.markdown("##### Graham Number")
        st.caption("√(22.5 × EPS × Book Value Per Share)")

        eps_default = float(base.get("eps") or 0.0)
        bvps_default = float(base.get("bvps") or 0.0)
        g1, g2 = st.columns(2)
        with g1:
            eps_in = st.number_input(
                "EPS (TTM)",
                min_value=-1000.0,
                max_value=1000.0,
                value=round(eps_default, 2),
                step=0.05,
                key=f"graham_eps_{symbol}",
            )
        with g2:
            bvps_in = st.number_input(
                "Book Value / Share",
                min_value=-1000.0,
                max_value=10000.0,
                value=round(bvps_default, 2),
                step=0.05,
                key=f"graham_bvps_{symbol}",
            )

        g_val = graham_number(eps_in, bvps_in)
        # Prefer live calc from inputs; fall back to precomputed
        if g_val is None:
            g_val = base.get("graham")

        r1, r2, r3 = st.columns(3)
        with r1:
            _upsert_vs_price(st, "Graham Value", g_val, price, currency)
        with r2:
            r2.metric("Current Price", format_currency(price, currency))
        with r3:
            if g_val and price:
                gap = (g_val - price) / price
                r3.metric("Gap vs price", f"{gap * 100:+.1f}%")

        if eps_in <= 0 or bvps_in <= 0:
            st.info("Graham number requires positive EPS and book value per share.")

    # ----- Multiples -----
    with tab_multiples:
        st.markdown("##### P/E vs history")
        cur_pe = base.get("trailing_pe")
        hist_pe = base.get("hist_pe_avg")
        fwd_pe = base.get("forward_pe")

        m1, m2, m3 = st.columns(3)
        m1.metric("Current P/E", format_number(cur_pe, decimals=1))
        m2.metric("5Y Avg P/E (approx.)", format_number(hist_pe, decimals=1))
        m3.metric("Forward P/E", format_number(fwd_pe, decimals=1))

        if cur_pe is not None and hist_pe is not None and hist_pe > 0:
            discount = (hist_pe - cur_pe) / hist_pe
            if discount > 0.05:
                st.success(
                    f"Current P/E ({format_number(cur_pe, 1)}) is below the approx. "
                    f"5-year average ({format_number(hist_pe, 1)}) — "
                    f"appears discounted by ~{discount * 100:.0f}% on a multiple basis."
                )
            elif discount < -0.05:
                st.warning(
                    f"Current P/E ({format_number(cur_pe, 1)}) is above the approx. "
                    f"5-year average ({format_number(hist_pe, 1)}) — "
                    f"appears rich by ~{abs(discount) * 100:.0f}% on a multiple basis."
                )
            else:
                st.info("Current P/E is roughly in line with the approximate 5-year average.")
        else:
            st.caption(
                "Need both trailing P/E and enough annual history to compare. "
                f"Growth default used elsewhere: {format_percent(base.get('default_growth'), 1)}."
            )

        eps_ttm = base.get("eps")
        if hist_pe and eps_ttm and eps_ttm > 0:
            implied = hist_pe * eps_ttm
            st.markdown("##### Implied price at historical P/E")
            i1, i2 = st.columns(2)
            with i1:
                _upsert_vs_price(st, "Implied Price", implied, price, currency)
            i2.metric(
                "Using",
                f"{format_number(hist_pe, 1)}× × EPS {format_number(eps_ttm, 2)}",
            )
