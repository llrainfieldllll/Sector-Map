# --- 5. MAIN UI ---
def main():
    st.title("🌎 Sector Momentum Map")
    st.markdown(f"**Status:** Market Scan @ {datetime.datetime.now().strftime('%H:%M ET')}")
    st.info("💡 **How to Read:** Look for **⭐⭐ (Stars)** in the table below. Hover over the **'Trade Setup'** column header for the logic.")

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

        # B. Scorecard Table with Signals
        def color_regime(val):
            colors = {'BULL': '#d4edda', 'RECOVERY': '#fff3cd', 'BEAR': '#f8d7da'}
            text_colors = {'BULL': '#155724', 'RECOVERY': '#856404', 'BEAR': '#721c24'}
            return f'background-color: {colors.get(val, "")}; color: {text_colors.get(val, "")}; font-weight: bold'

        def color_z(val):
            color = 'red' if val > 2.0 else ('green' if val < -2.0 else 'black')
            return f'color: {color}; font-weight: bold'

        def color_signal(val):
            if "⭐⭐" in val: return 'color: #28a745; font-weight: bold; font-size: 1.1em' # Green
            if "⛔" in val: return 'color: #dc3545; font-weight: bold' # Red
            if "✋" in val: return 'color: #fd7e14; font-weight: bold' # Orange
            return 'color: gray'

        # THE LOGIC MATRIX TOOLTIP (Hidden behind the ? icon)
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
            use_container_width=True,
            height=600,
            column_config={
                "Signal": st.column_config.TextColumn(
                    "Trade Setup", 
                    width="medium", 
                    help=logic_tooltip  # <--- THIS ADDS THE HOVER QUESTION MARK
                )
            }
        )
    else:
        st.error("Critical Failure: Even the heavy armor was blocked. Try deploying locally.")
