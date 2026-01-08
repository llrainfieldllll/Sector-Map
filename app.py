import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from curl_cffi import requests as crequests
from concurrent.futures import ThreadPoolExecutor
import datetime
import pytz

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Red-Team Sector Map", layout="wide", page_icon="🛡️")

SECTORS = {
    'XLK': 'Technology', 'XLF': 'Financials', 'XLE': 'Energy',
    'XLV': 'Health Care', 'XLY': 'Consumer Disc', 'XLP': 'Consumer Staples',
    'XLI': 'Industrials', 'XLB': 'Materials', 'XLRE': 'Real Estate',
    'XLC': 'Comm Services', 'XLU': 'Utilities', 'SMH': 'Semiconductors',
    'SPY': 'S&P 500'
}

# --- 2. STEALTH HYBRID FETCH ENGINE ---
def fetch_data_robust(ticker):
    """
    1. Tries yfinance (cleaner data).
    2. Fails over to curl_cffi (impersonates Chrome 110) if Yahoo blocks IP.
    """
    # Attempt 1: Standard API
    try:
        df = yf.download(ticker, period="2y", interval="1d", progress=False)
        if not df.empty and len(df) > 100:
            if isinstance(df.columns, pd.MultiIndex):
                return df.xs('Close', axis=1, level=1)
            return df['Close']
    except Exception:
        pass 
    
    # Attempt 2: "Nuclear" Bypass (Stealth)
    try:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?range=2y&interval=1d"
        r = crequests.get(url, impersonate="chrome110", timeout=5)
        if r.status_code == 200:
            data = r.json()['chart']['result'][0]
            df = pd.DataFrame({
                'Close': data['indicators']['quote'][0]['close'],
                'Timestamp': data['timestamp']
            })
            df['Date'] = pd.to_datetime(df['Timestamp'], unit='s')
            return df.set_index('Date')['Close'].dropna()
    except Exception:
        return None
    return None

# --- 3. MATH & LOGIC BRAIN ---
def calculate_metrics(ticker, name):
    closes = fetch_data_robust(ticker)
    if closes is None or len(closes) < 200: return None
        
    curr = float(closes.iloc[-1])
    
    # A. Trend Logic (EMA for speed + Alignment)
    ema_50 = closes.ewm(span=50, adjust=False).mean().iloc[-1]
    ema_200 = closes.ewm(span=200, adjust=False).mean().iloc[-1]
    
    # B. Volatility Logic (Z-Score + Percentile)
    roll = closes.rolling(20)
    mu, sigma = roll.mean().iloc[-1], roll.std().iloc[-1]
    if sigma == 0: sigma = 0.001
    z_score = (curr - mu) / sigma
    
    # Percentile Rank (Historical Context)
    past_z = (closes - closes.rolling(20).mean()) / closes.rolling(20).std()
    recent_z = past_z.tail(126).dropna() # Last 6 months
    percentile = (recent_z < z_score).mean() * 100 if not recent_z.empty else 50.0

    # C. Regime Classification
    regime = "NEUTRAL"
    if curr > ema_200 and ema_50 > ema_200: regime = "BULL"
    elif curr < ema_200 and ema_50 < ema_200: regime = "BEAR"
    elif curr > ema_200: regime = "RECOVERY"

    return {
        "Ticker": ticker, "Name": name, "Price": curr,
        "Z_Score": z_score, "Pct_Rank": percentile,
        "Regime": regime, "Stop_Loss": curr - (3 * sigma)
    }

def get_signal(row):
    z, p, r = row['Z_Score'], row['Pct_Rank'], row['Regime']
    
    if r == "BULL":
        if z < -2.0 and p < 5: return "⭐⭐⭐ (Prime)" # Confluence
        if z < -1.0: return "⭐⭐ (Watch)"
        if z > 2.5: return "✋ (Extended)"
    if r == "BEAR":
        if z > 1.5: return "📉 (Short?)"
        if z < -2.0: return "⛔ (Knife)"
    return "❄️ (Wait)"

# --- 4. PARALLEL EXECUTION ---
def run_scan():
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(calculate_metrics, t, n): t for t, n in SECTORS.items()}
        for future in futures:
            if res := future.result(): results.append(res)
    return pd.DataFrame(results)

# --- 5. MAIN UI ---
def main():
    st.title("🛡️ Market Regime & Momentum Map")
    
    # Time & Status
    tz = pytz.timezone('America/Toronto')
    st.markdown(f"**Scan Time:** {datetime.datetime.now(tz).strftime('%H:%M:%S %Z')}")

    if st.button("🚀 Run Analysis"):
        st.cache_data.clear()

    with st.spinner("Triangulating Market Data..."):
        df = run_scan()

    if not df.empty:
        df['Signal'] = df.apply(get_signal, axis=1)
        df = df.sort_values(by="Z_Score", ascending=False)

        # Visuals
        fig = px.bar(
            df, x="Ticker", y="Z_Score", color="Z_Score",
            color_continuous_scale="RdYlGn_r",
            title="Volatility Deviation (20-Day Window)",
            hover_data=["Name", "Regime", "Pct_Rank"], text_auto='.2f'
        )
        fig.add_hline(y=2.0, line_dash="dot", line_color="red")
        fig.add_hline(y=-2.0, line_dash="dot", line_color="green")
        st.plotly_chart(fig, use_container_width=True)

        # Table Styling
        def color_regime(val):
            colors = {'BULL': '#d4edda', 'BEAR': '#f8d7da', 'RECOVERY': '#fff3cd'}
            return f'background-color: {colors.get(val, "")}; color: black'

        st.dataframe(
            df[['Ticker', 'Signal', 'Z_Score', 'Pct_Rank', 'Regime', 'Price', 'Stop_Loss', 'Name']]
            .style.map(color_regime, subset=['Regime'])
            .format({"Z_Score": "{:.2f}σ", "Price": "${:.2f}", "Stop_Loss": "${:.2f}", "Pct_Rank": "{:.0f}%"}),
            use_container_width=True, height=600
        )
    else:
        st.error("Connection Blocked. Deploy locally or use VPN.")

if __name__ == "__main__":
    main()
