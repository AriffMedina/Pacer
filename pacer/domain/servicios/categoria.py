"""Con qué plan se entrena una carrera de una distancia cualquiera.

El generador conoce cuatro distancias: 5k, 10k, 21k y maratón. Esa lista NO se
amplía inventando parámetros: los topes de fondo, la progresión y el tapering
salen de evidencia para esas distancias, e interpolar números para un 3.5 km
sería fabricar ciencia del entrenamiento.

Pero el límite del motor no puede filtrarse hasta el corredor. Una carrera de
3.5 km se entrena como un 5K —eso es verdad deportiva, no un parche— y lo que
faltaba era decirlo. Este servicio traduce cualquier distancia a la categoría
cuyo plan le corresponde, y da la frase para explicarlo.

Fuera del rango devuelve None a propósito. Un 300 m es una prueba de pista y un
100 km es ultrafondo: darles el plan de 5k o de maratón sería peor que negarse.
"""

from pacer.domain.entidades.perfil import Objetivo

# Distancia real de cada categoría. Es lo que define las fronteras.
KM_OFICIALES: dict[Objetivo, float] = {
    "5k": 5.0,
    "10k": 10.0,
    "21k": 21.1,
    "maraton": 42.2,
}

NOMBRES: dict[Objetivo, str] = {
    "5k": "5K",
    "10k": "10K",
    "21k": "medio maratón",
    "maraton": "maratón",
}

# Las fronteras son los puntos medios entre distancias oficiales: una carrera
# está más cerca de una que de otra, y esa es toda la regla.
FRONTERAS: tuple[tuple[float, Objetivo], ...] = (
    (7.5, "5k"),      # medio entre 5 y 10
    (15.55, "10k"),   # medio entre 10 y 21.1
    (31.65, "21k"),   # medio entre 21.1 y 42.2
)

# Debajo de esto es pista, no fondo: otra preparación por completo.
KM_MINIMO = 2.0
# Un poco por encima del maratón todavía se prepara como maratón. Más allá es
# ultrafondo, y eso Pacer no lo cubre.
KM_MAXIMO = 45.0


def km_oficiales() -> dict[Objetivo, float]:
    return dict(KM_OFICIALES)


def categoria_de_km(km: float) -> Objetivo | None:
    """La categoría cuyo plan corresponde a esa distancia, o None si no hay."""
    if not KM_MINIMO <= km <= KM_MAXIMO:
        return None

    for tope, objetivo in FRONTERAS:
        if km < tope:
            return objetivo
    return "maraton"


def como_se_entrena(km: float) -> str:
    """La frase que el coach y la interfaz usan para explicar el mapeo.

    Existe para que no vuelva a pasar lo de decir "es una carrera de 3.5 km" y
    a renglón seguido "no puedo hacer planes de 5 km". O se entrena con uno de
    los cuatro planes, o se dice claramente que no se cubre.
    """
    categoria = categoria_de_km(km)

    if categoria is None:
        if km < KM_MINIMO:
            return "es una prueba de pista, no de fondo: no la cubro"
        return "es ultrafondo: no la cubro"

    if abs(km - KM_OFICIALES[categoria]) < 0.15:
        return f"es un {NOMBRES[categoria]}"
    return f"se entrena como un {NOMBRES[categoria]}"
