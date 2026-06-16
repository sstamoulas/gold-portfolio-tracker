import datetime

import plotly.graph_objects as go
import streamlit as st

from gold_ledger_ui import build_ledger_column_config
from gold_portfolio_math import format_money, get_display_currency_config


def render_purchase_controls():
    st.sidebar.header("📝 Log Purchase Records")
    st.sidebar.markdown("Add your transaction details below:")

    chosen_currency = st.sidebar.radio(
        "Purchase entry currency:",
        options=["TRY", "USD"],
        horizontal=True,
        key="input_currency",
    )
    st.sidebar.caption("This only affects the new purchase record you are entering.")

    purchase_date = st.sidebar.date_input(
        "Purchase Date",
        value=datetime.date.today(),
        max_value=datetime.date.today(),
        key="input_date",
    )

    grams = st.sidebar.number_input(
        "Grams Purchased",
        min_value=0.1,
        value=10.0,
        step=1.0,
        key="input_grams",
    )

    sell_spread_pct = st.sidebar.slider(
        "Sell spread (%)",
        min_value=0.0,
        max_value=20.0,
        value=0.0,
        step=0.1,
        key="sell_spread_pct",
    )

    return chosen_currency, purchase_date, grams, sell_spread_pct


def prepare_purchase_prefill(fetch_market_snapshot_for_date, purchase_date, grams, chosen_currency):
    purchase_snapshot = fetch_market_snapshot_for_date(purchase_date)
    if chosen_currency == "TRY":
        suggested_logged_cost = round(grams * purchase_snapshot.gold_try_per_gram, 2)
    else:
        suggested_logged_cost = round(grams * purchase_snapshot.gold_usd_per_gram, 2)

    st.session_state["input_cost_raw"] = suggested_logged_cost
    st.session_state["input_fx"] = float(purchase_snapshot.usd_try)
    return purchase_snapshot, suggested_logged_cost


def render_purchase_snapshot(purchase_snapshot):
    st.sidebar.markdown("### Purchase Snapshot")
    st.sidebar.metric("Gold / gram (USD)", f"${purchase_snapshot.gold_usd_per_gram:,.2f}")
    st.sidebar.metric("Gold / gram (TRY)", f"{purchase_snapshot.gold_try_per_gram:,.2f} TL")
    st.sidebar.metric("USD/TRY", f"{purchase_snapshot.usd_try:,.4f}")
    st.sidebar.caption(
        f"Reference-only market close from {purchase_snapshot.gold_source_date} for gold and {purchase_snapshot.fx_source_date} for FX."
    )


def render_purchase_form(chosen_currency, suggested_logged_cost, purchase_snapshot, save_callback):
    with st.sidebar.form("purchase_form", clear_on_submit=True):
        if chosen_currency == "TRY":
            label_text = "Logged Cost (in Turkish Lira - TRY)"
            step_val = 500.0
        else:
            label_text = "Logged Cost (in US Dollars - USD)"
            step_val = 50.0

        st.number_input(
            label_text,
            min_value=0.01,
            value=suggested_logged_cost,
            step=step_val,
            key="input_cost_raw",
        )

        st.number_input(
            "Purchase USD/TRY rate (auto-filled from purchase date):",
            min_value=1.0,
            value=float(purchase_snapshot.usd_try),
            step=0.01,
            format="%.4f",
            key="input_fx",
        )

        st.caption(
            "The suggested logged cost refreshes when you change purchase date, grams, or entry currency. "
            "This applies only to the row you are saving. You can override it with the exact amount you paid before saving. "
            "Gain/loss uses the saved cost basis, and the sell spread applies to every row in the sell-today view."
        )
        st.form_submit_button("➕ Save Permanently to DB", on_click=save_callback)


def render_purchase_sidebar(fetch_market_snapshot_for_date, save_callback):
    chosen_currency, purchase_date, grams, sell_spread_pct = render_purchase_controls()
    purchase_snapshot, suggested_logged_cost = prepare_purchase_prefill(
        fetch_market_snapshot_for_date,
        purchase_date,
        grams,
        chosen_currency,
    )
    render_purchase_snapshot(purchase_snapshot)
    render_purchase_form(chosen_currency, suggested_logged_cost, purchase_snapshot, save_callback)

    return sell_spread_pct


def render_market_snapshot_banner(live_snapshot, sell_spread_pct, historical_fallback_used):
    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric(
        "Gold Price / Gram (USD)",
        f"${live_snapshot.gold_usd_per_gram:,.2f}",
    )
    m_col2.metric(
        "Gold Price / Gram (TRY)",
        f"{live_snapshot.gold_try_per_gram:,.2f} TL",
    )
    m_col3.metric(
        "Forex Exchange (USD/TRY)",
        f"{live_snapshot.usd_try:,.4f}",
    )
    st.caption(
        f"Current snapshot uses market close from {live_snapshot.gold_source_date} for gold and {live_snapshot.fx_source_date} for FX. "
        f"Sell spread: {sell_spread_pct:.1f}%"
    )

    st.markdown("---")

    if live_snapshot.is_fallback or historical_fallback_used:
        st.info(
            "Historical pricing uses the closest available market close on or before each purchase date. "
            "If Yahoo Finance misses a date, the app falls back to the current market snapshot."
        )


def _get_portfolio_display_context(analysis_df, display_currency):
    currency_cfg = get_display_currency_config(display_currency)
    selected_currency_code = currency_cfg["code"]
    selected_purchase_price_col = currency_cfg["purchase_price_col"]
    selected_purchase_cost_col = currency_cfg["purchase_cost_col"]
    selected_sell_price_col = currency_cfg["sell_price_col"]
    selected_sell_value_col = currency_cfg["sell_value_col"]
    selected_pl_col = currency_cfg["pl_col"]

    total_grams = analysis_df["Grams"].sum()
    total_logged_cost = analysis_df[selected_purchase_cost_col].sum()
    total_sell_value = analysis_df[selected_sell_value_col].sum()
    projected_pl = total_sell_value - total_logged_cost
    pct_growth = (projected_pl / total_logged_cost) * 100 if total_logged_cost > 0 else 0

    return {
        "selected_currency_code": selected_currency_code,
        "selected_purchase_price_col": selected_purchase_price_col,
        "selected_purchase_cost_col": selected_purchase_cost_col,
        "selected_sell_price_col": selected_sell_price_col,
        "selected_sell_value_col": selected_sell_value_col,
        "selected_pl_col": selected_pl_col,
        "total_grams": total_grams,
        "total_logged_cost": total_logged_cost,
        "total_sell_value": total_sell_value,
        "projected_pl": projected_pl,
        "pct_growth": pct_growth,
    }


def render_portfolio_currency_selector():
    display_currency = st.radio(
        "View currency for chart, summary, and ledger",
        options=["USD", "TRY"],
        horizontal=True,
        key="display_currency",
    )
    st.caption("This changes how the results are displayed. It does not change any saved purchase values.")
    return display_currency


def render_portfolio_kpis(total_grams, total_sell_value, projected_pl, pct_growth, selected_currency_code):
    st.subheader("📊 Combined Portfolio Performance")
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total Weight Owned", f"{total_grams:.2f} grams")
    kpi2.metric(
        f"Sell Today Value ({selected_currency_code})",
        format_money(total_sell_value, selected_currency_code),
        delta=f"{format_money(projected_pl, selected_currency_code)} ({pct_growth:+.2f}%)",
    )
    kpi3.metric(
        f"Net Gain/Loss ({selected_currency_code})",
        format_money(projected_pl, selected_currency_code),
    )


def render_portfolio_chart(analysis_df, selected_purchase_cost_col, selected_sell_value_col, selected_currency_code):
    st.subheader(f"📈 Logged Cost vs. Sell Today Value ({selected_currency_code})")
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=analysis_df["Date"] + " (" + analysis_df["Grams"].astype(str) + "g)",
            y=analysis_df[selected_purchase_cost_col],
            name=f"Logged Cost ({selected_currency_code})",
            marker_color="#636EFA",
        )
    )
    fig.add_trace(
        go.Bar(
            x=analysis_df["Date"] + " (" + analysis_df["Grams"].astype(str) + "g)",
            y=analysis_df[selected_sell_value_col],
            name=f"Sell Today Value ({selected_currency_code})",
            marker_color="#00CC96",
        )
    )
    fig.update_layout(
        barmode="group",
        yaxis_title="US Dollars (USD)" if selected_currency_code == "USD" else "Turkish Lira (TL)",
        template="plotly_dark",
        height=350,
    )
    st.plotly_chart(fig, use_container_width=True)


def _build_ledger_display_df(
    analysis_df,
    selected_purchase_price_col,
    selected_purchase_cost_col,
    selected_sell_price_col,
    selected_sell_value_col,
    selected_pl_col,
    selected_currency_code,
):
    display_df = analysis_df.set_index("id")[
        [
            "Date",
            "Grams",
            selected_purchase_price_col,
            selected_purchase_cost_col,
            selected_sell_price_col,
            selected_sell_value_col,
            selected_pl_col,
        ]
    ].copy()
    display_df = display_df.rename(
        columns={
            selected_purchase_price_col: "Buy Px/g",
            selected_purchase_cost_col: "Logged Cost",
            selected_sell_price_col: "Sell Px/g",
            selected_sell_value_col: "Sell Value",
            selected_pl_col: "P/L",
        }
    )
    display_df["Date"] = display_df["Date"].astype(str)
    display_df["Grams"] = display_df["Grams"].map(lambda value: f"{value:.2f} g")
    display_df["Buy Px/g"] = display_df["Buy Px/g"].map(lambda value: format_money(value, selected_currency_code))
    display_df["Logged Cost"] = display_df["Logged Cost"].map(lambda value: format_money(value, selected_currency_code))
    display_df["Sell Px/g"] = display_df["Sell Px/g"].map(lambda value: format_money(value, selected_currency_code))
    display_df["Sell Value"] = display_df["Sell Value"].map(lambda value: format_money(value, selected_currency_code))
    display_df["P/L"] = display_df["P/L"].map(lambda value: format_money(value, selected_currency_code))
    return display_df


def render_portfolio_ledger(
    analysis_df,
    selected_currency_code,
    selected_purchase_price_col,
    selected_purchase_cost_col,
    selected_sell_price_col,
    selected_sell_value_col,
    selected_pl_col,
    delete_row_callback,
):
    st.subheader("📜 Historical Transaction Ledger")
    st.caption(
        "💡 **To Delete Entries:** Click a row's left checkbox and press **Backspace/Delete**. Deletions are saved automatically. "
        f"The ledger is showing {selected_currency_code} columns only to keep it compact. "
        "Hover the column headers for field details. The logged cost is your exact paid amount; the purchase-date price is reference-only. Sell values include the sell spread."
    )

    display_df = _build_ledger_display_df(
        analysis_df,
        selected_purchase_price_col,
        selected_purchase_cost_col,
        selected_sell_price_col,
        selected_sell_value_col,
        selected_pl_col,
        selected_currency_code,
    )

    edited_df = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config=build_ledger_column_config(selected_currency_code),
        disabled=[
            "Date",
            "Grams",
            "Buy Px/g",
            "Logged Cost",
            "Sell Px/g",
            "Sell Value",
            "P/L",
        ],
        key="ledger_editor",
    )

    deleted_ids = set(display_df.index.tolist()) - set(edited_df.index.tolist())
    if deleted_ids:
        delete_errors = []
        for target_id in deleted_ids:
            try:
                delete_row_callback(target_id)
            except Exception as exc:
                delete_errors.append(str(exc))

        if delete_errors:
            st.error("One or more deletions failed in Supabase. The row(s) will still be present after refresh.")
            for error_message in delete_errors:
                st.code(error_message)
            st.stop()

        st.rerun()


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


def render_portfolio_dashboard(analysis_df, live_snapshot, sell_spread_pct, delete_row_callback):
    if analysis_df.empty:
        st.info(
            "ℹ️ Your portfolio cloud database is currently empty! Fill out the forms on the left sidebar to add transactions."
        )
        return

    analysis_df = analysis_df.copy()
    analysis_df["Date"] = analysis_df["Date"].astype(str)

    display_currency = render_portfolio_currency_selector()
    context = _get_portfolio_display_context(analysis_df, display_currency)

    render_portfolio_kpis(
        context["total_grams"],
        context["total_sell_value"],
        context["projected_pl"],
        context["pct_growth"],
        context["selected_currency_code"],
    )

    st.markdown("---")

    render_portfolio_chart(
        analysis_df,
        context["selected_purchase_cost_col"],
        context["selected_sell_value_col"],
        context["selected_currency_code"],
    )

    render_portfolio_ledger(
        analysis_df,
        context["selected_currency_code"],
        context["selected_purchase_price_col"],
        context["selected_purchase_cost_col"],
        context["selected_sell_price_col"],
        context["selected_sell_value_col"],
        context["selected_pl_col"],
        delete_row_callback,
    )

    render_portfolio_summary(
        context["total_grams"],
        context["total_logged_cost"],
        context["total_sell_value"],
        context["projected_pl"],
        sell_spread_pct,
        live_snapshot,
        context["selected_currency_code"],
    )
