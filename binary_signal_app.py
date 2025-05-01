import streamlit as st
import pandas as pd
import yfinance as yf
import ta

# ─── SYMBOL SELECTION ───────────────────────────────────
symbol = st.selectbox("Choose a symbol:", ["EUR/USD", "GBP/USD", "BTC/USD", "ETH/USD", "AAPL", "TSLA"])

# ─── FETCH FROM YAHOO FINANCE ───────────────────────────
@st.cache_data(ttl=300)
def fetch_yahoo(symbol):
    symbol_map_yf = {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "BTC/USD": "BTC-USD",
        "ETH/USD": "ETH-USD",
        "AAPL": "AAPL",
        "TSLA": "TSLA"
    }
    yf_symbol = symbol_map_yf[symbol]
    df = yf.download(tickers=yf_symbol, interval='5m', period='1d', threads=False)
    st.write("Raw data:")
    st.write(df.tail())
    if df.empty:
        return None
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    return df

# ─── TITLE AND LOAD DATA ────────────────────────────────
st.title("📈 Binary Trading Signal Bot (5-Min) with Live Data")

df = fetch_yahoo(symbol)
if df is None:
    st.error("❌ Could not fetch data from Yahoo Finance.")
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
