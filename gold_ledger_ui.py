import streamlit as st


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
