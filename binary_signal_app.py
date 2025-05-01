import streamlit as st
import pandas as pd
import requests
import ta
import time

# ─── YOUR TWELVE DATA API KEY ─────────────────────────
twelve_key = "4d5b1e81f9314e28a7ee285497d3b273"  # ← replace with your own key

# ─── SYMBOL MAPPING FOR FOREX PAIRS ────────────────────
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

# ─── TRACKING LIVE ACCURACY ────────────────────────────
if "accuracy" not in st.session_state:
    st.session_state.accuracy = []
    st.session_state.correct_signals = 0
    st.session_state.total_signals = 0

# Store the most recent signal for comparison
latest = df.iloc[-1]
st.session_state.total_signals += 1

# Check if the prediction was correct (for demonstration, compare with close)
if latest["Signal"] == "CALL" and latest["Close"] > latest["Open"]:
    st.session_state.correct_signals += 1
elif latest["Signal"] == "PUT" and latest["Close"] < latest["Open"]:
    st.session_state.correct_signals += 1

# Calculate accuracy
accuracy = (st.session_state.correct_signals / st.session_state.total_signals) * 100

# ─── COUNTDOWN TIMER ───────────────────────────────────
countdown = 5 * 60  # 5 minutes countdown in seconds
if "time_left" not in st.session_state:
    st.session_state.time_left = countdown

if st.session_state.time_left > 0:
    st.session_state.time_left -= 60  # Subtract 60 seconds each refresh
    st.metric("⏳ Countdown", f"{st.session_state.time_left // 60} min {st.session_state.time_left % 60} sec")
else:
    # Reset timer when countdown ends
    st.session_state.time_left = countdown

# ─── DISPLAY SIGNAL ────────────────────────────────────
st.metric("📍 Signal", latest["Signal"], help="Based on EMA9, RSI & MACD")

# ─── DISPLAY LIVE ACCURACY ─────────────────────────────
st.metric("📊 Live Accuracy", f"{accuracy:.2f}%", help="Based on past signals accuracy")

# ─── SHOW RECENT DATA AND BACKTESTING ──────────────────
with st.expander("📊 Show recent data"):
    st.dataframe(df.tail(10))

# ─── DOWNLOAD BACKTEST RESULTS ─────────────────────────
backtest_data = pd.DataFrame({
    "Signal": df["Signal"],
    "Actual": ["CALL" if row["Close"] > row["Open"] else "PUT" for _, row in df.iterrows()],
    "Correct": [1 if row["Signal"] == ("CALL" if row["Close"] > row["Open"] else "PUT") else 0 for _, row in df.iterrows()]
})
backtest_data["Cumulative Correct"] = backtest_data["Correct"].cumsum()

@st.cache_data(ttl=600)
def download_backtest():
    return backtest_data

st.download_button(
    label="Download Backtest Results",
    data=download_backtest().to_csv(index=False),
    file_name="backtest_results.csv",
    mime="text/csv"
)
