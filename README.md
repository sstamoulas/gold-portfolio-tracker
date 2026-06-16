---

# 🪙 Gold Purchase & Sell-Today Tracker (USD & TRY)

A lightweight, real-time web application built with **Streamlit**, **Python**, and **Supabase** to log and track gold purchases in grams. It stores the exact amount you paid, looks up the gold price and USD/TRY rate at the purchase date for reference, compares them with the latest available market close, and shows whether you would gain or lose if you sold today after the configured sell spread.

---

## 🚀 Key Features

* **Historical Purchase Snapshots:** Fetches the closest available market close for the selected purchase date and shows the gold price per gram plus USD/TRY at that point in time.
* **Sell-Today Simulation:** Compares the purchase snapshot against the latest available market close and calculates the value you would receive if you sold today.
* **Configurable Spreads:** Uses a sell spread to model the portfolio-wide sale side of the trade.
* **Flexible Currency Logging:** Gives you the choice to log your transaction records natively in either USD or TRY base currencies.
* **View Currency Toggle:** Switches the chart, summary, and ledger between USD and TRY views so the display stays narrower and easier to scan.
* **Hover Tooltips:** Shows short explanations on the ledger column headers so each field stays compact but still understandable.
* **Interactive Transaction Ledger:** Displays all historical entries via `st.data_editor` supporting interactive checkbox row selection for clean, bulk database deletions.
* **Persistent Cloud Storage:** Integrates with Supabase so your transaction entry records survive script restarts.

---

## 🛠️ Tech Stack & Requirements

* **Language:** Python 3.8+
* **Framework:** Streamlit (UI & App Engine)
* **Data & Math:** Pandas
* **Visualization:** Plotly Graph Objects
* **Database:** Supabase/Postgres
* **Financial API:** yfinance
* **HTTP Client:** requests

---

## 💾 Local Installation & Setup

If you are coming back to this project after a break, use these quick steps to spin it up on your local machine:

### 1. File Structure Verification

Ensure your project directory contains the following file structure:

```text
gold-portfolio-tracker/
│
├── gold_growth.py          # Thin Streamlit entrypoint
├── gold_purchase_sidebar_ui.py # Purchase sidebar controls and form
├── gold_streamlit_ui.py    # Market banner, chart, and ledger renderers
├── gold_ledger_ui.py       # Ledger column config and tooltip labels
├── gold_market_data.py     # Live and historical market snapshot fetchers
├── gold_portfolio_math.py  # Portfolio valuation and formatting helpers
├── gold_portfolio_summary_ui.py # Ledger totals summary renderer
├── gold_supabase_repo.py   # Supabase CRUD helpers
├── tests/                  # Unit tests for portfolio math
├── requirements.txt        # Cloud & Local Dependencies
└── README.md               # Project documentation

```

You also need a Supabase project with a `transactions` table and the following Streamlit secrets:

```toml
SUPABASE_URL = "https://..."
SUPABASE_KEY = "..."
```

### 2. Set Up a Virtual Environment (Recommended)

```bash
# Create a virtual environment
python -m venv venv

# Activate the environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
.\venv\Scripts\activate

```

### 3. Install Dependencies

```bash
python3 -m pip install -r requirements.txt

```

### 4. Run the Tests

```bash
python3 -m unittest discover -s tests

```

### 5. Boot Up the Dashboard

```bash
python3 -m streamlit run gold_growth.py
```

This will automatically launch a tab in your local web browser at `http://localhost:8501`.

---

## ☁️ Free Web Deployment Guide

This app is fully optimized for zero-cost deployment on **Streamlit Community Cloud**.

### Requirements File (`requirements.txt`)

Ensure your `requirements.txt` file is saved in the root directory exactly like this:

```text
streamlit
pandas
plotly
yfinance
requests
supabase

```

### Deployment Steps:

1. Push the project repository to your personal GitHub account (make sure the visibility is set to **Public**).
2. Head over to [share.streamlit.io](https://share.streamlit.io/) and log in using your linked GitHub account.
3. Head over to [supabase.com](https://supabase.com/dashboard/) and find the database used for the live app.
4. Click **"New App"** in the upper right corner.
5. Point the configuration fields to your repository branch, and set the Main file path to `gold_growth.py`.
6. Click **"Deploy"**. Your application will be live on a custom `.streamlit.app` URL within 2 minutes.

> ⚠️ **Important Architecture Note for Cloud Deployments:** This app now expects a Supabase-backed `transactions` table. Streamlit Community Cloud itself is still stateless, so Supabase is the persistence layer that keeps your data between deploys and restarts.

---

## 🧠 Architectural Notes for Future Reference

### Refactored Module Layout

The application logic is now split across small helper modules so the Streamlit entrypoint stays focused on layout and widget state:

- `gold_market_data.py` handles live and historical market snapshots.
- `gold_portfolio_math.py` handles valuation, formatting, and display-currency selection.
- `gold_portfolio_summary_ui.py` handles the ledger totals summary section.
- `gold_purchase_sidebar_ui.py` handles the purchase entry sidebar and form.
- `gold_supabase_repo.py` handles Supabase initialization plus insert, query, and delete operations.
- `gold_ledger_ui.py` handles the ledger column labels and hover tooltips.
- `gold_streamlit_ui.py` handles the market banner, chart, and ledger rendering.
- `gold_growth.py` stays as the Streamlit entrypoint that wires the pieces together.

### Floating-Point Fix (`$-0.01` Mismatch Resolved)

When base assets are stored as raw floating numbers and converted via multi-decimal exchange rates, cumulative fractional cents can trigger discrepancies between adding up pre-rounded table values vs. calculating totals from raw variables.

The application forces absolute synchronization by running an explicit `round(..., 2)` sequence during the data processing phase:

```python
analysis_df["Sell Today Value (USD)"] = round(
    analysis_df["Grams"] * analysis_df["Sell Today Price / Gram (USD)"],
    2,
)
# The summary row then adds up these display figures natively to maintain visual and logical parity
total_sell_usd = analysis_df["Sell Today Value (USD)"].sum()

```
