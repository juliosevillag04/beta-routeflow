"""Pruebas del grafo dirigido con listas enlazadas (sin Internet)."""
from grafo import Graph, distancia_m


def test_vertices_busqueda_y_duplicados():
    grafo = Graph()
    assert grafo.insertVertex(1, 12.10, -86.27)
    assert not grafo.insertVertex(1, 12.11, -86.28)
    assert grafo.search(1).lat == 12.10
    assert grafo.search(99) is None


def test_lista_enlazada_y_sentido_unico():
    grafo = Graph()
    for n in range(3):
        grafo.insertVertex(n, 12.10, -86.27 + n * .001)
    assert grafo.insertAris(0, 1, 110)
    assert grafo.insertAris(0, 2, 220)
    assert not grafo.insertAris(0, 99, 120)
    assert grafo.search(0).neig.next is not None
    assert len(list(grafo.vecinos(0))) == 2
    assert len(list(grafo.vecinos(1))) == 0  # Grafo DIRIGIDO


def test_haversine():
    assert distancia_m(12.1, -86.27, 12.1, -86.27) == 0
    assert 100 < distancia_m(12.1, -86.27, 12.1, -86.2685) < 200
