"""Orden opcional de paradas usando programación dinámica (Held–Karp).

Tema adicional de clase: listas, matrices, diccionarios, ciclos, búsqueda
combinatoria y análisis de eficiencia. No se usa OR-Tools.
"""
from math import inf

def optimizar_orden(matriz, cantidad_paradas):
    """Índices: 0 origen, 1..n paradas, n+1 destino fijo.

    Devuelve la secuencia [0, ...paradas_en_orden..., n+1] o None.
    Complejidad: O(n²·2ⁿ), n <= 5 en RouteFlow V1.
    """
    n = cantidad_paradas
    destino = n + 1
    if n == 0:
        return [0, destino] if matriz[0][destino] < inf else None

    dp = {}  # (máscara, última_parada) -> (costo, anterior)
    for k in range(n):
        costo = matriz[0][k + 1]
        if costo < inf:
            dp[(1 << k, k)] = (costo, -1)

    for mascara in range(1, 1 << n):
        for ultimo in range(n):
            if (mascara, ultimo) not in dp:
                continue
            previo = dp[(mascara, ultimo)][0]
            for siguiente in range(n):
                if mascara & (1 << siguiente):
                    continue
                siguiente_mascara = mascara | (1 << siguiente)
                nuevo = previo + matriz[ultimo + 1][siguiente + 1]
                clave = (siguiente_mascara, siguiente)
                if nuevo < dp.get(clave, (inf, None))[0]:
                    dp[clave] = (nuevo, ultimo)

    completa = (1 << n) - 1
    mejor = inf
    ultimo_mejor = None
    for ultimo in range(n):
        entrada = dp.get((completa, ultimo))
        if entrada is not None:
            costo = entrada[0] + matriz[ultimo + 1][destino]
            if costo < mejor:
                mejor, ultimo_mejor = costo, ultimo
    if ultimo_mejor is None:
        return None

    orden = []
    mascara = completa
    ultimo = ultimo_mejor
    while ultimo != -1:
        orden.append(ultimo + 1)
        anterior = dp[(mascara, ultimo)][1]
        mascara ^= 1 << ultimo
        ultimo = anterior
    orden.reverse()
    return [0] + orden + [destino]
