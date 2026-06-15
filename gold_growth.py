import datetime
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from sqlalchemy import create_engine, text

# Set up the web page configurations
st.set_page_config(
    page_title="Multi-Asset Gold Portfolio Tracker", page_icon="🪙", layout="wide"
)

st.title("🪙 Gold Portfolio Tracker (USD & TRY)")
st.markdown(
    "Log your historical purchases in grams and track their real-time values across multiple currencies."
)

# Conversion Constant: 1 Troy Ounce = ~31.1035 Grams
GRAMS_PER_ONCE = 31.1034768

# ----------------------------------------------------
# DATABASE MANAGEMENT LAYER (POSTGRESQL VIA SUPABASE)
# ----------------------------------------------------
try:
    DB_URL = st.secrets["db_url"]
    engine = create_engine(DB_URL)
except Exception as e:
    st.error("Missing database connection details. Please set up 'db_url' in your Streamlit Secrets.")
    st.stop()


def add_callback():
    """Isolated callback to handle dynamic input calculations and save to Supabase."""
    p_date = st.session_state["input_date"]
    g_weight = st.session_state["input_grams"]
    currency_choice = st.session_state["input_currency"]
    fx_rate = st.session_state["input_fx"]
    c_raw = st.session_state["input_cost_raw"]

    if currency_choice == "TRY":
        c_try = c_raw
        c_usd = round(c_try / fx_rate, 2)
    else:  # USD selected
        c_usd = c_raw
        c_try = round(c_usd * fx_rate, 2)

    query = text(
        "INSERT INTO transactions (purchase_date, grams, cost_try, cost_usd) VALUES (:p_date, :grams, :c_try, :c_usd)"
    )
    with engine.begin() as conn:
        conn.execute(
            query,
            {
                "p_date": p_date,
                "grams": g_weight,
                "c_try": c_try,
                "c_usd": c_usd,
            },
        )


def get_all_transactions():
    """Fetches full tabular array data out of the cloud Postgres instance."""
    with engine.connect() as conn:
        df = pd.read_sql_query("SELECT * FROM transactions ORDER BY id ASC", conn)
    return df


# ----------------------------------------------------
# FETCH LIVE MARKET DATA (With anti-rate-limiting headers)
# ----------------------------------------------------
@st.cache_data(ttl=300)
def fetch_live_market_data():
    try:
        # Create a custom session with custom browser headers to bypass yfinance blocks
        import requests
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        tickers = yf.Tickers("GC=F USDTRY=X", session=session)
        gold_close = tickers.tickers["GC=F"].history(period="1d")["Close"].iloc[-1]
        try_close = tickers.tickers["USDTRY=X"].history(period="1d")["Close"].iloc[-1]

        gold_price_per_gram_usd = gold_close / GRAMS_PER_ONCE
        gold_price_per_gram_try = gold_price_per_gram_usd * try_close
        
        return gold_price_per_gram_usd, gold_price_per_gram_try, try_close, False

    except Exception as e:
        # Fallback values if Yahoo Finance continues to block the IP address completely
        fallback_gold_usd = 75.25  # Rough baseline price per gram (~$2340/oz)
        fallback_usd_try = 32.50   # Rough baseline conversion rate
        fallback_gold_try = fallback_gold_usd * fallback_usd_try
        
        return fallback_gold_usd, fallback_gold_try, fallback_usd_try, True


# Execute data fetch
live_gold_usd, live_gold_try, live_usd_try, is_fallback = fetch_live_market_data()

# Warn the user beautifully if we are running on fallback data instead of crashing
if is_fallback:
    st.warning("⚠️ Yahoo Finance is temporarily rate-limiting connections. Displaying approximate baseline asset pricing for now.")

# ----------------------------------------------------
# SIDEBAR - DATA ENTRY LOG
# ----------------------------------------------------
st.sidebar.header("📝 Log Purchase Records")
st.sidebar.markdown("Add your transaction details below:")

chosen_currency = st.sidebar.radio(
    "Purchase Currency Base:",
    options=["TRY", "USD"],
    horizontal=True,
    key="input_currency",
)

grams = st.sidebar.number_input(
    "Grams Purchased", min_value=0.1, value=10.0, step=1.0, key="input_grams"
)

with st.sidebar.form("purchase_form", clear_on_submit=True):
    purchase_date = st.date_input(
        "Purchase Date",
        value=datetime.date.today(),
        max_value=datetime.date.today(),
        key="input_date",
    )

    if chosen_currency == "TRY":
        label_text = "Total Paid (in Turkish Lira - TRY)"
        dynamic_default_cost = round(grams * live_gold_try, 2)
        step_val = 500.0
    else:
        label_text = "Total Paid (in US Dollars - USD)"
        dynamic_default_cost = round(grams * live_gold_usd, 2)
        step_val = 50.0

    total_paid_raw = st.number_input(
        label_text,
        min_value=0.01,
        value=dynamic_default_cost,
        step=step_val,
        key="input_cost_raw",
    )

    historical_usd_try = st.number_input(
        "Historical USD/TRY rate at purchase:",
        min_value=1.0,
        value=float(live_usd_try),
        step=0.01,
        format="%.4f",
        key="input_fx",
    )

    st.form_submit_button("➕ Save Permanently to DB", on_click=add_callback)

# ----------------------------------------------------
# PROCESS PORTFOLIO DATA ARCHITECTURE
# ----------------------------------------------------
df_portfolio = get_all_transactions()

m_col1, m_col2, m_col3 = st.columns(3)
m_col1.metric("Gold Price / Gram (USD)", f"${live_gold_usd:,.2f}")
m_col2.metric("Gold Price / Gram (TRY)", f"{live_gold_try:,.2f} TL")
m_col3.metric("Forex Exchange (USD/TRY)", f"{live_usd_try:,.4f}")

st.markdown("---")

if df_portfolio.empty:
    st.info(
        "ℹ️ Your portfolio cloud database is currently empty! Fill out the forms on the left sidebar to add transactions."
    )
else:
    # Ensure standard string conversion for dates fetched from postgresql
    df_portfolio["purchase_date"] = df_portfolio["purchase_date"].astype(str)
    
    df_portfolio = df_portfolio.rename(
        columns={
            "purchase_date": "Date",
            "grams": "Grams",
            "cost_try": "Cost (TRY)",
            "cost_usd": "Cost (USD)",
        }
    )

    df_portfolio["Current Value (USD)"] = round(df_portfolio["Grams"] * live_gold_usd, 2)
    df_portfolio["Current Value (TRY)"] = round(df_portfolio["Grams"] * live_gold_try, 2)
    df_portfolio["Growth (USD)"] = round(
        df_portfolio["Current Value (USD)"] - df_portfolio["Cost (USD)"], 2
    )
    df_portfolio["Growth (TRY)"] = round(
        df_portfolio["Current Value (TRY)"] - df_portfolio["Cost (TRY)"], 2
    )

    total_grams = df_portfolio["Grams"].sum()
    total_cost_usd = df_portfolio["Cost (USD)"].sum()
    total_cost_try = df_portfolio["Cost (TRY)"].sum()
    
    total_val_usd = df_portfolio["Current Value (USD)"].sum()
    total_val_try = df_portfolio["Current Value (TRY)"].sum()
    growth_usd = df_portfolio["Growth (USD)"].sum()
    growth_try = df_portfolio["Growth (TRY)"].sum()
    
    pct_growth_usd = (growth_usd / total_cost_usd) * 100 if total_cost_usd > 0 else 0

    st.subheader("📊 Combined Portfolio Performance")
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total Weight Owned", f"{total_grams:.2f} grams")
    kpi2.metric(
        "Total Portfolio Value (USD)",
        f"${total_val_usd:,.2f}",
        delta=f"${growth_usd:+,.2f} ({pct_growth_usd:+.2f}%)",
    )
    kpi3.metric(
        "Total Portfolio Value (TRY)",
        f"{total_val_try:,.2f} TL",
        delta=f"{growth_try:+,.2f} TL",
    )

    st.markdown("---")

    st.subheader("📈 Value Comparison vs. Purchase Cost")
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df_portfolio["Date"] + " (" + df_portfolio["Grams"].astype(str) + "g)",
            y=df_portfolio["Cost (TRY)"],
            name="Purchase Cost (TRY)",
            marker_color="#636EFA",
        )
    )
    fig.add_trace(
        go.Bar(
            x=df_portfolio["Date"] + " (" + df_portfolio["Grams"].astype(str) + "g)",
            y=df_portfolio["Current Value (TRY)"],
            name="Current Value (TRY)",
            marker_color="#00CC96",
        )
    )
    fig.update_layout(
        barmode="group",
        yaxis_title="Turkish Lira (TL)",
        template="plotly_dark",
        height=350,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ----------------------------------------------------
    # INTERACTIVE LEDGER (WITH DELETIONS)
    # ----------------------------------------------------
    st.subheader("📜 Historical Transaction Ledger")
    st.caption(
        "💡 **To Delete Entries:** Click a row's left checkbox and press **Backspace/Delete**, then sync below."
    )

    display_df = df_portfolio.copy()
    display_df["Cost (USD)"] = display_df["Cost (USD)"].map("${:,.2f}".format)
    display_df["Current Value (USD)"] = display_df["Current Value (USD)"].map("${:,.2f}".format)
    display_df["Growth (USD)"] = display_df["Growth (USD)"].map("${:+,.2f}".format)
    display_df["Cost (TRY)"] = display_df["Cost (TRY)"].map("{:,.2f} TL".format)
    display_df["Current Value (TRY)"] = display_df["Current Value (TRY)"].map("{:,.2f} TL".format)
    display_df["Growth (TRY)"] = display_df["Growth (TRY)"].map("{:+,.2f} TL".format)

    edited_df = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        disabled=[
            "id", "Date", "Grams", "Cost (TRY)", "Cost (USD)",
            "Current Value (USD)", "Current Value (TRY)", "Growth (USD)", "Growth (TRY)"
        ],
        key="ledger_editor",
    )

    st.markdown("### 🧮 Ledger Totals Summary")
    t_col1, t_col2, t_col3, t_col4, t_col5, t_col6, t_col7 = st.columns(7)
    t_col1.markdown(f"**Total Grams:**\n{total_grams:.2f}g")
    t_col2.markdown(f"**Total Cost (TRY):**\n{total_cost_try:,.2f} TL")
    t_col3.markdown(f"**Total Cost (USD):**\n${total_cost_usd:,.2f}")
    t_col4.markdown(f"**Current Value (USD):**\n${total_val_usd:,.2f}")
    t_col5.markdown(f"**Current Value (TRY):**\n{total_val_try:,.2f} TL")
    
    g_usd_color = "green" if growth_usd >= 0 else "red"
    g_try_color = "green" if growth_try >= 0 else "red"
    t_col6.markdown(f"**Total Growth (USD):**\n<span style='color:{g_usd_color}; font-weight:bold;'>${growth_usd:+,.2f}</span>", unsafe_allow_html=True)
    t_col7.markdown(f"**Total Growth (TRY):**\n<span style='color:{g_try_color}; font-weight:bold;'>{growth_try:+,.2f} TL</span>", unsafe_allow_html=True)

    if len(edited_df) < len(display_df):
        st.markdown("")
        col_sync1, col_sync2 = st.columns([1, 4])
        with col_sync1:
            if st.button("🗑️ Sync Deletions to Database", use_container_width=True):
                remaining_ids = set(edited_df["id"].tolist())
                all_original_ids = set(display_df["id"].tolist())
                deleted_ids = all_original_ids - remaining_ids

                query = text("DELETE FROM transactions WHERE id = :target_id")
                with engine.begin() as conn:
                    for target_id in deleted_ids:
                        conn.execute(query, {"target_id": target_id})

                st.success("Cloud Database synced successfully!")
                st.rerun()