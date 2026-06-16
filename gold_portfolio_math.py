import datetime

import pandas as pd

from gold_market_data import fetch_market_snapshot_for_date


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
