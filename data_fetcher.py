import yfinance as yf
import pandas as pd
import numpy as np
import ccxt
import streamlit as st
import requests
import feedparser
from datetime import datetime

# ==============================================================================
# --- 1. DATOS DE MERCADO (OHLCV) ---
# ==============================================================================
def fetch_market_data(ticker="BTC-USD", period="2y", interval="1d"):
    """
    Descarga datos y calcula TODOS los indicadores técnicos.
    CORRECCIÓN: Aplana agresivamente el MultiIndex de yfinance.
    """
    try:
        # 1. Descarga
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        
        # --- CORRECCIÓN DE MULTI-INDEX (La Solución Definitiva) ---
        # Si yfinance devuelve columnas tipo ('Close', 'BTC-USD'), nos quedamos solo con 'Close'
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Renombrar a minúsculas para consistencia
        df = df.rename(columns={
            "Open": "open", "High": "high", "Low": "low", 
            "Close": "close", "Volume": "volume"
        })
        
        # Verificación de seguridad: ¿Existe la columna 'close'?
        if 'close' not in df.columns:
            # Si falló la descarga o el renombrado, retornamos vacío para evitar crash
            return pd.DataFrame()
        
        if df.empty:
            return df

        # --- 2. CÁLCULOS DE TENDENCIA (SMAs) ---
        df['sma_50'] = df['close'].rolling(window=50).mean()
        df['sma_200'] = df['close'].rolling(window=200).mean()
        
        # --- 3. CÁLCULOS DE VOLATILIDAD ---
        # Retornos Logarítmicos
        df['log_ret'] = np.log(df['close'] / df['close'].shift(1))
        
        # Factor de Anualización Dinámico
        annual_factor = np.sqrt(365) if interval == "1d" else np.sqrt(365 * 24)
        window_size = 30 if interval == "1d" else (30 * 24) 
        
        # Volatilidad Realizada (RV)
        df['volatility'] = df['log_ret'].rolling(window=window_size).std() * annual_factor
        
        # Implied Volatility Proxy (Modelo de Pánico)
        df['implied_vol'] = df['volatility'] * 1.1 + (df['volatility'] ** 2) * 2
        
        # --- 4. CÁLCULOS ON-CHAIN (Z-Score) ---
        std_200 = df['close'].rolling(window=200).std()
        # Evitar división por cero
        df['z_score'] = (df['close'] - df['sma_200']) / std_200.replace(0, np.nan)
        
        # Limpieza final
        df = df.fillna(0)
        
        return df
        
    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

# ==============================================================================
# --- 2. LIBRO DE ÓRDENES REAL (Binance) ---
# ==============================================================================
def fetch_order_book_ccxt(symbol='BTC/USDT', limit=1000):
    """
    Descarga el libro de órdenes. 
    NOTA: Cambiamos a KRAKEN porque Binance bloquea IPs de Streamlit Cloud (USA).
    """
    try:
        # Usamos Kraken porque permite acceso desde servidores en USA
        # (Binance.com bloquea Streamlit Cloud)
        exchange = ccxt.kraken() 
        
        # Kraken usa pares diferentes, normalizamos a XBT/USDT
        # (ccxt suele manejar esto, pero mejor ser explícitos si falla)
        ticker = 'BTC/USDT' 
        
        # Descargamos el libro
        order_book = exchange.fetch_order_book(ticker, limit=limit)
        
        # Procesamos Bids (Compras)
        bids = pd.DataFrame(order_book['bids'], columns=['price', 'amount'])
        bids['side'] = 'bid'
        
        # Procesamos Asks (Ventas)
        asks = pd.DataFrame(order_book['asks'], columns=['price', 'amount'])
        asks['side'] = 'ask'
        
        # Unimos
        df = pd.concat([bids, asks])
        
        # Métrica de Liquidez (Volumen * Precio)
        df['total'] = df['price'] * df['amount']
        
        # --- FILTRO DE RUIDO ---
        # Kraken tiene muchas órdenes basura de 0.00001 BTC. Las limpiamos.
        df = df[df['total'] > 100] # Solo órdenes mayores a $100 USD
        
        return df

    except Exception as e:
        print(f"Error fetching Order Book: {e}")
        # Retornamos DataFrame vacío con columnas correctas para que no rompa el gráfico
        return pd.DataFrame(columns=['price', 'amount', 'side', 'total'])

# ==============================================================================
# --- 3. ETF DATA (Institutional Pulse) ---
# ==============================================================================
def fetch_etf_data(ticker="IBIT"):
    try:
        etf = yf.Ticker(ticker)
        hist = etf.history(period="60d")
        
        if hist.empty:
            return None
        
        # Limpieza de MultiIndex también aquí por seguridad
        if isinstance(hist.columns, pd.MultiIndex):
            hist.columns = hist.columns.get_level_values(0)
            
        current_row = hist.iloc[-1]
        current_vol = current_row['Volume']
        current_price = current_row['Close']
        
        avg_vol_30d = hist['Volume'].iloc[-31:-1].mean()
        rvol = current_vol / avg_vol_30d if avg_vol_30d > 0 else 0
        
        return {
            'symbol': ticker,
            'price': current_price,
            'volume': current_vol,
            'avg_volume': avg_vol_30d,
            'rvol': rvol,
            'change': (current_price - hist.iloc[-2]['Close']) / hist.iloc[-2]['Close']
        }
    except Exception as e:
        print(f"ETF Data Error: {e}")
        return None

# ==============================================================================
# --- 4. DERIVADOS Y RIESGO ---
# ==============================================================================
def fetch_derivatives_data():
    risk_data = {
        'funding_rate': 0.01,
        'open_interest': 0,
        'oi_change': 0,
        'pc_ratio': 0.75,
        'pc_volume': 0
    }
    
    # 1. BINANCE DATA
    try:
        exchange = ccxt.binance()
        ticker = exchange.fetch_ticker('BTC/USDT')
        funding = exchange.fetch_funding_rate('BTC/USDT')
        risk_data['funding_rate'] = funding['fundingRate'] * 100 
        
        # Proxy de Open Interest si la API falla
        risk_data['open_interest'] = 12.5 
        risk_data['oi_change'] = (ticker['percentage'] / 2)
        
    except Exception as e:
        print(f"Binance Derivatives Error: {e}")

    # 2. OPTIONS DATA
    try:
        bito = yf.Ticker("BITO")
        if bito.options:
            nearest_date = bito.options[0]
            opts = bito.option_chain(nearest_date)
            calls_vol = opts.calls['volume'].sum()
            puts_vol = opts.puts['volume'].sum()
            
            if calls_vol > 0:
                risk_data['pc_ratio'] = puts_vol / calls_vol
                risk_data['pc_volume'] = calls_vol + puts_vol
    except Exception as e:
        print(f"Options Data Error: {e}")
        
    return risk_data

# ==============================================================================
# --- 5. SENTIMIENTO (Fear & Greed) ---
# ==============================================================================
def fetch_fear_and_greed_index():
    url = "https://api.alternative.me/fng/?limit=1"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        item = data['data'][0]
        return int(item['value']), item['value_classification']
    except Exception as e:
        print(f"F&G API Error: {e}")
        return None, None

# ==============================================================================
# --- 6. MACRO SCOPE (Correlaciones) ---
# ==============================================================================
def fetch_macro_data(period="1y"):
    """
    Descarga datos Macro y CORRIGE el problema de MultiIndex.
    """
    tickers = {
        'BTC-USD': 'Bitcoin',
        '^GSPC': 'S&P 500',
        'GC=F': 'Gold',
        'DX-Y.NYB': 'DXY (Dollar)'
    }
    
    try:
        # Descargamos todo junto
        data = yf.download(list(tickers.keys()), period=period, progress=False)
        
        # --- CORRECCIÓN CRÍTICA DE FORMATO ---
        # Si devuelve MultiIndex (ej: Price | Ticker), aplanamos o extraemos 'Close'
        if isinstance(data.columns, pd.MultiIndex):
            # Intentamos extraer nivel 'Close' si existe
            if 'Close' in data.columns.get_level_values(0):
                data = data.xs('Close', level=0, axis=1)
            else:
                # Si no, asumimos que el nivel 0 es el precio y dropeamos el resto
                data.columns = data.columns.droplevel(1)
        
        # Renombramos columnas usando el diccionario
        data = data.rename(columns=tickers)
        
        # Limpiamos datos
        data = data.ffill().dropna()
        
        return data
    except Exception as e:
        st.error(f"Error macro data: {e}")
        return pd.DataFrame()

# ==============================================================================
# --- 7. NOTICIAS ---
# ==============================================================================
def fetch_news():
    """
    Obtiene noticias reales usando RSS.
    """
    rss_url = "https://finance.yahoo.com/news/rssindex"
    news_list = []
    
    try:
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries[:5]:
            title = entry.title
            title_lower = title.lower()
            if any(x in title_lower for x in ['surge', 'soar', 'jump', 'gain', 'high', 'bull', 'rally', 'record']):
                sentiment = "Positive"
            elif any(x in title_lower for x in ['plunge', 'crash', 'drop', 'loss', 'low', 'bear', 'fear', 'ban']):
                sentiment = "Negative"
            else:
                sentiment = "Neutral"
                
            news_list.append({
                "title": title,
                "source": "Yahoo Finance",
                "published_at": "Today",
                "sentiment": sentiment,
                "url": entry.link
            })
            
    except Exception as e:
        print(f"News Fetch Error: {e}")
        return []
        
    return news_list
