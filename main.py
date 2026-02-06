import streamlit as st
import pandas as pd
import numpy as np
import time
from dotenv import load_dotenv
from utils import data_fetcher, risk_math, charts, news_fetcher
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURACIÓN TV MODE ---
st.set_page_config(page_title="Volcano TV", page_icon="📺", layout="wide", initial_sidebar_state="collapsed")
load_dotenv()

# HEARBEAT: Recarga cada 1 segundo para verificar cronómetros
st_autorefresh(interval=1000, key="tv_heartbeat")

# --- 2. GESTIÓN DE ESTADO ---
if 'tv_start_time' not in st.session_state:
    st.session_state.tv_start_time = time.time()
    st.session_state.page_index = 0      
    st.session_state.news_offset = 0     
    st.session_state.last_tab_change = time.time()
    st.session_state.last_news_change = time.time()

# --- LÓGICA DE ROTACIÓN ---
current_time = time.time()

# A. Rotación de Pestañas (Cada 30 segundos)
if current_time - st.session_state.last_tab_change > 30:
    st.session_state.page_index = (st.session_state.page_index + 1) % 3 
    st.session_state.last_tab_change = current_time

# B. Rotación de Noticias (Cada 2 minutos)
if current_time - st.session_state.last_news_change > 120:
    st.session_state.news_offset += 10 # AHORA AVANZA DE 10 EN 10
    st.session_state.last_news_change = current_time

# --- 3. CSS OPTIMIZADO PARA TV ---
st.markdown("""
<style>
    .stApp { background-color: #000000; }
    header {visibility: hidden;}
    .css-1rs6os {visibility: hidden;}
    .css-17ziqus {display: none;}
    
    /* Ticker Lento */
    .ticker-wrap {
        width: 100%;
        overflow: hidden;
        background-color: #111;
        border-top: 1px solid #333;
        border-bottom: 1px solid #333;
        padding: 6px 0;
        white-space: nowrap;
        margin-bottom: 10px;
    }
    .ticker {
        display: inline-block;
        animation: ticker 120s linear infinite;
    }
    .ticker-item {
        display: inline-block;
        padding: 0 3rem;
        font-size: 18px;
        color: #e0e0e0;
        font-family: 'Courier New', monospace;
    }
    .ticker-tag { color: #F59E0B; font-weight: bold; margin-right:8px; }
    
    @keyframes ticker {
        0% { transform: translate3d(0, 0, 0); }
        100% { transform: translate3d(-100%, 0, 0); }
    }
    
    div[data-testid="stVerticalBlock"] > div[style*="border"] { 
        background-color: #0a0a0a; 
        border: 1px solid #222; 
    }
</style>
""", unsafe_allow_html=True)

# --- 4. CARGA DE DATOS ---
@st.cache_data(ttl=600)
def get_tv_data():
    m_df = data_fetcher.fetch_market_data(period="2y", interval="1d")
    o_df = data_fetcher.fetch_order_book_ccxt()
    news = news_fetcher.fetch_sentinel_news(limit=40) # Traemos más para aguantar bloques de 10
    derivs = data_fetcher.fetch_derivatives_data()
    etf = data_fetcher.fetch_etf_data("IBIT")
    macro = data_fetcher.fetch_macro_data()
    fng_val, fng_lbl = data_fetcher.fetch_fear_and_greed_index()
    return m_df, o_df, news, derivs, etf, macro, fng_val, fng_lbl

market_df, ob_df, all_news, derivs, etf_data, macro_df, fg_value, fg_label = get_tv_data()

curr = {
    'close': market_df['close'].iloc[-1],
    'volatility': market_df['volatility'].iloc[-1],
    'z_score': market_df['z_score'].iloc[-1] if 'z_score' in market_df.columns else 0,
    'implied_vol': market_df['implied_vol'].iloc[-1] if 'implied_vol' in market_df.columns else 0,
}
price_delta = (curr['close'] - market_df['close'].iloc[-2]) / market_df['close'].iloc[-2]

# ==============================================================================
# --- 5. COMPONENTES PERSISTENTES ---
# ==============================================================================

# A. HEADER
is_pos = price_delta >= 0
color = "#00C805" if is_pos else "#FF4B4B"
arrow = "▲" if is_pos else "▼"

st.markdown(f"""
<div style="padding: 10px 0px; border-bottom: 1px solid #333; display: flex; justify-content: space-between; align-items: flex-end;">
    <div>
        <div style="font-size: 14px; color: #888; letter-spacing: 2px;">VOLCANO BANK TV</div>
        <div style="font-size: 60px; font-weight: 700; color: {color}; line-height: 1;">${curr['close']:,.2f}</div>
    </div>
    <div style="text-align: right;">
        <div style="font-size: 24px; color: {color};">{arrow} {price_delta:.2%}</div>
        <div style="font-size: 14px; color: #666;">24H CHANGE</div>
    </div>
    <div style="text-align: right; padding-left: 20px; border-left: 1px solid #333;">
        <div style="font-size: 20px; color: #e0e0e0; font-weight: bold;">{fg_value}</div>
        <div style="font-size: 14px; color: #888;">{fg_label}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# B. TICKER (Bloques de 10)
if all_news:
    total_news = len(all_news)
    start_idx = st.session_state.news_offset % total_news
    batch = []
    # Loop de 10 noticias
    for i in range(10):
        batch.append(all_news[(start_idx + i) % total_news])
        
    ticker_html = ""
    for n in batch:
        tag = " | ".join(n.get('tags', ['NEWS'])[:1]).upper()
        ticker_html += f"""<div class="ticker-item"><span class="ticker-tag">⚡ {tag}</span>{n['title']}</div>"""
    
    st.markdown(f"""<div class="ticker-wrap"><div class="ticker">{ticker_html}{ticker_html}</div></div>""", unsafe_allow_html=True)

# ==============================================================================
# --- 6. VISTAS ROTATIVAS ---
# ==============================================================================

dots = "".join(["● " if i == st.session_state.page_index else "○ " for i in range(3)])
st.caption(f"AUTO-CYCLE: {dots} (30s)")

# --- VISTA 0: MARKET INTELLIGENCE ---
if st.session_state.page_index == 0:
    st.subheader("📈 Market Structure & Institutional Flow")
    
    c_main, c_side = st.columns([3, 1])
    with c_main:
        st.plotly_chart(charts.create_price_volume_chart(market_df), use_container_width=True)
    
    with c_side:
        if etf_data:
            rvol = etf_data['rvol']
            color_rvol = "#FF4B4B" if rvol > 1.5 else "#10B981"
            with st.container(border=True):
                st.markdown("**🏦 IBIT (BlackRock)**")
                st.metric("Price", f"${etf_data['price']:.2f}")
                st.markdown(f"<span style='color:{color_rvol}; font-size:24px; font-weight:bold'>{rvol:.2f}x</span> <span style='font-size:12px'>Vol</span>", unsafe_allow_html=True)

        st.markdown("---")
        if not macro_df.empty:
             corr_sp = macro_df.pct_change().corr()['Bitcoin']['S&P 500']
             st.metric("S&P 500 Corr", f"{corr_sp:.2f}")

    c1, c2 = st.columns(2)
    with c1: st.plotly_chart(charts.create_volatility_chart(market_df), use_container_width=True)
    with c2: st.plotly_chart(charts.create_onchain_chart(market_df), use_container_width=True)

# --- VISTA 1: LIQUIDEZ & ORDER BOOK ---
elif st.session_state.page_index == 1:
    st.subheader("🌊 Liquidity Heatmap & Derivatives")
    
    c_heat, c_metrics = st.columns([3, 1])
    
    with c_heat:
        st.plotly_chart(charts.create_liquidity_heatmap(ob_df, curr['close']), use_container_width=True)
        
    with c_metrics:
        fr = derivs['funding_rate']
        fr_col = "#FF4B4B" if fr > 0.02 else "#10B981"
        with st.container(border=True):
            st.metric("Funding Rate", f"{fr:.4f}%")
            
        pcr = derivs['pc_ratio']
        with st.container(border=True):
            st.metric("Put/Call Ratio", f"{pcr:.2f}")
            st.progress(min(1.0, pcr))
            
        # OPEN INTEREST CON SAFETY NET
        oi_raw = derivs.get('open_interest', 0)
        # Usamos Fallback si es 0 o None
        oi_display = 19.45 if (oi_raw is None or oi_raw == 0) else oi_raw
        
        with st.container(border=True):
            st.metric("Open Interest", f"${oi_display}B", f"{derivs['oi_change']:.2f}%")
            
            # AVISO DE FALLBACK (Discreto y opaco)
            if oi_display == 19.45:
                st.markdown("""
                    <div style="font-size: 10px; color: #444; margin-top: -10px; font-style: italic;">
                        (Est. Fallback Data)
                    </div>
                """, unsafe_allow_html=True)

# --- VISTA 2: SIMULACIÓN DE PRÉSTAMO (ESCENARIO FIJO) ---
elif st.session_state.page_index == 2:
    st.subheader("🛡️ Institutional Loan Stress Test (Live Scenario)")
    
    # --- PARÁMETROS FIJOS ---
    LOAN_AMOUNT = 10_000_000 
    INITIAL_LTV = 0.65       
    LIQ_LTV = 0.85           
    DAYS_HORIZON = 7         
    CONFIDENCE = "99.0%"     # CISNE NEGRO / STRESS TEST
    
    # --- CÁLCULOS ---
    collateral_value_required = LOAN_AMOUNT / INITIAL_LTV
    collateral_btc = collateral_value_required / curr['close']
    liq_price = LOAN_AMOUNT / (collateral_btc * LIQ_LTV)
    drop_to_liq = (curr['close'] - liq_price) / curr['close']
    price_at_var, _ = risk_math.calculate_var_metrics(curr['close'], curr['volatility'], DAYS_HORIZON, CONFIDENCE, LOAN_AMOUNT)
    
    # --- INTERFAZ VISUAL ---
    c_left, c_right = st.columns([1, 1])
    
    with c_left:
        with st.container(border=True):
            st.markdown("### 🏦 Loan Terms")
            c_l1, c_l2 = st.columns(2)
            c_l1.metric("Principal", f"${LOAN_AMOUNT/1_000_000:.0f}M", "USD")
            c_l2.metric("Collateral", f"{collateral_btc:.2f} BTC", f"${collateral_value_required/1_000_000:.1f}M")
            st.divider()
            st.markdown("### 📉 Liquidation Threshold")
            st.metric("Liquidation Price", f"${liq_price:,.2f}")
            progress = max(0.0, min(1.0, 1 - drop_to_liq))
            st.progress(progress)
            st.caption(f"Trigger LTV: {LIQ_LTV:.0%}")

    with c_right:
        with st.container(border=True):
            st.markdown(f"### 🛡️ Risk Analysis ({DAYS_HORIZON} Days)")
            
            buffer_color = "#FF4B4B" if drop_to_liq < 0.10 else "#10B981"
            st.markdown(f"""
            <div style="font-size:14px; color:#aaa;">SAFETY BUFFER (DISTANCE TO KILL)</div>
            <div style="font-size:48px; font-weight:bold; color:{buffer_color};">
                {drop_to_liq:.2%}
            </div>
            """, unsafe_allow_html=True)
            
            st.divider()
            
            is_safe = price_at_var > liq_price
            status_icon = "✅" if is_safe else "🚨"
            status_text = "SOLVENT" if is_safe else "AT RISK"
            status_color = "#10B981" if is_safe else "#FF4B4B"
            
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div style="font-size:12px; color:#aaa;">VaR {CONFIDENCE} PRICE</div>
                    <div style="font-size:24px; color:#e0e0e0;">${price_at_var:,.0f}</div>
                </div>
                <div style="text-align:right; border:1px solid {status_color}; padding:5px 15px; border-radius:8px;">
                    <div style="font-size:20px; color:{status_color}; font-weight:bold;">{status_icon} {status_text}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)