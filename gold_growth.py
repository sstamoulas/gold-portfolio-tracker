import datetime
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

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
# DATABASE MANAGEMENT LAYER
# ----------------------------------------------------
DB_FILE = "gold_portfolio.db"


def init_db():
    """Initializes the local SQLite database and creates the transactions table."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_date TEXT,
            grams REAL,
            cost_try REAL,
            cost_usd REAL
        )
    """
    )
    conn.commit()
    conn.close()


def add_callback():
    """Isolated callback to handle dynamic input calculations and save to the database."""
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

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO transactions (purchase_date, grams, cost_try, cost_usd) VALUES (?, ?, ?, ?)",
        (str(p_date), g_weight, c_try, c_usd),
    )
    conn.commit()
    conn.close()


def get_all_transactions():
    """Fetches full tabular array data out of the SQLite file."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM transactions", conn)
    conn.close()
    return df


# Trigger DB setup sequence
init_db()

# ----------------------------------------------------
# FETCH LIVE MARKET DATA (Cached for 5 minutes)
# ----------------------------------------------------
@st.cache_data(ttl=300)
def fetch_live_market_data():
    tickers = yf.Tickers("GC=F USDTRY=X")
    gold_close = tickers.tickers["GC=F"].history(period="1d")["Close"].iloc[-1]
    try_close = tickers.tickers["USDTRY=X"].history(period="1d")["Close"].iloc[-1]

    gold_price_per_gram_usd = gold_close / GRAMS_PER_ONCE
    gold_price_per_gram_try = gold_price_per_gram_usd * try_close

    return gold_price_per_gram_usd, gold_price_per_gram_try, try_close


try:
    live_gold_usd, live_gold_try, live_usd_try = fetch_live_market_data()
except Exception as e:
    st.error(f"Error fetching live exchange data from Yahoo Finance: {e}")
    st.stop()

# ----------------------------------------------------
# SIDEBAR - DATA ENTRY LOG
# ----------------------------------------------------
st.sidebar.header("📝 Log Purchase Records")
st.sidebar.markdown("Add your transaction details below:")

# Currency selector
chosen_currency = st.sidebar.radio(
    "Purchase Currency Base:",
    options=["TRY", "USD"],
    horizontal=True,
    key="input_currency",
)

# Gram input outside the form container
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

# Display real-time ticker values globally at the top
m_col1, m_col2, m_col3 = st.columns(3)
m_col1.metric("Live Gold Price / Gram (USD)", f"${live_gold_usd:,.2f}")
m_col2.metric("Live Gold Price / Gram (TRY)", f"{live_gold_try:,.2f} TL")
m_col3.metric("Live Forex Exchange (USD/TRY)", f"{live_usd_try:,.4f}")

st.markdown("---")

# Check if portfolio has contents before continuing UI operations
if df_portfolio.empty:
    st.info(
        "ℹ️ Your portfolio database is currently empty! Fill out the forms on the left sidebar to add transactions."
    )
else:
    df_portfolio = df_portfolio.rename(
        columns={
            "purchase_date": "Date",
            "grams": "Grams",
            "cost_try": "Cost (TRY)",
            "cost_usd": "Cost (USD)",
        }
    )

    # Compute live performance updates (Pre-rounding here ensures math consistency across modules)
    df_portfolio["Current Value (USD)"] = round(df_portfolio["Grams"] * live_gold_usd, 2)
    df_portfolio["Current Value (TRY)"] = round(df_portfolio["Grams"] * live_gold_try, 2)
    df_portfolio["Growth (USD)"] = round(
        df_portfolio["Current Value (USD)"] - df_portfolio["Cost (USD)"], 2
    )
    df_portfolio["Growth (TRY)"] = round(
        df_portfolio["Current Value (TRY)"] - df_portfolio["Cost (TRY)"], 2
    )

    # Portfolio Aggregation Summaries
    total_grams = df_portfolio["Grams"].sum()
    total_cost_usd = df_portfolio["Cost (USD)"].sum()
    total_cost_try = df_portfolio["Cost (TRY)"].sum()
    
    # FIXED: Summary calculations now sum the rounded columns directly to avoid a 1-cent discrepancy
    total_val_usd = df_portfolio["Current Value (USD)"].sum()
    total_val_try = df_portfolio["Current Value (TRY)"].sum()
    growth_usd = df_portfolio["Growth (USD)"].sum()
    growth_try = df_portfolio["Growth (TRY)"].sum()
    
    pct_growth_usd = (growth_usd / total_cost_usd) * 100 if total_cost_usd > 0 else 0

    # Comprehensive Metrics Breakdown
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

    # Charting Layer
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
    # INTERACTIVE LEDGER (WITH INLINE / BULK DELETE)
    # ----------------------------------------------------
    st.subheader("📜 Historical Transaction Ledger")
    st.caption(
        "💡 **To Delete Entries:** Click a row's left checkbox (or select multiple rows) and press **Backspace/Delete** on your keyboard, then click the Save button below."
    )

    # Format values cleanly for display while preserving raw database mappings
    display_df = df_portfolio.copy()
    display_df["Cost (USD)"] = display_df["Cost (USD)"].map("${:,.2f}".format)
    display_df["Current Value (USD)"] = display_df["Current Value (USD)"].map(
        "${:,.2f}".format
    )
    display_df["Growth (USD)"] = display_df["Growth (USD)"].map("${:+,.2f}".format)
    display_df["Cost (TRY)"] = display_df["Cost (TRY)"].map("{:,.2f} TL".format)
    display_df["Current Value (TRY)"] = display_df["Current Value (TRY)"].map(
        "{:,.2f} TL".format
    )
    display_df["Growth (TRY)"] = display_df["Growth (TRY)"].map("{:+,.2f} TL".format)

    # Render interactive data table
    edited_df = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        disabled=[
            "id",
            "Date",
            "Grams",
            "Cost (TRY)",
            "Cost (USD)",
            "Current Value (USD)",
            "Current Value (TRY)",
            "Growth (USD)",
            "Growth (TRY)",
        ],
        key="ledger_editor",
    )

    # Ledger Totals Summary
    st.markdown("### 🧮 Ledger Totals Summary")
    t_col1, t_col2, t_col3, t_col4, t_col5, t_col6, t_col7 = st.columns(7)
    t_col1.markdown(f"**Total Grams:**\n{total_grams:.2f}g")
    t_col2.markdown(f"**Total Cost (TRY):**\n{total_cost_try:,.2f} TL")
    t_col3.markdown(f"**Total Cost (USD):**\n${total_cost_usd:,.2f}")
    t_col4.markdown(f"**Current Value (USD):**\n${total_val_usd:,.2f}")
    t_col5.markdown(f"**Current Value (TRY):**\n{total_val_try:,.2f} TL")
    
    # Format growth values with dynamic coloring markup strings
    g_usd_color = "green" if growth_usd >= 0 else "red"
    g_try_color = "green" if growth_try >= 0 else "red"
    t_col6.markdown(f"**Total Growth (USD):**\n<span style='color:{g_usd_color}; font-weight:bold;'>${growth_usd:+,.2f}</span>", unsafe_allow_html=True)
    t_col7.markdown(f"**Total Growth (TRY):**\n<span style='color:{g_try_color}; font-weight:bold;'>{growth_try:+,.2f} TL</span>", unsafe_allow_html=True)

    # Database sync handler for deletions
    if len(edited_df) < len(display_df):
        st.markdown("")
        col_sync1, col_sync2 = st.columns([1, 4])
        with col_sync1:
            if st.button("🗑️ Sync Deletions to Database", use_container_width=True):
                remaining_ids = set(edited_df["id"].tolist())
                all_original_ids = set(display_df["id"].tolist())
                deleted_ids = all_original_ids - remaining_ids

                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                for target_id in deleted_ids:
                    cursor.execute(
                        "DELETE FROM transactions WHERE id = ?", (target_id,)
                    )
                conn.commit()
                conn.close()

                st.success("Database synced successfully!")
                st.rerun()