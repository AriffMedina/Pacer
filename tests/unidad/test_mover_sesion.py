"""Mover una sesión de día.

La vida pasa: un martes con junta, un domingo de viaje. Sin esto el coach
inventaba —decía que sí sin cambiar nada, o se sacaba de la manga un descanso
obligatorio— y se contradecía al turno siguiente.

Lo que NO se negocia es la alternancia fuerte/suave: dos sesiones duras
pegadas es como se lesiona la gente, y eso no lo decide una conversación.
"""

from datetime import date

import pytest

from pacer.domain.entidades.plan import Plan, Semana, Sesion
from pacer.domain.servicios.mover import MovimientoImposible, mover_sesion

HOY = date(2026, 8, 16)  # domingo


def sesion(dia: int, tipo: str = "facil", km: float = 6.0, hecha: bool = False) -> Sesion:
    return Sesion(fecha=date(2026, 8, dia), tipo=tipo, km=km, completada=hecha)  # type: ignore[arg-type]


def plan_con(*sesiones: Sesion) -> Plan:
    return Plan(version=1, semanas=(Semana(numero=1, sesiones=sesiones, bloque="base"),))


def fechas(plan: Plan) -> list[date]:
    return sorted(s.fecha for semana in plan.semanas for s in semana.sesiones)


# --- lo que sí se puede -------------------------------------------------


def test_mueve_una_sesion_a_un_dia_libre() -> None:
    plan = plan_con(sesion(18), sesion(20))

    movido = mover_sesion(plan, date(2026, 8, 18), date(2026, 8, 17), hoy=HOY)

    assert fechas(movido) == [date(2026, 8, 17), date(2026, 8, 20)]


def test_la_sesion_conserva_su_tipo_y_sus_kilometros() -> None:
    plan = plan_con(sesion(18, "calidad", km=9.6), sesion(22))

    movido = mover_sesion(plan, date(2026, 8, 18), date(2026, 8, 19), hoy=HOY)

    movida = next(s for semana in movido.semanas for s in semana.sesiones if s.fecha == date(2026, 8, 19))
    assert movida.tipo == "calidad"
    assert movida.km == 9.6


def test_mover_no_toca_las_demas_sesiones() -> None:
    plan = plan_con(sesion(18), sesion(20, "calidad"), sesion(22, "largo"))

    movido = mover_sesion(plan, date(2026, 8, 18), date(2026, 8, 17), hoy=HOY)

    assert fechas(movido) == [date(2026, 8, 17), date(2026, 8, 20), date(2026, 8, 22)]


def test_una_facil_puede_quedar_pegada_a_otra_facil() -> None:
    """Dos suaves seguidas son un plan normal, no un riesgo."""
    plan = plan_con(sesion(18), sesion(21))

    movido = mover_sesion(plan, date(2026, 8, 21), date(2026, 8, 19), hoy=HOY)

    assert fechas(movido) == [date(2026, 8, 18), date(2026, 8, 19)]


# --- lo que no ----------------------------------------------------------


def test_no_se_mueve_al_pasado() -> None:
    plan = plan_con(sesion(18))

    with pytest.raises(MovimientoImposible) as rechazo:
        mover_sesion(plan, date(2026, 8, 18), date(2026, 8, 15), hoy=HOY)

    assert rechazo.value.razon


def test_no_se_mueve_a_un_dia_que_ya_tiene_sesion() -> None:
    """Doblar dos sesiones en un día es multiplicar la carga de ese día."""
    plan = plan_con(sesion(18), sesion(20))

    with pytest.raises(MovimientoImposible):
        mover_sesion(plan, date(2026, 8, 18), date(2026, 8, 20), hoy=HOY)


def test_no_se_pega_una_dura_a_otra_dura() -> None:
    """Calidad y fondo necesitan un día blando en medio. Es la regla que el
    modelo se inventaba a medias y luego se desdecía."""
    plan = plan_con(sesion(18, "calidad"), sesion(22, "largo"))

    with pytest.raises(MovimientoImposible) as rechazo:
        mover_sesion(plan, date(2026, 8, 22), date(2026, 8, 19), hoy=HOY)

    assert "duras" in rechazo.value.razon.lower() or "fuerte" in rechazo.value.razon.lower()


def test_una_dura_si_puede_ir_junto_a_una_facil() -> None:
    plan = plan_con(sesion(18), sesion(22, "largo"))

    movido = mover_sesion(plan, date(2026, 8, 22), date(2026, 8, 19), hoy=HOY)

    assert fechas(movido) == [date(2026, 8, 18), date(2026, 8, 19)]


def test_no_se_mueve_una_sesion_ya_reportada() -> None:
    """Ya ocurrió. Moverla reescribiría el pasado."""
    plan = plan_con(sesion(14, hecha=True), sesion(18))

    with pytest.raises(MovimientoImposible):
        mover_sesion(plan, date(2026, 8, 14), date(2026, 8, 19), hoy=HOY)


def test_una_sesion_que_no_existe_no_se_mueve() -> None:
    plan = plan_con(sesion(18))

    with pytest.raises(MovimientoImposible):
        mover_sesion(plan, date(2026, 8, 19), date(2026, 8, 21), hoy=HOY)


def test_cada_rechazo_trae_su_motivo_en_castellano() -> None:
    """El coach lo explica con sus palabras; sin motivo diría "no me deja"."""
    plan = plan_con(sesion(18, "calidad"), sesion(20, "largo"))

    for origen, destino in [
        (date(2026, 8, 18), date(2026, 8, 15)),
        (date(2026, 8, 18), date(2026, 8, 20)),
        (date(2026, 8, 20), date(2026, 8, 19)),
    ]:
        with pytest.raises(MovimientoImposible) as rechazo:
            mover_sesion(plan, origen, destino, hoy=HOY)
        assert len(rechazo.value.razon) > 25
