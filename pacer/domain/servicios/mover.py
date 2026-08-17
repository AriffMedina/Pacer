"""Cambiar una sesión de día.

La vida pasa: un martes con junta, un domingo de viaje. Que el plan no se
pueda acomodar es lo que hace que la gente lo abandone, así que se puede
mover — pero dentro de reglas, y las reglas viven aquí y no en la
conversación.

La que no se negocia es la alternancia fuerte/suave: dos sesiones duras
pegadas es como se lesiona la gente. Antes el coach se inventaba esa regla a
medias, la aplicaba y al turno siguiente se desdecía. Escrita en código dice
siempre lo mismo.

Devuelve un plan nuevo. No muta: la sesión cambia de día, no de identidad.
"""

from dataclasses import replace
from datetime import date, timedelta

from pacer.domain.entidades.plan import Plan, Semana, Sesion

# Las que piden un día blando antes y después.
DURAS = frozenset({"calidad", "largo"})


class MovimientoImposible(Exception):
    """No se puede mover ahí, y hay un motivo que se puede explicar."""

    def __init__(self, motivo: str, razon: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo
        self.razon = razon
        """El porqué en lenguaje humano. Sin esto el coach diría "no me deja"."""


def mover_sesion(plan: Plan, origen: date, destino: date, hoy: date) -> Plan:
    """Mueve la sesión del día `origen` al día `destino`."""
    todas = [s for semana in plan.semanas for s in semana.sesiones]
    sesion = next((s for s in todas if s.fecha == origen), None)

    if sesion is None:
        raise MovimientoImposible(
            "no hay sesión ese día",
            "Ese día no tienes nada programado, así que no hay qué mover.",
        )
    if sesion.completada:
        raise MovimientoImposible(
            "la sesión ya se reportó",
            "Esa sesión ya la corriste y quedó registrada. Moverla sería "
            "reescribir lo que ya pasó; lo que sí puedo es acomodar las que "
            "vienen.",
        )
    if destino < hoy:
        raise MovimientoImposible(
            "el destino ya pasó",
            "No puedo mandarte a entrenar un día que ya pasó. Dime un día de "
            "hoy en adelante.",
        )
    if any(s.fecha == destino for s in todas if s is not sesion):
        raise MovimientoImposible(
            "ese día ya tiene sesión",
            "Ese día ya tienes entrenamiento. Juntar dos en el mismo día "
            "duplica la carga de golpe, que es justo lo que el plan reparte a "
            "propósito.",
        )

    _exigir_alternancia(todas, sesion, destino)

    return Plan(
        version=plan.version,
        motivo_cambio=plan.motivo_cambio,
        semanas=tuple(_semana_con(semana, sesion, destino) for semana in plan.semanas),
    )


def _exigir_alternancia(todas: list[Sesion], sesion: Sesion, destino: date) -> None:
    """Una sesión dura necesita un día blando antes y después."""
    if sesion.tipo not in DURAS:
        return

    vecinas = [
        s
        for s in todas
        if s is not sesion and abs((s.fecha - destino).days) == 1 and s.tipo in DURAS
    ]
    if vecinas:
        raise MovimientoImposible(
            "quedarían dos sesiones duras seguidas",
            "Ahí te quedarían dos sesiones fuertes en días seguidos, y el "
            "cuerpo se adapta en el descanso, no en el esfuerzo. Entre una "
            "dura y otra necesitas un día suave o de descanso. Dime otro día y "
            "te la acomodo.",
        )


def _semana_con(semana: Semana, sesion: Sesion, destino: date) -> Semana:
    if sesion not in semana.sesiones:
        return semana

    return replace(
        semana,
        sesiones=tuple(
            replace(s, fecha=destino) if s is sesion else s for s in semana.sesiones
        ),
    )


def dias_libres(plan: Plan, desde: date, cuantos: int = 10) -> tuple[date, ...]:
    """Días sin sesión en la ventana que viene.

    Se le ofrecen al coach para que proponga alternativas concretas en vez de
    preguntar "¿qué otro día te viene bien?" y volver a chocar con la regla.
    """
    ocupados = {s.fecha for semana in plan.semanas for s in semana.sesiones}
    return tuple(
        desde + timedelta(days=n)
        for n in range(cuantos)
        if desde + timedelta(days=n) not in ocupados
    )
