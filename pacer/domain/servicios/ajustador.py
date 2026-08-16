"""El corazón: el plan cambia solo cuando una sesión sale mal.

El ajuste lo decide este código, nunca el modelo de lenguaje. El modelo
solamente redacta la explicación hablada leyendo `motivo_cambio`.
"""

from dataclasses import replace

from pacer.domain.entidades.plan import Plan, Semana, Sesion
from pacer.domain.reglas.descarga import FACTOR_VOLUMEN

SENSACIONES_QUE_BAJAN_CARGA = ("muy_dura", "con_dolor")


def ajustar(plan: Plan, reporte: Sesion) -> Plan:
    """Devuelve un plan nuevo si el reporte lo amerita, o el mismo plan."""
    if reporte.sensacion not in SENSACIONES_QUE_BAJAN_CARGA:
        return plan

    indice = _indice_de_la_semana(plan, reporte)
    if indice is None:
        return plan

    semanas = list(plan.semanas)
    semanas[indice] = _con_volumen_reducido(semanas[indice])

    motivo = (
        f"reportaste '{reporte.sensacion}' el {reporte.fecha.isoformat()}; "
        f"bajé el volumen de la semana {semanas[indice].numero}"
    )
    return Plan(
        version=plan.version + 1,
        semanas=tuple(semanas),
        motivo_cambio=motivo,
    )


def _indice_de_la_semana(plan: Plan, reporte: Sesion) -> int | None:
    """Ubica la semana que contiene la sesión reportada."""
    for indice, semana in enumerate(plan.semanas):
        if any(sesion.fecha == reporte.fecha for sesion in semana.sesiones):
            return indice
    return None


def _con_volumen_reducido(semana: Semana) -> Semana:
    """Recorta kilómetros manteniendo el número de días y el tipo de sesión."""
    sesiones = tuple(
        replace(sesion, km=round(sesion.km * FACTOR_VOLUMEN, 1))
        for sesion in semana.sesiones
    )
    return replace(semana, sesiones=sesiones)
