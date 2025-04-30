import streamlit as st
import pandas as pd
import ta
import requests

# ─── API KEYS ───────────────────────────────────────────
alpha_key = "P4ISS18L9D90IZH4"
twelve_key = "4d5b1e81f9314e28a7ee285497d3b273"

# ─── SYMBOLS ────────────────────────────────────────────
symbol = st.selectbox("Choose a symbol:", ["EUR/USD", "GBP/USD", "BTC/USD", "ETH/USD", "AAPL", "TSLA"])
symbol_map = {
    "EUR/USD": ("EUR", "USD"),
    "GBP/USD": ("GBP", "USD"),
    "BTC/USD": ("BTC", "USD"),
    "ETH/USD": ("ETH", "USD"),
    "AAPL": "AAPL",
    "TSLA": "TSLA"
}
is_fx = isinstance(symbol_map[symbol], tuple)

# ─── FETCH FROM ALPHA VANTAGE ───────────────────────────
@st.cache_data(ttl=300)
def fetch_alpha(symbol):
    if is_fx:
        from_sym, to_sym = symbol_map[symbol]
        url = f"https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol={from_sym}&to_symbol={to_sym}&interval=5min&apikey={alpha_key}"
        key = "Time Series FX (5min)"
    else:
        sym = symbol_map[symbol]
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={sym}&interval=5min&apikey={alpha_key}"
        key = "Time Series (5min)"
    
    r = requests.get(url)
    data = r.json()
    if key not in data:
        return None
    df = pd.DataFrame(data[key]).T
    df.columns = ["Open", "High", "Low", "Close"]
    df = df.astype(float)
    df.index = pd.to_datetime(df.index)
    return df.sort_index()

# ─── FETCH FROM TWELVE DATA ─────────────────────────────
@st.cache_data(ttl=300)
def fetch_twelve(sym, twelve_key):
    url = f"https://api.twelvedata.com/time_series?symbol={sym}&interval=5min&apikey={twelve_key}&outputsize=100"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception("Failed to fetch from Twelve Data")

    data = response.json()
    if 'values' not in data:
        raise Exception("Missing 'values' in Twelve Data response")

    df = pd.DataFrame(data['values'])
    df = df.rename(columns={
        'datetime': 'datetime',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'volume': 'volume'
    })
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.astype({
        'open': 'float',
        'high': 'float',
        'low': 'float',
        'close': 'float',
        'volume': 'float'
    })
    df = df.sort_values('datetime')
    df.set_index("datetime", inplace=True)
    return df

# ─── TITLE AND LOAD DATA ────────────────────────────────
st.title("📈 Binary Trading Signal Bot (5-Min) with Live Data")

df = fetch_alpha(symbol)
if df is None:
    st.warning("⚠️ Alpha Vantage failed – switching to Twelve Data...")
    df = fetch_twelve(symbol, twelve_key)

if df is None:
    st.error("❌ Could not fetch data from either Alpha Vantage or Twelve Data.")
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
