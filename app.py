import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from curl_cffi import requests as crequests # The "Nuclear" Browser Spoofer
import datetime

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Macro Sector Map", layout="wide", page_icon="🌎")

# --- 2. CONSTANTS ---
SECTORS = {
    'XLK': 'Technology', 'XLF': 'Financials', 'XLE': 'Energy',
    'XLV': 'Health Care', 'XLY': 'Consumer Disc', 'XLP': 'Consumer Staples',
    'XLI': 'Industrials', 'XLB': 'Materials', 'XLRE': 'Real Estate',
    'XLC': 'Comm Services', 'XLU': 'Utilities', 'SPY': 'S&P 500 (Market)'
}

# --- 3. THE "NUCLEAR" FETCH ENGINE (Direct API) ---
@st.cache_data(ttl=3600)
def get_raw_data(ticker):
    """
    Bypasses yfinance library entirely. 
    Uses curl_cffi to impersonate Chrome 110 and fetch raw JSON from Yahoo.
    """
    try:
        # Yahoo's Raw Chart API Endpoint
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?range=2y&interval=1d"
        
        # The Heavy Lifter: Impersonate a real browser TLS fingerprint
        r = crequests.get(url, impersonate="chrome110", timeout=10)
        
        if r.status_code != 200:
            return None
            
        # Parse JSON
        data = r.json()
        result = data['chart']['result'][0]
        
        # Extract Timestamps and Closes
        timestamps = result['timestamp']
        closes = result['indicators']['quote'][0]['close']
        
        # Create DataFrame
        df = pd.DataFrame({'Close': closes, 'Timestamp': timestamps})
        df['Date'] = pd.to_datetime(df['Timestamp'], unit='s')
        df.set_index('Date', inplace=True)
        df = df.dropna()
        
        return df['Close']
    except Exception as e:
        return None

def process_market_data():
    results = []
    progress_text = "Establishing Secure Connection..."
    my_bar = st.progress(0, text=progress_text)
    
    total = len(SECTORS)
    for i, (ticker, name) in enumerate(SECTORS.items()):
        closes = get_raw_data(ticker)
        
        if closes is not None and len(closes) > 200:
            # --- MATH ENGINE ---
            curr = closes.iloc[-1]
            sma50 = closes.rolling(50).mean().iloc[-1]
            sma200 = closes.rolling(200).mean().iloc[-1]
            
            # Z-Score (20 Day)
            mu = closes.rolling(20).mean().iloc[-1]
            sigma = closes.rolling(20).std().iloc[-1]
            z = (curr - mu) / sigma if sigma > 1e-6 else 0
            
            # Regime Logic
            regime = "BEAR"
            if curr > sma200: regime = "BULL"
            elif curr > sma50: regime = "RECOVERY"
            
            results.append({
                "Ticker": ticker,
                "Name": name,
                "Price": float(curr),
                "Z-Score": float(z),
                "Regime": regime,
                "Pct_Above_200": float((curr / sma200) - 1)
            })
        
        # Update Progress
        my_bar.progress((i + 1) / total, text=f"Scanning {ticker}...")
        
    my_bar.empty()
    return pd.DataFrame(results)

# --- 4. MAIN UI ---
def main():
    st.title("🌎 Sector Momentum Map")
    st.markdown(f"**Status:** Market Scan @ {datetime.datetime.now().strftime('%H:%M ET')}")
    st.info("💡 **Strategy:** Buy stocks only if their Sector is **BULL** or **Oversold (Z < -2.0)**.")

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()

    # Run the "Nuclear" Scan
    df = process_market_data()

    if not df.empty:
        df = df.sort_values(by="Z-Score", ascending=False)

        # A. Heatmap Chart
        fig = px.bar(
            df, x="Ticker", y="Z-Score", color="Z-Score",
            color_continuous_scale="RdYlGn_r",
            title="Sector Z-Scores (Mean Reversion)",
            hover_data=["Name", "Regime"],
            text_auto='.2f'
        )
        fig.add_hline(y=2.0, line_dash="dash", line_color="red", annotation_text="Overheated")
        fig.add_hline(y=-2.0, line_dash="dash", line_color="green", annotation_text="Buy Zone")
        st.plotly_chart(fig, use_container_width=True)

        # B. Scorecard Table
        def color_regime(val):
            colors = {'BULL': '#d4edda', 'RECOVERY': '#fff3cd', 'BEAR': '#f8d7da'}
            text_colors = {'BULL': '#155724', 'RECOVERY': '#856404', 'BEAR': '#721c24'}
            return f'background-color: {colors.get(val, "")}; color: {text_colors.get(val, "")}; font-weight: bold'

        def color_z(val):
            color = 'red' if val > 2.0 else ('green' if val < -2.0 else 'black')
            return f'color: {color}; font-weight: bold'

        st.dataframe(
            df.style.map(color_regime, subset=['Regime'])
                    .map(color_z, subset=['Z-Score'])
                    .format({"Price": "${:.2f}", "Z-Score": "{:.2f}σ", "Pct_Above_200": "{:.1%}"}),
            use_container_width=True,
            height=500
        )
    else:
        st.error("Critical Failure: Even the heavy armor was blocked. Try deploying locally.")

if __name__ == "__main__":
    main()
