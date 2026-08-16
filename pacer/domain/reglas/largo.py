"""Restricciones del long run. La parte con evidencia real del generador.

`PROGRESION_SESION_MAX` sale de Nielsen et al. 2025 (Garmin-RunSafe, 5.205
corredores, 588.071 sesiones): el predictor de lesión no es el volumen semanal
sino la distancia de UNA sesión comparada con la salida más larga de los
últimos 30 días. Superarla entre 10 y 30% se asoció a +64% de riesgo; más del
100%, a +128%.

Es evidencia observacional: muestra asociación entre saltos grandes y más
lesiones, no demuestra que un incremento ≤10% sea seguro. Se documenta como
restricción operacional derivada de evidencia observacional, no como límite
probado.
"""

# Grado B — restricción operacional derivada de evidencia observacional.
PROGRESION_SESION_MAX = 1.10

# La ventana del estudio son 30 días. Se modela como 4 semanas de plan.
SEMANAS_DE_VENTANA = 4

# Grado C — topes de convención (`paramethers.md` §8).
LARGO_PCT = {"5k": 0.28, "10k": 0.30, "21k": 0.33, "maraton": 0.33}
LARGO_TOPE_KM = {"5k": 12.0, "10k": 18.0, "21k": 24.0, "maraton": 32.0}

# Límite operativo conservador de Pacer, NO una frontera fisiológica universal:
# por encima de ~3 h el daño muscular crece sin beneficio aeróbico proporcional.
LARGO_TOPE_HORAS = 3.0

# SUPUESTO OPERATIVO, no evidencia: sin un tiempo de referencia del corredor no
# se puede calcular su ritmo fácil real. 6:30 min/km es una estimación
# conservadora para corredor recreativo. Cuando el perfil incluya un tiempo de
# referencia, esto se sustituye por el ritmo estimado de esa persona.
RITMO_FACIL_ESTIMADO_MIN_KM = 6.5


def tope_por_tiempo() -> float:
    """Kilómetros que caben en el límite de horas al ritmo fácil estimado."""
    return LARGO_TOPE_HORAS * 60 / RITMO_FACIL_ESTIMADO_MIN_KM


def largo_maximo_permitido(distancia: str, largos_recientes: list[float]) -> float:
    """El techo del long run de esta semana.

    Manda el más restrictivo de tres: el tope por distancia, el tope por tiempo,
    y el crecimiento sobre las salidas más largas de las últimas 4 semanas.
    """
    topes = [LARGO_TOPE_KM[distancia], tope_por_tiempo()]

    ventana = largos_recientes[-SEMANAS_DE_VENTANA:]
    if ventana:
        topes.append(max(ventana) * PROGRESION_SESION_MAX)

    return min(topes)
