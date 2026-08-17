"""Parar el entrenamiento unos días, y volver como se debe volver.

Una lesión, una gripe, un viaje. Sin esto el coach solo podía NARRAR el
descanso —"listo, ajusto el plan"— sin que el plan cambiara. Prometer un
cambio que no ocurre es lo peor que puede hacer un producto que maneja la
salud de alguien.

La regla que de verdad importa no es quitar las sesiones: es que VOLVER NO ES
RETOMAR. Se pierde forma parado, y regresar al volumen de antes es como se
recae. Por eso la primera semana de vuelta entra reducida.

Función pura. Devuelve una versión nueva del plan, con su motivo.
"""

from dataclasses import replace
from datetime import date, timedelta

from pacer.domain.entidades.plan import Plan, Semana, Sesion

# Cuánto se recorta la vuelta por cada semana parado. Cifra conservadora y
# deliberadamente discutible: el desentrenamiento real depende de la persona y
# del motivo. Se prefiere quedarse corto —volver suave nunca lesionó a nadie—.
PERDIDA_POR_SEMANA = 0.15

# Suelo: por larga que sea la parada, la vuelta no se convierte en un paseo.
# Por debajo de esto el plan deja de tener sentido y toca rehacerlo.
MINIMO_DE_VUELTA = 0.50

# La reducción aplica solo a la primera semana de vuelta. Después se sigue
# progresando: el parón cuesta, no borra el plan.
DIAS_DE_VUELTA = 7


class PausaImposible(Exception):
    """No tiene sentido pausar así, y hay un motivo que se puede explicar."""

    def __init__(self, motivo: str, razon: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo
        self.razon = razon


def pausar(plan: Plan, desde: date, hasta: date, hoy: date) -> Plan:
    """Quita las sesiones del periodo de descanso y suaviza la vuelta."""
    if hasta < desde:
        raise PausaImposible(
            "el periodo está al revés",
            "Esas fechas están invertidas. Dime desde qué día y hasta qué día "
            "tienes que parar.",
        )

    todas = [s for semana in plan.semanas for s in semana.sesiones]
    if hasta < hoy:
        raise PausaImposible(
            "el periodo ya pasó",
            "Ese descanso ya quedó atrás. Si te perdiste sesiones no pasa "
            "nada: seguimos desde donde estás, sin intentar recuperarlas.",
        )

    quedan = [
        s for s in todas if s.completada or not (desde <= s.fecha <= hasta)
    ]
    if not any(not s.completada for s in quedan):
        raise PausaImposible(
            "no quedaría ninguna sesión",
            "Ese descanso se come el plan entero. Cuando estés listo lo "
            "hacemos nuevo desde donde estés, en vez de dejar uno vacío.",
        )

    parado = max((hasta - desde).days + 1, 1)
    factor = max(MINIMO_DE_VUELTA, 1 - PERDIDA_POR_SEMANA * (parado / 7))
    fin_de_la_vuelta = hasta + timedelta(days=DIAS_DE_VUELTA)

    return Plan(
        version=plan.version + 1,
        motivo_cambio=(
            f"Descanso del {desde.isoformat()} al {hasta.isoformat()}. "
            "La vuelta entra más suave: se pierde forma parado y volver al "
            "volumen de antes es como se recae."
        ),
        semanas=tuple(
            _semana_sin(semana, desde, hasta, fin_de_la_vuelta, factor)
            for semana in plan.semanas
        ),
    )


def _semana_sin(
    semana: Semana, desde: date, hasta: date, fin_de_la_vuelta: date, factor: float
) -> Semana:
    return replace(
        semana,
        sesiones=tuple(
            _ajustada(s, hasta, fin_de_la_vuelta, factor)
            for s in semana.sesiones
            if s.completada or not (desde <= s.fecha <= hasta)
        ),
    )


def _ajustada(
    sesion: Sesion, hasta: date, fin_de_la_vuelta: date, factor: float
) -> Sesion:
    """Recorta solo las sesiones de la primera semana de vuelta."""
    if sesion.completada or not (hasta < sesion.fecha <= fin_de_la_vuelta):
        return sesion
    return replace(sesion, km=round(sesion.km * factor, 1))
