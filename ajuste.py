"""Vincula los puntos del mapa a TRAMOS de calle, no a cruces lejanos.

Tema de clase: listas, objetos, referencias y búsqueda geográfica.
El grafo real permanece inalterado; las conexiones virtuales existen SOLO
para la consulta del usuario. Se preserva el sentido de cada calle.

La proximidad física no garantiza acceso vehicular (portones, medianas,
restricciones de giros o intersecciones a desnivel): NO es navegación legal.
"""
from math import cos, radians
from shapely.geometry import LineString, Point
from shapely.ops import substring
from shapely.strtree import STRtree

from grafo import NodoArista, Vertex

# Proyección local aproximada para calcular distancias a calles, en metros.
ESCALA_Y = 111195.0
ESCALA_X = 111195.0 * cos(radians(12.12))

def _xy(lat, lon):
    return lon * ESCALA_X, lat * ESCALA_Y


def _latlon(x, y):
    return [y / ESCALA_Y, x / ESCALA_X]


class AjusteTramo:
    def __init__(self, arista, linea, posicion, distancia):
        self.arista = arista
        self.linea = linea
        self.posicion = posicion             # Metros desde origen de esta arista
        self.distancia = distancia           # Metros del punto al eje de la calle
        coordenada = linea.interpolate(posicion)
        self.lat, self.lon = _latlon(coordenada.x, coordenada.y)


class IndiceTramos:
    def __init__(self, grafo):
        self.aristas = []
        self.lineas = []
        for vertice in grafo.vertexs:
            for arista in grafo.vecinos(vertice.id):
                puntos = arista.coordenadas or [
                    [vertice.lat, vertice.lon],
                    [arista.destino.lat, arista.destino.lon],
                ]
                coordenadas = [_xy(lat, lon) for lat, lon in puntos]
                # Shapely puede rechazar LineString con una única coordenada.
                if len(coordenadas) < 2 or len(set(coordenadas)) < 2:
                    continue
                linea = LineString(coordenadas)
                if linea.length < 0.001:
                    continue
                self.aristas.append(arista)
                self.lineas.append(linea)
        if not self.lineas:
            raise ValueError("La red no contiene tramos transitables.")
        self.arbol = STRtree(self.lineas)

    def buscar(self, lat, lon, max_candidatos=8):
        punto = Point(*_xy(lat, lon))
        indice_mas_cercano = int(self.arbol.nearest(punto))
        distancia_minima = self.lineas[indice_mas_cercano].distance(punto)
        # Agrupar únicamente carriles coincidentes o casi coincidentes.
        # Un carril al otro lado de una mediana no debe elegirse libremente.
        radio = max(4.0, distancia_minima + 1.5)
        indices = self.arbol.query(punto.buffer(radio))
        opciones = []
        for indice in indices:
            indice = int(indice)
            linea = self.lineas[indice]
            distancia = linea.distance(punto)
            if distancia <= distancia_minima + 1.5 + 1e-8:
                opciones.append(AjusteTramo(
                    self.aristas[indice], linea, linea.project(punto), distancia
                ))
        opciones.sort(key=lambda a: a.distancia)
        return opciones[:max_candidatos]


def preparar_punto(punto, ajustes, numero):
    """Guarda el encaje en la calle; NO cambia las coordenadas elegidas."""
    if not ajustes:
        raise ValueError("No se encontró ninguna calle para el punto indicado.")
    mejor = ajustes[0]
    punto["ajustes"] = ajustes
    punto["acceso_m"] = round(mejor.distancia)
    punto["vertice"] = Vertex(f"__routeflow_punto_{numero}__", mejor.lat, mejor.lon)


def _porcentaje(parcial, total):
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, parcial / total))


def _crear_parcial(ajuste, desde_m, hasta_m, origen, destino, acceso=0.0):
    """Construye la porción recorrible de una calle, con la misma dirección."""
    linea = ajuste.linea
    desde = max(0.0, min(linea.length, desde_m))
    hasta = max(desde, min(linea.length, hasta_m))
    recorte = substring(linea, desde, hasta)
    if recorte.geom_type == "Point":
        coordenadas = [_latlon(recorte.x, recorte.y)] * 2
    else:
        coordenadas = [_latlon(x, y) for x, y in recorte.coords]

    base = ajuste.arista
    proporcion = _porcentaje(hasta - desde, linea.length)
    nuevo = NodoArista(destino, base.distancia * proporcion,
                       base.tipo_via, base.velocidad, coordenadas, base.nombre)
    nuevo.origen = origen
    # La distancia desde el marcador a la calle no se dibuja como una vía.
    # Se agrega un costo de acceso moderado para no elegir puntos más lejanos.
    nuevo.recargo_acceso = acceso * 0.6
    return nuevo


class GrafoConsulta:
    """Vista temporal del grafo, sin copiar ni alterar sus miles de aristas."""
    def __init__(self, base, puntos, indice_origen, indices_destino):
        self.base = base
        self.extra = {}
        self.temporales = {p["vertice"].id: p["vertice"] for p in puntos}
        self.giros_prohibidos = base.giros_prohibidos
        origen = puntos[indice_origen]
        origen_virtual = origen["vertice"]

        for ajuste in origen["ajustes"]:
            arista = ajuste.arista
            # Del marcador hasta el extremo final en el sentido de la calle.
            self._agregar(origen_virtual.id, _crear_parcial(
                ajuste, ajuste.posicion, ajuste.linea.length,
                origen_virtual, arista.destino, ajuste.distancia
            ))

        for indice in indices_destino:
            destino = puntos[indice]
            destino_virtual = destino["vertice"]
            for ajuste_fin in destino["ajustes"]:
                arista = ajuste_fin.arista
                # Del extremo inicial de la calle hasta el marcador destino.
                self._agregar(arista.origen.id, _crear_parcial(
                    ajuste_fin, 0, ajuste_fin.posicion,
                    arista.origen, destino_virtual, ajuste_fin.distancia
                ))
                # Importante: si ambos puntos están en la MISMA calle,
                # permitir el trayecto directo respetando su sentido.
                for ajuste_inicio in origen["ajustes"]:
                    if (ajuste_inicio.arista is arista and
                            ajuste_inicio.posicion <= ajuste_fin.posicion):
                        self._agregar(origen_virtual.id, _crear_parcial(
                            ajuste_inicio, ajuste_inicio.posicion, ajuste_fin.posicion,
                            origen_virtual, destino_virtual,
                            ajuste_inicio.distancia + ajuste_fin.distancia
                        ))

    def _agregar(self, origen, arista):
        self.extra.setdefault(origen, []).append(arista)

    def search(self, identificador):
        return self.temporales.get(identificador) or self.base.search(identificador)

    def vecinos(self, identificador):
        yield from self.base.vecinos(identificador)
        yield from self.extra.get(identificador, ())
