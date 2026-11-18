"""Configuración central de RouteFlow (Managua, Nicaragua)."""
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATOS = BASE / "datos"
ARCHIVO_RED = DATOS / "managua_urbana.graphml"

# OSMnx 2.x utiliza (OESTE, SUR, ESTE, NORTE).
# Núcleo urbano inicial: cobertura parcial, NO todo el municipio.
BBOX = (-86.345, 12.065, -86.175, 12.178)
CENTRO = (12.124, -86.260)
MAX_PARADAS = 5
MAX_DISTANCIA_ACCESO_METROS = 1300
PUERTO = 5000
