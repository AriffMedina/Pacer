from datetime import date

from pacer.domain.entidades.plan import Plan, Semana, Sesion
from pacer.domain.servicios.resolutor import resolver_sesion

HOY = date(2026, 8, 20)  # jueves


def plan_con(*sesiones: Sesion) -> Plan:
    return Plan(version=1, semanas=(Semana(numero=1, sesiones=sesiones),))


def sesion(dia: int, tipo: str = "facil", km: float = 6.0) -> Sesion:
    return Sesion(fecha=date(2026, 8, dia), tipo=tipo, km=km)  # type: ignore[arg-type]


def test_ayer_resuelve_la_sesion_del_dia_anterior() -> None:
    plan = plan_con(sesion(19), sesion(20))

    resultado = resolver_sesion(plan, "ayer", hoy=HOY)

    assert resultado.sesion is not None
    assert resultado.sesion.fecha == date(2026, 8, 19)


def test_hoy_resuelve_la_sesion_de_hoy() -> None:
    plan = plan_con(sesion(19), sesion(20))

    resultado = resolver_sesion(plan, "hoy", hoy=HOY)

    assert resultado.sesion is not None
    assert resultado.sesion.fecha == HOY


def test_anteayer_no_se_confunde_con_ayer() -> None:
    plan = plan_con(sesion(18), sesion(19))

    resultado = resolver_sesion(plan, "anteayer", hoy=HOY)

    assert resultado.sesion is not None
    assert resultado.sesion.fecha == date(2026, 8, 18)


def test_un_dia_de_la_semana_busca_hacia_atras() -> None:
    plan = plan_con(sesion(17), sesion(19))  # lunes 17, miércoles 19

    resultado = resolver_sesion(plan, "el lunes", hoy=HOY)

    assert resultado.sesion is not None
    assert resultado.sesion.fecha == date(2026, 8, 17)


def test_dos_sesiones_el_mismo_dia_devuelven_opciones() -> None:
    plan = plan_con(sesion(19, "facil"), sesion(19, "calidad"))

    resultado = resolver_sesion(plan, "ayer", hoy=HOY)

    assert resultado.sesion is None
    assert resultado.es_ambigua
    assert len(resultado.candidatas) == 2


def test_una_pista_que_no_se_entiende_no_revienta() -> None:
    plan = plan_con(sesion(19), sesion(20))

    resultado = resolver_sesion(plan, "el otro día", hoy=HOY)

    assert resultado.sesion is None
    assert resultado.candidatas


def test_sin_sesiones_cercanas_no_hay_candidatas() -> None:
    plan = plan_con(sesion(1))

    resultado = resolver_sesion(plan, "ayer", hoy=HOY)

    assert resultado.sesion is None
    assert resultado.candidatas == ()
