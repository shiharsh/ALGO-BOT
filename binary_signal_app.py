import streamlit as st
import pandas as pd
import ta
import requests
import time

st.set_page_config(page_title="Binary Signal Bot", layout="centered")
st.title("📈 Binary Trading Signal Bot (5-Min) with Live Data")

# === SETTINGS ===
symbol = st.selectbox("Choose a symbol:", ["EUR/USD", "GBP/USD", "BTC/USD", "ETH/USD", "AAPL", "TSLA"])
api_key = "P4ISS18L9D90IZH4"  # Replace with your actual Alpha Vantage API key

symbol_map = {
    "EUR/USD": "EURUSD",
    "GBP/USD": "GBPUSD",
    "BTC/USD": "BTCUSD",
    "ETH/USD": "ETHUSD",
    "AAPL": "AAPL",
    "TSLA": "TSLA"
}

selected_symbol = symbol_map[symbol]

# === Function to fetch data from Alpha Vantage ===
def get_alpha_vantage_data(symbol):
    try:
        url = f"https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol={symbol[:3]}&to_symbol={symbol[3:]}&interval=5min&apikey={api_key}&outputsize=compact"
        if symbol in ["AAPL", "TSLA"]:
            url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval=5min&apikey={api_key}&outputsize=compact"
            data_key = "Time Series (5min)"
        else:
            data_key = "Time Series FX (5min)"

        r = requests.get(url)
        data = r.json()

        if data_key not in data:
            return pd.DataFrame()

        df = pd.DataFrame.from_dict(data[data_key], orient='index')
        df = df.rename(columns={
            '1. open': 'Open',
            '2. high': 'High',
            '3. low': 'Low',
            '4. close': 'Close'
        })
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df = df.astype(float)
        return df

    except Exception as e:
        st.error(f"API error: {e}")
        return pd.DataFrame()

# === Fetch Data ===
st.subheader(f"Live data for {symbol}")
df = get_alpha_vantage_data(selected_symbol)

if df.empty:
    st.error("No data found. Try a different symbol or check your API usage limit.")
    st.stop()

# === Calculate Indicators ===
df['EMA9'] = ta.trend.ema_indicator(df['Close'], window=9)
df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
macd = ta.trend.macd(df['Close'])
df['MACD'] = macd.macd_diff()
bbands = ta.volatility.BollingerBands(df['Close'])
df['BB_High'] = bbands.bollinger_hband()
df['BB_Low'] = bbands.bollinger_lband()

# === Generate Signal ===
def generate_signal(row):
    if row['Close'] > row['EMA9'] and row['RSI'] > 50 and row['MACD'] > 0 and row['Close'] < row['BB_High']:
        return 'CALL'
    elif row['Close'] < row['EMA9'] and row['RSI'] < 50 and row['MACD'] < 0 and row['Close'] > row['BB_Low']:
        return 'PUT'
    else:
        return 'HOLD'

df['Signal'] = df.apply(generate_signal, axis=1)

# === Show Latest Signal ===
latest = df.iloc[-1]
st.metric("Latest Signal", latest['Signal'])

# === Backtesting Accuracy ===
st.subheader("Backtest Accuracy (Last 50 candles)")
df['Next Close'] = df['Close'].shift(-1)
df['Next Direction'] = df['Next Close'] > df['Close']
df['Predicted Direction'] = df['Signal'].apply(lambda x: True if x == 'CALL' else (False if x == 'PUT' else None))
df['Correct'] = df['Predicted Direction'] == df['Next Direction']

recent = df.dropna().tail(50)
accuracy = (recent['Correct'].sum() / len(recent)) * 100
st.metric("Prediction Accuracy", f"{accuracy:.2f}%")

# === Optional: Show Data ===
with st.expander("📊 Show raw data"):
    st.dataframe(df.tail(20))
