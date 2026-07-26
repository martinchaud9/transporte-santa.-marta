import math

import requests

CENTRO_LAT = -27.7834  # Plaza Libertad, Santiago del Estero
CENTRO_LON = -64.2642

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'SantaMartaLogistica-Prototipo/1.0 (proyecto universitario)'


def geocodificar(direccion):
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={
                'q': f'{direccion}, Santiago del Estero, Argentina',
                'format': 'json',
                'limit': 1,
                'countrycodes': 'ar',
            },
            headers={'User-Agent': USER_AGENT},
            timeout=5,
        )
        resultados = resp.json()
    except (requests.RequestException, ValueError):
        return None
    if not resultados:
        return None
    return float(resultados[0]['lat']), float(resultados[0]['lon'])


def calcular_zona(lat, lon):
    dlat = lat - CENTRO_LAT
    dlon = lon - CENTRO_LON
    angulo = math.degrees(math.atan2(dlat, dlon))  # 0°=Este, 90°=Norte, ±180°=Oeste, -90°=Sur
    if -45 <= angulo < 45:
        return 'este'
    if 45 <= angulo < 135:
        return 'norte'
    if angulo >= 135 or angulo < -135:
        return 'oeste'
    return 'sur'


def _distancia_km(lat1, lon1, lat2, lon2):
    R = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def ordenar_ruta(envios):
    con_coords = [e for e in envios if e.lat is not None and e.lon is not None]
    sin_coords = [e for e in envios if e.lat is None or e.lon is None]

    ordenados = []
    restantes = con_coords[:]
    lat_actual, lon_actual = CENTRO_LAT, CENTRO_LON
    while restantes:
        siguiente = min(restantes, key=lambda e: _distancia_km(lat_actual, lon_actual, e.lat, e.lon))
        ordenados.append(siguiente)
        restantes.remove(siguiente)
        lat_actual, lon_actual = siguiente.lat, siguiente.lon
    return ordenados + sin_coords
