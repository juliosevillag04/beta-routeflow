"""Importación de calles reales de OpenStreetMap y modo de demostración.

OSMnx SOLO obtiene geometría, sentidos y atributos de las calles.
La red se convierte a nuestro Graph con nodos enlazados (grafo.py).
La optimización siempre la hace dijkstra.py, no NetworkX.
"""
from pathlib import Path
from threading import Lock, Thread
from grafo import Graph, distancia_m
from config import ARCHIVO_RED, BBOX, DATOS

def tipo_via(valor):
    return str(valor[0] if isinstance(valor, list) and valor else valor or "residential")


def puntos_arista(atributos, primero, segundo):
    geometria = atributos.get("geometry")
    if geometria is None:
        return [[primero.lat, primero.lon], [segundo.lat, segundo.lon]]
    try:
        puntos = [[float(y), float(x)] for x, y in geometria.coords]
    except (AttributeError, ValueError, TypeError):
        return [[primero.lat, primero.lon], [segundo.lat, segundo.lon]]
    if not puntos:
        return [[primero.lat, primero.lon], [segundo.lat, segundo.lon]]
    # En algunos objetos LineString, los puntos están orientados al revés.
    if distancia_m(primero.lat, primero.lon, *puntos[-1]) < distancia_m(primero.lat, primero.lon, *puntos[0]):
        puntos.reverse()
    return [[primero.lat, primero.lon]] + puntos[1:-1] + [[segundo.lat, segundo.lon]]


def convertir_grafo(osm):
    grafo = Graph()
    for id_nodo, atributos in osm.nodes(data=True):
        etiqueta = str(atributos.get("highway", ""))
        semaforo = "traffic_signals" in etiqueta
        grafo.insertVertex(id_nodo, atributos["y"], atributos["x"], semaforo)

    for origen, destino, _, datos in osm.edges(keys=True, data=True):
        v1 = grafo.search(origen)
        v2 = grafo.search(destino)
        distancia = float(datos.get("length", 0))
        if v1 is None or v2 is None or distancia <= 0:
            continue
        grafo.insertAris(origen, destino, distancia, tipo_via(datos.get("highway")),
                         datos.get("maxspeed"), puntos_arista(datos, v1, v2),
                         str(datos.get("name", "")))
    if len(grafo.vertexs) < 3 or grafo.total_aristas < 2:
        raise RuntimeError("La red vial descargada no contiene suficientes calles.")
    return grafo


def red_demostracion():
    """Grafo SINTÉTICO para probar sin Internet. NO representa vías reales."""
    grafo = Graph()
    filas, columnas = 10, 12
    inicio_lat, inicio_lon = 12.100, -86.308
    paso_lat, paso_lon = 0.0035, 0.0047
    for i in range(filas):
        for j in range(columnas):
            grafo.insertVertex(i * columnas + j, inicio_lat + i * paso_lat,
                               inicio_lon + j * paso_lon, (i + 3 * j) % 11 == 0)

    def conexion(a, b, tipo):
        va, vb = grafo.search(a), grafo.search(b)
        distancia = distancia_m(va.lat, va.lon, vb.lat, vb.lon)
        grafo.insertAris(a, b, distancia, tipo,
                         coordenadas=[[va.lat, va.lon], [vb.lat, vb.lon]],
                         nombre="Calle ficticia de demostración")

    for i in range(filas):
        for j in range(columnas):
            actual = i * columnas + j
            if j < columnas - 1:
                derecho = actual + 1
                categoria = "primary" if i in (2, 6) else "residential"
                conexion(actual, derecho, categoria)
                if i not in (2, 6):
                    conexion(derecho, actual, categoria)
            if i < filas - 1:
                abajo = actual + columnas
                categoria = "secondary" if j in (3, 8) else "residential"
                conexion(actual, abajo, categoria)
                if j not in (3, 8):
                    conexion(abajo, actual, categoria)
    return grafo


class GestorRed:
    def __init__(self):
        self.grafo = None
        self.modo = None
        self.estado = "sin_iniciar"
        self.mensaje = "La red vial todavía no se ha preparado."
        self.lock = Lock()
        self.tarea = None

    def informar(self):
        with self.lock:
            return {
                "estado": self.estado,
                "mensaje": self.mensaje,
                "modo": self.modo,
                "nodos": len(self.grafo.vertexs) if self.grafo else 0,
                "calles": self.grafo.total_aristas if self.grafo else 0,
                "cobertura": {"oeste": BBOX[0], "sur": BBOX[1],
                              "este": BBOX[2], "norte": BBOX[3]},
            }

    def iniciar(self, tipo="real", forzar=False):
        if tipo not in ("real", "demo"):
            raise ValueError("Tipo de red desconocido.")
        with self.lock:
            if self.estado == "cargando":
                return self.informar_sin_lock()
            if self.estado == "listo" and self.modo == tipo and not forzar:
                return self.informar_sin_lock()
            self.estado = "cargando"
            self.mensaje = ("Descargando o recuperando las calles de OpenStreetMap…"
                            if tipo == "real" else "Preparando demostración sintética…")
            self.tarea = Thread(target=self._cargar, args=(tipo, forzar), daemon=True)
            self.tarea.start()
            return self.informar_sin_lock()

    def informar_sin_lock(self):
        return {"estado": self.estado, "mensaje": self.mensaje, "modo": self.modo,
                "nodos": len(self.grafo.vertexs) if self.grafo else 0,
                "calles": self.grafo.total_aristas if self.grafo else 0}

    def _cargar(self, tipo, forzar):
        try:
            if tipo == "demo":
                grafo = red_demostracion()
                mensaje = "Red sintética de demostración lista (NO calles reales)."
            else:
                import osmnx as ox
                DATOS.mkdir(exist_ok=True)
                ox.settings.use_cache = True
                ox.settings.cache_folder = str(DATOS / "cache_osm")
                ox.settings.requests_timeout = 180
                # Para conservar semáforos en los atributos de vértices.
                if "highway" not in ox.settings.useful_tags_node:
                    ox.settings.useful_tags_node = list(ox.settings.useful_tags_node) + ["highway"]
                if Path(ARCHIVO_RED).exists() and not forzar:
                    osm = ox.load_graphml(ARCHIVO_RED)
                else:
                    osm = ox.graph_from_bbox(BBOX, network_type="drive",
                                             simplify=True, retain_all=False,
                                             truncate_by_edge=True)
                    ox.save_graphml(osm, ARCHIVO_RED)
                grafo = convertir_grafo(osm)
                mensaje = "Calles reales cargadas. Motor Dijkstra propio preparado."
            with self.lock:
                self.grafo = grafo
                self.modo = tipo
                self.estado = "listo"
                self.mensaje = mensaje
        except Exception as error:
            with self.lock:
                # No sustituir silenciosamente las calles reales por una red ficticia.
                self.estado = "error"
                self.mensaje = (f"No fue posible preparar la red: {type(error).__name__}: {str(error)[:220]}. "
                                "Comprueba Internet o utiliza el modo demostración.")


GESTOR = GestorRed()
