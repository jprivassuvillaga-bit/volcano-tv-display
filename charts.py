import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import plotly.express as px

def create_price_volume_chart(df):
    """
    Gráfico de Estructura de Precio CON VOLUMEN y AUTO-FIBONACCI.
    Detecta High/Low del último año y dibuja los retrocesos automáticamente.
    """
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
    # Líneas Base (0 y 1)
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
        title="Price Structure & Volume",
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
    max_vol = plot_df['volume'].max()
    fig.update_yaxes(range=[0, max_vol * 4], secondary_y=True, showgrid=False, visible=False)
    fig.update_yaxes(gridcolor='rgba(255,255,255,0.05)', secondary_y=False)

    return fig
    
    # 3. DISEÑO CON BOTONES DE RANGO (SELECTOR DE TIEMPO)
    fig.update_layout(
        title="Price Structure & Trends",
        height=500, # Un poco más alto para ver mejor
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(count=6, label="6m", step="month", stepmode="backward"),
                    dict(count=1, label="YTD", step="year", stepmode="todate"),
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=5, label="5y", step="year", stepmode="backward"),
                    dict(step="all", label="MAX")
                ]),
                bgcolor="#262626", # Color de fondo de los botones
                activecolor="#00C805", # Verde Robinhood cuando está activo
                font=dict(color="white")
            ),
            rangeslider=dict(visible=False), # Ocultamos el slider inferior feo, usamos los botones
            type="date"
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e0e0e0'),
        legend=dict(orientation="h", y=1, x=0)
    )
    return fig

def create_volatility_chart(df):
    # Mostramos los últimos 180 días para ver el régimen reciente
    plot_df = df.iloc[-180:]
    
    fig = go.Figure()
    
    # CORRECCIÓN AQUÍ: Usamos plot_df.index en lugar de plot_df['date']
    fig.add_trace(go.Scatter(
        x=plot_df.index, 
        y=plot_df['volatility'],
        name='Realized Vol (30D)',
        line=dict(color='#10B981', width=2)
    ))
    
    if 'implied_vol' in plot_df.columns:
        fig.add_trace(go.Scatter(
            x=plot_df.index, 
            y=plot_df['implied_vol'],
            name='Implied Vol (Proxy)',
            line=dict(color='#F59E0B', width=2, dash='dot')
        ))

    fig.update_layout(
        title="Volatility Regime (RV vs IV)",
        height=300,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e0e0e0'),
        legend=dict(orientation="h", y=1, x=0)
    )
    return fig

def create_onchain_chart(df):
    # Mostramos 2 años para ver ciclos
    plot_df = df.iloc[-730:]
    
    fig = go.Figure()
    
    # CORRECCIÓN AQUÍ: Usamos plot_df.index
    fig.add_trace(go.Scatter(
        x=plot_df.index, 
        y=plot_df['z_score'],
        name='MVRV Z-Score',
        fill='tozeroy',
        line=dict(color='#8B5CF6')
    ))
    
    # Bandas de Riesgo
    fig.add_hline(y=3.0, line_dash="dash", line_color="#FF4B4B", annotation_text="Overvalued (Top)")
    fig.add_hline(y=0.0, line_dash="dash", line_color="#10B981", annotation_text="Undervalued (Bottom)")

    fig.update_layout(
        title="On-Chain Valuation (Z-Score)",
        height=300,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e0e0e0')
    )
    return fig
    
def create_depth_chart(ob_df, current_price):
    # ... (Tu código de depth chart existente va aquí, no necesita cambios de índice)
    # Si no lo tienes a mano, avísame y te lo paso también.
    import plotly.graph_objects as go # Re-import por seguridad
    
    # Filtrar datos cercanos al precio para zoom (±15%)
    mask = (ob_df['price'] > current_price * 0.85) & (ob_df['price'] < current_price * 1.15)
    plot_df = ob_df[mask]
    
    bids = plot_df[plot_df['side'] == 'bid']
    asks = plot_df[plot_df['side'] == 'ask']
    
    fig = go.Figure()
    
    # Bids (Verde)
    fig.add_trace(go.Scatter(
        x=bids['price'], y=bids['total'],
        fill='tozeroy', name='Bids (Buy)',
        line=dict(color='#10B981')
    ))
    
    # Asks (Rojo)
    fig.add_trace(go.Scatter(
        x=asks['price'], y=asks['total'],
        fill='tozeroy', name='Asks (Sell)',
        line=dict(color='#FF4B4B')
    ))
    
    # Línea de Precio Actual
    fig.add_vline(x=current_price, line_dash="dash", line_color="white", annotation_text="Spot")
    
    fig.update_layout(
        title="Market Depth (Order Book)",
        height=300,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e0e0e0'),
        showlegend=False
    )
    return fig
def create_correlation_chart(df):
    """
    Genera un gráfico de Correlación Móvil (Rolling 60-day Correlation).
    Muestra cómo se mueve BTC respecto a otros activos.
    """
    # 1. Calcular Retornos Diarios (Cambio %)
    returns = df.pct_change().dropna()
    
    # 2. Calcular Correlación Móvil de BTC contra los otros
    # Usamos una ventana de 60 días (aprox un trimestre de trading)
    rolling_corr = returns.rolling(window=60).corr(returns['Bitcoin'])
    
    # Eliminamos la columna de Bitcoin (porque su correlación consigo mismo siempre es 1)
    rolling_corr = rolling_corr.drop(columns=['Bitcoin'])
    
    # 3. Graficar
    fig = go.Figure()
    
    # S&P 500 (Azul - Risk On)
    fig.add_trace(go.Scatter(
        x=rolling_corr.index, y=rolling_corr['S&P 500'],
        name='vs S&P 500 (Stocks)',
        line=dict(color='#3B82F6', width=2)
    ))
    
    # Gold (Amarillo - Safe Haven)
    fig.add_trace(go.Scatter(
        x=rolling_corr.index, y=rolling_corr['Gold'],
        name='vs Gold',
        line=dict(color='#F59E0B', width=2)
    ))
    
    # DXY (Verde/Gris - Cash)
    fig.add_trace(go.Scatter(
        x=rolling_corr.index, y=rolling_corr['DXY (Dollar)'],
        name='vs Dollar (DXY)',
        line=dict(color='#9CA3AF', width=2, dash='dot')
    ))

    # Línea Cero (Neutral)
    fig.add_hline(y=0, line_color="white", line_width=1, line_dash="dash")

    fig.update_layout(
        title="Macro Correlations (60-Day Rolling)",
        yaxis_title="Correlation Coefficient (-1 to +1)",
        height=350,
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e0e0e0'),
        legend=dict(orientation="h", y=1, x=0),
        yaxis=dict(range=[-1, 1]) # Fijamos el rango entre -1 y +1
    )
    
    return fig

def create_liquidity_heatmap(ob_df, current_price):
    """
    Genera un Mapa de Densidad de Liquidez en Alta Definición (HD).
    Usa bins más pequeños y escala de colores para simular 'Heatmap'.
    """
    import pandas as pd
    import plotly.express as px # Necesitaremos escalas de color express

    # 1. Configuración de Zoom (Rango más ajustado para ver detalle)
    # Enfocamos ±2% para ver la acción cercana en HD
    range_mask = (ob_df['price'] > current_price * 0.98) & (ob_df['price'] < current_price * 1.02)
    df = ob_df[range_mask].copy()
    
    # 2. "Binning" de Alta Resolución
    # Reducimos el tamaño del bloque de $50 a $10 para mayor detalle
    bin_size = 10 
    df['price_bin'] = (df['price'] // bin_size) * bin_size
    
    # Agrupamos
    df_grouped = df.groupby(['price_bin', 'side'])['amount'].sum().reset_index()
    
    # Separamos Bids y Asks
    bids = df_grouped[df_grouped['side']=='bid']
    asks = df_grouped[df_grouped['side']=='ask']
    
    fig = go.Figure()
    
    # 3. Dibujar Barras con Gradiente de Color (Efecto Heatmap)
    
    # BIDS (Compradores - Escala de Verdes)
    # Cuanto más volumen, más brillante.
    fig.add_trace(go.Bar(
        y=bids['price_bin'], 
        x=bids['amount'],
        orientation='h',
        name='Buy Density',
        marker=dict(
            color=bids['amount'], # El color depende del volumen
            colorscale=[[0, '#004d1a'], [1, '#00ff41']], # De verde oscuro a verde láser
            line=dict(width=0)
        ),
        hovertemplate='Price: $%{y:,.0f}<br>Vol: %{x:.2f} BTC'
    ))
    
    # ASKS (Vendedores - Escala de Rojos)
    fig.add_trace(go.Bar(
        y=asks['price_bin'], 
        x=asks['amount'],
        orientation='h',
        name='Sell Density',
        marker=dict(
            color=asks['amount'], 
            colorscale=[[0, '#4d0000'], [1, '#ff0000']], # De rojo sangre a rojo brillante
            line=dict(width=0)
        ),
        hovertemplate='Price: $%{y:,.0f}<br>Vol: %{x:.2f} BTC'
    ))
    
    # 4. Línea de Precio Actual
    fig.add_hline(y=current_price, line_dash="dash", line_color="white", opacity=0.5)

    # 5. Styling "Cyberpunk HD"
    fig.update_layout(
        title="Liquidity Density (High Res)",
        xaxis_title="Volume Density (BTC)",
        yaxis_title="Price Level (USD)",
        height=550,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e0e0e0', size=10),
        barmode='overlay', 
        bargap=0.05, # Pequeño espacio para distinguir líneas
        showlegend=False,
        # Zoom inicial centrado en el precio
        yaxis=dict(
            range=[current_price*0.99, current_price*1.01],
            gridcolor='rgba(255,255,255,0.05)'
        )
    )
    
    fig.update_xaxes(showgrid=False, zeroline=False)
    
    return fig