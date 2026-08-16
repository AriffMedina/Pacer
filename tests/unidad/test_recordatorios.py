from datetime import UTC, date, datetime

from pacer.domain.entidades.plan import Plan, Semana, Sesion
from pacer.domain.servicios.recordatorios import HORA_DE_AVISO, recordatorios_pendientes

CORREDOR = 1


def plan_con(*sesiones: Sesion) -> Plan:
    return Plan(version=1, semanas=(Semana(numero=1, sesiones=sesiones),))


def ahora(dia: int, hora: int = 12) -> datetime:
    return datetime(2026, 8, dia, hora, tzinfo=UTC)


def test_pregunta_por_una_sesion_que_ya_paso_y_sigue_sin_reportar() -> None:
    plan = plan_con(Sesion(fecha=date(2026, 8, 20), tipo="largo", km=14.0))

    pendientes = recordatorios_pendientes(plan, CORREDOR, ahora(21))

    assert len(pendientes) == 1
    assert "14" in pendientes[0].texto


def test_no_pregunta_por_una_sesion_ya_completada() -> None:
    plan = plan_con(
        Sesion(
            fecha=date(2026, 8, 20),
            tipo="largo",
            km=14.0,
            completada=True,
            sensacion="normal",
        )
    )

    assert recordatorios_pendientes(plan, CORREDOR, ahora(21)) == []


def test_no_pregunta_por_una_sesion_que_todavia_no_toca() -> None:
    plan = plan_con(Sesion(fecha=date(2026, 8, 25), tipo="facil", km=6.0))

    assert recordatorios_pendientes(plan, CORREDOR, ahora(21)) == []


def test_no_pregunta_el_mismo_dia_de_la_sesion() -> None:
    # Preguntar "¿cómo te fue?" antes de que corra es ruido, no coaching.
    plan = plan_con(Sesion(fecha=date(2026, 8, 21), tipo="facil", km=6.0))

    assert recordatorios_pendientes(plan, CORREDOR, ahora(21, hora=23)) == []


def test_se_programa_a_la_hora_de_aviso_del_dia_siguiente() -> None:
    plan = plan_con(Sesion(fecha=date(2026, 8, 20), tipo="largo", km=14.0))

    pendiente = recordatorios_pendientes(plan, CORREDOR, ahora(21))[0]

    assert pendiente.programado_para.date() == date(2026, 8, 21)
    assert pendiente.programado_para.hour == HORA_DE_AVISO


def test_la_clave_es_estable_entre_materializaciones() -> None:
    # Correr el materializador cada noche no puede duplicar recordatorios.
    plan = plan_con(Sesion(fecha=date(2026, 8, 20), tipo="largo", km=14.0))

    primera = recordatorios_pendientes(plan, CORREDOR, ahora(21))
    segunda = recordatorios_pendientes(plan, CORREDOR, ahora(22))

    assert primera[0].clave == segunda[0].clave


def test_solo_se_pregunta_por_las_sesiones_recientes() -> None:
    # Preguntar por algo de hace tres semanas no le sirve a nadie.
    plan = plan_con(
        Sesion(fecha=date(2026, 8, 1), tipo="facil", km=6.0),
        Sesion(fecha=date(2026, 8, 20), tipo="largo", km=14.0),
    )

    pendientes = recordatorios_pendientes(plan, CORREDOR, ahora(21))

    assert len(pendientes) == 1
    assert pendientes[0].clave.endswith("2026-08-20")


def test_el_texto_nombra_el_tipo_y_los_kilometros() -> None:
    plan = plan_con(Sesion(fecha=date(2026, 8, 20), tipo="largo", km=14.0))

    texto = recordatorios_pendientes(plan, CORREDOR, ahora(21))[0].texto

    assert "largo" in texto.lower()
    assert "14" in texto
