import streamlit as st

from gold_portfolio_math import format_money


def render_portfolio_summary(total_grams, total_logged_cost, total_sell_value, projected_pl, sell_spread_pct, live_snapshot, selected_currency_code):
    st.markdown("### 🧮 Ledger Totals Summary")
    t_col1, t_col2, t_col3, t_col4, t_col5, t_col6, t_col7 = st.columns(7)
    t_col1.markdown(f"**Total Grams:**\n{total_grams:.2f}g")
    t_col2.markdown(f"**Logged Cost ({selected_currency_code}):**\n{format_money(total_logged_cost, selected_currency_code)}")
    t_col3.markdown(f"**Sell Today Value ({selected_currency_code}):**\n{format_money(total_sell_value, selected_currency_code)}")
    g_color = "green" if projected_pl >= 0 else "red"
    t_col4.markdown(
        f"**Net Gain/Loss ({selected_currency_code}):**\n<span style='color:{g_color}; font-weight:bold;'>{format_money(projected_pl, selected_currency_code)}</span>",
        unsafe_allow_html=True,
    )
    t_col5.markdown(f"**Sell Spread:**\n{sell_spread_pct:.1f}%")
    t_col6.markdown(
        f"**Sell Snapshot:**\n{live_snapshot.gold_source_date}",
    )
    t_col7.markdown(
        f"**View Mode:**\n{selected_currency_code}",
    )
