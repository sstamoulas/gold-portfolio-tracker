import streamlit as st

st.set_page_config(page_title="Multi-Asset Gold Portfolio Tracker", page_icon="🪙", layout="wide")

from gold_market_data import fetch_live_market_data, fetch_market_snapshot_for_date
from gold_portfolio_math import build_portfolio_analysis
from gold_purchase_sidebar_ui import render_purchase_sidebar
from gold_streamlit_ui import render_market_snapshot_banner, render_portfolio_dashboard
from gold_supabase_repo import add_transaction, delete_transaction, get_all_transactions, init_supabase

supabase = init_supabase()


def add_callback(p_date, g_weight, c_raw, fx_rate, currency):
    add_transaction(
        supabase,
        p_date,
        g_weight,
        c_raw,
        fx_rate,
        currency,
    )


def delete_callback(target_id):
    delete_transaction(supabase, target_id)


live_snapshot = fetch_live_market_data()

if live_snapshot.is_fallback:
    st.warning("⚠️ Yahoo Finance is temporarily rate-limiting connections. Displaying approximate baseline asset pricing for now.")

sell_spread_pct = render_purchase_sidebar(fetch_market_snapshot_for_date, add_callback)

df_portfolio = get_all_transactions(supabase)
analysis_df, historical_fallback_used = build_portfolio_analysis(df_portfolio, sell_spread_pct, live_snapshot)

render_market_snapshot_banner(live_snapshot, sell_spread_pct, historical_fallback_used)
render_portfolio_dashboard(analysis_df, live_snapshot, sell_spread_pct, delete_callback)
