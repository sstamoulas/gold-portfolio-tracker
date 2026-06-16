---

# 🪙 Multi-Asset Gold Portfolio Tracker (USD & TRY)

A lightweight, real-time web application built with **Streamlit**, **Python**, and **SQLite** to log and track historical gold purchases in grams. It provides an instantaneous, comprehensive view of your portfolio value, cost basis, and net growth across both **US Dollars (USD)** and **Turkish Lira (TRY)** using live market feeds.

---

## 🚀 Key Features

* **Live Market Feeds:** Automatically fetches real-time spot gold prices (per gram) and USD/TRY forex rates directly from Yahoo Finance (`yfinance`).
* **Flexible Currency Logging:** Gives you the choice to log your transaction records natively in either USD or TRY base currencies.
* **Dynamic Cost Auto-Calculation:** When logging new purchases, the sidebar form dynamically scales the total cost using live market rates. This ensures that a purchase logged at current prices accurately reflects a flat starting growth of exactly `$0.00` / `0.00 TL`.
* **Synchronized Accounting Layer:** Features built-in floating-point mitigation that forces the ledger summary modules to sum screen-rounded figures, successfully preventing common `$0.01` fractional cent mismatches.
* **Interactive Transaction Ledger:** Displays all historical entries via `st.data_editor` supporting interactive checkbox row selection for clean, bulk database deletions.
* **Local Persistent Database:** Integrates a local SQLite architecture (`gold_portfolio.db`) so your transaction entry records safely survive script restarts.

---

## 🛠️ Tech Stack & Requirements

* **Language:** Python 3.8+
* **Framework:** Streamlit (UI & App Engine)
* **Data & Math:** Pandas, NumPy
* **Visualization:** Plotly Graph Objects
* **Database:** SQLite3 (Python Standard Library)
* **Financial API:** yfinance

---

## 💾 Local Installation & Setup

If you are coming back to this project after a break, use these quick steps to spin it up on your local machine:

### 1. File Structure Verification

Ensure your project directory contains the following file structure:

```text
gold-portfolio-tracker/
│
├── gold_growth.py         # Main Application Script
├── requirements.txt       # Cloud & Local Dependencies
└── gold_portfolio.db      # SQLite Database File (auto-generated on first run)

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
pip install -r requirements.txt

```

### 4. Boot Up the Dashboard

```bash
streamlit run gold_growth.py

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

```

### Deployment Steps:

1. Push the project repository to your personal GitHub account (make sure the visibility is set to **Public**).
2. Head over to [share.streamlit.io](https://share.streamlit.io/) and log in using your linked GitHub account.
3. Head over to [supbase.com](https://supabase.com/dashboard/) and find the database used for the live app.
4. Click **"New App"** in the upper right corner.
5. Point the configuration fields to your repository branch, and set the Main file path to `gold_growth.py`.
6. Click **"Deploy"**. Your application will be live on a custom `.streamlit.app` URL within 2 minutes.

> ⚠️ **Important Architecture Note for Cloud Deployments:** Because this app utilizes a local filesystem SQLite file (`gold_portfolio.db`), data stored on the free Streamlit Community Cloud tier is **ephemeral**. The database file will reset whenever the cloud container goes to sleep or gets rebooted by Streamlit. For permanent storage in a production web environment, transition the backend connection layer from SQLite3 to a cloud-hosted Postgres database (such as Supabase or Neon) using Streamlit Secrets.

---

## 🧠 Architectural Notes for Future Reference

### Floating-Point Fix (`$-0.01` Mismatch Resolved)

When base assets are stored as raw floating numbers and converted via multi-decimal exchange rates, cumulative fractional cents can trigger discrepancies between adding up pre-rounded table values vs. calculating totals from raw variables.

The application forces absolute synchronization by running an explicit `round(..., 2)` sequence during the data processing phase:

```python
df_portfolio["Current Value (USD)"] = round(df_portfolio["Grams"] * live_gold_usd, 2)
# The summary row then adds up these display figures natively to maintain 100% visual and logical parity
total_val_usd = df_portfolio["Current Value (USD)"].sum()

```
