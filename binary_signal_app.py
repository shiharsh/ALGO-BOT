import streamlit as st
import pandas as pd
import yfinance as yf
import ta

# ─── SYMBOL MAPPING FOR FOREX PAIRS ─────────────────────
symbol_map = {
    "EUR/USD": "EURUSD=X",
    "USD/JPY": "JPY=X",
    "GBP/USD": "GBPUSD=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "CAD=X"
}

symbol = st.selectbox("Choose a symbol:", list(symbol_map.keys()))

# ─── FETCH DATA FROM YAHOO FINANCE ──────────────────────
@st.cache_data(ttl=300)
def fetch_yahoo(sym_key):
    yf_sym = symbol_map[sym_key]
    # try 5-minute candles over the past 1 day
    df = yf.download(
        tickers=yf_sym,
        interval="5m",
        period="1d",
        threads=False
    )
    # fallback to 1-hour if 5m is empty
    if df.empty:
        df = yf.download(
            tickers=yf_sym,
            interval="1h",
            period="5d",
            threads=False
        )
    if df.empty:
        return None
    return df[["Open", "High", "Low", "Close", "Volume"]]

# ─── TITLE AND DATA LOAD ───────────────────────────────
st.title("📈 Binary Trading Signal Bot (Forex Pairs)")

df = fetch_yahoo(symbol)
if df is None:
    st.error("❌ Could not fetch any data from Yahoo Finance.")
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

# ─── DISPLAY ───────────────────────────────────────────
latest = df.iloc[-1]
st.metric("📍 Signal", latest["Signal"], help="Based on EMA9, RSI & MACD")

with st.expander("📊 Show recent data"):
    st.dataframe(df.tail(10))
