import streamlit as st
import pandas as pd
import plotly.express as px
from curl_cffi import requests as crequests
import datetime
import pytz

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
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?range=2y&interval=1d"
        r = crequests.get(url, impersonate="chrome110", timeout=10)
        
        if r.status_code != 200: return None
            
        data = r.json()
        result = data['chart']['result'][0]
        timestamps = result['timestamp']
        closes = result['indicators']['quote'][0]['close']
        
        df = pd.DataFrame({'Close': closes, 'Timestamp': timestamps})
        df['Date'] = pd.to_datetime(df['Timestamp'], unit='s')
        df.set_index('Date', inplace=True)
        df = df.dropna()
        
        return df['Close']
    except Exception:
        return None

# --- 4. THE SIGNAL BRAIN ---
def get_signal_rating(row):
    z = row['Z-Score']
    regime = row['Regime']
    
    # BULL TREND
    if regime == "BULL":
        if z < -2.0: return "⭐⭐⭐ (Prime)"
        if z < -1.0: return "⭐⭐ (Watch)"
        if z > 2.0:  return "✋ (Hot)"
    
    # BEAR TREND
    if regime == "BEAR":
        if z < -2.0: return "⛔ (Trap)"
        if z > 1.5:  return "📉 (Short?)"

    # RECOVERY
    if regime == "RECOVERY":
        return "⚠️ (Mixed)"
        
    return "❄️ (Wait)"

def process_market_data():
    results = []
    last_valid_date = None # Store the date of the data
    
    my_bar = st.progress(0, text="Establishing Secure Connection...")
    
    total = len(SECTORS)
    for i, (ticker, name) in enumerate(SECTORS.items()):
        closes = get_raw_data(ticker)
        
        if closes is not None and len(closes) > 200:
            # Capture the last date from the data itself
            if last_valid_date is None:
                last_valid_date = closes.index[-1]
            
            curr = closes.iloc[-1]
            sma50 = closes.rolling(50).mean().iloc[-1]
            sma200 = closes.rolling(200).mean().iloc[-1]
            mu = closes.rolling(20).mean().iloc[-1]
            sigma = closes.rolling(20).std().iloc[-1]
            z = (curr - mu) / sigma if sigma > 1e-6 else 0
            
            regime = "BEAR"
            if curr > sma200: regime = "BULL"
            elif curr > sma50: regime = "RECOVERY"
            
            results.append({
                "Ticker": ticker, "Name": name, "Price": float(curr),
                "Z-Score": float(z), "Regime": regime,
                "Pct_Above_200": float((curr / sma200) - 1)
            })
        my_bar.progress((i + 1) / total, text=f"Scanning {ticker}...")
        
    my_bar.empty()
    
    df = pd.DataFrame(results)
    if not df.empty:
        df['Signal'] = df.apply(get_signal_rating, axis=1)
        cols = ['Ticker', 'Signal', 'Z-Score', 'Regime', 'Price', 'Name', 'Pct_Above_200']
        df = df[cols]
        
    return df, last_valid_date

# --- 5. MAIN UI ---
def main():
    st.title("🌎 Sector Momentum Map")
    
    # 1. Calculate Scan Time (Execution Time)
    toronto_tz = pytz.timezone('America/Toronto')
    scan_time = datetime.datetime.now(toronto_tz)
    
    st.info("💡 **How to Read:** Look for **⭐⭐ (Stars)** in the table below. Hover over the **'Trade Setup'** column header for the logic.")

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()

    # 2. Run Scan & Get Data Date
    df, data_date = process_market_data()

    # 3. Format Data Date
    data_date_str = "Unknown"
    if data_date:
        data_date_str = data_date.strftime('%Y-%m-%d') # Shows the actual close date (e.g. Friday)

    # 4. Display Dual Status Line
    st.markdown(f"**Scan Status:** Executed @ {scan_time.strftime('%H:%M:%S %Z')} | **Data Valid As Of:** Market Close {data_date_str}")

    if not df.empty:
        df = df.sort_values(by="Z-Score", ascending=False)

        # Heatmap
        fig = px.bar(
            df, x="Ticker", y="Z-Score", color="Z-Score",
            color_continuous_scale="RdYlGn_r",
            title=f"Sector Z-Scores (Data: {data_date_str})",
            hover_data=["Name", "Regime"], text_auto='.2f'
        )
        fig.add_hline(y=2.0, line_dash="dash", line_color="red", annotation_text="Overheated")
        fig.add_hline(y=-2.0, line_dash="dash", line_color="green", annotation_text="Buy Zone")
        st.plotly_chart(fig, use_container_width=True)

        # Styling
        def color_regime(val):
            colors = {'BULL': '#d4edda', 'RECOVERY': '#fff3cd', 'BEAR': '#f8d7da'}
            text_colors = {'BULL': '#155724', 'RECOVERY': '#856404', 'BEAR': '#721c24'}
            return f'background-color: {colors.get(val, "")}; color: {text_colors.get(val, "")}; font-weight: bold'

        def color_z(val):
            color = 'red' if val > 2.0 else ('green' if val < -2.0 else 'black')
            return f'color: {color}; font-weight: bold'

        def color_signal(val):
            if "⭐⭐" in val: return 'color: #28a745; font-weight: bold; font-size: 1.1em'
            if "⛔" in val: return 'color: #dc3545; font-weight: bold'
            if "✋" in val: return 'color: #fd7e14; font-weight: bold'
            return 'color: gray'

        # Tooltip Logic
        logic_tooltip = """
        THE SIGNAL LOGIC MATRIX:
        ✅ BULL TREND (Safe to Buy):
        ⭐⭐⭐ PRIME = Price is Deeply Oversold (Z < -2.0).
        ⭐⭐ WATCH = Price is Pulling Back (Z < -1.0).
        ✋ HOT = Price is Overextended (Z > +2.0). Wait.
        
        ⚠️ BEAR TREND (Dangerous):
        ⛔ TRAP = Price is crashing (Z < -2.0). Do not buy.
        📉 SHORT = Bear Market Rally (Z > +1.5). Likely to fail.
        
        *Methodology only. Not financial advice.*
        """

        st.dataframe(
            df.style.map(color_regime, subset=['Regime'])
                    .map(color_z, subset=['Z-Score'])
                    .map(color_signal, subset=['Signal'])
                    .format({"Price": "${:.2f}", "Z-Score": "{:.2f}σ", "Pct_Above_200": "{:.1%}"}),
            use_container_width=True, height=600,
            column_config={
                "Signal": st.column_config.TextColumn("Trade Setup", width="medium", help=logic_tooltip)
            }
        )
    else:
        st.error("Critical Failure: Connection Blocked. Try deploying locally.")

if __name__ == "__main__":
    main()
