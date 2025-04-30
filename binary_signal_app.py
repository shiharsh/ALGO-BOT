import streamlit as st
import pandas as pd
import ta
import requests

st.set_page_config(page_title="Binary Signal Bot", layout="centered")
st.title("📈 Binary Trading Signal Bot (5-Min) with Live Data")

# ─── YOUR API KEY ───────────────────────────────────────────────
api_key = "P4ISS18L9D90IZH4"  # ← your Alpha Vantage key

# ─── SYMBOL SELECTION ───────────────────────────────────────────
symbol = st.selectbox("Choose a symbol:", ["EUR/USD", "GBP/USD", "BTC/USD", "ETH/USD", "AAPL", "TSLA"])
symbol_map = {
    "EUR/USD": "EURUSD",
    "GBP/USD": "GBPUSD",
    "BTC/USD": "BTCUSD",
    "ETH/USD": "ETHUSD",
    "AAPL":   "AAPL",
    "TSLA":   "TSLA"
}
s = symbol_map[symbol]

# ─── FETCH 5-MIN DATA ────────────────────────────────────────────
def fetch_5min_data(sym):
    if len(sym) == 6 and sym.isalpha():  # FX pair
        url = (
            "https://www.alphavantage.co/query"
            f"?function=FX_INTRADAY&from_symbol={sym[:3]}&to_symbol={sym[3:]}"
            f"&interval=5min&outputsize=compact&apikey={api_key}"
        )
        key = "Time Series FX (5min)"
    else:  # stock
        url = (
            "https://www.alphavantage.co/query"
            f"?function=TIME_SERIES_INTRADAY&symbol={sym}"
            f"&interval=5min&outputsize=compact&apikey={api_key}"
        )
        key = "Time Series (5min)"

    r = requests.get(url)
    j = r.json()

    # Debug in sidebar
    st.sidebar.subheader("🔍 Raw API response")
    st.sidebar.text(r.text[:500])

    if key not in j:
        st.error(f"⚠️ Missing ‘{key}’ in response – check rate limits or key validity.")
        return pd.DataFrame()

    df = pd.DataFrame.from_dict(j[key], orient="index")
    df = df.rename(columns={
        "1. open":  "Open",
        "2. high":  "High",
        "3. low":   "Low",
        "4. close": "Close"
    })
    df.index = pd.to_datetime(df.index)
    return df.sort_index().astype(float)

df = fetch_5min_data(s)
if df.empty:
    st.stop()

# ─── INDICATORS ─────────────────────────────────────────────────
df["EMA9"] = ta.trend.ema_indicator(df["Close"], window=9)
df["RSI"]  = ta.momentum.rsi(df["Close"], window=14)
macd = ta.trend.MACD(df["Close"])
df["MACD"]    = macd.macd_diff()
bb  = ta.volatility.BollingerBands(df["Close"])
df["BB_High"] = bb.bollinger_hband()
df["BB_Low"]  = bb.bollinger_lband()

# ─── SIGNAL LOGIC ────────────────────────────────────────────────
def generate_signal(r):
    if  r["Close"] > r["EMA9"] and r["RSI"] > 50 and r["MACD"] > 0 and r["Close"] < r["BB_High"]:
        return "CALL"
    if  r["Close"] < r["EMA9"] and r["RSI"] < 50 and r["MACD"] < 0 and r["Close"] > r["BB_Low"]:
        return "PUT"
    return "HOLD"

df["Signal"] = df.apply(generate_signal, axis=1)
latest = df.iloc[-1]

st.subheader("🔔 Latest Signal")
st.metric("Call / Put / Hold", latest["Signal"])

# ─── BACKTEST ACCURACY ───────────────────────────────────────────
df["Next_Close"] = df["Close"].shift(-1)
df["Up_Next"]    = df["Next_Close"] > df["Close"]
df["Pred_Up"]    = df["Signal"] == "CALL"
df["Correct"]    = df["Pred_Up"] == df["Up_Next"]

recent = df.dropna().tail(50)
acc    = recent["Correct"].mean() * 100

st.subheader("📊 Backtest Accuracy (last 50 candles)")
st.metric("Accuracy", f"{acc:.2f}%")

# ─── RAW DATA INSPECTION ────────────────────────────────────────
with st.expander("Show recent data"):
    st.dataframe(df.tail(20))
