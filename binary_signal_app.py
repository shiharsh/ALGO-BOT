import streamlit as st
import pandas as pd
import ta
import requests
from datetime import datetime, timedelta
import time

# ─── YOUR FINNHUB API KEY ───────────────────────────────
finnhub_key = "d09hj5hr01qnv9cj0a10d09hj5hr01qnv9cj0a1g"

# ─── SYMBOL MAPPING ─────────────────────────────────────
symbol = st.selectbox("Choose a symbol:", ["EUR/USD", "GBP/USD", "BTC/USD", "ETH/USD", "AAPL", "TSLA"])
finnhub_map = {
    "EUR/USD": "OANDA:EUR_USD",
    "GBP/USD": "OANDA:GBP_USD",
    "BTC/USD": "BINANCE:BTCUSDT",
    "ETH/USD": "BINANCE:ETHUSDT",
    "AAPL": "AAPL",
    "TSLA": "TSLA"
}
finnhub_symbol = finnhub_map[symbol]

# ─── FETCH DATA FROM FINNHUB ────────────────────────────
@st.cache_data(ttl=300)
def fetch_finnhub(symbol):
    now = int(time.time())
    past = now - 60 * 60 * 5  # last 5 hours (5-min candles)

    url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=5&from={past}&to={now}&token={finnhub_key}"
    r = requests.get(url)
    data = r.json()

    if data.get("s") != "ok":
        return None

    df = pd.DataFrame({
        "Time": [datetime.fromtimestamp(t) for t in data["t"]],
        "Open": data["o"],
        "High": data["h"],
        "Low": data["l"],
        "Close": data["c"],
        "Volume": data["v"]
    })
    df.set_index("Time", inplace=True)
    return df

# ─── TITLE AND FETCH DATA ───────────────────────────────
st.title("📈 Binary Trading Signal Bot (5-Min) with Live Data")

df = fetch_finnhub(finnhub_symbol)
if df is None:
    st.error("❌ Could not fetch data from Finnhub.")
    st.stop()

# ─── INDICATORS ─────────────────────────────────────────
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

# ─── DISPLAY SIGNAL ─────────────────────────────────────
latest = df.iloc[-1]
st.metric("📍 Signal", latest["Signal"], help="Based on EMA9, RSI, and MACD")

# ─── SHOW RECENT DATA ───────────────────────────────────
with st.expander("📊 Show recent data"):
    st.dataframe(df.tail(10))
