"""Carreras que el corredor tiene apuntadas.

Distintas del plan: el plan se entrena para UNA carrera objetivo, pero la gente
tiene más fechas en la cabeza —el 10k del trabajo, la carrera del pueblo, la
que corre con un amigo—. Que vivan aquí y no en el perfil permite que el coach
las tenga en cuenta sin que cada una redefina el entrenamiento.

`distancia` es texto libre a propósito: existen carreras de 15k, de 8k y de
milla, y obligar a elegir entre cuatro opciones haría que la gente mienta.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Carrera:
    fecha: date
    nombre: str
    distancia: str | None = None
    nota: str = ""
    id: int | None = None
    """Lo asigna la base. En memoria una carrera recién dicha no tiene id."""


def pendientes(carreras: tuple[Carrera, ...], hoy: date) -> tuple[Carrera, ...]:
    """Las que todavía no ocurrieron, de la más próxima a la más lejana.

    La del día cuenta como pendiente: el día de la carrera es justo cuando más
    quieres verla en la agenda.
    """
    return tuple(sorted((c for c in carreras if c.fecha >= hoy), key=lambda c: c.fecha))
