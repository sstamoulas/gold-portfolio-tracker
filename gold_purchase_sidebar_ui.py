import datetime

import streamlit as st


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
