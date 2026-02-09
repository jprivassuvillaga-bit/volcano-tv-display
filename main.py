import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime
from dotenv import load_dotenv
import data_fetcher, risk_math, charts, news_fetcher
from streamlit_autorefresh import st_autorefresh

# ==============================================================================
# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
# ==============================================================================
st.set_page_config(page_title="Volcano TV", page_icon="📺", layout="wide", initial_sidebar_state="collapsed")
load_dotenv()

# HEARBEAT: Recarga la página cada 1 segundo para verificar cronómetros de rotación
st_autorefresh(interval=1000, key="tv_heartbeat")

# GESTIÓN DE ESTADO (Session State)
if 'tv_start_time' not in st.session_state:
    st.session_state.tv_start_time = time.time()
    st.session_state.page_index = 0      
    st.session_state.news_offset = 0     
    st.session_state.last_tab_change = time.time()
    st.session_state.last_news_change = time.time()
    # Cache para el modelo AI (para no re-entrenar cada segundo)
    st.session_state.forecast_cache = None 
    st.session_state.last_forecast_time = 0

# --- LÓGICA DE PROPHET (AI FORECAST) ---
# Intentamos importar Prophet. Si falla (por errores de C++ en Mac), usamos fallback.
HAS_PROPHET = False
try:
    from prophet import Prophet
    HAS_PROPHET = True
except ImportError:
    pass

def get_or_train_forecast(df):
    """Entrena el modelo solo si ha pasado 1 hora o no existe"""
    if not HAS_PROPHET: return None
    
    current_t = time.time()
    # Re-entrenar cada 1 hora (3600s)
    if st.session_state.forecast_cache is not None and (current_t - st.session_state.last_forecast_time < 3600):
        return st.session_state.forecast_cache

    try:
        # Preparamos datos
        ph_df = df.reset_index()[['Date', 'close']].rename(columns={'Date': 'ds', 'close': 'y'})
        if ph_df['ds'].dt.tz is not None: ph_df['ds'] = ph_df['ds'].dt.tz_localize(None)
        
        # Entrenamos (Rápido)
        m = Prophet(daily_seasonality=True, changepoint_prior_scale=0.15)
        m.fit(ph_df)
        
        # Predicción 30 días
        future = m.make_future_dataframe(periods=30)
        forecast = m.predict(future)
        
        # Guardamos en cache
        st.session_state.forecast_cache = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
        st.session_state.last_forecast_time = current_t
        return st.session_state.forecast_cache
    except Exception as e:
        print(f"Prophet Error: {e}")
        return None

# ==============================================================================
# --- 2. CSS & ESTILOS DE TV ---
# ==============================================================================
st.markdown("""
<style>
    .stApp { background-color: #000000; }
    header {visibility: hidden;}
    .css-1rs6os {visibility: hidden;}
    .css-17ziqus {display: none;}
    
    /* Ticker Lento */
    .ticker-wrap {
        width: 100%; overflow: hidden; background-color: #111;
        border-top: 1px solid #333; border-bottom: 1px solid #333;
        padding: 6px 0; white-space: nowrap; margin-bottom: 10px;
    }
    .ticker { display: inline-block; animation: ticker 120s linear infinite; }
    .ticker-item { display: inline-block; padding: 0 3rem; font-size: 18px; color: #e0e0e0; font-family: 'Courier New', monospace; }
    .ticker-tag { color: #F59E0B; font-weight: bold; margin-right:8px; }
    @keyframes ticker { 0% { transform: translate3d(0, 0, 0); } 100% { transform: translate3d(-100%, 0, 0); } }
    
    /* ALTO CONTRASTE (Solo para Vista 3) */
    .tv-high-contrast div[data-testid="stMetricValue"],
    .tv-high-contrast div[data-testid="stMetricLabel"],
    .tv-high-contrast h1, .tv-high-contrast h2, .tv-high-contrast h3, .tv-high-contrast p, .tv-high-contrast span {
        color: #FFFFFF !important;
        opacity: 1 !important;
        text-shadow: 0px 2px 4px rgba(0,0,0,0.8); /* Sombra para resaltar */
        font-weight: 700 !important;
    }
    .tv-high-contrast div[data-testid="stMarkdownContainer"] p { font-size: 1.3rem !important; }
    
    div[data-testid="stVerticalBlock"] > div[style*="border"] { 
        background-color: #0a0a0a; border: 1px solid #222; 
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# --- 3. CARGA DE DATOS ---
# ==============================================================================
@st.cache_data(ttl=600)
def get_tv_data():
    m_df = data_fetcher.fetch_market_data(period="2y", interval="1d")
    # News y Macro
    news = news_fetcher.fetch_sentinel_news(limit=40) 
    macro = data_fetcher.fetch_macro_data(period="6mo") # Traemos 6 meses para el gráfico macro
    fng_val, fng_lbl = data_fetcher.fetch_fear_and_greed_index()
    return m_df, news, macro, fng_val, fng_lbl

market_df, all_news, macro_df, fg_value, fg_label = get_tv_data()

# Safety Check
if market_df.empty or 'close' not in market_df.columns:
    st.warning("⚠️ Market Data Feed Reconnecting...")
    time.sleep(2)
    st.rerun()

curr = {
    'close': market_df['close'].iloc[-1],
    'volatility': market_df['volatility'].iloc[-1],
    'z_score': market_df['z_score'].iloc[-1] if 'z_score' in market_df.columns else 0,
    'high': market_df['high'].iloc[-1],
    'low': market_df['low'].iloc[-1],
    'vwap': market_df['sma_50'].iloc[-1] # Usamos SMA50 como proxy de tendencia visual si no hay VWAP intradía
}
price_delta = (curr['close'] - market_df['close'].iloc[-2]) / market_df['close'].iloc[-2]

# Entrenar AI Forecast (Si Prophet está disponible)
forecast_df = get_or_train_forecast(market_df)

# ==============================================================================
# --- 4. CONTROL DE TIEMPO Y ROTACIÓN ---
# ==============================================================================
current_time = time.time()

# Rotación de Pestañas (Tiempos personalizados por vista)
# Vista 0: 30s | Vista 1: 15s | Vista 2: 15s
cycle_times = [30, 15, 15] 
current_duration = cycle_times[st.session_state.page_index]

if current_time - st.session_state.last_tab_change > current_duration:
    st.session_state.page_index = (st.session_state.page_index + 1) % 3 
    st.session_state.last_tab_change = current_time

# Rotación de Noticias (Cada 2 mins avanzamos 10 noticias)
if current_time - st.session_state.last_news_change > 120:
    st.session_state.news_offset += 10
    st.session_state.last_news_change = current_time

# ==============================================================================
# --- 5. COMPONENTES VISUALES (HEADER & TICKER) ---
# ==============================================================================
# HEADER
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

# TICKER DE NOTICIAS
if all_news:
    total_news = len(all_news)
    start_idx = st.session_state.news_offset % total_news
    batch = [all_news[(start_idx + i) % total_news] for i in range(10)]
    
    ticker_html = ""
    for n in batch:
        tag = " | ".join(n.get('tags', ['NEWS'])[:1]).upper()
        ticker_html += f"""<div class="ticker-item"><span class="ticker-tag">⚡ {tag}</span>{n['title']}</div>"""
    
    st.markdown(f"""<div class="ticker-wrap"><div class="ticker">{ticker_html}{ticker_html}</div></div>""", unsafe_allow_html=True)

# Indicador de Página (Puntos)
dots = "".join(["● " if i == st.session_state.page_index else "○ " for i in range(3)])
st.caption(f"LIVE FEED: {dots} (View {st.session_state.page_index + 1}/3)")

# ==============================================================================
# --- 6. VISTAS PRINCIPALES ---
# ==============================================================================

# --- VISTA 1: MARKET OVERVIEW (0-30s) ---
if st.session_state.page_index == 0:
    st.subheader("📈 Market Structure & Volume")
    st.plotly_chart(charts.create_price_volume_chart(market_df), use_container_width=True)
    
    # Métricas inferiores rápidas
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("24h High", f"${curr['high']:,.0f}")
    m2.metric("24h Low", f"${curr['low']:,.0f}")
    m3.metric("Trend (SMA50)", "BULLISH" if curr['close'] > curr['vwap'] else "BEARISH")
    m4.metric("Volatility", f"{curr['volatility']:.1%}")


# --- VISTA 2: RISK TRINITY (30s-45s) ---
elif st.session_state.page_index == 1:
    st.subheader("⚠️ Risk Radar & Macro Correlations")
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.caption("Historical Volatility (30D)")
        st.plotly_chart(charts.create_volatility_chart(market_df), use_container_width=True)
        
    with c2:
        st.caption("Mean Reversion (Z-Score)")
        st.plotly_chart(charts.create_zscore_chart(market_df), use_container_width=True)
        
    with c3:
        st.caption("Macro Correlations (vs S&P500 / Gold)")
        # Usamos la nueva función Macro
        if not macro_df.empty:
            st.plotly_chart(charts.create_macro_chart(macro_df), use_container_width=True)
        else:
            st.info("Loading Macro Data...")


# --- VISTA 3: INSTITUTIONAL CREDIT SIMULATOR (SOLO SIMULACIÓN) ---
# ** HIGH CONTRAST MODE (FULL SCREEN) **
elif st.session_state.page_index == 2:
    
    # Activamos Alto Contraste (Letras Blancas y Brillantes)
    st.markdown('<div class="tv-high-contrast">', unsafe_allow_html=True)
    
    st.subheader("🛡️ Live Credit Stress Test (Institutional)")
    
    # --- 1. PARÁMETROS DEL ESCENARIO (Fijos para TV) ---
    SIM_LOAN = 5_000_000   # $5 Millones (Ejemplo Institucional)
    SIM_HAIRCUT = 30       # 30% Haircut
    SIM_LTV = 0.65         # 65% LTV Inicial
    SIM_LIQ_THRESH = 0.85  # 85% Umbral de Liquidación
    
    # --- 2. CÁLCULO "DOUBLE SHIELD" (Tu Lógica) ---
    # A. Precio que el banco reconoce (Lending Value)
    lending_price = curr['close'] * (1 - (SIM_HAIRCUT / 100))
    
    # B. Colateral Requerido (Basado en Lending Price)
    collateral_btc = SIM_LOAN / (lending_price * SIM_LTV)
    collateral_usd_market = collateral_btc * curr['close']
    
    # C. Precio de Liquidación
    # Deuda = (BTC * Liq_Price * (1-Haircut)) * Threshold
    liq_price = SIM_LOAN / (collateral_btc * (1 - SIM_HAIRCUT/100) * SIM_LIQ_THRESH)
    
    # D. Buffer de Seguridad
    buffer_pct = (curr['close'] - liq_price) / curr['close']
    
    # --- 3. DISEÑO VISUAL (3 COLUMNAS GRANDES) ---
    c1, c2, c3 = st.columns([1, 1, 1])
    
    # COLUMNA 1: ESTRUCTURA DEL TRATO
    with c1:
        st.markdown("#### 💼 Deal Structure")
        st.metric("Principal", f"${SIM_LOAN/1_000_000:.1f}M", "USD")
        st.metric("Haircut Applied", f"{SIM_HAIRCUT}%", f"Adj. Price: ${lending_price:,.0f}")
        st.metric("Effective LTV", f"{SIM_LTV:.0%}", "Risk Policy")

    # COLUMNA 2: REQUERIMIENTOS DE COLATERAL (EL NÚMERO IMPORTANTE)
    with c2:
        st.markdown("#### 🔐 Collateral Required")
        # Mostramos BTC en gigante
        st.markdown(f"""
        <div style="font-size: 50px; font-weight: bold; color: #F59E0B; line-height: 1.2;">
            {collateral_btc:.2f} BTC
        </div>
        """, unsafe_allow_html=True)
        
        st.metric("Market Value", f"${collateral_usd_market:,.0f}", "100% Value")
        
        # Barra de progreso visual: Cuánto del colateral es "reconocido" vs "recorte"
        st.caption(f"Bank Recognition Rate: {100-SIM_HAIRCUT}%")
        st.progress(1.0 - (SIM_HAIRCUT/100))

    # COLUMNA 3: ANÁLISIS DE RIESGO (LIQUIDACIÓN)
    with c3:
        st.markdown("#### 📉 Risk Thresholds")
        
        liq_color = "#FF4B4B" if buffer_pct < 0.15 else "#10B981"
        
        st.metric("Liquidation Price", f"${liq_price:,.0f}", f"Threshold: {SIM_LIQ_THRESH:.0%}")
        
        st.markdown(f"""
        <div style="margin-top: 10px;">
            <div style="font-size: 16px; color: #aaa;">SAFETY BUFFER</div>
            <div style="font-size: 40px; font-weight: bold; color: {liq_color};">
                {buffer_pct:.2%}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if buffer_pct > 0.20:
            st.success("✅ LOW RISK SCENARIO")
        else:
            st.warning("⚠️ MODERATE RISK")

    st.markdown('</div>', unsafe_allow_html=True)
