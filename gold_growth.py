import datetime
from dataclasses import dataclass
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
import requests
from supabase import create_client

# 1. Page Config
st.set_page_config(page_title="Multi-Asset Gold Portfolio Tracker", page_icon="🪙", layout="wide")

# 2. Supabase Initialization
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()
GRAMS_PER_ONCE = 31.1034768


@dataclass(frozen=True)
class MarketSnapshot:
    gold_usd_per_gram: float
    gold_try_per_gram: float
    usd_try: float
    gold_source_date: datetime.date
    fx_source_date: datetime.date
    is_fallback: bool = False


def build_yfinance_session():
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
    )
    return session


def _close_on_or_before(ticker_symbol, target_date, lookback_days=14):
    target_date = pd.Timestamp(target_date).date()
    session = build_yfinance_session()
    ticker = yf.Ticker(ticker_symbol, session=session)
    start = pd.Timestamp(target_date) - pd.Timedelta(days=lookback_days)
    end = pd.Timestamp(target_date) + pd.Timedelta(days=2)

    history = ticker.history(
        start=start.to_pydatetime(),
        end=end.to_pydatetime(),
        interval="1d",
        auto_adjust=False,
    )

    if history.empty or "Close" not in history.columns:
        raise ValueError(f"No market data returned for {ticker_symbol}")

    history = history.dropna(subset=["Close"])
    history = history.loc[history.index.date <= target_date]

    if history.empty:
        expanded_start = pd.Timestamp(target_date) - pd.Timedelta(days=lookback_days * 2)
        history = ticker.history(
            start=expanded_start.to_pydatetime(),
            end=end.to_pydatetime(),
            interval="1d",
            auto_adjust=False,
        )
        if history.empty or "Close" not in history.columns:
            raise ValueError(f"No market data returned for {ticker_symbol}")
        history = history.dropna(subset=["Close"])
        history = history.loc[history.index.date <= target_date]

    if history.empty:
        raise ValueError(f"No market data available on or before {target_date} for {ticker_symbol}")

    row = history.iloc[-1]
    source_date = history.index[-1].date()
    return float(row["Close"]), source_date


@st.cache_data(ttl=300)
def fetch_live_market_data():
    try:
        gold_close, gold_source_date = _close_on_or_before("GC=F", datetime.date.today())
        usd_try, fx_source_date = _close_on_or_before("USDTRY=X", datetime.date.today())
        gold_price_per_gram_usd = gold_close / GRAMS_PER_ONCE
        gold_price_per_gram_try = gold_price_per_gram_usd * usd_try
        return MarketSnapshot(
            gold_price_per_gram_usd,
            gold_price_per_gram_try,
            usd_try,
            gold_source_date,
            fx_source_date,
            False,
        )
    except Exception:
        fallback_gold_usd = 75.25  # Rough baseline price per gram (~$2340/oz)
        fallback_usd_try = 32.50
        fallback_gold_try = fallback_gold_usd * fallback_usd_try
        today = datetime.date.today()
        return MarketSnapshot(
            fallback_gold_usd,
            fallback_gold_try,
            fallback_usd_try,
            today,
            today,
            True,
        )


@st.cache_data(ttl=86400)
def fetch_market_snapshot_for_date(target_date):
    target_date = pd.Timestamp(target_date).date()
    try:
        gold_close, gold_source_date = _close_on_or_before("GC=F", target_date)
        usd_try, fx_source_date = _close_on_or_before("USDTRY=X", target_date)
        gold_price_per_gram_usd = gold_close / GRAMS_PER_ONCE
        gold_price_per_gram_try = gold_price_per_gram_usd * usd_try
        return MarketSnapshot(
            gold_price_per_gram_usd,
            gold_price_per_gram_try,
            usd_try,
            gold_source_date,
            fx_source_date,
            False,
        )
    except Exception:
        live_snapshot = fetch_live_market_data()
        return MarketSnapshot(
            live_snapshot.gold_usd_per_gram,
            live_snapshot.gold_try_per_gram,
            live_snapshot.usd_try,
            target_date,
            target_date,
            True,
        )


def build_portfolio_analysis(df_portfolio, sell_spread_pct, live_snapshot):
    if df_portfolio.empty:
        return df_portfolio, {}

    analysis_df = df_portfolio.copy()
    analysis_df["Date"] = pd.to_datetime(analysis_df["Date"], errors="coerce").dt.date
    analysis_df["Grams"] = pd.to_numeric(analysis_df["Grams"], errors="coerce")
    analysis_df["Cost (TRY)"] = pd.to_numeric(analysis_df["Cost (TRY)"], errors="coerce")
    analysis_df["Cost (USD)"] = pd.to_numeric(analysis_df["Cost (USD)"], errors="coerce")

    unique_dates = sorted({d for d in analysis_df["Date"].dropna().tolist() if isinstance(d, datetime.date)})
    purchase_snapshots = {target_date: fetch_market_snapshot_for_date(target_date) for target_date in unique_dates}
    fallback_used = live_snapshot.is_fallback or any(snapshot.is_fallback for snapshot in purchase_snapshots.values())

    def snapshot_for_date(target_date):
        snapshot = purchase_snapshots.get(target_date)
        if snapshot is None:
            return live_snapshot
        return snapshot

    analysis_df["Purchase Price / Gram (USD)"] = analysis_df["Date"].apply(
        lambda target_date: snapshot_for_date(target_date).gold_usd_per_gram
    )
    analysis_df["Purchase Price / Gram (TRY)"] = analysis_df["Date"].apply(
        lambda target_date: snapshot_for_date(target_date).gold_try_per_gram
    )
    analysis_df["Purchase USD/TRY"] = analysis_df["Date"].apply(
        lambda target_date: snapshot_for_date(target_date).usd_try
    )

    sell_multiplier = 1 - (sell_spread_pct / 100)

    analysis_df["Sell Today Price / Gram (USD)"] = round(
        live_snapshot.gold_usd_per_gram * sell_multiplier,
        4,
    )
    analysis_df["Sell Today Price / Gram (TRY)"] = round(
        live_snapshot.gold_try_per_gram * sell_multiplier,
        4,
    )
    analysis_df["Sell Today Value (USD)"] = round(
        analysis_df["Grams"] * analysis_df["Sell Today Price / Gram (USD)"],
        2,
    )
    analysis_df["Sell Today Value (TRY)"] = round(
        analysis_df["Grams"] * analysis_df["Sell Today Price / Gram (TRY)"],
        2,
    )
    analysis_df["Projected P/L (USD)"] = round(
        analysis_df["Sell Today Value (USD)"] - analysis_df["Cost (USD)"],
        2,
    )
    analysis_df["Projected P/L (TRY)"] = round(
        analysis_df["Sell Today Value (TRY)"] - analysis_df["Cost (TRY)"],
        2,
    )

    return analysis_df, fallback_used


def get_display_currency_config(display_currency):
    if display_currency == "USD":
        return {
            "code": "USD",
            "purchase_price_col": "Purchase Price / Gram (USD)",
            "purchase_cost_col": "Cost (USD)",
            "sell_price_col": "Sell Today Price / Gram (USD)",
            "sell_value_col": "Sell Today Value (USD)",
            "pl_col": "Projected P/L (USD)",
        }

    return {
        "code": "TRY",
        "purchase_price_col": "Purchase Price / Gram (TRY)",
        "purchase_cost_col": "Cost (TRY)",
        "sell_price_col": "Sell Today Price / Gram (TRY)",
        "sell_value_col": "Sell Today Value (TRY)",
        "pl_col": "Projected P/L (TRY)",
    }


def format_money(value, currency_code):
    if pd.isna(value):
        return ""

    if currency_code == "USD":
        return f"${value:,.2f}"

    return f"{value:,.2f} TL"


def build_ledger_column_config(currency_code):
    return {
        "Date": st.column_config.Column(
            "Date",
            help="Purchase date used to look up the historical market close.",
            width="small",
        ),
        "Grams": st.column_config.Column(
            "g",
            help="Amount of gold in the transaction.",
            width="small",
        ),
        "Buy Px/g": st.column_config.Column(
            "Buy Px/g",
            help=f"Reference market price per gram on the purchase date. This is informational and not your actual paid amount. Displayed in {currency_code}.",
            width="small",
        ),
        "Logged Cost": st.column_config.Column(
            "Logged Cost",
            help=f"The amount you actually paid and logged for this transaction. Displayed in {currency_code}.",
            width="small",
        ),
        "Sell Px/g": st.column_config.Column(
            "Sell Px/g",
            help=f"Current sell price per gram after the sell spread. Displayed in {currency_code}.",
            width="small",
        ),
        "Sell Value": st.column_config.Column(
            "Sell Value",
            help=f"Expected cash value if you sold today after the sell spread. Displayed in {currency_code}.",
            width="small",
        ),
        "P/L": st.column_config.Column(
            "P/L",
            help=f"Sell Value minus Logged Cost for the selected currency. Displayed in {currency_code}.",
            width="small",
        ),
    }

# 3. Data Functions (REST API ONLY)
def add_transaction(p_date, g_weight, c_raw, fx_rate, currency):
    if currency == "TRY":
        c_try, c_usd = c_raw, round(c_raw / fx_rate, 2)
    else:
        c_usd, c_try = c_raw, round(c_raw * fx_rate, 2)
    
    data = {
        "purchase_date": str(p_date),
        "grams": float(g_weight),
        "cost_try": float(c_try),
        "cost_usd": float(c_usd)
    }
    response = supabase.table("transactions").insert(data).execute()
    return response

def get_all_transactions():
    response = supabase.table("transactions").select("*").order("id").execute()
    return pd.DataFrame(response.data)

def delete_transaction(target_id):
    try:
        response = supabase.table("transactions").delete().eq("id", target_id).execute()
    except Exception as exc:
        raise RuntimeError(f"Supabase delete failed for transaction ID {target_id}: {exc}") from exc

    return response

# --- CALLBACKS ---
def add_callback():
    add_transaction(
        st.session_state["input_date"],
        st.session_state["input_grams"],
        st.session_state["input_cost_raw"],
        st.session_state["input_fx"],
        st.session_state["input_currency"]
    )

# Execute data fetch
live_snapshot = fetch_live_market_data()

# Warn the user beautifully if we are running on fallback data instead of crashing
if live_snapshot.is_fallback:
    st.warning("⚠️ Yahoo Finance is temporarily rate-limiting connections. Displaying approximate baseline asset pricing for now.")

# ----------------------------------------------------
# SIDEBAR - DATA ENTRY LOG
# ----------------------------------------------------
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

purchase_snapshot = fetch_market_snapshot_for_date(purchase_date)

st.sidebar.markdown("### Purchase Snapshot")
st.sidebar.metric("Gold / gram (USD)", f"${purchase_snapshot.gold_usd_per_gram:,.2f}")
st.sidebar.metric("Gold / gram (TRY)", f"{purchase_snapshot.gold_try_per_gram:,.2f} TL")
st.sidebar.metric("USD/TRY", f"{purchase_snapshot.usd_try:,.4f}")
st.sidebar.caption(
    f"Reference-only market close from {purchase_snapshot.gold_source_date} for gold and {purchase_snapshot.fx_source_date} for FX."
)

with st.sidebar.form("purchase_form", clear_on_submit=True):
    if chosen_currency == "TRY":
        label_text = "Logged Cost (in Turkish Lira - TRY)"
        dynamic_default_cost = round(grams * purchase_snapshot.gold_try_per_gram, 2)
        step_val = 500.0
    else:
        label_text = "Logged Cost (in US Dollars - USD)"
        dynamic_default_cost = round(grams * purchase_snapshot.gold_usd_per_gram, 2)
        step_val = 50.0

    total_paid_raw = st.number_input(
        label_text,
        min_value=0.01,
        value=dynamic_default_cost,
        step=step_val,
        key="input_cost_raw",
    )

    historical_usd_try = st.number_input(
        "Purchase USD/TRY rate (auto-filled from purchase date):",
        min_value=1.0,
        value=float(purchase_snapshot.usd_try),
        step=0.01,
        format="%.4f",
        key="input_fx",
    )

    st.caption(
        "The prefilled logged cost uses the selected purchase date and the purchase-day USD/TRY rate. "
        "This applies only to the row you are saving. You can override it with the exact amount you paid before saving. "
        "Gain/loss uses the saved cost basis, and the sell spread applies to every row in the sell-today view."
    )
    st.form_submit_button("➕ Save Permanently to DB", on_click=add_callback)

# ----------------------------------------------------
# PROCESS PORTFOLIO DATA ARCHITECTURE
# ----------------------------------------------------
df_portfolio = get_all_transactions()

if not df_portfolio.empty:
    df_portfolio["purchase_date"] = pd.to_datetime(df_portfolio["purchase_date"], errors="coerce").dt.date
    df_portfolio = df_portfolio.rename(
        columns={
            "purchase_date": "Date",
            "grams": "Grams",
            "cost_try": "Cost (TRY)",
            "cost_usd": "Cost (USD)",
        }
    )
    analysis_df, historical_fallback_used = build_portfolio_analysis(
        df_portfolio,
        sell_spread_pct,
        live_snapshot,
    )
else:
    analysis_df = df_portfolio
    historical_fallback_used = False

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

if analysis_df.empty:
    st.info(
        "ℹ️ Your portfolio cloud database is currently empty! Fill out the forms on the left sidebar to add transactions."
    )
else:
    analysis_df["Date"] = analysis_df["Date"].astype(str)

    display_currency = st.radio(
        "View currency for chart, summary, and ledger",
        options=["USD", "TRY"],
        horizontal=True,
        key="display_currency",
    )
    st.caption("This changes how the results are displayed. It does not change any saved purchase values.")
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

    st.markdown("---")

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

    # ----------------------------------------------------
    # INTERACTIVE LEDGER (WITH DELETIONS)
    # ----------------------------------------------------
    st.subheader("📜 Historical Transaction Ledger")
    st.caption(
        "💡 **To Delete Entries:** Click a row's left checkbox and press **Backspace/Delete**. Deletions are saved automatically. "
        f"The ledger is showing {selected_currency_code} columns only to keep it compact. "
        "Hover the column headers for field details. The logged cost is your exact paid amount; the purchase-date price is reference-only. Sell values include the sell spread."
    )

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
                delete_transaction(target_id)
            except Exception as exc:
                delete_errors.append(str(exc))

        if delete_errors:
            st.error("One or more deletions failed in Supabase. The row(s) will still be present after refresh.")
            for error_message in delete_errors:
                st.code(error_message)
            st.stop()

        st.rerun()

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
