"""Streamlit Cloud Web App for the NASDAQ-100 & STOXX 50 Options Edge Screener."""

from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from screener.analytics import run_screen
from screener.exporter import export_to_csv, generate_html_dashboard
from screener.universe import DEFAULT_UNIVERSE

st.set_page_config(
    page_title="NASDAQ-100 & STOXX 50 Options Edge Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CSV_PATH = Path("output/megacap_options_yields.csv")
HTML_PATH = Path("output/dashboard.html")

col_title, col_btn, col_dl = st.columns([6, 2, 2])
with col_title:
    st.markdown("### 🌐 Worldwide Layover Edition — NASDAQ-100 & STOXX 50 Options Screener")
with col_btn:
    refresh_clicked = st.button("🔄 Pull Live Yahoo Finance Data", type="primary", use_container_width=True)

if refresh_clicked or not CSV_PATH.exists():
    with st.spinner("Screening 158 NASDAQ-100, STOXX 50 & Global stocks in parallel..."):
        df = run_screen(DEFAULT_UNIVERSE, target_dte=30, target_otm_pct=0.05, min_pe=0.0)
        if not df.empty:
            export_to_csv(df, CSV_PATH)
            generate_html_dashboard(df, HTML_PATH)

if CSV_PATH.exists():
    df_current = pd.read_csv(CSV_PATH)
    if not HTML_PATH.exists():
        generate_html_dashboard(df_current, HTML_PATH)
    with col_dl:
        st.download_button(
            label="📥 Download CSV",
            data=CSV_PATH.read_bytes(),
            file_name="megacap_options_yields.csv",
            mime="text/csv",
            use_container_width=True,
        )
    html_content = HTML_PATH.read_text(encoding="utf-8")
    components.html(html_content, height=1350, scrolling=True)
else:
    st.warning("Click 'Pull Live Yahoo Finance Data' above to run your first screen.")
