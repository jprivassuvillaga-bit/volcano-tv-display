import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import plotly.express as px

# ==============================================================================
# --- 1. ESTRUCTURA DE PRECIO (FIBONACCI + VOLUMEN) ---
# ==============================================================================
def create_price_volume_chart(df):
    """
    Gráfico de Estructura de Precio CON VOLUMEN y AUTO-FIBONACCI.
    """
    if df.empty:
        return go.Figure().update_layout(title="Waiting for Market Data...")

    # 1. Definir datos visuales (Últimos 365 días)
    plot_df = df.iloc[-365:].copy()
    
    # --- CÁLCULO AUTO-FIBONACCI ---
    max_price = plot_df['high'].max()
    min_price = plot_df['low'].min()
    diff = max_price - min_price
    
    # (Nivel, Color, Grosor)
    fib_levels = [
        (0.236, 'rgba(255, 255, 255, 0.3)', 1),
        (0.382, 'rgba(255, 255, 255, 0.3)', 1),
        (0.5,   'rgba(255, 255, 255, 0.5)', 1),
        (0.618, 'rgba(245, 158, 11, 0.8)', 2), # Golden Pocket
        (0.786, 'rgba(255, 255, 255, 0.3)', 1),
    ]
    
    # Crear figura con eje secundario para volumen
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # --- DIBUJAR NIVELES FIBONACCI (Al fondo) ---
    fig.add_hline(y=min_price, line_dash="dot", line_color="rgba(255,255,255,0.2)", annotation_text="0.0 (Min)")
    fig.add_hline(y=max_price, line_dash="dot", line_color="rgba(255,255,255,0.2)", annotation_text="1.0 (Max)")
    
    for level, color, width in fib_levels:
        price_level = max_price - (diff * level)
        fig.add_hline(
            y=price_level, 
            line_width=width, 
            line_dash="dash" if width == 1 else "solid", 
            line_color=color,
            annotation_text=f"Fib {level}",
            annotation_position="right",
            annotation_font_size=10,
            annotation_font_color=color
        )

    # --- VELAS ---
    fig.add_trace(go.Candlestick(
        x=plot_df.index,
        open=plot_df['open'], high=plot_df['high'],
        low=plot_df['low'], close=plot_df['close'],
        name="Price"
    ), secondary_y=False)
    
    # --- VOLUMEN (Abajo) ---
    colors = ['rgba(38, 166, 154, 0.3)' if c >= o else 'rgba(239, 83, 80, 0.3)' 
              for c, o in zip(plot_df['close'], plot_df['open'])]
    
    fig.add_trace(go.Bar(
        x=plot_df.index,
        y=plot_df['volume'],
        marker_color=colors,
        name="Volume",
        opacity=0.5,
        showlegend=False
    ), secondary_y=True)

    # --- SMAs ---
    if 'sma_50' in plot_df.columns:
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['sma_50'], line=dict(color='#3B82F6', width=1), name="SMA 50"), secondary_y=False)
    
    if 'sma_200' in plot_df.columns:
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['sma_200'], line=dict(color='#8B5CF6', width=2), name="SMA 200"), secondary_y=False)
    
    # --- DISEÑO ---
    fig.update_layout(
        title="Price Structure & Volume (Auto-Fib)",
        height=550,
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis_rangeslider_visible=False,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e0e0e0'),
        legend=dict(orientation="h", y=1, x=0),
        hovermode='x unified'
    )
    # Escala volumen para que ocupe solo la parte baja
    if not plot_df['volume'].empty:
        max_vol = plot_df['volume'].max()
        fig.update_yaxes(range=[0, max_vol * 4], secondary_y=True, showgrid=False, visible=False)
    
    fig.update_yaxes(gridcolor='rgba(255,255,255,0.05)', secondary_y=False)

    return fig

# ==============================================================================
# --- 2. HEATMAP DE LIQUIDEZ (HD) ---
# ==============================================================================

def create_liquidity_heatmap(ob_df, current_price):
    """
    Genera un Mapa de Densidad de Liquidez en Alta Definición (HD).
    """
    if ob_df.empty or 'price' not in ob_df.columns:
        fig = go.Figure()
        fig.update_layout(title="Waiting for Liquidity Data feed...", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#666'), xaxis=dict(showgrid=False, showticklabels=False), yaxis=dict(showgrid=False, showticklabels=False))
        return fig

    # DETECTOR DE SIMULACIÓN
    is_simulated = False
    if 'is_simulated' in ob_df.columns and ob_df['is_simulated'].any():
        is_simulated = True

    # Zoom ±2%
    range_mask = (ob_df['price'] > current_price * 0.98) & (ob_df['price'] < current_price * 1.02)
    df = ob_df[range_mask].copy()
    if df.empty: df = ob_df.copy()

    # Binning
    bin_size = 10 
    df['price_bin'] = (df['price'] // bin_size) * bin_size
    df_grouped = df.groupby(['price_bin', 'side'])['amount'].sum().reset_index()
    
    bids = df_grouped[df_grouped['side']=='bid']
    asks = df_grouped[df_grouped['side']=='ask']
    
    fig = go.Figure()
    
    # BIDS (Verde Matrix)
    fig.add_trace(go.Bar(y=bids['price_bin'], x=bids['amount'], orientation='h', name='Buy Density', marker=dict(color=bids['amount'], colorscale=[[0, '#004d1a'], [1, '#00ff41']], line=dict(width=0)), hovertemplate='BID<br>Price: $%{y:,.0f}<br>Vol: %{x:.2f} BTC'))
    
    # ASKS (Rojo Lava)
    fig.add_trace(go.Bar(y=asks['price_bin'], x=asks['amount'], orientation='h', name='Sell Density', marker=dict(color=asks['amount'], colorscale=[[0, '#4d0000'], [1, '#ff0000']], line=dict(width=0)), hovertemplate='ASK<br>Price: $%{y:,.0f}<br>Vol: %{x:.2f} BTC'))
    
    fig.add_hline(y=current_price, line_dash="dash", line_color="white", opacity=0.5, annotation_text="SPOT")

    main_title = "⚠️ LIQUIDITY MAP (SIMULATION)" if is_simulated else "Liquidity Density (High Res)"
    title_color = "#FF4B4B" if is_simulated else "#e0e0e0"

    fig.update_layout(
        title=dict(text=main_title, font=dict(color=title_color)),
        xaxis_title="Volume Density (BTC)", yaxis_title="Price Level (USD)",
        height=550, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e0e0e0', size=10), barmode='overlay', bargap=0.05, showlegend=False,
        yaxis=dict(range=[current_price*0.99, current_price*1.01], gridcolor='rgba(255,255,255,0.05)', tickformat=",.0f")
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    return fig

# ==============================================================================
# --- 3. GRÁFICOS ANALÍTICOS Y MACRO ---
# ==============================================================================

def create_volatility_chart(df):
    if df.empty: return go.Figure()
    plot_df = df.iloc[-180:]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['volatility'], name='Realized Vol (30D)', line=dict(color='#10B981', width=2)))
    if 'implied_vol' in plot_df.columns:
        fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['implied_vol'], name='Implied Vol (Proxy)', line=dict(color='#F59E0B', width=2, dash='dot')))
    fig.update_layout(title="Volatility Regime", height=300, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#e0e0e0'), legend=dict(orientation="h", y=1, x=0))
    return fig

def create_zscore_chart(df): # (Antes create_onchain_chart) - Mismo gráfico, nombre más preciso
    if df.empty: return go.Figure()
    plot_df = df.iloc[-730:]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['z_score'], name='Z-Score (200D)', fill='tozeroy', line=dict(color='#8B5CF6')))
    fig.add_hline(y=3.0, line_dash="dash", line_color="#FF4B4B")
    fig.add_hline(y=0.0, line_dash="dash", line_color="#10B981")
    fig.add_hline(y=-3.0, line_dash="dash", line_color="#10B981")
    fig.update_layout(title="Mean Reversion (Z-Score)", height=300, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#e0e0e0'))
    return fig

def create_onchain_chart(df): # Alias para compatibilidad
    return create_zscore_chart(df)

def create_macro_chart(df):
    """
    Gráfico comparativo de rendimientos normalizados (Base 0%).
    """
    import plotly.express as px
    if df.empty: return go.Figure()
    
    fig = px.line(df, x=df.index, y=df.columns)
    
    # Personalización para TV
    fig.update_layout(
        title="Macro Correlations (Normalized Returns)",
        xaxis_title=None, yaxis_title="Performance %", legend_title=None,
        height=350, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e0e0e0'), hovermode="x unified",
        margin=dict(l=0, r=0, t=40, b=0)
    )
    # Colores específicos
    color_map = {'Bitcoin': '#F7931A', 'S&P 500': '#3B82F6', 'Gold': '#F59E0B', 'DXY (Dollar)': '#9CA3AF'}
    for d in fig.data:
        if d.name in color_map:
            d.line.color = color_map[d.name]
            d.line.width = 3 if d.name == 'Bitcoin' else 1.5
            
    return fig

def create_forecast_chart(historical_df, forecast_df):
    """
    Gráfico de Profecía: Historia + Predicción + Cono de Incertidumbre
    """
    fig = go.Figure()

    # 1. Datos Históricos
    fig.add_trace(go.Scatter(
        x=historical_df.index, y=historical_df['close'],
        mode='lines', name='Historical Price',
        line=dict(color='rgba(255,255,255,0.5)', width=1)
    ))

    # Filtramos solo la parte futura
    last_date = historical_df.index.max()
    future_forecast = forecast_df[forecast_df['ds'] > last_date]

    # 2. Cono de Incertidumbre
    fig.add_trace(go.Scatter(
        x=future_forecast['ds'], y=future_forecast['yhat_upper'],
        mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'
    ))
    fig.add_trace(go.Scatter(
        x=future_forecast['ds'], y=future_forecast['yhat_lower'],
        mode='lines', line=dict(width=0),
        fill='tonexty', fillcolor='rgba(59, 130, 246, 0.2)',
        name='Confidence Interval'
    ))

    # 3. La Predicción Central
    fig.add_trace(go.Scatter(
        x=future_forecast['ds'], y=future_forecast['yhat'],
        mode='lines', name='AI Trend Forecast',
        line=dict(color='#3B82F6', width=2, dash='dash')
    ))

    fig.update_layout(
        title="🔮 AI Trend Forecast (Prophet Model)",
        yaxis_title="Price (USD)", height=450,
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e0e0e0'), hovermode="x unified"
    )
    return fig
# --- 4. SEASONALITY HEATMAP (VISUAL IMPONENTE) ---
def create_seasonality_heatmap(df):
    if df.empty: return go.Figure()
    
    # Preparamos los datos
    df_seas = df.copy()
    df_seas['year'] = df_seas.index.year
    df_seas['month'] = df_seas.index.month_name().str[:3] # Jan, Feb...
    df_seas['month_num'] = df_seas.index.month
    
    # Calculamos retorno mensual
    # Agrupamos por Año y Mes, tomamos el último precio y lo comparamos con el primero
    monthly_data = df_seas.resample('M').agg({'close': ['first', 'last']})
    monthly_data.columns = ['open', 'close']
    monthly_data['pct_change'] = (monthly_data['close'] - monthly_data['open']) / monthly_data['open']
    monthly_data['year'] = monthly_data.index.year
    monthly_data['month'] = monthly_data.index.month_name().str[:3]
    monthly_data['month_num'] = monthly_data.index.month

    # Pivot Table para el Heatmap
    heatmap_data = monthly_data.pivot(index='year', columns='month_num', values='pct_change')
    
    # Ordenamos meses
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # CREACIÓN DEL HEATMAP
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data.values,
        x=month_names,
        y=heatmap_data.index,
        colorscale=[
            [0, '#EF4444'],      # Rojo Fuerte (Caída)
            [0.5, '#111111'],    # Negro (Neutro)
            [1, '#00C805']       # Verde Neón (Subida)
        ],
        zmid=0, # Centrar el color negro en 0%
        text=heatmap_data.values,
        texttemplate="%{text:.0%}", # Mostrar porcentaje dentro del cuadro
        textfont={"size": 14, "color": "white"}, # Texto grande para TV
        xgap=2, # Espacio entre celdas (estilo rejilla)
        ygap=2
    ))

    fig.update_layout(
        title="📅 Bitcoin Monthly Seasonality Matrix",
        height=550,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e0e0e0'),
        xaxis=dict(side="top"), # Meses arriba para leer mejor
        yaxis=dict(autorange="reversed") # Años recientes arriba
    )
    
    return fig

# --- 5. RAINBOW CHART (ESTILO NEÓN) ---
def create_rainbow_chart(df):
    if df.empty: return go.Figure()
    
    # Necesitamos historia completa para que se vea bien
    # Usamos la misma lógica de Power Law pero con bandas de colores
    # Formula simple aproximada del Rainbow: Log price regression + Desviaciones
    
    import numpy as np
    from scipy import stats
    
    df_rain = df[df['close'] > 0].copy()
    genesis = pd.Timestamp("2009-01-03")
    df_rain['days'] = (df_rain.index - genesis).dt.days
    df_rain = df_rain[df_rain['days'] > 0]
    
    x = np.log10(df_rain['days'])
    y = np.log10(df_rain['close'])
    
    slope, intercept, _, _, _ = stats.linregress(x, y)
    
    # Bandas del Arcoiris (Offsets logarítmicos)
    bands = [
        ("Bubble Territory",  1.0,  '#FF0000'), # Rojo
        ("FOMO",              0.75, '#FF7F00'), # Naranja
        ("HODL",              0.5,  '#FFFF00'), # Amarillo
        ("Still Cheap",       0.25, '#00FF00'), # Verde
        ("Fire Sale",         0.0,  '#0000FF'), # Azul
    ]
    
    fig = go.Figure()
    
    # Dibujamos bandas (De arriba a abajo)
    for name, offset, color in bands:
        # Calculamos la curva
        y_band = 10 ** (intercept + slope * x + offset)
        
        fig.add_trace(go.Scatter(
            x=df_rain.index, y=y_band,
            mode='lines',
            line=dict(color=color, width=2),
            name=name
        ))

    # Precio Real (Blanco Brillante y grueso para que destaque sobre el arcoiris)
    fig.add_trace(go.Scatter(
        x=df_rain.index, y=df_rain['close'],
        mode='lines',
        line=dict(color='white', width=3),
        name='BTC Price'
    ))

    fig.update_layout(
        title="🌈 Bitcoin Rainbow Valuation Model",
        yaxis_type="log",
        height=550,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e0e0e0'),
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", y=0, x=0.5, xanchor="center")
    )
    
    return fig
