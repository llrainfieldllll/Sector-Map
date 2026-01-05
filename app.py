import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import datetime
import requests
from fake_useragent import UserAgent

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Macro Sector Map", layout="wide", page_icon="🌎")

# --- 2. CONSTANTS ---
SECTORS = {
    'XLK': 'Technology', 'XLF': 'Financials', 'XLE': 'Energy',
    'XLV': 'Health Care', 'XLY': 'Consumer Disc', 'XLP': 'Consumer Staples',
    'XLI': 'Industrials', 'XLB': 'Materials', 'XLRE': 'Real Estate',
    'XLC': 'Comm Services', 'XLU': 'Utilities', 'SPY': 'S&P 500 (Market)'
}

# --- 3. SESSION BUILDER (Anti-Blocking) ---
def get_session():
    """Creates a session that impersonates a real Chrome browser."""
    session = requests.Session()
    ua = UserAgent()
    session.headers.update({
        'User-Agent': ua.chrome,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    })
    return session

# --- 4. MATH ENGINE (Cached & Fortified) ---
@st.cache_data(ttl=3600)
def fetch_market_data():
    results = []
    session = get_session() # Initialize the "Stealth" session
    
    for ticker, name in SECTORS.items():
        try:
            # Pass the custom session to yf to bypass Yahoo blocks
            df = yf.download(ticker, period="1y", interval="1d", progress=False, session=session)
            
            if df.empty or len(df) < 200:
                continue

            # Handle MultiIndex logic
            if isinstance(df.columns, pd.MultiIndex):
                df = df.xs(ticker, axis=1, level=1) if ticker in df.columns.levels[1] else df
                if 'Close' not in df.columns and len(df.columns) == 1:
                     df.columns = ['Close']
            
            closes = df['Close'] if 'Close' in df.columns else df.iloc[:, 0]
            
            # --- CALCULATIONS ---
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
        except Exception as e:
            continue
            
    return pd.DataFrame(results)

# --- 5. MAIN UI ---
def main():
    st.title("🌎 Sector Momentum Map")
    st.markdown(f"**Status:** Market Scan @ {datetime.datetime.now().strftime('%H:%M ET')}")
    st.info("💡 **Strategy:** Buy stocks only if their Sector is **BULL** or **Oversold (Z < -2.0)**.")

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()

    with st.spinner("Scanning Sectors (Stealth Mode)..."):
        df = fetch_market_data()

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
        st.error("Data Fetch Failed. The server may be blocking the connection.")

if __name__ == "__main__":
    main()
