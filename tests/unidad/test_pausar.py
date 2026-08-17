"""Parar el entrenamiento unos días y volver.

El caso reportado: "me duele el pie, el doctor me mandó descansar una semana".
El coach contestó "listo, ajusto el plan" y el plan no cambió NADA. Prometer un
cambio que no ocurre es lo peor que puede hacer esto.

La regla de fondo: volver de un parón NO es retomar donde lo dejaste. Se pierde
forma parado, y volver al volumen de antes es como se recae.
"""

from datetime import date

import pytest

from pacer.domain.entidades.plan import Plan, Semana, Sesion
from pacer.domain.servicios.pausa import PausaImposible, pausar

HOY = date(2026, 8, 16)  # domingo


def sesion(dia: int, tipo: str = "facil", km: float = 6.0, hecha: bool = False) -> Sesion:
    return Sesion(fecha=date(2026, 8, dia), tipo=tipo, km=km, completada=hecha)  # type: ignore[arg-type]


def plan_con(*sesiones: Sesion) -> Plan:
    return Plan(version=2, semanas=(Semana(numero=1, sesiones=sesiones, bloque="base"),))


def de(plan: Plan) -> list[Sesion]:
    return sorted(
        (s for semana in plan.semanas for s in semana.sesiones), key=lambda s: s.fecha
    )


# --- lo que quita -------------------------------------------------------


def test_quita_las_sesiones_del_periodo_de_descanso() -> None:
    plan = plan_con(sesion(18), sesion(20), sesion(22), sesion(25))

    parado = pausar(plan, desde=date(2026, 8, 17), hasta=date(2026, 8, 22), hoy=HOY)

    assert [s.fecha for s in de(parado)] == [date(2026, 8, 25)]


def test_no_borra_lo_que_ya_se_corrio() -> None:
    """Lo reportado es historia. Borrarlo sería reescribir el pasado."""
    plan = plan_con(sesion(14, hecha=True), sesion(18), sesion(29))

    parado = pausar(plan, desde=date(2026, 8, 10), hasta=date(2026, 8, 22), hoy=HOY)

    assert [s.fecha for s in de(parado)] == [date(2026, 8, 14), date(2026, 8, 29)]
    assert de(parado)[0].completada


def test_lo_de_despues_del_descanso_sigue_ahi() -> None:
    plan = plan_con(sesion(18), sesion(30), sesion(31))

    parado = pausar(plan, desde=date(2026, 8, 17), hasta=date(2026, 8, 22), hoy=HOY)

    assert len(de(parado)) == 2


# --- lo que reduce ------------------------------------------------------


def test_al_volver_no_se_retoma_el_volumen_de_antes() -> None:
    """Una semana parado y volver a los mismos kilómetros es como se recae."""
    plan = plan_con(sesion(18, km=10.0), sesion(24, km=10.0), sesion(26, km=10.0))

    parado = pausar(plan, desde=date(2026, 8, 17), hasta=date(2026, 8, 23), hoy=HOY)

    vuelta = de(parado)
    assert all(s.km < 10.0 for s in vuelta)


def test_cuanto_mas_tiempo_parado_mas_baja_la_vuelta() -> None:
    # Cada plan tiene su sesión de vuelta justo después de SU parón.
    corto = plan_con(sesion(25, km=10.0), sesion(40 - 9, km=9.0))
    largo = Plan(
        version=2,
        semanas=(
            Semana(
                numero=1,
                sesiones=(
                    Sesion(fecha=date(2026, 9, 8), tipo="facil", km=10.0),
                    Sesion(fecha=date(2026, 9, 20), tipo="facil", km=9.0),
                ),
            ),
        ),
    )

    una_semana = pausar(corto, desde=date(2026, 8, 17), hasta=date(2026, 8, 23), hoy=HOY)
    tres_semanas = pausar(largo, desde=date(2026, 8, 17), hasta=date(2026, 9, 6), hoy=HOY)

    assert de(tres_semanas)[0].km < de(una_semana)[0].km


def test_la_vuelta_nunca_baja_de_un_suelo() -> None:
    """Un parón largo no puede dejar el plan en sesiones de juguete."""
    plan = Plan(
        version=2,
        semanas=(
            Semana(
                numero=1,
                sesiones=(Sesion(fecha=date(2026, 12, 3), tipo="facil", km=10.0),),
            ),
        ),
    )

    parado = pausar(plan, desde=date(2026, 8, 17), hasta=date(2026, 12, 1), hoy=HOY)

    assert de(parado)[0].km >= 5.0


def test_solo_baja_la_primera_semana_de_vuelta() -> None:
    """Después se sigue progresando: el parón cuesta, no borra el plan."""
    plan = plan_con(sesion(25, km=10.0), sesion(28, km=10.0), sesion(40 - 9, km=12.0))

    parado = pausar(plan, desde=date(2026, 8, 17), hasta=date(2026, 8, 23), hoy=HOY)

    lejana = next(s for s in de(parado) if s.fecha >= date(2026, 8, 31))
    assert lejana.km == 12.0


# --- versionado y motivo ------------------------------------------------


def test_el_paron_produce_una_version_nueva_con_su_motivo() -> None:
    plan = plan_con(sesion(18), sesion(29))

    parado = pausar(plan, desde=date(2026, 8, 17), hasta=date(2026, 8, 22), hoy=HOY)

    assert parado.version == 3
    assert parado.motivo_cambio
    assert "descanso" in parado.motivo_cambio.lower()


# --- lo que no se puede -------------------------------------------------


def test_no_se_pausa_al_reves() -> None:
    plan = plan_con(sesion(18))

    with pytest.raises(PausaImposible):
        pausar(plan, desde=date(2026, 8, 25), hasta=date(2026, 8, 20), hoy=HOY)


def test_no_se_pausa_algo_que_ya_termino() -> None:
    plan = plan_con(sesion(18))

    with pytest.raises(PausaImposible) as rechazo:
        pausar(plan, desde=date(2026, 7, 1), hasta=date(2026, 7, 10), hoy=HOY)

    assert rechazo.value.razon


def test_pausar_el_plan_entero_lo_dice_en_vez_de_dejarlo_vacio() -> None:
    """Un plan sin ninguna sesión no es un plan: hay que rehacerlo."""
    plan = plan_con(sesion(18), sesion(20))

    with pytest.raises(PausaImposible) as rechazo:
        pausar(plan, desde=date(2026, 8, 17), hasta=date(2026, 9, 30), hoy=HOY)

    assert "rehacer" in rechazo.value.razon.lower() or "nuevo" in rechazo.value.razon.lower()
