from datetime import date

from pacer.application.contexto.bloque_estado import construir_bloque
from pacer.domain.entidades.plan import Plan, Semana, Sesion

HOY = date(2026, 8, 20)
CARRERA = date(2026, 11, 1)


def plan_de_prueba() -> Plan:
    semana_uno = Semana(
        numero=1,
        sesiones=(
            Sesion(
                fecha=date(2026, 8, 18),
                tipo="calidad",
                km=6.0,
                completada=True,
                sensacion="pesada",
            ),
        ),
    )
    semana_dos = Semana(
        numero=2,
        sesiones=(
            Sesion(fecha=HOY, tipo="largo", km=14.0),
            Sesion(fecha=date(2026, 8, 22), tipo="facil", km=6.0),
        ),
    )
    return Plan(version=1, semanas=(semana_uno, semana_dos))


def test_indica_la_semana_actual_y_el_total() -> None:
    bloque = construir_bloque(plan_de_prueba(), hoy=HOY, fecha_carrera=CARRERA)

    assert "SEMANA 2 DE 2" in bloque


def test_indica_los_dias_que_faltan_para_la_carrera() -> None:
    bloque = construir_bloque(plan_de_prueba(), hoy=HOY, fecha_carrera=CARRERA)

    assert "faltan 73 días" in bloque


def test_nombra_la_sesion_de_hoy() -> None:
    bloque = construir_bloque(plan_de_prueba(), hoy=HOY, fecha_carrera=CARRERA)

    assert "SESIÓN DE HOY: largo 14.0 km (pendiente)" in bloque


def test_nombra_la_siguiente_sesion() -> None:
    bloque = construir_bloque(plan_de_prueba(), hoy=HOY, fecha_carrera=CARRERA)

    assert "SIGUIENTE: sábado, facil 6.0 km" in bloque


def test_nombra_la_ultima_completada_con_su_sensacion() -> None:
    bloque = construir_bloque(plan_de_prueba(), hoy=HOY, fecha_carrera=CARRERA)

    assert 'ÚLTIMA COMPLETADA: martes, calidad 6.0 km, sensación "pesada"' in bloque


def test_sin_sesiones_completadas_lo_dice() -> None:
    plan = Plan(
        version=1,
        semanas=(Semana(numero=1, sesiones=(Sesion(fecha=HOY, tipo="facil", km=5.0),)),),
    )

    bloque = construir_bloque(plan, hoy=HOY, fecha_carrera=CARRERA)

    assert "ÚLTIMA COMPLETADA: ninguna todavía" in bloque
