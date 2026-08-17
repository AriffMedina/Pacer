"""Carreras que el corredor tiene apuntadas.

Distintas del plan: el plan se entrena para UNA carrera objetivo, pero la gente
tiene más fechas en la cabeza —el 10k del trabajo, la carrera del pueblo, la
que corre con un amigo—. Que vivan aquí y no en el perfil permite que el coach
las tenga en cuenta sin que cada una redefina el entrenamiento.

La distancia son KILÓMETROS, no texto. Empezó siendo texto libre para no
obligar a nadie a elegir entre cuatro opciones, y salió mal: "15k", "15 k" y
"15km" son la misma carrera y el sistema las trataba como tres cosas distintas,
así que no podía decir con qué plan se entrena ninguna. Un número admite
cualquier distancia Y se puede razonar sobre él. Con qué plan se entrena cada
una lo decide `domain/servicios/categoria.py`.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Carrera:
    fecha: date
    nombre: str
    distancia_km: float | None = None
    nota: str = ""
    id: int | None = None
    """Lo asigna la base. En memoria una carrera recién dicha no tiene id."""

    es_objetivo: bool = False
    """Si es LA carrera para la que se está entrenando.

    No se guarda en la carrera: se deduce comparando con la fecha objetivo del
    perfil, que es donde vive el plan. Viaja aquí para que la interfaz y el
    coach puedan decir cuál es sin volver a cruzar los datos ellos mismos.
    """


def pendientes(carreras: tuple[Carrera, ...], hoy: date) -> tuple[Carrera, ...]:
    """Las que todavía no ocurrieron, de la más próxima a la más lejana.

    La del día cuenta como pendiente: el día de la carrera es justo cuando más
    quieres verla en la agenda.
    """
    return tuple(sorted((c for c in carreras if c.fecha >= hoy), key=lambda c: c.fecha))
