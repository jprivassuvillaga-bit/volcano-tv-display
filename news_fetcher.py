import feedparser
import time
from datetime import datetime
import random
from youtubesearchpython import VideosSearch

# --- CONFIGURACIÓN DE FUENTES ---
RSS_FEEDS = [
    {
        "url": "https://cointelegraph.com/rss",
        "category": "Crypto",
        "source_name": "CoinTelegraph"
    },
    {
        "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html",
        "category": "Finance",
        "source_name": "CNBC Finance"
    },
    {
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "category": "Geopolitics",
        "source_name": "BBC World"
    }
]

def get_smart_tags(title, category_default):
    """
    Analiza el título para asignar tags específicos, 
    o usa la categoría por defecto del feed.
    """
    t = title.lower()
    tags = []
    
    # Tags Prioritarios (Keywords)
    if any(x in t for x in ['bitcoin', 'btc', 'satoshi', 'etf', 'halving']):
        tags.append("Bitcoin")
    if any(x in t for x in ['gold', 'silver', 'commodity', 'oil']):
        tags.append("Commodities")
    if any(x in t for x in ['fed', 'powell', 'rate', 'inflation', 'cpi', 'recession']):
        tags.append("Macro")
    if any(x in t for x in ['war', 'missile', 'army', 'treaty', 'china', 'russia']):
        tags.append("Conflict")
    if any(x in t for x in ['sec', 'gensler', 'lawsuit', 'ban', 'regulation', 'tax']):
        tags.append("Regulation")
        
    # Si no encontró keywords específicas, usa la categoría del feed (ej: Crypto)
    if not tags:
        tags.append(category_default)
        
    return tags

def fetch_sentinel_news(limit=15):
    """
    Descarga noticias de múltiples fuentes RSS, las mezcla y las ordena por fecha.
    """
    news_feed = []
    
    # 1. ITERAR SOBRE CADA FUENTE (Crypto, Finance, Geo)
    for source in RSS_FEEDS:
        try:
            # Parsear el RSS
            feed = feedparser.parse(source["url"])
            
            # Extraer las 5 mejores de cada fuente para tener variedad
            for entry in feed.entries[:5]: 
                
                # Gestión de Tiempos (A veces RSS no trae published_parsed)
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    ts = time.mktime(entry.published_parsed)
                else:
                    ts = time.time() # Fallback a 'ahora'
                
                # Limpieza de Título
                title = entry.title
                if len(title) < 15: continue # Saltar títulos rotos
                
                news_feed.append({
                    'source': source["source_name"],
                    'title': title,
                    'link': entry.link,
                    'tags': get_smart_tags(title, source["category"]),
                    'timestamp': ts,
                    'date_str': datetime.fromtimestamp(ts).strftime('%H:%M')
                })
                
        except Exception as e:
            print(f"Error fetching {source['source_name']}: {e}")
            continue

    # 2. MEZCLAR Y ORDENAR
    # Ordenamos por timestamp (del más reciente al más antiguo)
    news_feed.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # 3. FALLBACK (Si internet falla y la lista está vacía)
    if not news_feed:
        return generate_mock_news()

    return news_feed[:limit]

def generate_mock_news():
    """Datos simulados por si fallan todos los RSS."""
    return [
        {
            'source': 'System',
            'title': 'Live feeds unreachable - Displaying cached data',
            'link': '#',
            'tags': ['Alert'],
            'timestamp': time.time(),
            'date_str': 'Now'
        },
        {
            'source': 'CoinDesk', 
            'title': 'Bitcoin reclaims $96k as institutional outflows stabilize', 
            'link': '#',
            'tags': ['Bitcoin', 'Market'],
            'timestamp': time.time()-100,
            'date_str': '10:00'
        },
        {
            'source': 'CNBC', 
            'title': 'Fed signals "higher for longer" rates amid sticky inflation data', 
            'link': '#',
            'tags': ['Macro', 'Finance'],
            'timestamp': time.time()-200,
            'date_str': '09:45'
        },
        {
            'source': 'Reuters', 
            'title': 'Gold hits new highs as central banks increase reserves', 
            'link': '#',
            'tags': ['Commodities'],
            'timestamp': time.time()-300,
            'date_str': '09:30'
        }
    ]
    
    def check_for_breaking_video():
    """
    Busca transmisiones en vivo o videos urgentes de fuentes confiables.
    Retorna un diccionario con la info del video si encuentra algo, o None.
    """
    try:
        # 1. LISTA VIP (Solo interrumpimos por estos canales)
        trusted_channels = [
            "CNBC Television", "Bloomberg Television", "Fox Business", 
            "CoinDesk", "Yahoo Finance", "Sky News"
        ]
        
        # 2. PALABRAS CLAVE DE ALTO IMPACTO (Protagonistas y Eventos)
        # Si el título no tiene uno de estos, lo ignoramos.
        vip_keywords = [
            "Kevin Warsh", "Fed Chair", "FOMC", "Rate Hike", "Rate Cut", # FED
            "Gary Gensler", "SEC Approval", "ETF Approval", # Regulación
            "El Salvador Bitcoin", # Relevancia Local
            "Michael Saylor", "BlackRock", "Larry Fink", # Institucional
            "Bitcoin Crash", "Bitcoin ATH", "All Time High", "Binance" # Mercado
        ]

        # 3. BUSCAMOS "LIVE" O "BREAKING"
        # Buscamos específicamente noticias de Bitcoin/Finanzas
        search = VideosSearch('Bitcoin Breaking News Finance', limit=10)
        results = search.result()['result']
        
        for video in results:
            title = video['title']
            channel = video['channel']['name']
            publish_time = video['publishedTime'] # Ej: "LIVE", "10 minutes ago"
            link = video['link']
            
            # --- FILTRO 1: CANAL CONFIABLE ---
            if channel not in trusted_channels:
                continue

            # --- FILTRO 2: PALABRA CLAVE VIP ---
            # Verificamos si alguna palabra VIP está en el título
            is_vip = any(vip.lower() in title.lower() for vip in vip_keywords)
            if not is_vip:
                continue

            # --- FILTRO 3: URGENCIA (TIEMPO) ---
            # Solo aceptamos videos EN VIVO ("LIVE") o publicados hace MENOS DE 1 HORA
            is_live = "live" in publish_time.lower()
            is_fresh = "minute" in publish_time.lower() # "minutes ago"
            
            if is_live or is_fresh:
                return {
                    "is_breaking": True,
                    "title": title,
                    "channel": channel,
                    "url": link,
                    "id": video['id']
                }
                
        # Si no encontramos nada relevante
        return {"is_breaking": False}

    except Exception as e:
        print(f"Error checking breaking news: {e}")
        return {"is_breaking": False}
