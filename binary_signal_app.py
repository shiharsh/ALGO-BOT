import streamlit as st
import pandas as pd
import requests
import ta
import time
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
from zoneinfo import ZoneInfo  # ✅ For IST time zone

# ─── AUTO-REFRESH EVERY SECOND ────────────────────────
st_autorefresh(interval=1000, limit=None, key="timer_refresh")

# ─── YOUR TWELVE DATA API KEY ─────────────────────────
twelve_key = "4d5b1e81f9314e28a7ee285497d3b273"

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
        f"?symbol={sym}&interval=5min&outputsize=500&apikey={twelve_key}"
    )
    r = requests.get(url, timeout=10)
    data = r.json()
    if data.get("status") != "ok" or "values" not in data:
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

    # ✅ Convert time from UTC to IST
    df.index = df.index.tz_localize("UTC").tz_convert("Asia/Kolkata")

    return df.sort_index()

# ─── TITLE & LOAD DATA ─────────────────────────────────
st.title("📈 Binary Trading Signal Bot (Forex Pairs, 5-min)")

df = fetch_twelve(symbol)
if df is None:
    st.error("❌ Could not fetch data from Twelve Data.")
    st.stop()

# ─── INDICATORS ────────────────────────────────────────
df["EMA9"] = ta.trend.ema_indicator(df["Close"], window=9)
df["EMA21"] = ta.trend.ema_indicator(df["Close"], window=21)
df["RSI"]  = ta.momentum.rsi(df["Close"], window=14)

macd = ta.trend.MACD(df["Close"])
df["MACD"] = macd.macd_diff()

bb = ta.volatility.BollingerBands(df["Close"], window=20, window_dev=2)
df["BB_upper"] = bb.bollinger_hband()
df["BB_lower"] = bb.bollinger_lband()

# ─── REVISED SIGNAL LOGIC ──────────────────────────────
def generate_signal(r):
    trend_up = r["EMA9"] > r["EMA21"]
    trend_down = r["EMA9"] < r["EMA21"]
    momentum_up = r["RSI"] > 55 and r["MACD"] > 0
    momentum_down = r["RSI"] < 45 and r["MACD"] < 0
    breakout_up = r["Close"] > r["BB_upper"]
    breakout_down = r["Close"] < r["BB_lower"]

    if trend_up and momentum_up and breakout_up:
        return "CALL"
    elif trend_down and momentum_down and breakout_down:
        return "PUT"
    else:
        return "HOLD"

df["Signal"] = df.apply(generate_signal, axis=1)

# ─── SESSION STATE FOR LIVE ACCURACY ───────────────────
if "history" not in st.session_state:
    st.session_state.history = []

# ─── ACTUAL OUTCOME CALCULATION ────────────────────────
last_time = df.index[-1]
outcome = 1 if ((df.iloc[-1]['Signal'] == 'CALL' and df.iloc[-1]['Close'] > df.iloc[-1]['Open']) or
                (df.iloc[-1]['Signal'] == 'PUT'  and df.iloc[-1]['Close'] < df.iloc[-1]['Open'])) else 0

# ─── AVOID DUPLICATE ACCURACY ENTRIES ─────────────────
if not st.session_state.history or st.session_state.history[-1]['time'] != last_time:
    total = len(st.session_state.history) + 1
    correct = sum(item['outcome'] for item in st.session_state.history) + outcome
    accuracy = (correct / total) * 100
    st.session_state.history.append({'time': last_time, 'outcome': outcome, 'accuracy': accuracy})
else:
    accuracy = st.session_state.history[-1]['accuracy']

# ─── COUNTDOWN TIMER TO NEXT 5-MIN CANDLE (IST) ────────
now = datetime.now(ZoneInfo("Asia/Kolkata"))
minute = (now.minute // 5) * 5
next_candle_time = (now.replace(minute=minute, second=0, microsecond=0) + timedelta(minutes=5))
remaining = (next_candle_time - now).total_seconds()
minutes, seconds = divmod(int(remaining), 60)

# ─── DISPLAY METRICS ──────────────────────────────────
st.metric("⏳ Time to next candle", f"{minutes}m {seconds}s")
st.metric("📍 Latest Signal", df.iloc[-1]["Signal"], help="Based on EMA9, EMA21, RSI, MACD & Bollinger Bands")
st.metric("🔎 Live Accuracy", f"{accuracy:.2f}%", help="Accuracy tracked this session")

# ─── ACCURACY HISTORY CHART ────────────────────────────
hist_df = pd.DataFrame(st.session_state.history).set_index('time')
st.line_chart(hist_df['accuracy'], height=200)

with st.expander("📊 Show recent data & signal history"):
    st.dataframe(df.tail(10))
    st.dataframe(hist_df.tail(10))

# ─── DOWNLOAD HISTORY CSV ──────────────────────────────
csv = hist_df.to_csv().encode('utf-8')
st.download_button(
    "Download session history as CSV", csv, file_name="session_history.csv", mime="text/csv"
)
