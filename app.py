import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor
import datetime
import pytz

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Quant Sector Map", layout="wide", page_icon="🛡️")

# Expanded Sector List for better breadth analysis
SECTORS = {
    'XLK': 'Technology', 'XLF': 'Financials', 'XLE': 'Energy',
    'XLV': 'Health Care', 'XLY': 'Consumer Disc', 'XLP': 'Consumer Staples',
    'XLI': 'Industrials', 'XLB': 'Materials', 'XLRE': 'Real Estate',
    'XLC': 'Comm Services', 'XLU': 'Utilities', 'SMH': 'Semiconductors',
    'SPY': 'S&P 500'
}

# --- 2. MATHEMATICAL ENGINE ---
def calculate_metrics(ticker, name):
    try:
        # RED TEAM FIX: Fetch 2 years to ensure EMA-200 is accurate
        # Using yfinance is more stable than raw requests
        df = yf.download(ticker, period="2y", interval="1d", progress=False)
        
        if df.empty or len(df) < 200:
            return None
            
        # Standardize columns (yfinance structure varies)
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs('Close', axis=1, level=1)
        else:
            df = df['Close']
            
        # --- MATH AUDIT ---
        curr_price = float(df.iloc[-1])
        
        # 1. Trend Filter (EMA > SMA for speed)
        ema_50 = df.ewm(span=50, adjust=False).mean().iloc[-1]
        ema_200 = df.ewm(span=200, adjust=False).mean().iloc[-1]
        
        # 2. Volatility Normalization (Z-Score)
        # Using 20-day Lookback (Short-term Mean Reversion)
        roll = df.rolling(20)
        mu = roll.mean().iloc[-1]
        sigma = roll.std().iloc[-1]
        
        # Avoid division by zero
        if sigma == 0: sigma = 0.001
            
        z_score = (curr_price - mu) / sigma
        
        # 3. Percentile Rank (Non-Parametric Verification)
        # Checks where current Z-score sits relative to last 6 months of Z-scores
        # This confirms if a "2.0" is actually rare for THIS specific stock
        past_z = (df - df.rolling(20).mean()) / df.rolling(20).std()
        recent_z = past_z.tail(126).dropna() # Last 6 months
        if not recent_z.empty:
            percentile = (recent_z < z_score).mean() * 100
        else:
            percentile = 50.0

        # --- LOGIC GATES ---
        regime = "NEUTRAL"
        # Golden Alignment: Price > 200 AND 50 > 200 (Strong Trend)
        if curr_price > ema_200 and ema_50 > ema_200:
            regime = "BULL"
        # Death Alignment: Price < 200 AND 50 < 200 (Strong Downtrend)
        elif curr_price < ema_200 and ema_50 < ema_200:
            regime = "BEAR"
        elif curr_price > ema_200:
            regime = "RECOVERY" # Price above 200, but moving averages not aligned
            
        return {
            "Ticker": ticker,
            "Name": name,
            "Price": curr_price,
            "Z_Score": z_score,
            "Pct_Rank": percentile,
            "Regime": regime,
            "EMA_200": ema_200
        }
    except Exception as e:
        return None

def get_signal_rating(row):
    z = row['Z_Score']
    p = row['Pct_Rank']
    regime = row['Regime']
    
    # RED TEAM LOGIC: Confluence of Parametric (Z) and Non-Parametric (Percentile)
    
    if regime == "BULL":
        # Pullback in Uptrend
        if z < -2.0 and p < 5: return "⭐⭐⭐ (Prime)" # Rare (<5% occurrence)
        if z < -1.0: return "⭐⭐ (Watch)"
        if z > 2.5: return "✋ (Extended)"
        
    if regime == "BEAR":
        # Rally in Downtrend
        if z > 1.5: return "📉 (Short Setup)"
        if z < -2.0: return "⛔ (Knife)"
        
    return "❄️ (Wait)"

# --- 3. PARALLEL EXECUTION ---
def run_scan():
    results = []
    # RED TEAM FIX: Non-blocking I/O
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(calculate_metrics, t, n): t for t, n in SECTORS.items()}
        
        for future in futures:
            res = future.result()
            if res:
                results.append(res)
                
    return pd.DataFrame(results)

# --- 4. UI ---
def main():
    st.title("🛡️ Red-Teamed Momentum Map")
    
    col1, col2 = st.columns([3,1])
    with col1:
        st.markdown("Math-Verified Swing Trading Dashboard")
    with col2:
        if st.button("🚀 Run Audit"):
            st.cache_data.clear()

    # Execution
    with st.spinner("Calculating Volatility Surfaces..."):
        df = run_scan()

    if not df.empty:
        df['Signal'] = df.apply(get_signal_rating, axis=1)
        
        # Sort by Z-Score for Heatmap
        df = df.sort_values(by="Z_Score", ascending=False)
        
        # --- VISUALIZATION ---
        # 1. Z-Score Heatmap
        fig = px.bar(
            df, x="Ticker", y="Z_Score", color="Z_Score",
            color_continuous_scale="RdYlGn_r",
            title="Standard Deviation from 20-Day Mean",
            hover_data=["Name", "Regime", "Pct_Rank"], text_auto='.2f'
        )
        # Statistical Bounds
        fig.add_hline(y=2.0, line_dash="dot", line_color="red", annotation_text="+2σ (95%)")
        fig.add_hline(y=-2.0, line_dash="dot", line_color="green", annotation_text="-2σ (5%)")
        st.plotly_chart(fig, use_container_width=True)
        
        # 2. Detailed Data Table
        st.subheader("Algorithmic Output")
        
        # Formatting
        def highlight_regime(val):
            colors = {'BULL': '#d4edda', 'BEAR': '#f8d7da', 'RECOVERY': '#fff3cd', 'NEUTRAL': '#e2e3e5'}
            return f'background-color: {colors.get(val, "white")}; color: black'

        st.dataframe(
            df[['Ticker', 'Signal', 'Z_Score', 'Pct_Rank', 'Regime', 'Price', 'Name']]
            .style.map(highlight_regime, subset=['Regime'])
            .format({
                "Z_Score": "{:.2f}σ", 
                "Price": "${:.2f}",
                "Pct_Rank": "{:.1f}%"
            }),
            use_container_width=True,
            height=600
        )
        
        st.caption("Audit Note: 'Prime' signals now require Z-Score < -2.0 AND Historical Percentile < 5%.")
        
    else:
        st.error("Data Feed Error. Check Internet Connection or API Limits.")

if __name__ == "__main__":
    main()
