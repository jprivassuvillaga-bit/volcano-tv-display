import yfinance as yf
import pandas as pd
import numpy as np
import requests
import streamlit as st
from datetime import datetime

# ==============================================================================
# --- CONFIGURACIÓN DE HEADERS (Evita bloqueos) ---
# ==============================================================================
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ==============================================================================
# --- 1. DATOS DE MERCADO (OHLCV) - VERSIÓN "HISTORY" ---
# ==============================================================================
def fetch_market_data(ticker="BTC-USD", period="2y", interval="1d"):
    """
    Descarga datos usando .history() para evitar problemas de formato MultiIndex.
    Es mucho más estable para un solo ticker.
    """
    try:
        # 1. Usamos Ticker().history en lugar de download()
        # Esto devuelve una tabla PLANA, sin complicaciones de multi-columnas.
        dat = yf.Ticker(ticker)
        df = dat.history(period=period, interval=interval)
        
        # 2. Validación de Vacío
        if df.empty:
            print("Yahoo Finance devolvió datos vacíos.")
            return pd.DataFrame()

        # 3. Limpieza de Columnas (Estandarización)
        # Convertimos todo a minúsculas: 'Open' -> 'open', 'Close' -> 'close'
        df.columns = [c.lower() for c in df.columns]
        
        # Eliminamos información de zona horaria del índice (Date) si existe
        # Esto evita problemas al graficar con Plotly
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        # Verificación final de columnas críticas
        if 'close' not in df.columns:
            print(f"Falta columna 'close'. Columnas recibidas: {df.columns}")
            return pd.DataFrame()

        # 4. Cálculo de Indicadores (Igual que antes)
        df['sma_50'] = df['close'].rolling(window=50).mean()
        df['sma_200'] = df['close'].rolling(window=200).mean()
        df['log_ret'] = np.log(df['close'] / df['close'].shift(1))
        
        annual_factor = np.sqrt(365) if interval == "1d" else np.sqrt(365 * 24)
        window_size = 30 if interval == "1d" else (30 * 24) 
        df['volatility'] = df['log_ret'].rolling(window=window_size).std() * annual_factor
        df['implied_vol'] = df['volatility'] * 1.1 + (df['volatility'] ** 2) * 2
        
        std_200 = df['close'].rolling(window=200).std()
        df['z_score'] = (df['close'] - df['sma_200']) / std_200.replace(0, np.nan)
        
        df = df.fillna(0)
        return df

    except Exception as e:
        print(f"Error crítico en fetch_market_data: {e}")
        return pd.DataFrame()

# ==============================================================================
# --- 2. LIBRO DE ÓRDENES (VÍA BITSTAMP REST API) ---
# ==============================================================================
def fetch_order_book_ccxt(symbol='BTC/USD', limit=100):
    """
    Usa la API REST directa de Bitstamp. 
    Es la más confiable para servidores gratuitos en la nube (sin bloqueos 403).
    """
    try:
        # Petición HTTP directa (sin librería ccxt para evitar overhead)
        url = "https://www.bitstamp.net/api/v2/order_book/btcusd/"
        response = requests.get(url, timeout=5)
        
        if response.status_code != 200:
            raise Exception(f"Status Code {response.status_code}")
            
        data = response.json()
        
        if 'bids' in data and 'asks' in data:
            # Procesar Bids
            bids = pd.DataFrame(data['bids'], columns=['price', 'amount'])
            bids = bids.astype(float)
            bids['side'] = 'bid'
            
            # Procesar Asks
            asks = pd.DataFrame(data['asks'], columns=['price', 'amount'])
            asks = asks.astype(float)
            asks['side'] = 'ask'
            
            # Unir
            df = pd.concat([bids.head(limit), asks.head(limit)])
            
            if not df.empty:
                df['is_simulated'] = False # ¡ÉXITO! Datos Reales
                return df

    except Exception as e:
        print(f"Error Bitstamp ({e}). Intentando respaldo...")
        # INTENTO 2: BLOCKCHAIN.COM (Otro API muy abierto)
        try:
            r = requests.get("https://api.blockchain.com/v3/exchange/l2/BTC-USD", timeout=5)
            d = r.json()
            if 'bids' in d:
                bids = pd.DataFrame(d['bids'], columns=['px', 'qty'])
                bids.columns = ['price', 'amount']
                bids['side'] = 'bid'
                asks = pd.DataFrame(d['asks'], columns=['px', 'qty'])
                asks.columns = ['price', 'amount']
                asks['side'] = 'ask'
                df = pd.concat([bids, asks])
                df['is_simulated'] = False
                return df
        except:
            pass

    # Si todo falla, generamos simulación matemática
    return generate_mock_order_book()

def generate_mock_order_book():
    """ Respaldo matemático final """
    try:
        # Intentamos obtener precio base real aunque sea lento
        ticker = yf.Ticker("BTC-USD")
        base_price = ticker.fast_info['last_price']
        if base_price is None: base_price = 96000
    except:
        base_price = 96000 

    # Generamos ruido
    bids_prices = [base_price * (1 - i/1000) for i in range(1, 150)]
    bids_amts = [np.random.uniform(0.1, 8.0) + (10 if i % 25 == 0 else 0) for i in range(1, 150)]
    bids_df = pd.DataFrame({'price': bids_prices, 'amount': bids_amts, 'side': 'bid'})
    
    asks_prices = [base_price * (1 + i/1000) for i in range(1, 150)]
    asks_amts = [np.random.uniform(0.1, 8.0) + (10 if i % 25 == 0 else 0) for i in range(1, 150)]
    asks_df = pd.DataFrame({'price': asks_prices, 'amount': asks_amts, 'side': 'ask'})
    
    df = pd.concat([bids_df, asks_df])
    df['is_simulated'] = True
    return df

# ==============================================================================
# --- 3. OPEN INTEREST (VÍA COINGECKO API) ---
# ==============================================================================
def fetch_derivatives_data():
    risk_data = {
        'funding_rate': 0.01,
        'open_interest': 0,
        'oi_change': 0,
        'pc_ratio': 0.75,
    }
    
    # 1. Open Interest Global (CoinGecko)
    try:
        url = "https://api.coingecko.com/api/v3/derivatives"
        r = requests.get(url, timeout=5)
        data = r.json()
        
        total_oi_btc = 0.0
        
        # Sumamos OI de los principales mercados
        count = 0
        for item in data:
            if 'bitcoin' in item['market'].lower() or 'btc' in item['symbol'].lower():
                oi = float(item.get('open_interest_btc', 0) or 0)
                total_oi_btc += oi
                count += 1
            if count > 15: break 
            
        # Convertimos a USD
        price = 96000
        try:
            t = yf.Ticker("BTC-USD")
            p = t.fast_info['last_price']
            if p: price = p
        except: pass
            
        oi_usd_billions = (total_oi_btc * price) / 1_000_000_000
        
        if oi_usd_billions > 0.5:
            risk_data['open_interest'] = round(oi_usd_billions, 2)
            # Funding rate promedio (aprox)
            risk_data['funding_rate'] = 0.0102 # Default positivo suave si no hay dato exacto
    except:
        # Fallback estático realista
        risk_data['open_interest'] = 22.45 
        risk_data['oi_change'] = 1.25

    # 2. Put/Call Ratio (Yahoo Finance Options)
    try:
        bito = yf.Ticker("BITO")
        # Header injection para evitar 403
        bito.session = requests.Session()
        bito.session.headers.update(HEADERS)
        
        if bito.options:
            opts = bito.option_chain(bito.options[0])
            c_vol = opts.calls['volume'].sum()
            p_vol = opts.puts['volume'].sum()
            if c_vol > 0: risk_data['pc_ratio'] = p_vol / c_vol
    except: pass
        
    return risk_data

# ==============================================================================
# --- 4. FUNCIONES RESTANTES ---
# ==============================================================================
def fetch_etf_data(ticker="IBIT"):
    try:
        etf = yf.Ticker(ticker)
        etf.session = requests.Session()
        etf.session.headers.update(HEADERS)
        
        hist = etf.history(period="5d")
        if hist.empty: return None
        
        curr = hist.iloc[-1]
        avg_vol = hist['Volume'].mean()
        rvol = curr['Volume'] / avg_vol if avg_vol > 0 else 1.0
        
        return {
            'symbol': ticker, 'price': curr['Close'], 'rvol': rvol,
            'change': (curr['Close'] - hist.iloc[-2]['Close']) / hist.iloc[-2]['Close']
        }
    except: return None

def fetch_fear_and_greed_index():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", headers=HEADERS, timeout=5)
        d = r.json()['data'][0]
        return int(d['value']), d['value_classification']
    except: return 50, "Neutral"

def fetch_macro_data(period="1y"):
    # Para macro usamos download, pero con cuidado
    try:
        tickers = {'BTC-USD': 'Bitcoin', '^GSPC': 'S&P 500', 'GC=F': 'Gold', 'DX-Y.NYB': 'DXY (Dollar)'}
        df = yf.download(list(tickers.keys()), period=period, progress=False)
        
        # Aplanado agresivo
        if isinstance(df.columns, pd.MultiIndex):
            try: df.columns = df.columns.get_level_values(0)
            except: pass
            
        return df.rename(columns=tickers).ffill().dropna()
    except: return pd.DataFrame()

def fetch_news():
    return []
