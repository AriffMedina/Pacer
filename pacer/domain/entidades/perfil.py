"""Perfil del corredor. Todo lo que el código necesita saber para decidir."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

Objetivo = Literal["5k", "10k", "21k", "maraton"]
Nivel = Literal["nuevo", "principiante", "intermedio", "avanzado"]


@dataclass(frozen=True)
class Perfil:
    objetivo: Objetivo | None = None
    nivel: Nivel | None = None
    dias_disponibles: int | None = None
    km_semana: int | None = None
    fecha_carrera: date | None = None
    dolor_actual: bool = False
