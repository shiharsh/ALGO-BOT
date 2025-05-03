import streamlit as st
import pandas as pd
import requests
import ta
import time
import joblib  # ✅ Load ML model
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
from zoneinfo import ZoneInfo  # ✅ For IST time zone

# ─── MODEL TRAINING SECTION ───────────────────────────
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib

@st.cache_resource
def train_rf_model_from_csv():
    path = "eurusd_5min_history_under25mb.csv"
    if not os.path.exists(path):
        st.warning("Upload the CSV file named: eurusd_5min_history_under25mb.csv")
        return None

    df = pd.read_csv(path, parse_dates=["Datetime"])
    df = df.sort_values("Datetime")
    df["EMA9"] = ta.trend.ema_indicator(df["Close"], window=9)
    df["RSI"] = ta.momentum.rsi(df["Close"], window=14)
    macd = ta.trend.MACD(df["Close"])
    df["MACD"] = macd.macd_diff()

    df.dropna(inplace=True)

    # Create label: 1 = CALL, 0 = PUT
    df["Target"] = (df["Close"].shift(-1) > df["Close"]).astype(int)

    features = df[["EMA9", "RSI", "MACD"]]
    target = df["Target"]

    X_train, X_test, y_train, y_test = train_test_split(features, target, test_size=0.2, shuffle=False)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Evaluate model
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    st.success(f"✅ Model trained with accuracy: {acc:.2f}")

    # Save model
    joblib.dump(model, "rf_model.pkl")
    return model

# Train and cache the model
model = train_rf_model_from_csv()


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
df["RSI"]  = ta.momentum.rsi(df["Close"], window=14)
macd = ta.trend.MACD(df["Close"])
df["MACD"] = macd.macd_diff()

# ✅ Load trained ML model
model = joblib.load("rf_model.pkl")

def generate_signal(r):
    if r["Close"] > r["EMA9"] and r["RSI"] > 50 and r["MACD"] > 0:
        return "CALL"
    elif r["Close"] < r["EMA9"] and r["RSI"] < 50 and r["MACD"] < 0:
        return "PUT"
    else:
        return "HOLD"

def generate_ml_signal(row):
    if pd.isna(row["EMA9"]) or pd.isna(row["RSI"]) or pd.isna(row["MACD"]):
        return "HOLD"
    features = [row["EMA9"], row["RSI"], row["MACD"]]
    pred = model.predict([features])[0]
    return "CALL" if pred == 1 else "PUT"

df["Signal"] = df.apply(generate_signal, axis=1)
df["ML_Signal"] = df.apply(generate_ml_signal, axis=1)

# ─── SESSION STATE FOR LIVE ACCURACY ───────────────────
if "history" not in st.session_state:
    st.session_state.history = []

# ─── ACTUAL OUTCOME CALCULATION ────────────────────────
last_time = df.index[-1]
outcome = 1 if ((df.iloc[-1]['ML_Signal'] == 'CALL' and df.iloc[-1]['Close'] > df.iloc[-1]['Open']) or
                (df.iloc[-1]['ML_Signal'] == 'PUT'  and df.iloc[-1]['Close'] < df.iloc[-1]['Open'])) else 0

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
st.metric("📍 Traditional Signal", df.iloc[-1]["Signal"])
st.metric("🤖 ML-Based Signal", df.iloc[-1]["ML_Signal"], help="Predicted using Random Forest model")
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
