import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Stochastic", layout="wide")

PAIRS = [
    "USDJPY",
    "GBPUSD",
    "EURUSD",
    "AUDUSD",
    "GBPJPY",
    "EURJPY",
    "AUDJPY",
    "EURGBP",
    "GBPAUD",
    "EURAUD",
]
TIMEFRAMES = {"5分足": ("5m", "5d", 1), "15分足": ("15m", "5d", 1),
              "30分足": ("30m", "5d", 1), "1時間足": ("60m", "1mo", 1),
              "4時間足": ("60m", "1mo", 4), "日足": ("1d", "6mo", 1)}

@st.cache_data(ttl=120, show_spinner=False)
def load(ticker, interval, period):
    df = yf.download(ticker, interval=interval, period=period, progress=False, auto_adjust=False, threads=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def stochastic(df):
    low14 = df["Low"].rolling(14, min_periods=14).min()
    high14 = df["High"].rolling(14, min_periods=14).max()
    span = (high14 - low14).replace(0, float("nan"))
    fast_k = 100 * (df["Close"] - low14) / span
    slow_k = fast_k.rolling(5, min_periods=5).mean()
    slow_d = slow_k.rolling(3, min_periods=3).mean()
    return slow_k, slow_d

def calculate(df, factor):
    if factor == 4:
        # Resample hourly candles into four-hour OHLC candles in UTC.
        df = df.resample("4h", origin="start_day", label="left", closed="left").agg(
            {"Open":"first", "High":"max", "Low":"min", "Close":"last"}).dropna()
    # Yahoo's last bar may be forming; discard it to avoid changing signals.
    if len(df) < 22:
        return None
    df = df.iloc[:-1]
    k, d = stochastic(df)
    if k.empty or pd.isna(k.iloc[-1]):
        return None
    return float(k.iloc[-1])

if st.button("更新", type="primary"):
    st.cache_data.clear()

results = {}
errors = []
with st.spinner("為替データを取得しています…"):
    for label, (interval, period, factor) in TIMEFRAMES.items():
        signals = []
        for pair in PAIRS:
            try:
                data = load(f"{pair}=X", interval, period)
                if data.empty:
                    errors.append(f"{label}: {pair} のデータがありません")
                    continue
                value = calculate(data, factor)
                if value is None:
                    errors.append(f"{label}: {pair} の計算に十分なデータがありません")
                elif value <= 7:
                    signals.append((pair[:3] + "/" + pair[3:], "買い"))
                elif value >= 93:
                    signals.append((pair[:3] + "/" + pair[3:], "売り"))
            except Exception as exc:
                errors.append(f"{label}: {pair} ({type(exc).__name__})")
        results[label] = signals

for row in (list(TIMEFRAMES)[:3], list(TIMEFRAMES)[3:]):
    columns = st.columns(3)
    for column, label in zip(columns, row):
        with column:
            with st.container(border=True):
                st.subheader(label)
                if not results[label]:
                    st.caption("シグナルなし / 取得失敗は下記参照")
                for pair, side in results[label]:
                    color = "#12805c" if side == "買い" else "#d33b3b"
                    st.markdown(f"**{pair}**　<span style='color:{color};font-weight:700'>{side}</span>", unsafe_allow_html=True)

if errors:
    with st.expander(f"データ取得・計算上の注意（{len(errors)}件）"):
        st.text("\n".join(errors))
st.caption("Yahoo Financeの遅延・欠損があり得ます。4時間足は1時間足から合成。取引推奨ではありません。")
