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
# --- EN UTILS/CHARTS.PY ---

def create_seasonality_heatmap(df):
    if df.empty: return go.Figure()
    
    # 1. Preparación de Datos
    df_seas = df.copy()
    
    # Calculamos cambio mensual
    monthly_data = df_seas.resample('ME').agg({'close': 'last'}) # 'ME' es Month End
    monthly_data['pct_change'] = monthly_data['close'].pct_change()
    
    # Creamos columnas para el pivote
    monthly_data['year'] = monthly_data.index.year
    monthly_data['month_num'] = monthly_data.index.month
    
    # Pivot Table
    heatmap_data = monthly_data.pivot(index='year', columns='month_num', values='pct_change')
    
    # IMPORTANTE: Eliminamos años que no tengan NINGÚN dato (limpieza de filas vacías)
    heatmap_data = heatmap_data.dropna(how='all')
    
    # Nombres de meses fijos
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # 2. Matriz de Texto (Para ocultar los NaNs)
    # Creamos una copia donde los valores nulos sean strings vacíos ""
    text_matrix = heatmap_data.copy()
    # Formateamos a porcentaje sin decimales (ej: 12%) y quitamos los nulos
    text_display = text_matrix.applymap(lambda x: f"{x:.0%}" if pd.notnull(x) else "")

    # 3. CREACIÓN DEL HEATMAP
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data.values,
        x=month_names,
        y=heatmap_data.index,
        colorscale=[
            [0, '#EF4444'],      # Rojo (Bearish)
            [0.5, '#1a1a1a'],    # Gris Oscuro (Neutro/Cero) - Mejor que negro absoluto
            [1, '#00C805']       # Verde Neón (Bullish)
        ],
        zmid=0, # El centro del color es 0%
        text=text_display.values, # Usamos nuestra matriz de texto limpia
        texttemplate="%{text}",   # Mostrar solo el texto limpio
        textfont={"size": 12, "family": "Arial Black", "color": "white"}, # Letra más gruesa y grande
        showscale=False, # <--- ADIÓS A LA BARRA LATERAL
        xgap=3, # Espacio entre celdas
        ygap=3,
        hoverinfo='none' # <--- ADIÓS A LOS TOOLTIPS MOLESTOS
    ))

    fig.update_layout(
        
        height=600, # Un poco más alto para que respire
        margin=dict(l=0, r=0, t=0, b=0), # Márgenes ajustados
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#888'), # Color de los ejes (años/meses) más sutil
        xaxis=dict(
            side="top", 
            tickfont=dict(size=14, color='white'),
            fixedrange=True # Evita zoom accidental
        ), 
        yaxis=dict(
            autorange="reversed", # Años recientes abajo (o arriba si prefieres)
            tickfont=dict(size=14, color='white'),
            dtick=1, # Mostrar todos los años
            fixedrange=True
        ) 
    )
    
    return fig
    
# --- 5. RAINBOW CHART (CORREGIDO) ---
def create_rainbow_chart(df):
    if df.empty: return go.Figure()
    
    import numpy as np
    from scipy import stats
    
    df_rain = df[df['close'] > 0].copy()
    
    # 1. Aseguramos que el índice no tenga zona horaria (para evitar choque con genesis)
    if df_rain.index.tz is not None:
        df_rain.index = df_rain.index.tz_localize(None)

    genesis = pd.Timestamp("2009-01-03")
    
    # 2. CORRECCIÓN: Usamos .days directamente (sin .dt)
    # Al restar el Index - Timestamp, obtenemos un TimedeltaIndex que tiene .days nativo
    df_rain['days'] = (df_rain.index - genesis).days
    
    # Filtramos días negativos o cero (antes del génesis)
    df_rain = df_rain[df_rain['days'] > 0]
    
    # --- MATEMÁTICA LOG-LOG ---
    x = np.log10(df_rain['days'])
    y = np.log10(df_rain['close'])
    
    slope, intercept, _, _, _ = stats.linregress(x, y)
    
    # Bandas del Arcoiris (Offsets logarítmicos calibrados)
    bands = [
        ("Bubble Territory",  1.0,  '#FF0000'), # Rojo
        ("FOMO",              0.75, '#FF7F00'), # Naranja
        ("HODL",              0.5,  '#FFFF00'), # Amarillo
        ("Still Cheap",       0.25, '#00FF00'), # Verde
        ("Fire Sale",         0.0,  '#0000FF'), # Azul
    ]
    
    fig = go.Figure()
    
    # Dibujamos bandas
    for name, offset, color in bands:
        y_band = 10 ** (intercept + slope * x + offset)
        fig.add_trace(go.Scatter(
            x=df_rain.index, y=y_band,
            mode='lines', line=dict(color=color, width=2), name=name
        ))

    # Precio Real
    fig.add_trace(go.Scatter(
        x=df_rain.index, y=df_rain['close'],
        mode='lines', line=dict(color='white', width=3), name='BTC Price'
    ))

    fig.update_layout(
        
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

# --- EN UTILS/CHARTS.PY ---

def create_power_law_chart(df):
    if df.empty: return go.Figure()
    
    from scipy import stats
    import numpy as np
    
    # 1. Preparación de Datos
    # Copiamos y limpiamos zonas horarias
    pl_df = df[df['close'] > 0].copy()
    if pl_df.index.tz is not None: pl_df.index = pl_df.index.tz_localize(None)
    
    genesis_date = pd.Timestamp("2009-01-03")
    pl_df['days_since'] = (pl_df.index - genesis_date).days
    pl_df = pl_df[pl_df['days_since'] > 0]

    # 2. Matemática Power Law (Log-Log Regression)
    x = np.log10(pl_df['days_since'])
    y = np.log10(pl_df['close'])
    
    slope, intercept, _, _, _ = stats.linregress(x, y)
    
    # Calculamos Fair Value y Bandas
    pl_df['fair_value'] = 10 ** (intercept + slope * x)
    pl_df['support'] = 10 ** (intercept - 0.35 + slope * x)    # Banda inferior
    pl_df['resistance'] = 10 ** (intercept + 0.5 + slope * x)  # Banda superior

    # 3. Graficado
    fig = go.Figure()
    
    # Bandas (Rellenos Sutiles)
    fig.add_trace(go.Scatter(
        x=pl_df.index, y=pl_df['resistance'], 
        mode='lines', line=dict(color='rgba(139, 92, 246, 0.4)', width=1), # Morado
        name='Resistance (Top)'
    ))
    
    fig.add_trace(go.Scatter(
        x=pl_df.index, y=pl_df['support'], 
        mode='lines', line=dict(color='rgba(239, 68, 68, 0.4)', width=1), # Rojo
        fill='tonexty', fillcolor='rgba(255, 255, 255, 0.03)', # Relleno muy sutil
        name='Support (Bottom)'
    ))

    # Fair Value (La línea "imán")
    fig.add_trace(go.Scatter(
        x=pl_df.index, y=pl_df['fair_value'], 
        mode='lines', line=dict(color='#10B981', width=2), # Verde
        name='Fair Value'
    ))

    # Precio Real
    fig.add_trace(go.Scatter(
        x=pl_df.index, y=pl_df['close'], 
        mode='lines', line=dict(color='#F59E0B', width=1), 
        name='BTC Price'
    ))

    fig.update_layout(
        title=None, # <--- SIN TÍTULO INTERNO (LIMPIO)
        yaxis_type="log", # Escala Logarítmica obligatoria
        height=550,
        margin=dict(l=0, r=0, t=10, b=0), # Márgenes mínimos
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e0e0e0'),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
        hovermode="x unified",
        legend=dict(orientation="h", y=0, x=0.5, xanchor="center")
    )
    
    return fig
