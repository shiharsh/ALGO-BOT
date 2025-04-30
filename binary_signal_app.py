import streamlit as st
import pandas as pd
import yfinance as yf
import ta
import datetime

st.set_page_config(page_title="Binary Signal Bot", layout="wide")

st.title("📈 Binary Trading Signal Bot (5-Min) with Live Data")

symbol = st.selectbox("Choose a symbol:", ["EURUSD=X", "GBPUSD=X", "USDJPY=X"])

# Time setup
time_now = datetime.datetime.utcnow()
time_start = time_now - datetime.timedelta(days=1)
data = yf.download(tickers=symbol, interval="5m", start=time_start, end=time_now)

if data.empty:
    st.warning("No data found. Try again later or change symbol.")
    st.stop()

# Indicator calculation
data.dropna(inplace=True)
data['EMA9'] = ta.trend.ema_indicator(data['Close'], window=9)
data['RSI'] = ta.momentum.rsi(data['Close'], window=14)
macd = ta.trend.macd(data['Close'])
data['MACD'] = macd.macd()
data['MACD_signal'] = macd.macd_signal()
bb = ta.volatility.BollingerBands(data['Close'])
data['BB_upper'] = bb.bollinger_hband()
data['BB_lower'] = bb.bollinger_lband()

# Signal logic
def generate_signal(row):
    if (
        row['Close'] > row['EMA9']
        and row['RSI'] < 70
        and row['MACD'] > row['MACD_signal']
        and row['Close'] > row['BB_lower']
    ):
        return "CALL"
    elif (
        row['Close'] < row['EMA9']
        and row['RSI'] > 30
        and row['MACD'] < row['MACD_signal']
        and row['Close'] < row['BB_upper']
    ):
        return "PUT"
    else:
        return "NO SIGNAL"

data['Signal'] = data.apply(generate_signal, axis=1)

# Accuracy tracking
def get_actual_direction(df):
    return ["CALL" if close2 > close1 else "PUT" for close1, close2 in zip(df['Close'][:-1], df['Close'][1:])]

data['Actual'] = get_actual_direction(data)
data['Match'] = data['Signal'].shift(1) == data['Actual']
accuracy = round(data['Match'].mean() * 100, 2)

# Display latest signal
latest = data.iloc[-1]
st.subheader("Live Signal")
st.metric(label="Last Signal (5-min)", value=latest['Signal'])
st.metric(label="Signal Accuracy", value=f"{accuracy}%")

# Chart view
st.subheader("Price & Indicators Chart")
st.line_chart(data[['Close', 'EMA9', 'BB_upper', 'BB_lower']].dropna())

# Backtest section
st.subheader("Backtesting Module")
with st.expander("📤 Upload Historical CSV for Backtest"):
    uploaded_file = st.file_uploader("Upload CSV", type="csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        df['EMA9'] = ta.trend.ema_indicator(df['Close'], window=9)
        df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
        macd = ta.trend.macd(df['Close'])
        df['MACD'] = macd.macd()
        df['MACD_signal'] = macd.macd_signal()
        bb = ta.volatility.BollingerBands(df['Close'])
        df['BB_upper'] = bb.bollinger_hband()
        df['BB_lower'] = bb.bollinger_lband()
        df['Signal'] = df.apply(generate_signal, axis=1)
        df['Actual'] = get_actual_direction(df)
        df['Match'] = df['Signal'].shift(1) == df['Actual']
        backtest_acc = round(df['Match'].mean() * 100, 2)
        st.success(f"Backtest Accuracy: {backtest_acc}%")
        st.line_chart(df['Close'])
