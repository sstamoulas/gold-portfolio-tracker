import datetime
from dataclasses import dataclass

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

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
