"""La red externa se transforma a nuestro grafo, sin NetworkX para rutas."""
import networkx as nx
from shapely.geometry import LineString
from mapas import convertir_grafo


def test_convertir_multidigraph_a_lista_enlazada():
    osm = nx.MultiDiGraph()
    osm.add_node(11, x=-86.270, y=12.120)
    osm.add_node(12, x=-86.269, y=12.120, highway="traffic_signals")
    osm.add_node(13, x=-86.268, y=12.120)
    # Geometría deliberadamente al revés para probar la orientación.
    geometry = LineString([(-86.269, 12.120), (-86.2695, 12.1202), (-86.270, 12.120)])
    osm.add_edge(11, 12, length=125.0, highway="primary", geometry=geometry)
    osm.add_edge(12, 11, length=125.0, highway="primary")

    grafo = convertir_grafo(osm)
    assert len(grafo.vertexs) == 3
    assert grafo.total_aristas == 2
    assert grafo.search(12).semaforo
    primera_arista = next(grafo.vecinos(11))
    assert primera_arista.destino.id == 12
    assert primera_arista.coordenadas[0] == [12.120, -86.270]
    assert primera_arista.coordenadas[-1] == [12.120, -86.269]
