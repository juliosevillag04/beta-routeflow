"""RouteFlow V1: aplicación web local para rutas de menor tiempo modelado.

Temas académicos: funciones, condicionales, excepciones, listas, grafos,
listas enlazadas, búsqueda y programación dinámica para paradas.
"""
from datetime import datetime
from math import inf, isfinite
from threading import Timer
import webbrowser

from flask import Flask, jsonify, render_template, request

from config import BBOX, CENTRO, MAX_PARADAS, MAX_DISTANCIA_ACCESO_METROS, PUERTO
from ajuste import IndiceTramos, GrafoConsulta, preparar_punto
from dijkstra import SinRutaError, buscar_ruta, buscar_rutas_desde, geometria_camino, resumir_camino
from geocodificacion import buscar_lugares
from mapas import GESTOR
from paradas import optimizar_orden
from trafico import ahora_managua, interpretar_salida, nombre_franja

app = Flask(__name__)
app.json.ensure_ascii = False
app.config["MAX_CONTENT_LENGTH"] = 24 * 1024

@app.get("/")
def inicio():
    return render_template("index.html", centro=CENTRO, bbox=BBOX, max_paradas=MAX_PARADAS)


@app.get("/api/estado")
def estado():
    info = GESTOR.informar()
    info["hora_managua"] = ahora_managua().isoformat()
    return jsonify(info)


@app.post("/api/preparar")
def preparar():
    datos = request.get_json(silent=True) or {}
    if not isinstance(datos, dict):
        return jsonify({"error": "Solicitud inválida."}), 400
    tipo = datos.get("modo", "real")
    if tipo not in ("real", "demo"):
        return jsonify({"error": "Modo no válido."}), 400
    return jsonify(GESTOR.iniciar(tipo, bool(datos.get("forzar", False))))


@app.get("/api/buscar")
def buscar():
    try:
        return jsonify({"lugares": buscar_lugares(request.args.get("q", ""))})
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 503


def validar_punto(dato, etiqueta):
    if not isinstance(dato, dict):
        raise ValueError(f"Falta el punto: {etiqueta}.")
    try:
        lat = float(dato["lat"])
        lon = float(dato["lon"])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"Coordenadas incorrectas para {etiqueta}.") from None
    if not isfinite(lat) or not isfinite(lon) or not (11.5 <= lat <= 13) or not (-87 <= lon <= -85):
        raise ValueError(f"{etiqueta} debe estar en la región de Managua.")
    nombre = str(dato.get("nombre") or etiqueta).strip()[:95]
    return {"lat": lat, "lon": lon, "nombre": nombre}


def calcular_itinerario(grafo, datos):
    if not isinstance(datos, dict):
        raise ValueError("Solicitud inválida.")
    origen = validar_punto(datos.get("origen"), "Origen")
    destino = validar_punto(datos.get("destino"), "Destino")
    paradas = datos.get("paradas", [])
    if not isinstance(paradas, list) or len(paradas) > MAX_PARADAS:
        raise ValueError(f"Se permiten como máximo {MAX_PARADAS} paradas.")
    puntos = [origen] + [validar_punto(p, f"Parada {i+1}") for i, p in enumerate(paradas)] + [destino]
    fecha = interpretar_salida(datos.get("salida", "ahora"))
    ordenar = bool(datos.get("ordenar", True))

    # Tema de clase: búsqueda y referencias. Se encajan los marcadores en
    # segmentos reales, respetando el sentido de circulación, no en nodos.
    if not hasattr(grafo, "_indice_tramos"):
        grafo._indice_tramos = IndiceTramos(grafo)
    for i, punto in enumerate(puntos):
        ajustes = grafo._indice_tramos.buscar(punto["lat"], punto["lon"])
        if not ajustes or ajustes[0].distancia > MAX_DISTANCIA_ACCESO_METROS:
            raise ValueError(f"'{punto['nombre']}' está fuera de la zona vial disponible. Selecciona un punto más cercano a las calles cargadas.")
        preparar_punto(punto, ajustes, i)

    n = len(puntos)
    if n == 2 and (abs(puntos[0]["lat"] - puntos[1]["lat"]) < 1e-7 and
                   abs(puntos[0]["lon"] - puntos[1]["lon"]) < 1e-7):
        raise ValueError("El origen y el destino coinciden. Elige ubicaciones distintas.")
    if ordenar and len(paradas) >= 2:
        matriz = [[inf] * n for _ in range(n)]
        for i in range(n - 1):
            origen_id = puntos[i]["vertice"].id
            objetivos = {puntos[j]["vertice"].id for j in range(n) if i != j}
            consulta = GrafoConsulta(grafo, puntos, i, [j for j in range(n) if i != j])
            rutas = buscar_rutas_desde(consulta, origen_id, objetivos, fecha)
            for j in range(n):
                if i == j:
                    matriz[i][j] = 0.0
                elif puntos[j]["vertice"].id in rutas:
                    matriz[i][j] = rutas[puntos[j]["vertice"].id][1]
        orden = optimizar_orden(matriz, len(paradas))
        if orden is None:
            raise SinRutaError("No existe un recorrido que conecte todas las paradas con los sentidos viales disponibles.")
    else:
        orden = list(range(n))

    recorridos = []
    total_tiempo, total_metros, total_semaforos = 0.0, 0.0, 0
    total_metros_corta, total_tiempo_corta = 0.0, 0.0
    referencias_cortas = []

    for posicion in range(len(orden) - 1):
        a, b = puntos[orden[posicion]], puntos[orden[posicion + 1]]
        consulta = GrafoConsulta(grafo, puntos, orden[posicion], [orden[posicion + 1]])
        camino = buscar_ruta(consulta, a["vertice"].id, b["vertice"].id, fecha, "tiempo")
        resumen = resumir_camino(camino, fecha)
        geometria = geometria_camino(a["vertice"], camino)
        recorridos.append({
            "origen": a["nombre"], "destino": b["nombre"],
            "coordenadas": geometria, "km": round(resumen["metros"] / 1000, 2),
            "minutos": round(resumen["segundos"] / 60, 1),
        })
        total_tiempo += resumen["segundos"]
        total_metros += resumen["metros"]
        total_semaforos += resumen["semaforos"]

        ruta_corta = buscar_ruta(consulta, a["vertice"].id, b["vertice"].id, fecha, "distancia")
        metrica_corta = resumir_camino(ruta_corta, fecha)
        total_metros_corta += metrica_corta["metros"]
        total_tiempo_corta += metrica_corta["segundos"]
        referencias_cortas.append(geometria_camino(a["vertice"], ruta_corta))

    return {
        "modo": "demostracion" if GESTOR.modo == "demo" else "calles_reales",
        "advertencia": ("DEMOSTRACIÓN: la red vial es sintética y no corresponde a calles reales."
                        if GESTOR.modo == "demo" else
                        "Tiempos simulados por franja horaria; giros penalizados, sin verificación completa de prohibiciones de giro ni congestión en tiempo real."),
        "minutos": round(total_tiempo / 60, 1),
        "km": round(total_metros / 1000, 2),
        "semaforos": total_semaforos,
        "referencia_distancia": {"km": round(total_metros_corta / 1000, 2),
                                  "minutos": round(total_tiempo_corta / 60, 1),
                                  "tramos": referencias_cortas},
        "franja": nombre_franja(fecha),
        "salida": fecha.isoformat(),
        "orden_optimizado": ordenar and len(paradas) >= 2,
        "puntos": [{"nombre": puntos[i]["nombre"], "lat": puntos[i]["lat"],
                    "lon": puntos[i]["lon"], "acceso_m": puntos[i]["acceso_m"]}
                   for i in orden],
        "tramos": recorridos,
    }


@app.post("/api/ruta")
def ruta():
    info = GESTOR.informar()
    if info["estado"] != "listo":
        return jsonify({"error": "La red vial todavía no está disponible. Revisa el estado de carga."}), 503
    try:
        resultado = calcular_itinerario(GESTOR.grafo, request.get_json(silent=True))
        return jsonify(resultado)
    except (ValueError, SinRutaError) as error:
        return jsonify({"error": str(error)}), 422
    except Exception:
        app.logger.exception("Error no esperado al calcular la ruta")
        return jsonify({"error": "No se pudo calcular la ruta. Revisa las ubicaciones e inténtalo de nuevo."}), 500


if __name__ == "__main__":
    print("\n" + "=" * 56)
    print(" ROUTEFLOW | Managua · Nicaragua")
    print(" Aplicación: http://127.0.0.1:5000")
    print(" La primera descarga vial necesita conexión a Internet.")
    print(" Presiona Ctrl+C para detener el servidor.")
    print("=" * 56 + "\n")
    Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{PUERTO}")).start()
    app.run(host="127.0.0.1", port=PUERTO, debug=False, use_reloader=False)
