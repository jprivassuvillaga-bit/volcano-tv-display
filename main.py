import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime
from dotenv import load_dotenv
import data_fetcher
import risk_math
import charts
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

# 1. Intentamos obtener precio en vivo (Kraken)
# (Asegúrate de haber agregado la función fetch_live_price en data_fetcher.py)
live_price = data_fetcher.fetch_live_price()

# 2. Decidimos qué precio usar
if live_price:
    current_price = live_price
else:
    current_price = market_df['close'].iloc[-1]

# 3. Calculamos el cambio % (Precio Vivo vs Cierre de Ayer)
prev_close = market_df['close'].iloc[-2]
price_delta = (current_price - prev_close) / prev_close

# 4. Construimos el estado actual con el precio vivo
curr = {
    'close': current_price, # <--- USAMOS EL PRECIO VIVO
    'volatility': market_df['volatility'].iloc[-1],
    'z_score': market_df['z_score'].iloc[-1] if 'z_score' in market_df.columns else 0,
    # Ajustamos High/Low dinámicamente si el precio vivo rompe los rangos del día
    'high': max(market_df['high'].iloc[-1], current_price),
    'low': min(market_df['low'].iloc[-1], current_price),
    'vwap': market_df['sma_50'].iloc[-1] 
}
# Entrenar AI Forecast (Si Prophet está disponible)
forecast_df = get_or_train_forecast(market_df)

# ==============================================================================
# --- 4. CONTROL DE TIEMPO Y ROTACIÓN ---
# ==============================================================================
current_time = time.time()

# Rotación de Pestañas (Tiempos personalizados por vista)
# Vista 0: 30s | Vista 1: 15s | Vista 2: 15s
cycle_times = [25, 25, 25, 25, 25] 
current_duration = cycle_times[st.session_state.page_index]

if current_time - st.session_state.last_tab_change > current_duration:
    st.session_state.page_index = (st.session_state.page_index + 1) % 5
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
# ** HIGH CONTRAST MODE (PURE HTML) **
elif st.session_state.page_index == 2:
    
    st.subheader("🛡️ Live Credit Stress Test (Institutional)")
    
    # --- 1. PARÁMETROS ---
    SIM_LOAN = 5_000_000   
    SIM_HAIRCUT = 30       
    SIM_LTV = 0.65         
    SIM_LIQ_THRESH = 0.85  
    
    # --- 2. CÁLCULOS ---
    lending_price = curr['close'] * (1 - (SIM_HAIRCUT / 100))
    collateral_btc = SIM_LOAN / (lending_price * SIM_LTV)
    collateral_usd_market = collateral_btc * curr['close']
    liq_price = SIM_LOAN / (collateral_btc * (1 - SIM_HAIRCUT/100) * SIM_LIQ_THRESH)
    buffer_pct = (curr['close'] - liq_price) / curr['close']
    
    # --- 3. FUNCIÓN DE RENDERIZADO (TARJETA TV) ---
    # Esta función crea HTML puro, igual que el Header, para garantizar nitidez
    def render_tv_card(title, value, subvalue, color="#FFFFFF", bg_color="#111"):
        return f"""
        <div style="
            background-color: {bg_color};
            border: 1px solid #333;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 10px;
            height: 100%;
        ">
            <div style="color: #888; font-size: 16px; font-weight: 500; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 5px;">
                {title}
            </div>
            <div style="color: {color}; font-size: 42px; font-weight: 800; line-height: 1.1;">
                {value}
            </div>
            <div style="color: #ccc; font-size: 18px; margin-top: 5px; font-weight: 400;">
                {subvalue}
            </div>
        </div>
        """

    # --- 4. DISEÑO VISUAL ---
    c1, c2, c3 = st.columns([1, 1, 1])
    
    with c1:
        st.markdown("#### 💼 Deal Structure")
        st.markdown(render_tv_card(
            "Principal Loan", 
            f"${SIM_LOAN/1_000_000:.1f}M", 
            "USD Currency"
        ), unsafe_allow_html=True)
        
        st.markdown(render_tv_card(
            "Risk Policy", 
            f"{SIM_HAIRCUT}% HC", 
            f"Effective LTV: {SIM_LTV:.0%}"
        ), unsafe_allow_html=True)

    with c2:
        st.markdown("#### 🔐 Collateral Required")
        # Tarjeta Especial Destacada (Dorado)
        st.markdown(f"""
        <div style="
            background-color: #1a1a1a;
            border: 2px solid #F59E0B;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            margin-bottom: 15px;
        ">
            <div style="color: #F59E0B; font-size: 18px; letter-spacing: 2px; font-weight: bold; margin-bottom: 10px;">
                REQUIRED COLLATERAL
            </div>
            <div style="color: #FFFFFF; font-size: 65px; font-weight: 900; line-height: 1;">
                {collateral_btc:.2f} <span style="font-size: 30px; color: #888;">BTC</span>
            </div>
            <div style="color: #fff; font-size: 22px; margin-top: 10px;">
                Market Value: ${collateral_usd_market:,.0f}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Barra de progreso manual (HTML)
        rec_pct = 100 - SIM_HAIRCUT
        st.markdown(f"""
        <div style="color:#aaa; font-size:14px; margin-bottom:5px;">Bank Recognition Rate: {rec_pct}%</div>
        <div style="width:100%; background:#333; height:10px; border-radius:5px;">
            <div style="width:{rec_pct}%; background:#10B981; height:100%; border-radius:5px;"></div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown("#### 📉 Risk Analysis")
        
        liq_color = "#FF4B4B" if buffer_pct < 0.15 else "#10B981"
        buffer_status = "CRITICAL" if buffer_pct < 0.15 else "SAFE ZONE"
        
        st.markdown(render_tv_card(
            "Liquidation Price", 
            f"${liq_price:,.0f}", 
            f"Threshold: {SIM_LIQ_THRESH:.0%}",
            color=liq_color
        ), unsafe_allow_html=True)
        
        st.markdown(render_tv_card(
            "Safety Buffer", 
            f"{buffer_pct:.2%}", 
            f"Status: {buffer_status}",
            color=liq_color
        ), unsafe_allow_html=True)
        
     # --- VISTA 4: VISUAL ALPHA (POWER LAW & SEASONALITY) ---
elif st.session_state.page_index == 3:
    
    full_history = data_fetcher.fetch_full_history()
    
    c1, c2 = st.columns([3, 2]) # 60% Power Law | 40% Seasonality
    
    # COLUMNA 1: POWER LAW (Reemplazando al Rainbow)
    with c1:
        # Header Estilo Bitbo
        st.markdown("""
        <div style="margin-bottom: 5px; color: #888; font-size: 14px; letter-spacing: 1px; font-weight: 600; text-transform: uppercase;">
            🪐 Bitcoin Power Law Corridor
        </div>
        """, unsafe_allow_html=True)
        
        if not full_history.empty:
            st.plotly_chart(charts.create_power_law_chart(full_history), use_container_width=True)
            st.caption("Log-Log Regression. Price oscillates around the Green Fair Value line.")
        else:
            st.warning("Loading History...")

    # COLUMNA 2: SEASONALITY (Se queda igual, se ve muy bien)
    with c2:
        st.markdown("""
        <div style="margin-bottom: 5px; color: #888; font-size: 14px; letter-spacing: 1px; font-weight: 600; text-transform: uppercase;">
            📅 Historical Monthly Returns
        </div>
        """, unsafe_allow_html=True)
        
        if not full_history.empty:
            st.plotly_chart(charts.create_seasonality_heatmap(full_history), use_container_width=True)
        else:
            st.warning("Loading...")

# --- VISTA 4 (Indice 4): MINING & SECURITY ---
elif st.session_state.page_index == 4:
    
    # Header Estilo TV
    st.markdown("""
    <div style="margin-bottom: 10px; color: #888; font-size: 16px; letter-spacing: 2px; font-weight: 700; text-transform: uppercase;">
        ⛏️ Network Security & Miner Status
    </div>
    """, unsafe_allow_html=True)
    
    # Cargar Datos
    full_history = data_fetcher.fetch_full_history() # Asegúrate de tener esta en tu data_fetcher TV
    hash_df = data_fetcher.fetch_hashrate_data()
    
    if not hash_df.empty and not full_history.empty:
        
        # --- LÓGICA RÁPIDA ---
        curr_hash = hash_df['hash_rate'].iloc[-1] / 1_000_000 # EH/s
        ma30 = hash_df['hash_rate'].rolling(30).mean().iloc[-1]
        ma60 = hash_df['hash_rate'].rolling(60).mean().iloc[-1]
        
        # Lógica de Capitulación
        is_capitulation = ma30 < ma60
        status_text = "CAPITULATION" if is_capitulation else "HEALTHY EXPANSION"
        status_color = "#FF0000" if is_capitulation else "#00FF00" # Rojo o Verde Neón
        status_icon = "⚠️" if is_capitulation else "🚀"
        
        # --- TARJETAS GIGANTES HTML (DISEÑO TV) ---
        c1, c2 = st.columns([1, 2])
        
        with c1:
            # Tarjeta 1: Hashrate (Dato Duro)
            st.markdown(f"""
            <div style="background: #111; border: 1px solid #333; border-radius: 12px; padding: 20px; margin-bottom: 15px;">
                <div style="color: #888; font-size: 14px; text-transform: uppercase;">Total Hashrate</div>
                <div style="color: white; font-size: 50px; font-weight: 900; line-height: 1;">{curr_hash:.0f}</div>
                <div style="color: #666; font-size: 20px;">Exahashes/s</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Tarjeta 2: Status (Semáforo)
            st.markdown(f"""
            <div style="background: #111; border: 2px solid {status_color}; border-radius: 12px; padding: 20px;">
                <div style="color: #888; font-size: 14px; text-transform: uppercase;">Miner Cycle</div>
                <div style="color: {status_color}; font-size: 38px; font-weight: 900; line-height: 1.1; margin-top:5px;">
                    {status_icon} {status_text}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with c2:
            # Gráfico a la derecha (Ocupa 66% de pantalla)
            st.plotly_chart(charts.create_miner_metrics_chart_tv(full_history, hash_df), use_container_width=True)
            
    else:
        st.warning("⏳ Syncing Node Data...")
