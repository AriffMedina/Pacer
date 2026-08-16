"""Entidades puras del plan. Sin ORM, sin dependencias externas.

Los planes se versionan, no se mutan: cada ajuste produce un Plan nuevo y la
versión anterior queda archivada con su motivo.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

Sensacion = Literal["facil", "normal", "pesada", "muy_dura", "con_dolor"]
TipoSesion = Literal["facil", "calidad", "largo"]


@dataclass(frozen=True)
class Sesion:
    fecha: date
    tipo: TipoSesion
    km: float
    completada: bool = False
    sensacion: Sensacion | None = None


@dataclass(frozen=True)
class Semana:
    numero: int
    sesiones: tuple[Sesion, ...]
    es_descarga: bool = False
    bloque: str = ""
    """base, construccion, pico o tapering. El plan se describe a sí mismo."""

    recortada: bool = False
    """La restricción del long run bajó esta semana por debajo de su objetivo.

    Se registra porque cambia cómo se lee la semana siguiente: volver a la
    tendencia después de un recorte de seguridad no es una progresión, igual
    que no lo es salir de una descarga.
    """

    @property
    def largo(self) -> Sesion | None:
        return next((s for s in self.sesiones if s.tipo == "largo"), None)

    @property
    def km_total(self) -> float:
        return round(sum(sesion.km for sesion in self.sesiones), 1)


@dataclass(frozen=True)
class Plan:
    version: int
    semanas: tuple[Semana, ...]
    motivo_cambio: str | None = None
