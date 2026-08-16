"""Registro de lo que el corredor efectivamente hizo.

Registrar es anotar un hecho, no cambiar el plan: la versión no se toca. Si ese
hecho amerita un ajuste, lo decide el ajustador después, y ahí sí nace la v2.
"""

from dataclasses import replace

from pacer.domain.entidades.plan import Plan, Semana, Sensacion, Sesion


def registrar(
    plan: Plan, objetivo: Sesion, km: float, sensacion: Sensacion
) -> Plan:
    """Devuelve un plan nuevo con la sesión marcada como completada."""
    return replace(
        plan,
        semanas=tuple(_semana_con(semana, objetivo, km, sensacion) for semana in plan.semanas),
    )


def _semana_con(
    semana: Semana, objetivo: Sesion, km: float, sensacion: Sensacion
) -> Semana:
    if objetivo not in semana.sesiones:
        return semana

    return replace(
        semana,
        sesiones=tuple(
            replace(sesion, km=km, completada=True, sensacion=sensacion)
            if sesion == objetivo
            else sesion
            for sesion in semana.sesiones
        ),
    )
