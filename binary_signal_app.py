import streamlit as st
import pandas as pd
import requests
import ta

# ─── YOUR TWELVE DATA API KEY ─────────────────────────
twelve_key = "4d5b1e81f9314e28a7ee285497d3b273"  # ← replace with your own key

# ─── SYMBOL MAPPING FOR FOREX PAIRS ────────────────────
# Updated symbol format with slashes for Twelve Data
symbol_map = {
    "EUR/USD": "EUR/USD",
    "USD/JPY": "USD/JPY",
    "GBP/USD": "GBP/USD",
    "AUD/USD": "AUD/USD",
    "USD/CAD": "USD/CAD"
}

symbol = st.selectbox("Choose a forex pair:", list(symbol_map.keys()))

# ─── FETCH FROM TWELVE DATA ────────────────────────────
@st.cache_data(ttl=300)
def fetch_twelve(sym_key):
    sym = symbol_map[sym_key]
    url = (
        "https://api.twelvedata.com/time_series"
        f"?symbol={sym}&interval=5min&outputsize=100&apikey={twelve_key}"
    )
    r = requests.get(url, timeout=10)
    data = r.json()

    # Debug: show raw response
    st.write("Raw Twelve Data response:", data)

    if "values" not in data:
        return None

    df = pd.DataFrame(data["values"])
    df = df.rename(columns={
        "datetime": "Datetime",
        "open":     "Open",
        "high":     "High",
        "low":      "Low",
        "close":    "Close",
        "volume":   "Volume"
    })
    df["Datetime"] = pd.to_datetime(df["Datetime"])
    df = df.set_index("Datetime").astype(float)
    return df.sort_index()

# ─── TITLE & LOAD DATA ─────────────────────────────────
st.title("📈 Binary Trading Signal Bot (Forex Pairs, 5-min)")

df = fetch_twelve(symbol)
if df is None:
    st.error("❌ Could not fetch data from Twelve Data.")
    st.stop()

# ─── INDICATORS ────────────────────────────────────────
df["EMA9"] = ta.trend.ema_indicator(df["Close"], window=9)
df["RSI"]  = ta.momentum.rsi(df["Close"], window=14)
macd = ta.trend.MACD(df["Close"])
df["MACD"] = macd.macd_diff()

# ─── SIGNAL LOGIC ───────────────────────────────────────
def generate_signal(r):
    if r["Close"] > r["EMA9"] and r["RSI"] > 50 and r["MACD"] > 0:
        return "CALL"
    elif r["Close"] < r["EMA9"] and r["RSI"] < 50 and r["MACD"] < 0:
        return "PUT"
    else:
        return "HOLD"

df["Signal"] = df.apply(generate_signal, axis=1)

# ─── DISPLAY SIGNAL ────────────────────────────────────
latest = df.iloc[-1]
st.metric("📍 Signal", latest["Signal"], help="Based on EMA9, RSI & MACD")

# ─── SHOW RECENT DATA ───────────────────────────────────
with st.expander("📊 Show recent data"):
    st.dataframe(df.tail(10))
