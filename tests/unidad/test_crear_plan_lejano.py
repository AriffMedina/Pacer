"""Carreras que están MUY lejos.

Un bloque de entrenamiento tiene un largo máximo: pasado ese punto se llega al
pico demasiado pronto y se pierde forma antes de la carrera. Pero eso no
convierte una carrera a siete meses en imposible: convierte al plan en algo que
empieza más adelante. Negarse era la conducta equivocada.
"""

from datetime import date, timedelta

import pytest

from pacer.application.casos_uso.crear_plan import crear_plan, semanas_hasta
from pacer.domain.entidades.perfil import Perfil
from pacer.domain.reglas.duracion import SEMANAS, PlanImposible

HOY = date(2026, 8, 16)


def perfil(objetivo="10k", nivel="principiante", meses=7):  # type: ignore[no-untyped-def]
    return Perfil(
        objetivo=objetivo,
        nivel=nivel,
        dias_disponibles=4,
        km_semana=20,
        fecha_carrera=HOY + timedelta(weeks=meses * 4),
    )


def test_una_carrera_muy_lejana_no_se_rechaza() -> None:
    """El caso reportado: 30 semanas para un 10K devolvían "no puedo"."""
    plan = crear_plan(perfil(meses=7), hoy=HOY)

    assert plan is not None
    assert len(plan.semanas) == SEMANAS["10k"]["max"]


def test_el_plan_lejano_arranca_mas_adelante_no_hoy() -> None:
    """Es la diferencia entre "no puedo" y "empezamos en diciembre"."""
    objetivo = perfil(meses=7)

    plan = crear_plan(objetivo, hoy=HOY)

    primera = plan.semanas[0].sesiones[0].fecha
    assert primera > HOY
    # Y termina pegado a la carrera, que es de lo que se trata.
    ultima = plan.semanas[-1].sesiones[-1].fecha
    assert objetivo.fecha_carrera is not None
    assert 0 <= (objetivo.fecha_carrera - ultima).days <= 7


@pytest.mark.parametrize("distancia", ["5k", "10k", "21k", "maraton"])
def test_ninguna_distancia_se_pasa_de_su_bloque_maximo(distancia: str) -> None:
    plan = crear_plan(perfil(objetivo=distancia, nivel="avanzado", meses=10), hoy=HOY)

    assert len(plan.semanas) == SEMANAS[distancia]["max"]


def test_una_carrera_dentro_del_rango_sigue_arrancando_hoy() -> None:
    """Lo de siempre no cambia: si cabe, se empieza ya."""
    objetivo = perfil(meses=3)

    plan = crear_plan(objetivo, hoy=HOY)

    assert len(plan.semanas) == semanas_hasta(objetivo.fecha_carrera, HOY)  # type: ignore[arg-type]
    assert plan.semanas[0].sesiones[0].fecha >= HOY
    assert plan.semanas[0].sesiones[0].fecha < HOY + timedelta(days=7)


def test_lo_que_sigue_siendo_imposible_lo_sigue_siendo() -> None:
    """Que sobre tiempo no puede volver seguro lo que no lo es. Un maratón
    desde cero se rechaza aunque falten dos años."""
    with pytest.raises(PlanImposible) as rechazo:
        crear_plan(perfil(objetivo="maraton", nivel="nuevo", meses=24), hoy=HOY)

    assert rechazo.value.minimo is None


def test_una_carrera_demasiado_cerca_se_sigue_rechazando() -> None:
    with pytest.raises(PlanImposible) as rechazo:
        crear_plan(perfil(objetivo="21k", nivel="nuevo", meses=1), hoy=HOY)

    assert rechazo.value.minimo == 20
