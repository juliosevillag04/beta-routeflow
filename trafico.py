"""Modelo horario ilustrativo, NO tráfico en directo.

Tema adicional del syllabus: funciones, validación de datos, condicionales
anidados, manejo de fechas y cálculo de eficiencia temporal.
Los factores son SUPUESTOS ajustables; no son mediciones reales de Managua.
"""
from datetime import datetime
from math import atan2, cos, degrees, radians, sin
from zoneinfo import ZoneInfo
import re

ZONA = ZoneInfo("America/Managua")

VELOCIDADES = {                     # km/h supuestos para circulación urbana
    "motorway": 72,
    "motorway_link": 40,
    "trunk": 54,
    "trunk_link": 33,
    "primary": 42,
    "primary_link": 24,
    "secondary": 36,
    "secondary_link": 23,
    "tertiary": 32,
    "tertiary_link": 21,
    "residential": 27,
    "unclassified": 25,
    "living_street": 13,
    "service": 17,
}
ARTERIAS = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link"}

def ahora_managua():
    return datetime.now(ZONA)


def interpretar_salida(texto):
    if not texto or texto == "ahora":
        return ahora_managua()
    if not isinstance(texto, str) or len(texto) > 35:
        raise ValueError("Hora de salida inválida.")
    try:
        fecha = datetime.fromisoformat(texto)
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=ZONA)
        else:
            fecha = fecha.astimezone(ZONA)
        if not 2020 <= fecha.year <= 2100:
            raise ValueError("Fecha fuera del rango permitido.")
        return fecha
    except (ValueError, TypeError):
        raise ValueError("Usa una fecha y hora válidas.") from None


def categoria(tipo):
    if isinstance(tipo, list):
        tipo = tipo[0] if tipo else "residential"
    return str(tipo or "residential").lower()


def limite_velocidad(valor):
    """Extrae un límite numérico de OSM cuando existe; no inventa límites."""
    if isinstance(valor, list):
        valores = [limite_velocidad(v) for v in valor]
        validos = [v for v in valores if v is not None]
        return min(validos) if validos else None
    if valor is None:
        return None
    texto = str(valor).lower()
    encontrados = re.findall(r"\d+(?:\.\d+)?", texto)
    if not encontrados:
        return None
    n = float(encontrados[0])
    if "mph" in texto:
        n *= 1.609344
    return n if 5 <= n <= 130 else None


def franja_horaria(fecha):
    h = fecha.hour + fecha.minute / 60
    if fecha.weekday() < 5 and (6.5 <= h < 9 or 16.5 <= h < 19):
        return "hora_pico"
    if fecha.weekday() < 5 and (11.5 <= h < 14):
        return "mediodia"
    if 21 <= h or h < 5:
        return "noche"
    if fecha.weekday() >= 5 and 10 <= h < 18:
        return "fin_semana"
    return "normal"


def factor_circulacion(tipo, franja):
    principal = categoria(tipo) in ARTERIAS
    factores = {
        "hora_pico": (0.52, 0.72),
        "mediodia": (0.77, 0.87),
        "noche": (1.00, 1.00),
        "fin_semana": (0.83, 0.91),
        "normal": (0.90, 0.94),
    }
    return factores[franja][0 if principal else 1]


def velocidad_modelada(arista, fecha):
    base = VELOCIDADES.get(categoria(arista.tipo_via), 25)
    limite = limite_velocidad(arista.velocidad)
    if limite is not None:
        base = min(base, limite)
    return max(7.0, base * factor_circulacion(arista.tipo_via, franja_horaria(fecha)))


def tiempo_arista(arista, fecha):
    velocidad = velocidad_modelada(arista, fecha)
    segundos = arista.distancia / (velocidad * 1000 / 3600)
    if arista.destino.semaforo:
        recargo = {"hora_pico": 28, "mediodia": 17, "normal": 12,
                   "fin_semana": 11, "noche": 6}
        segundos += recargo[franja_horaria(fecha)]
    return segundos + getattr(arista, "recargo_acceso", 0.0)


def _vector_direccion(arista, al_final):
    """Dirección de los últimos/primeros metros de una calle, cerca del cruce.

    Se conserva la geometría de la calle de OSM: un retorno dibujado dentro
    de una única calle no equivale a un giro entre dos aristas distintas.
    """
    puntos = arista.coordenadas
    if not puntos or len(puntos) < 2:
        puntos = [[arista.origen.lat, arista.origen.lon],
                  [arista.destino.lat, arista.destino.lon]]
    partes = list(zip(puntos, puntos[1:]))
    if al_final:
        partes.reverse()
    # Sumar segmentos cerca del punto de maniobra para evitar ruido del GPS.
    este = norte = distancia_acumulada = 0.0
    for desde, hasta in partes:
        lat_media = (desde[0] + hasta[0]) / 2
        dx = (hasta[1] - desde[1]) * 111195 * cos(radians(lat_media))
        dy = (hasta[0] - desde[0]) * 111195
        medida = (dx * dx + dy * dy) ** .5
        if medida < 1e-5:
            continue
        tomar = min(medida, 18 - distancia_acumulada)
        # En la dirección de la circulación, incluso al iterar al revés.
        este += dx * tomar / medida
        norte += dy * tomar / medida
        distancia_acumulada += tomar
        if distancia_acumulada >= 18 - 1e-6:
            break
    return este, norte


def penalizacion_giro(entrada, salida, fecha):
    """Demora supuesta según ángulo y franja horaria, NO legislación vial.

    Tema complementario: vectores y función atan2; búsqueda con estado.
    No se prohíben giros por el ángulo: algunas vueltas en U son legales.
    """
    if entrada is None:
        return 0.0
    dx1, dy1 = _vector_direccion(entrada, True)
    dx2, dy2 = _vector_direccion(salida, False)
    if dx1 * dx1 + dy1 * dy1 < .0001 or dx2 * dx2 + dy2 * dy2 < .0001:
        return 0.0
    angulo = degrees(atan2(dx1 * dy2 - dy1 * dx2,
                           dx1 * dx2 + dy1 * dy2))
    giro = abs(angulo)
    pico = franja_horaria(fecha) == "hora_pico"

    if giro < 30:
        return 0.0
    if giro < 65:
        return 5.0 if angulo > 0 else 3.0
    if giro < 140:
        return (22.0 if pico else 13.0) if angulo > 0 else (11.0 if pico else 7.0)
    if giro < 160:
        return 55.0 if pico else 35.0
    # Los retornos reales pueden ser legales, pero hay que reflejar su costo.
    return 190.0 if pico else 130.0


def nombre_franja(fecha):
    return {
        "hora_pico": "Hora pico · simulada", "mediodia": "Mediodía · simulado",
        "noche": "Noche · simulada", "fin_semana": "Fin de semana · simulado",
        "normal": "Tránsito habitual · simulado",
    }[franja_horaria(fecha)]
