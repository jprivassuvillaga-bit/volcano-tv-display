import numpy as np
import pandas as pd

def calculate_volatility(prices, window=30):
    """Calcula Volatilidad Realizada (RV) anualizada."""
    log_returns = np.log(prices / prices.shift(1))
    vol = log_returns.rolling(window=window).std() * np.sqrt(365)
    return vol

def simulate_implied_volatility(realized_vol):
    """
    Simula IV basándose en RV con un Factor de Pánico Adaptativo.
    - Mercado Normal: Spread moderado.
    - Mercado Crisis (Vol > 60%): Spread exponencial (Liquidity Crunch).
    """
    # Calculamos el promedio de volatilidad reciente (suavizado)
    vol_avg = realized_vol.rolling(window=10).mean()
    
    # --- LÓGICA DE PÁNICO ADAPTATIVO ---
    # Si la volatilidad promedio supera el 60% (0.6), el factor de miedo sube de 0.15 a 0.40
    # Usamos np.where para aplicarlo a toda la serie de datos eficientemente
    panic_multiplier = np.where(vol_avg > 0.60, 0.40, 0.15)
    
    # Fórmula: (Volatilidad * Multiplicador Dinámico) + Piso Mínimo (5%)
    spread = (vol_avg * panic_multiplier) + 0.05
    
    iv = realized_vol + spread
    return iv

def calculate_mvrv_proxy(df, window=120):
    """Calcula Proxy del MVRV Z-Score."""
    realized_price_proxy = df['close'].rolling(window=window).mean()
    std_dev = df['close'].rolling(window=window).std()
    z_score = (df['close'] - realized_price_proxy) / std_dev
    return z_score, realized_price_proxy

# --- NUEVAS FUNCIONES PARA EL SIMULADOR VaR ---

def calculate_var_metrics(spot_price, volatility, days, confidence_level, loan_amount):
    """
    Calcula el Value at Risk (VaR) paramétrico.
    """
    # 1. Mapear nivel de confianza a Z-Score estándar
    z_scores = {
        "95.0%": 1.645,
        "97.5%": 1.960,
        "99.0%": 2.326
    }
    z_score = z_scores.get(confidence_level, 1.960)

    # 2. Ajustar volatilidad al horizonte de tiempo (Raíz cuadrada del tiempo)
    time_factor = np.sqrt(days / 365.0)
    
    # 3. Calcular caída de precio probable
    # Fórmula: Precio * Z * Vol * sqrt(t)
    price_drop_pct = z_score * volatility * time_factor
    price_at_var = spot_price * (1 - price_drop_pct)
    
    # 4. Calcular pérdida monetaria estimada (VaR en USD)
    # Asumimos que la pérdida es sobre el valor del colateral implícito
    # Pero para simplificar, mostramos cuánto valor perdería el BTC
    var_loss_pct = price_drop_pct
    
    return price_at_var, var_loss_pct