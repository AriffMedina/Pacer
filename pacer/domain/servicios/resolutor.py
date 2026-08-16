"""Resuelve a qué sesión se refiere el usuario cuando habla.

`registrar_sesion` nunca acepta un identificador: el usuario dice "ayer corrí
12" y este código deduce la fila. Si hay ambigüedad devuelve opciones para que
el coach pregunte, nunca un error ni una suposición.

`hoy` se inyecta: el dominio no lee el reloj.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from pacer.domain.entidades.plan import Plan, Sesion

DIAS_DE_VENTANA = 7

DESPLAZAMIENTOS = {
    "hoy": 0,
    "ayer": 1,
    "anteayer": 2,
}

DIAS_SEMANA = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "miércoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "sábado": 5,
    "domingo": 6,
}


@dataclass(frozen=True)
class Resolucion:
    sesion: Sesion | None
    candidatas: tuple[Sesion, ...]

    @property
    def es_ambigua(self) -> bool:
        return self.sesion is None and len(self.candidatas) > 1


def resolver_sesion(plan: Plan, pista_temporal: str, hoy: date) -> Resolucion:
    """Ubica la sesión a la que apunta una pista hablada."""
    todas = tuple(sesion for semana in plan.semanas for sesion in semana.sesiones)
    objetivo = _interpretar_fecha(pista_temporal, hoy)

    if objetivo is not None:
        coincidencias = tuple(s for s in todas if s.fecha == objetivo)
        if len(coincidencias) == 1:
            return Resolucion(sesion=coincidencias[0], candidatas=coincidencias)
        return Resolucion(sesion=None, candidatas=coincidencias)

    return Resolucion(sesion=None, candidatas=_cercanas(todas, hoy))


def _interpretar_fecha(pista: str, hoy: date) -> date | None:
    """Traduce una pista en español a una fecha concreta, o None si no se entiende."""
    texto = pista.strip().lower()

    # De más larga a más corta: "ayer" es substring de "anteayer" y ganaría
    # la coincidencia equivocada.
    for palabra in sorted(DESPLAZAMIENTOS, key=len, reverse=True):
        if palabra in texto:
            return hoy - timedelta(days=DESPLAZAMIENTOS[palabra])

    for nombre, indice in DIAS_SEMANA.items():
        if nombre in texto:
            retroceso = (hoy.weekday() - indice) % 7
            return hoy - timedelta(days=retroceso or 7)

    return None


def _cercanas(sesiones: tuple[Sesion, ...], hoy: date) -> tuple[Sesion, ...]:
    """Sesiones dentro de la ventana reciente, como opciones para preguntar."""
    desde = hoy - timedelta(days=DIAS_DE_VENTANA)
    return tuple(s for s in sesiones if desde <= s.fecha <= hoy)
