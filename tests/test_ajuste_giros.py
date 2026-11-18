"""Pruebas de la corrección: acceso por tramos y giros en los cruces."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from ajuste import IndiceTramos, GrafoConsulta, preparar_punto
from dijkstra import buscar_ruta, buscar_rutas_desde, resumir_camino, SinRutaError
from grafo import Graph
from trafico import penalizacion_giro

FECHA = datetime(2026, 11, 16, 7, 30, tzinfo=ZoneInfo("America/Managua"))


def recta_un_sentido():
    grafo = Graph()
    grafo.insertVertex(1, 12.1, -86.271)
    grafo.insertVertex(2, 12.1, -86.269)
    grafo.insertAris(1, 2, 220, "residential")
    return grafo


def con_puntos(grafo, coordenadas):
    buscador = IndiceTramos(grafo)
    puntos = []
    for i, (lat, lon) in enumerate(coordenadas):
        punto = {"lat": lat, "lon": lon, "nombre": str(i)}
        preparar_punto(punto, buscador.buscar(lat, lon), i)
        puntos.append(punto)
    return puntos


def test_ajusta_a_tramo_y_no_obliga_llegar_hasta_interseccion():
    grafo = recta_un_sentido()
    puntos = con_puntos(grafo, [(12.10001, -86.2706), (12.10001, -86.2695)])
    consulta = GrafoConsulta(grafo, puntos, 0, [1])
    aristas = buscar_ruta(consulta, puntos[0]["vertice"].id,
                         puntos[1]["vertice"].id, FECHA)
    assert len(aristas) == 1  # Misma calle: tramo directo, sin dar la vuelta
    assert 100 < resumir_camino(aristas, FECHA)["metros"] < 160
    assert puntos[0]["acceso_m"] < 3


def test_no_circula_contra_sentido_si_no_hay_otra_calle():
    grafo = recta_un_sentido()
    puntos = con_puntos(grafo, [(12.1, -86.2695), (12.1, -86.2706)])
    consulta = GrafoConsulta(grafo, puntos, 0, [1])
    with pytest.raises(SinRutaError):
        buscar_ruta(consulta, puntos[0]["vertice"].id,
                    puntos[1]["vertice"].id, FECHA)


def test_estado_de_arista_elimina_maniobra_en_u_desventajosa():
    grafo = Graph()
    # A->B hacia el este; B->C hacia el oeste (retorno), B->D hacia el este.
    for i, lon in enumerate([-86.273, -86.272, -86.273, -86.271], 1):
        grafo.insertVertex(i, 12.10, lon)
    grafo.insertAris(1, 2, 100, "residential")
    grafo.insertAris(2, 3, 30, "trunk")
    grafo.insertAris(2, 4, 170, "residential")
    entrada = next(grafo.vecinos(1))
    salidas = list(grafo.vecinos(2))
    retorno = next(a for a in salidas if a.destino.id == 3)
    directo = next(a for a in salidas if a.destino.id == 4)
    assert penalizacion_giro(entrada, retorno, FECHA) >= 100
    assert penalizacion_giro(entrada, directo, FECHA) == 0


def test_prohibicion_verificada_evitar_un_giro():
    grafo = Graph()
    coords = {1: (12.1, -86.272), 2: (12.1, -86.271),
              3: (12.101, -86.271), 4: (12.1, -86.270)}
    for i, (lat, lon) in coords.items():
        grafo.insertVertex(i, lat, lon)
    for a, b in [(1, 2), (2, 3), (2, 4), (4, 3)]:
        grafo.insertAris(a, b, 100, "residential")
    grafo.prohibirGiro(1, 2, 3)
    camino = buscar_ruta(grafo, 1, 3, FECHA)
    assert [a.destino.id for a in camino] == [2, 4, 3]


def test_multiple_destinos_con_virtuales():
    grafo = Graph()
    for i in range(3):
        grafo.insertVertex(i, 12.10, -86.27 + i * .001)
    for i in range(2):
        grafo.insertAris(i, i + 1, 110, "residential")
    puntos = con_puntos(grafo, [(12.1, -86.2699),
                               (12.1, -86.2695), (12.1, -86.2682)])
    consulta = GrafoConsulta(grafo, puntos, 0, [1, 2])
    resultados = buscar_rutas_desde(consulta, puntos[0]["vertice"].id,
        {puntos[1]["vertice"].id, puntos[2]["vertice"].id}, FECHA)
    assert len(resultados) == 2
    for _, (aristas, coste) in resultados.items():
        assert abs(resumir_camino(aristas, FECHA)["segundos"] - coste) < 1e-5
