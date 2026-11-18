"""Pruebas de rutas y costos horarios, sin descargar OpenStreetMap."""
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from dijkstra import SinRutaError, buscar_ruta, resumir_camino
from grafo import Graph
from paradas import optimizar_orden
from trafico import interpretar_salida, tiempo_arista

ZONA = ZoneInfo("America/Managua")


def red_prueba():
    red = Graph()
    for n in range(4):
        red.insertVertex(n, 12.1 + n*.0002, -86.27)
    # Camino corto en kilómetros, pero lento por ser servicio.
    red.insertAris(0, 1, 500, "service")
    red.insertAris(1, 3, 500, "service")
    # Camino ligeramente más largo, pero rápido en arteria.
    red.insertAris(0, 2, 800, "trunk")
    red.insertAris(2, 3, 800, "trunk")
    return red


def test_rapida_vs_corta():
    red = red_prueba()
    fecha = datetime(2026, 11, 16, 10, tzinfo=ZONA)
    rapida = buscar_ruta(red, 0, 3, fecha, "tiempo")
    corta = buscar_ruta(red, 0, 3, fecha, "distancia")
    assert sum(a.distancia for a in rapida) == 1600
    assert sum(a.distancia for a in corta) == 1000
    assert resumir_camino(rapida, fecha)["segundos"] < resumir_camino(corta, fecha)["segundos"]


def test_no_hay_camino_en_sentido_inverso():
    fecha = datetime(2026, 11, 16, 10, tzinfo=ZONA)
    with pytest.raises(SinRutaError):
        buscar_ruta(red_prueba(), 3, 0, fecha)


def test_hora_pico_afecta_tiempo():
    red = red_prueba()
    arista = list(red.vecinos(0))[0]
    pico = datetime(2026, 11, 16, 7, 30, tzinfo=ZONA)
    noche = datetime(2026, 11, 16, 22, 30, tzinfo=ZONA)
    assert tiempo_arista(arista, pico) > tiempo_arista(arista, noche)


def test_optimiza_orden_y_respeta_destino():
    inf = float("inf")
    matriz = [
        [0, 9, 1, 30],
        [9, 0, 1, 1],
        [1, 1, 0, 9],
        [inf, inf, inf, 0],
    ]
    assert optimizar_orden(matriz, 2) == [0, 2, 1, 3]


def test_validaciones_hora():
    assert interpretar_salida("2026-11-15T17:40").hour == 17
    with pytest.raises(ValueError):
        interpretar_salida("fecha imposible")
