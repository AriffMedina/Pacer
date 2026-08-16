from datetime import date

from pacer.domain.entidades.plan import Plan, Semana, Sesion
from pacer.domain.servicios.registro import registrar

HOY = date(2026, 8, 20)


def plan_de_prueba() -> Plan:
    return Plan(
        version=1,
        semanas=(
            Semana(
                numero=1,
                sesiones=(
                    Sesion(fecha=date(2026, 8, 19), tipo="facil", km=6.0),
                    Sesion(fecha=HOY, tipo="largo", km=14.0),
                ),
            ),
        ),
    )


def test_marca_la_sesion_como_completada() -> None:
    plan = plan_de_prueba()
    objetivo = plan.semanas[0].sesiones[1]

    actualizado = registrar(plan, objetivo, km=12.0, sensacion="muy_dura")
    registrada = actualizado.semanas[0].sesiones[1]

    assert registrada.completada
    assert registrada.km == 12.0
    assert registrada.sensacion == "muy_dura"


def test_no_toca_las_demas_sesiones() -> None:
    plan = plan_de_prueba()
    objetivo = plan.semanas[0].sesiones[1]

    actualizado = registrar(plan, objetivo, km=12.0, sensacion="normal")

    assert not actualizado.semanas[0].sesiones[0].completada


def test_el_plan_original_no_se_muta() -> None:
    plan = plan_de_prueba()
    objetivo = plan.semanas[0].sesiones[1]

    registrar(plan, objetivo, km=12.0, sensacion="normal")

    assert not plan.semanas[0].sesiones[1].completada


def test_registrar_no_cambia_la_version() -> None:
    plan = plan_de_prueba()
    objetivo = plan.semanas[0].sesiones[1]

    actualizado = registrar(plan, objetivo, km=12.0, sensacion="muy_dura")

    # Registrar es un hecho, no un cambio de plan. La v2 la produce el ajustador.
    assert actualizado.version == 1
    assert actualizado.motivo_cambio is None
