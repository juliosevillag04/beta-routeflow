"""Búsqueda manual de direcciones: Nominatim OpenStreetMap.

Política: máximo 1 consulta/segundo por aplicación, caché en memoria,
identificador User-Agent propio y SIN autocompletado al teclear.
Solo para uso académico local; para producción usar proveedor contratado.
"""
from collections import OrderedDict
from threading import Lock
from time import monotonic, sleep
import os
import requests
from config import BBOX

CERROJO = Lock()
ULTIMA_CONSULTA = 0.0
CACHE = OrderedDict()


def buscar_lugares(texto):
    global ULTIMA_CONSULTA
    q = (texto or "").strip()
    if len(q) < 3 or len(q) > 100:
        raise ValueError("Escribe al menos 3 caracteres para buscar un lugar.")
    clave = q.casefold()
    with CERROJO:
        if clave in CACHE:
            return CACHE[clave]
        espera = max(0, 1.1 - (monotonic() - ULTIMA_CONSULTA))
        if espera:
            sleep(espera)
        ULTIMA_CONSULTA = monotonic()
        contacto = os.getenv("ROUTEFLOW_CONTACTO", "prototipo-local")
        headers = {"User-Agent": f"RouteFlowAcademico/1.0 ({contacto}; consulta manual; OpenStreetMap)",
                   "Accept-Language": "es"}
        parametros = {
            "q": q, "format": "jsonv2", "limit": 6,
            "viewbox": f"{BBOX[0]},{BBOX[3]},{BBOX[2]},{BBOX[1]}",
            "bounded": 1, "addressdetails": 0,
        }
        try:
            respuesta = requests.get("https://nominatim.openstreetmap.org/search",
                                    params=parametros, headers=headers, timeout=15)
            respuesta.raise_for_status()
            datos = respuesta.json()
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError("La búsqueda de lugares no está disponible. También puedes seleccionar el punto directamente en el mapa.") from exc
        salida = [{"nombre": elemento.get("display_name", "Lugar"),
                   "lat": float(elemento["lat"]), "lon": float(elemento["lon"])}
                  for elemento in datos]
        CACHE[clave] = salida
        if len(CACHE) > 120:
            CACHE.popitem(last=False)
        return salida
