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
    Incluye protección contra datos vacíos.
    """
    # --- SAFETY CHECK: EVITA PANTALLA BLANCA ---
    if ob_df.empty or 'price' not in ob_df.columns:
        fig = go.Figure()
        fig.update_layout(
            title="Waiting for Liquidity Data feed...",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#666'),
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(showgrid=False, showticklabels=False)
        )
        return fig

    # 1. Configuración de Zoom (Rango más ajustado para ver detalle)
    range_mask = (ob_df['price'] > current_price * 0.98) & (ob_df['price'] < current_price * 1.02)
    df = ob_df[range_mask].copy()
    
    # Si después del filtro no queda nada (ej: precio muy lejos), devolvemos vacío para no crashear
    if df.empty:
        # Intentamos mostrar todo sin filtro si el zoom falla
        df = ob_df.copy()

    # 2. "Binning" de Alta Resolución ($10)
    bin_size = 10 
    df['price_bin'] = (df['price'] // bin_size) * bin_size
    
    df_grouped = df.groupby(['price_bin', 'side'])['amount'].sum().reset_index()
    
    bids = df_grouped[df_grouped['side']=='bid']
    asks = df_grouped[df_grouped['side']=='ask']
    
    fig = go.Figure()
    
    # 3. Dibujar Barras Heatmap
    
    # BIDS (Verde Láser)
    fig.add_trace(go.Bar(
        y=bids['price_bin'], x=bids['amount'], orientation='h', name='Buy Density',
        marker=dict(color=bids['amount'], colorscale=[[0, '#004d1a'], [1, '#00ff41']], line=dict(width=0)),
        hovertemplate='BID<br>$%{y:,.0f}<br>%{x:.2f} BTC'
    ))
    
    # ASKS (Rojo Fuego)
    fig.add_trace(go.Bar(
        y=asks['price_bin'], x=asks['amount'], orientation='h', name='Sell Density',
        marker=dict(color=asks['amount'], colorscale=[[0, '#4d0000'], [1, '#ff0000']], line=dict(width=0)),
        hovertemplate='ASK<br>$%{y:,.0f}<br>%{x:.2f} BTC'
    ))
    
    fig.add_hline(y=current_price, line_dash="dash", line_color="white", opacity=0.5, annotation_text="SPOT")

    # 4. Styling
    fig.update_layout(
        title="Liquidity Density (High Res)",
        xaxis_title="Volume Density (BTC)",
        yaxis_title="Price Level (USD)",
        height=550,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e0e0e0', size=10),
        barmode='overlay', 
        bargap=0.05, 
        showlegend=False,
        # Zoom inteligente
        yaxis=dict(
            range=[current_price*0.99, current_price*1.01],
            gridcolor='rgba(255,255,255,0.05)',
            tickformat=",.0f"
        )
    )
    
    fig.update_xaxes(showgrid=False, zeroline=False)
    
    return fig

# ==============================================================================
# --- 3. OTROS GRÁFICOS (ESTÁNDAR) ---
# ==============================================================================
def create_volatility_chart(df):
    if df.empty: return go.Figure()
    
    plot_df = df.iloc[-180:]
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=plot_df.index, y=plot_df['volatility'],
        name='Realized Vol (30D)', line=dict(color='#10B981', width=2)
    ))
    
    if 'implied_vol' in plot_df.columns:
        fig.add_trace(go.Scatter(
            x=plot_df.index, y=plot_df['implied_vol'],
            name='Implied Vol (Proxy)', line=dict(color='#F59E0B', width=2, dash='dot')
        ))

    fig.update_layout(
        title="Volatility Regime (RV vs IV)",
        height=300, margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e0e0e0'), legend=dict(orientation="h", y=1, x=0)
    )
    return fig

def create_onchain_chart(df):
    if df.empty: return go.Figure()
    plot_df = df.iloc[-730:]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['z_score'], name='MVRV Z-Score', fill='tozeroy', line=dict(color='#8B5CF6')))
    fig.add_hline(y=3.0, line_dash="dash", line_color="#FF4B4B")
    fig.add_hline(y=0.0, line_dash="dash", line_color="#10B981")
    fig.update_layout(title="On-Chain Valuation (Z-Score)", height=300, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#e0e0e0'))
    return fig

def create_correlation_chart(df):
    if df.empty: return go.Figure()
    returns = df.pct_change().dropna()
    # Verifica si existen las columnas antes de correlacionar
    if 'Bitcoin' not in returns.columns: return go.Figure()
    
    rolling_corr = returns.rolling(window=60).corr(returns['Bitcoin']).drop(columns=['Bitcoin'])
    fig = go.Figure()
    
    # Manejo de errores por si faltan columnas macro
    if 'S&P 500' in rolling_corr.columns:
        fig.add_trace(go.Scatter(x=rolling_corr.index, y=rolling_corr['S&P 500'], name='vs S&P 500', line=dict(color='#3B82F6')))
    if 'Gold' in rolling_corr.columns:
        fig.add_trace(go.Scatter(x=rolling_corr.index, y=rolling_corr['Gold'], name='vs Gold', line=dict(color='#F59E0B')))
    if 'DXY (Dollar)' in rolling_corr.columns:
        fig.add_trace(go.Scatter(x=rolling_corr.index, y=rolling_corr['DXY (Dollar)'], name='vs DXY', line=dict(color='#9CA3AF', dash='dot')))

    fig.add_hline(y=0, line_color="white", line_dash="dash")
    fig.update_layout(title="Macro Correlations (60D)", height=350, margin=dict(l=0, r=0, t=40, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#e0e0e0'), legend=dict(orientation="h", y=1, x=0), yaxis=dict(range=[-1, 1]))
    return fig

def create_depth_chart(ob_df, current_price):
    if ob_df.empty: return go.Figure()
    mask = (ob_df['price'] > current_price * 0.85) & (ob_df['price'] < current_price * 1.15)
    plot_df = ob_df[mask]
    bids, asks = plot_df[plot_df['side'] == 'bid'], plot_df[plot_df['side'] == 'ask']
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=bids['price'], y=bids['total'], fill='tozeroy', name='Bids', line=dict(color='#10B981')))
    fig.add_trace(go.Scatter(x=asks['price'], y=asks['total'], fill='tozeroy', name='Asks', line=dict(color='#FF4B4B')))
    fig.add_vline(x=current_price, line_dash="dash", line_color="white")
    fig.update_layout(title="Market Depth", height=300, margin=dict(t=30, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#e0e0e0'), showlegend=False)
    return fig
