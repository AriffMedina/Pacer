"""Progresión de volumen semanal.

El techo del 10% es operativo, no un escudo contra lesiones: un ECA (Buist
2008) no encontró efecto protector. La restricción con evidencia real es a
nivel de sesión y vive en `sesion.py`.
"""

from pacer.domain.reglas.descarga import FACTOR_VOLUMEN

PROGRESION_SEMANAL_MAX = 1.10


def siguiente_volumen(km_actual: int, es_descarga: bool) -> int:
    """Kilómetros de la semana siguiente según si toca descarga o no."""
    if es_descarga:
        return round(km_actual * FACTOR_VOLUMEN)
    return round(km_actual * PROGRESION_SEMANAL_MAX)
