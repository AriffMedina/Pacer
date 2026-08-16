from datetime import date

from pacer.application.contexto.bloque_estado import construir_bloque
from pacer.domain.entidades.carrera import Carrera
from pacer.domain.entidades.perfil import Perfil
from pacer.domain.entidades.plan import Plan, Semana, Sesion

HOY = date(2026, 8, 20)
CARRERA = date(2026, 11, 1)

PERFIL = Perfil(
    nombre="Ariff",
    objetivo="21k",
    nivel="intermedio",
    dias_disponibles=4,
    km_semana=30,
    fecha_carrera=CARRERA,
)


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


def test_siempre_dice_el_ano_en_que_estamos() -> None:
    """El fallo más caro que ha tenido esto.

    El bloque decía "domingo 16 de agosto" sin año. Sin ese dato el modelo cae
    a lo que aprendió en su entrenamiento —dijo estar en 2024—, guardó la
    carrera con el año equivocado, y a partir de ahí todo lo demás fue
    coherente con una fecha falsa: rechazó por falta de semanas un plan que
    tenía siete meses por delante.
    """
    bloque = construir_bloque(plan_de_prueba(), hoy=HOY, fecha_carrera=CARRERA)

    assert str(HOY.year) in bloque
    assert HOY.isoformat() in bloque


def test_el_ano_va_tambien_en_las_fechas_de_las_carreras() -> None:
    bloque = construir_bloque(
        hoy=HOY,
        carreras=(
            Carrera(fecha=date(2027, 3, 20), nombre="De marzo", distancia_km=10.0),
        ),
    )

    assert "de 2027" in bloque


def test_dice_quien_es_el_corredor() -> None:
    """Sin esto el perfil solo vivía en el historial de conversación, y al
    salirse de la ventana el modelo se inventaba hasta el nombre."""
    bloque = construir_bloque(hoy=HOY, perfil=PERFIL)

    assert "Ariff" in bloque
    assert "intermedio" in bloque
    assert "21k" in bloque
    assert "4 días" in bloque
    assert "30 km" in bloque


def test_lo_que_del_perfil_no_se_sabe_se_dice_que_falta() -> None:
    """Para que pregunte eso, y no algo que ya le dijeron."""
    bloque = construir_bloque(hoy=HOY, perfil=Perfil(nombre="Ariff"))

    assert "SIN DEFINIR" in bloque
    assert "nivel" in bloque


def test_sin_perfil_no_inventa_una_linea_de_corredor() -> None:
    assert "CORREDOR:" not in construir_bloque(hoy=HOY)


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
