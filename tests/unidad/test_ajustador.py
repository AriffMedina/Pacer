from datetime import date

from pacer.domain.entidades.plan import Plan, Semana, Sesion
from pacer.domain.servicios.ajustador import ajustar


def plan_de_prueba() -> Plan:
    semana = Semana(
        numero=1,
        sesiones=(
            Sesion(fecha=date(2026, 8, 10), tipo="facil", km=6.0),
            Sesion(fecha=date(2026, 8, 12), tipo="calidad", km=8.0),
            Sesion(fecha=date(2026, 8, 15), tipo="largo", km=14.0),
        ),
    )
    return Plan(version=1, semanas=(semana,))


def test_sesion_dura_genera_version_dos_con_motivo() -> None:
    plan = plan_de_prueba()
    reporte = Sesion(
        fecha=date(2026, 8, 15),
        tipo="largo",
        km=12.0,
        completada=True,
        sensacion="muy_dura",
    )

    ajustado = ajustar(plan, reporte)

    assert ajustado.version == 2
    assert ajustado.motivo_cambio is not None
    assert "muy_dura" in ajustado.motivo_cambio


def test_el_plan_original_no_se_muta() -> None:
    plan = plan_de_prueba()
    km_antes = plan.semanas[0].km_total
    reporte = Sesion(
        fecha=date(2026, 8, 15),
        tipo="largo",
        km=12.0,
        completada=True,
        sensacion="con_dolor",
    )

    ajustar(plan, reporte)

    assert plan.version == 1
    assert plan.motivo_cambio is None
    assert plan.semanas[0].km_total == km_antes


def test_la_semana_ajustada_baja_volumen() -> None:
    plan = plan_de_prueba()
    reporte = Sesion(
        fecha=date(2026, 8, 15),
        tipo="largo",
        km=12.0,
        completada=True,
        sensacion="con_dolor",
    )

    ajustado = ajustar(plan, reporte)

    assert ajustado.semanas[0].km_total < plan.semanas[0].km_total


def test_el_ajuste_no_quita_dias() -> None:
    plan = plan_de_prueba()
    reporte = Sesion(
        fecha=date(2026, 8, 15),
        tipo="largo",
        km=12.0,
        completada=True,
        sensacion="muy_dura",
    )

    ajustado = ajustar(plan, reporte)

    assert len(ajustado.semanas[0].sesiones) == len(plan.semanas[0].sesiones)


def test_sesion_normal_no_cambia_el_plan() -> None:
    plan = plan_de_prueba()
    reporte = Sesion(
        fecha=date(2026, 8, 15),
        tipo="largo",
        km=14.0,
        completada=True,
        sensacion="normal",
    )

    ajustado = ajustar(plan, reporte)

    assert ajustado.version == 1
    assert ajustado.motivo_cambio is None
