"""Crea el plan a partir del perfil. Traduce perfil → parámetros del generador.

Las semanas no las elige el usuario ni el modelo: salen de la fecha de la
carrera. Si no alcanzan, la compuerta dura de §2.2 lo rechaza y el coach
ofrece alternativas en vez de comprimir el plan.
"""

from datetime import date

from pacer.application.guardarrailes.reglas import campos_faltantes
from pacer.domain.entidades.perfil import Perfil
from pacer.domain.entidades.plan import Plan
from pacer.domain.servicios.generador_plan import generar_plan

DIAS_POR_DEFECTO = 4


def crear_plan(perfil: Perfil, hoy: date) -> Plan:
    """Genera el plan v1. Lanza `PlanImposible` si la meta no es alcanzable."""
    faltan = campos_faltantes(perfil)
    if faltan:
        raise ValueError(f"perfil incompleto: faltan {', '.join(faltan)}")

    # mypy no deduce que campos_faltantes ya garantizó que no son None.
    assert perfil.objetivo is not None
    assert perfil.nivel is not None
    assert perfil.fecha_carrera is not None
    assert perfil.km_semana is not None

    semanas = semanas_hasta(perfil.fecha_carrera, hoy)

    return generar_plan(
        distancia=perfil.objetivo,
        nivel=perfil.nivel,
        semanas=semanas,
        km_semana=perfil.km_semana,
        dias=perfil.dias_disponibles or DIAS_POR_DEFECTO,
        inicio=hoy,
    )


def semanas_hasta(fecha_carrera: date, hoy: date) -> int:
    """Semanas completas entre hoy y la carrera."""
    return max((fecha_carrera - hoy).days // 7, 0)
