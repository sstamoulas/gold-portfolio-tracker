import pandas as pd
import streamlit as st
from supabase import create_client


@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def build_transaction_payload(p_date, g_weight, c_raw, fx_rate, currency):
    if currency == "TRY":
        c_try, c_usd = c_raw, round(c_raw / fx_rate, 2)
    else:
        c_usd, c_try = c_raw, round(c_raw * fx_rate, 2)

    return {
        "purchase_date": str(p_date),
        "grams": float(g_weight),
        "cost_try": float(c_try),
        "cost_usd": float(c_usd),
    }


def add_transaction(client, p_date, g_weight, c_raw, fx_rate, currency):
    data = build_transaction_payload(p_date, g_weight, c_raw, fx_rate, currency)
    response = client.table("transactions").insert(data).execute()
    return response


def get_all_transactions(client):
    response = client.table("transactions").select("*").order("id").execute()
    return pd.DataFrame(response.data)


def delete_transaction(client, target_id):
    try:
        response = client.table("transactions").delete().eq("id", target_id).execute()
    except Exception as exc:
        raise RuntimeError(f"Supabase delete failed for transaction ID {target_id}: {exc}") from exc

    return response
