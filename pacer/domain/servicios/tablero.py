"""Lo que el tablero muestra, derivado del plan y nada más.

Racha, adherencia y actividad son hechos de entrenamiento, no adornos de la
vista: quien decide si una semana va al 82% es el dominio, no el JavaScript.
Ponerlo aquí es lo que permite testearlo y lo que evita que la web y Telegram
cuenten historias distintas sobre el mismo corredor.

Función pura: se le pasa `hoy`, no lee el reloj.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from pacer.domain.entidades.plan import Plan, Sesion

EstadoDelDia = Literal["hecha", "pendiente", "perdida", "descanso"]

# Cuatro entradas llenan la tarjeta sin obligar a hacer scroll dentro de ella.
MAXIMA_ACTIVIDAD = 4

INICIALES = ("L", "M", "M", "J", "V", "S", "D")
ABREVIATURAS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
MESES = (
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
)

# Más allá de esto se pierde la cuenta y una fecha dice más que "hace 12 días".
DIAS_EN_PALABRAS = 6


@dataclass(frozen=True)
class DiaDeLaSemana:
    inicial: str
    fecha: date
    estado: EstadoDelDia


@dataclass(frozen=True)
class ProximaSesion:
    fecha: date
    tipo: str
    km: float
    cuando: str


@dataclass(frozen=True)
class Hecho:
    fecha: date
    tipo: str
    km: float
    sensacion: str | None
    cuando: str


@dataclass(frozen=True)
class Tablero:
    racha: int
    semana: tuple[DiaDeLaSemana, ...]
    proxima: ProximaSesion | None
    km_hechos: float
    km_planeados: float
    porcentaje: int
    actividad: tuple[Hecho, ...]


def resumir(plan: Plan | None, hoy: date) -> Tablero:
    """El estado del corredor en los términos en que se le va a mostrar."""
    sesiones = (
        tuple(s for semana in plan.semanas for s in semana.sesiones) if plan else ()
    )
    ordenadas = tuple(sorted(sesiones, key=lambda s: s.fecha))
    de_la_semana = tuple(s for s in ordenadas if _es_de_la_semana_de(s.fecha, hoy))

    planeados = round(sum(s.km for s in de_la_semana), 1)
    hechos = round(sum(s.km for s in de_la_semana if s.completada), 1)

    return Tablero(
        racha=_racha(ordenadas, hoy),
        semana=_semana(ordenadas, hoy),
        proxima=_proxima(ordenadas, hoy),
        km_hechos=hechos,
        km_planeados=planeados,
        # No lleva tope: `km` es lo planeado y `completada` es el reporte, así
        # que lo hecho es un subconjunto de lo planeado y esto no pasa de 100.
        porcentaje=round(hechos / planeados * 100) if planeados else 0,
        actividad=_actividad(ordenadas, hoy),
    )


def _racha(ordenadas: tuple[Sesion, ...], hoy: date) -> int:
    """Sesiones cumplidas seguidas, contando hacia atrás desde la más reciente.

    La de hoy sin reportar no rompe nada: quien no salió a las ocho de la mañana
    todavía tiene el día por delante, y una racha que castiga eso miente.
    """
    pasadas = [s for s in ordenadas if s.fecha <= hoy]

    racha = 0
    for sesion in reversed(pasadas):
        if sesion.completada:
            racha += 1
        elif sesion.fecha == hoy:
            continue  # aún tiene el día
        else:
            break
    return racha


def _semana(ordenadas: tuple[Sesion, ...], hoy: date) -> tuple[DiaDeLaSemana, ...]:
    lunes = hoy - timedelta(days=hoy.weekday())

    dias = []
    for indice in range(7):
        fecha = lunes + timedelta(days=indice)
        del_dia = [s for s in ordenadas if s.fecha == fecha]
        dias.append(
            DiaDeLaSemana(
                inicial=INICIALES[indice],
                fecha=fecha,
                estado=_estado(del_dia, fecha, hoy),
            )
        )
    return tuple(dias)


def _estado(del_dia: list[Sesion], fecha: date, hoy: date) -> EstadoDelDia:
    if not del_dia:
        return "descanso"
    if any(s.completada for s in del_dia):
        return "hecha"
    return "perdida" if fecha < hoy else "pendiente"


def _proxima(ordenadas: tuple[Sesion, ...], hoy: date) -> ProximaSesion | None:
    siguiente = next(
        (s for s in ordenadas if s.fecha >= hoy and not s.completada), None
    )
    if siguiente is None:
        return None

    return ProximaSesion(
        fecha=siguiente.fecha,
        tipo=siguiente.tipo,
        km=siguiente.km,
        cuando=_cuando_viene(siguiente.fecha, hoy),
    )


def _actividad(ordenadas: tuple[Sesion, ...], hoy: date) -> tuple[Hecho, ...]:
    hechas = [s for s in ordenadas if s.completada]
    return tuple(
        Hecho(
            fecha=s.fecha,
            tipo=s.tipo,
            km=s.km,
            sensacion=s.sensacion,
            cuando=_cuando_fue(s.fecha, hoy),
        )
        for s in reversed(hechas[-MAXIMA_ACTIVIDAD:])
    )


def _es_de_la_semana_de(fecha: date, hoy: date) -> bool:
    lunes = hoy - timedelta(days=hoy.weekday())
    return lunes <= fecha <= lunes + timedelta(days=6)


def _cuando_viene(fecha: date, hoy: date) -> str:
    faltan = (fecha - hoy).days
    if faltan == 0:
        return "Hoy"
    if faltan == 1:
        return "Mañana"
    return f"{ABREVIATURAS[fecha.weekday()]} {fecha.day}"


def _cuando_fue(fecha: date, hoy: date) -> str:
    pasaron = (hoy - fecha).days
    if pasaron == 0:
        return "Hoy"
    if pasaron == 1:
        return "Ayer"
    if pasaron <= DIAS_EN_PALABRAS:
        return f"Hace {pasaron} días"
    return f"{fecha.day} {MESES[fecha.month - 1]}"
