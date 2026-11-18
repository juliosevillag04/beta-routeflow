"""Grafo dirigido y ponderado con listas de adyacencia ENLAZADAS.

Conserva el enfoque de clase (Vertex, Graph, insertVertex, search, insertAris).
Cada NodoArista dispone de 'next': no delegamos los caminos a NetworkX.
"""
from math import atan2, cos, radians, sin, sqrt

class NodoArista:
    def __init__(self, destino, distancia, tipo_via="residential", velocidad=None,
                 coordenadas=None, nombre=""):
        self.origen = None                    # Se asigna al insertar en el grafo
        self.destino = destino                # Referencia a otro objeto Vertex
        self.distancia = float(distancia)     # Metros
        self.tipo_via = tipo_via
        self.velocidad = velocidad            # Límite informado en OSM, si existe
        self.coordenadas = coordenadas or []
        self.nombre = nombre
        self.recargo_acceso = 0.0            # Solo para ajuste de puntos del usuario
        self.next = None                     # Lista simplemente enlazada


class Vertex:
    def __init__(self, identificador, lat, lon, semaforo=False):
        self.id = identificador
        self.lat = float(lat)
        self.lon = float(lon)
        self.semaforo = bool(semaforo)
        self.neig = None                     # Primer NodoArista, o None


class Graph:
    def __init__(self):
        self.vertexs = []                    # En clase: colección de vértices
        self.indice = {}                     # Búsqueda rápida en redes grandes
        self.total_aristas = 0
        self.giros_prohibidos = set()         # Solamente restricciones verificadas

    def insertVertex(self, identificador, lat, lon, semaforo=False):
        if identificador in self.indice:
            return False
        nuevo = Vertex(identificador, lat, lon, semaforo)
        self.vertexs.append(nuevo)
        self.indice[identificador] = nuevo
        return True

    def search(self, identificador):
        return self.indice.get(identificador)

    def insertAris(self, origen, destino, distancia, tipo_via="residential",
                   velocidad=None, coordenadas=None, nombre=""):
        primero = self.search(origen)
        segundo = self.search(destino)
        if primero is None or segundo is None or distancia <= 0:
            return False
        nuevo = NodoArista(segundo, distancia, tipo_via, velocidad,
                          coordenadas, nombre)
        nuevo.origen = primero
        nuevo.next = primero.neig
        primero.neig = nuevo
        self.total_aristas += 1
        return True

    def prohibirGiro(self, anterior, cruce, siguiente):
        """Registra una restricción comprobada: anterior -> cruce -> siguiente.

        Tema de clase: conjuntos, validaciones y grafos dirigidos.
        No inferir normas legales por proximidad geográfica.
        """
        if not all(self.search(n) is not None for n in (anterior, cruce, siguiente)):
            return False
        self.giros_prohibidos.add((anterior, cruce, siguiente))
        return True

    def vecinos(self, identificador):
        actual = self.search(identificador)
        actual = actual.neig if actual is not None else None
        while actual is not None:
            yield actual
            actual = actual.next

    def buscarCercano(self, lat, lon):
        """Busca el vértice vial más cercano (sin dependencia extra)."""
        mejor = None
        mejor_distancia = float("inf")
        for vertice in self.vertexs:
            distancia = distancia_m(lat, lon, vertice.lat, vertice.lon)
            if distancia < mejor_distancia:
                mejor = vertice
                mejor_distancia = distancia
        return mejor, mejor_distancia


def distancia_m(lat1, lon1, lat2, lon2):
    """Distancia aproximada geodésica, fórmula de Haversine."""
    radio = 6371000
    a = sin(radians(lat2 - lat1) / 2) ** 2
    a += cos(radians(lat1)) * cos(radians(lat2)) * sin(radians(lon2 - lon1) / 2) ** 2
    return 2 * radio * atan2(sqrt(a), sqrt(max(0, 1 - a)))
