import yfinance as yf
import pandas as pd
import numpy as np
import requests
import streamlit as st
from datetime import datetime

# ==============================================================================
# --- CONFIGURACIÓN ---
# ==============================================================================
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ==============================================================================
# --- 1. DATOS DE MERCADO (OHLCV) ---
# ==============================================================================
def fetch_market_data(ticker="BTC-USD", period="2y", interval="1d"):
    """
    Descarga individual segura para evitar MultiIndex.
    """
    try:
        dat = yf.Ticker(ticker)
        df = dat.history(period=period, interval=interval)
        
        if df.empty: return pd.DataFrame()

        # Limpieza de columnas (Todo a minúsculas)
        df.columns = [c.lower() for c in df.columns]
        if df.index.tz is not None: df.index = df.index.tz_localize(None)

        if 'close' not in df.columns: return pd.DataFrame()

        # Indicadores
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
        print(f"Error Market Data: {e}")
        return pd.DataFrame()

# ==============================================================================
# --- 2. LIBRO DE ÓRDENES (Bitstamp) ---
# ==============================================================================
def fetch_order_book_ccxt(symbol='BTC/USD', limit=100):
    try:
        url = "https://www.bitstamp.net/api/v2/order_book/btcusd/"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if 'bids' in data:
            bids = pd.DataFrame(data['bids'], columns=['price', 'amount']).astype(float)
            bids['side'] = 'bid'
            asks = pd.DataFrame(data['asks'], columns=['price', 'amount']).astype(float)
            asks['side'] = 'ask'
            df = pd.concat([bids.head(limit), asks.head(limit)])
            df['is_simulated'] = False
            return df
    except:
        pass
    return generate_mock_order_book()

def generate_mock_order_book():
    try:
        ticker = yf.Ticker("BTC-USD")
        base_price = ticker.fast_info['last_price'] or 96000
    except: base_price = 96000 
    
    bids = pd.DataFrame({'price': [base_price*(1-i/1000) for i in range(1,150)], 'amount': np.random.uniform(0.1, 5, 149), 'side': 'bid'})
    asks = pd.DataFrame({'price': [base_price*(1+i/1000) for i in range(1,150)], 'amount': np.random.uniform(0.1, 5, 149), 'side': 'ask'})
    df = pd.concat([bids, asks])
    df['is_simulated'] = True
    return df

# ==============================================================================
# --- 3. MACRO DATA (CORREGIDO: DESCAGAR INDIVIDUAL) ---
# ==============================================================================
def fetch_macro_data(period="1y"):
    """
    Descarga datos normalizados de BTC vs Macro (SPY, Gold, DXY).
    """
    tickers = {
        'BTC-USD': 'Bitcoin',
        'SPY': 'S&P 500',
        'GC=F': 'Gold',
        'DX-Y.NYB': 'DXY (Dollar)'
    }
    
    df_combined = pd.DataFrame()
    
    for symbol, name in tickers.items():
        try:
            # Descargamos solo cierre
            data = yf.Ticker(symbol).history(period=period)['Close']
            if not data.empty:
                # Normalizamos a porcentaje (Base 0%)
                # (Precio / Precio_Inicial) - 1
                normalized = (data / data.iloc[0]) - 1
                df_combined[name] = normalized
        except:
            continue
            
    return df_combined
    try:
        for ticker, name in tickers.items():
            # Descargamos uno por uno. Esto es 100% seguro.
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period=period)[['Close']] # Solo queremos el cierre
                hist.columns = [name] # Renombramos inmediatamente
                
                # Limpiar zona horaria para poder unir
                if hist.index.tz is not None:
                    hist.index = hist.index.tz_localize(None)
                
                data_frames.append(hist)
            except Exception as e:
                print(f"Error descargando {name}: {e}")
                continue
        
        if not data_frames:
            return pd.DataFrame()
            
        # Unimos todo en una sola tabla
        macro_df = pd.concat(data_frames, axis=1)
        macro_df = macro_df.ffill().dropna()
        
        return macro_df

    except Exception as e:
        print(f"Error Macro Data: {e}")
        return pd.DataFrame()

# ==============================================================================
# --- 4. DERIVADOS Y OTROS ---
# ==============================================================================
def fetch_derivatives_data():
    risk_data = {'funding_rate': 0.01, 'open_interest': 22.5, 'oi_change': 1.2, 'pc_ratio': 0.75}
    try:
        # Intento CoinGecko
        r = requests.get("https://api.coingecko.com/api/v3/derivatives", timeout=5)
        data = r.json()
        total_oi_btc = sum([float(x.get('open_interest_btc',0) or 0) for x in data if 'btc' in x['symbol'].lower()][:15])
        
        t = yf.Ticker("BTC-USD")
        price = t.fast_info['last_price'] or 96000
        oi_usd = (total_oi_btc * price) / 1e9
        
        if oi_usd > 1:
            risk_data['open_interest'] = round(oi_usd, 2)
            risk_data['funding_rate'] = 0.0102
    except: pass
    return risk_data

def fetch_etf_data(ticker="IBIT"):
    try:
        etf = yf.Ticker(ticker)
        etf.session = requests.Session(); etf.session.headers.update(HEADERS)
        h = etf.history(period="5d")
        if h.empty: return None
        curr = h.iloc[-1]
        return {'symbol': ticker, 'price': curr['Close'], 'rvol': curr['Volume']/h['Volume'].mean(), 'change': (curr['Close']-h.iloc[-2]['Close'])/h.iloc[-2]['Close']}
    except: return None

def fetch_fear_and_greed_index():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", headers=HEADERS, timeout=5)
        d = r.json()['data'][0]
        return int(d['value']), d['value_classification']
    except: return 50, "Neutral"

def fetch_news(): return []
