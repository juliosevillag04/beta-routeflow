"""Dijkstra propio con *estado de arista de llegada* y adyacencia enlazada.

En clase se estudian grafos, listas, búsqueda y colas. Esta versión conserva
las listas enlazadas de grafo.py y usa heapq (biblioteca estándar) para evitar
que se prefieran retornos inmediatos solo por comparar nodos de llegada.

El sistema NO conoce automáticamente todas las prohibiciones de giro de OSM.
Solo se bloquean las restricciones verificadas cargadas en el grafo; los giros
no verificados se penalizan mediante un modelo de tiempos ilustrativo.
"""
import heapq
from itertools import count
from trafico import tiempo_arista, penalizacion_giro

class SinRutaError(Exception):
    pass


def buscar_rutas_desde(grafo, origen, destinos, fecha, objetivo="tiempo"):
    """Busca caminos mínimos desde un origen a uno o varios destinos.

    Estado: arista por la que se llegó, NO únicamente el vértice.
    Esto permite evaluar la maniobra al pasar de una calle a otra.
    Costos no negativos; complejidad O(E log E) en el grafo expandido.
    """
    if objetivo not in ("tiempo", "distancia"):
        raise ValueError("Objetivo de búsqueda no válido.")
    if grafo.search(origen) is None:
        return {}

    pendientes = set(destinos)
    pendientes.discard(origen)
    resultados = {origen: ([], 0.0)} if origen in destinos else {}
    mejores = {None: 0.0}             # None representa el estado inicial
    anteriores = {}                   # Arista entrante -> arista anterior
    contador = count()
    cola = [(0.0, next(contador), None)]
    prohibidos = getattr(grafo, "giros_prohibidos", set())

    while cola and pendientes:
        costo_actual, _, entrada = heapq.heappop(cola)
        if costo_actual > mejores.get(entrada, float("inf")) + 1e-9:
            continue

        actual_id = origen if entrada is None else entrada.destino.id
        if actual_id in pendientes:
            camino = []
            cursor = entrada
            while cursor is not None:
                camino.append(cursor)
                cursor = anteriores[cursor]
            camino.reverse()
            resultados[actual_id] = (camino, costo_actual)
            pendientes.remove(actual_id)
            if not pendientes:
                break

        for salida in grafo.vecinos(actual_id):
            if entrada is not None and (entrada.origen.id, actual_id,
                                        salida.destino.id) in prohibidos:
                continue
            peso = salida.distancia if objetivo == "distancia" else (
                tiempo_arista(salida, fecha) + penalizacion_giro(entrada, salida, fecha)
            )
            nuevo_costo = costo_actual + peso
            if nuevo_costo + 1e-9 < mejores.get(salida, float("inf")):
                mejores[salida] = nuevo_costo
                anteriores[salida] = entrada
                heapq.heappush(cola, (nuevo_costo, next(contador), salida))

    return resultados


def buscar_ruta(grafo, origen, destino, fecha, objetivo="tiempo"):
    encontrado = buscar_rutas_desde(grafo, origen, {destino}, fecha, objetivo)
    if destino not in encontrado:
        raise SinRutaError("No se encontró una ruta transitable entre los puntos seleccionados.")
    return encontrado[destino][0]


def resumir_camino(aristas, fecha):
    """Incluye los recargos por giros en la duración mostrada al usuario."""
    segundos = 0.0
    entrada = None
    for arista in aristas:
        segundos += tiempo_arista(arista, fecha)
        segundos += penalizacion_giro(entrada, arista, fecha)
        entrada = arista
    return {
        "metros": sum(a.distancia for a in aristas),
        "segundos": segundos,
        "semaforos": sum(1 for a in aristas if a.destino.semaforo),
    }


def geometria_camino(inicio, aristas, max_puntos=8000):
    """Conserva las curvas originales, incluso tramos parciales de una calle."""
    actual = inicio
    coordenadas = [[actual.lat, actual.lon]]
    for arista in aristas:
        puntos = arista.coordenadas or [[actual.lat, actual.lon],
                                        [arista.destino.lat, arista.destino.lon]]
        if len(puntos) > 1:
            if (abs(coordenadas[-1][0] - puntos[0][0]) > 1e-8 or
                    abs(coordenadas[-1][1] - puntos[0][1]) > 1e-8):
                coordenadas.append(puntos[0])
            coordenadas.extend(puntos[1:])
        actual = arista.destino
    if len(coordenadas) > max_puntos:
        paso = (len(coordenadas) - 1) / (max_puntos - 1)
        coordenadas = [coordenadas[round(i * paso)] for i in range(max_puntos - 1)] + [coordenadas[-1]]
    return coordenadas
