"""Integración Flask/algoritmos con red sintética, sin conexión externa."""
import pytest
from app import app
from mapas import GESTOR, red_demostracion


@pytest.fixture()
def cliente():
    GESTOR.grafo = red_demostracion()
    GESTOR.estado = "listo"
    GESTOR.modo = "demo"
    app.config.update(TESTING=True)
    with app.test_client() as cliente:
        yield cliente


def test_pagina_principal(cliente):
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    assert b"RouteFlow" in respuesta.data


def test_estado(cliente):
    respuesta = cliente.get("/api/estado")
    datos = respuesta.get_json()
    assert datos["estado"] == "listo"
    assert datos["modo"] == "demo"
    assert datos["nodos"] == 120


def test_recorrido_de_varias_paradas(cliente):
    origen = {"lat": 12.1035, "lon": -86.2986, "nombre": "Origen"}
    destino = {"lat": 12.1245, "lon": -86.2704, "nombre": "Destino"}
    paradas = [
        {"lat": 12.1140, "lon": -86.2892, "nombre": "Primera"},
        {"lat": 12.1210, "lon": -86.2751, "nombre": "Segunda"},
    ]
    respuesta = cliente.post("/api/ruta", json={
        "origen": origen, "destino": destino, "paradas": paradas,
        "ordenar": True, "salida": "2026-11-16T07:30",
    })
    assert respuesta.status_code == 200, respuesta.get_json()
    datos = respuesta.get_json()
    assert len(datos["tramos"]) == 3
    assert len(datos["puntos"]) == 4
    assert datos["puntos"][0]["nombre"] == "Origen"
    assert datos["puntos"][-1]["nombre"] == "Destino"
    assert datos["minutos"] > 0
    assert datos["modo"] == "demostracion"
    assert datos["referencia_distancia"]["km"] <= datos["km"] + .01


def test_rechaza_paradas_excesivas(cliente):
    punto = {"lat": 12.12, "lon": -86.27}
    respuesta = cliente.post("/api/ruta", json={
        "origen": punto, "destino": punto, "paradas": [punto] * 6})
    assert respuesta.status_code == 422


def test_rechaza_puntos_fuera_de_cobertura(cliente):
    respuesta = cliente.post("/api/ruta", json={
        "origen": {"lat": 12.3, "lon": -86.27},
        "destino": {"lat": 12.12, "lon": -86.27},
    })
    assert respuesta.status_code == 422
