from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from pacer.domain.entidades.plan import Plan, Semana, Sesion
from pacer.domain.servicios.tablero import resumir

HOY = date(2026, 8, 20)  # jueves


def plan_con(*sesiones: Sesion) -> Plan:
    return Plan(version=1, semanas=(Semana(numero=1, sesiones=sesiones),))


def sesion(
    dia: int,
    tipo: str = "facil",
    km: float = 6.0,
    completada: bool = False,
    sensacion: str | None = None,
) -> Sesion:
    return Sesion(
        fecha=date(2026, 8, dia),
        tipo=tipo,  # type: ignore[arg-type]
        km=km,
        completada=completada,
        sensacion=sensacion,  # type: ignore[arg-type]
    )


# --- racha ---------------------------------------------------------------


def test_la_racha_cuenta_sesiones_seguidas_hacia_atras() -> None:
    plan = plan_con(
        sesion(17, completada=True),
        sesion(18, completada=True),
        sesion(19, completada=True),
    )

    assert resumir(plan, hoy=HOY).racha == 3


def test_una_sesion_saltada_corta_la_racha() -> None:
    """Lo que mide la racha es constancia, y saltarse una la rompe."""
    plan = plan_con(
        sesion(17, completada=True),
        sesion(18),  # se la saltó
        sesion(19, completada=True),
    )

    assert resumir(plan, hoy=HOY).racha == 1


def test_la_sesion_de_hoy_sin_hacer_no_rompe_la_racha() -> None:
    """Todavía tiene el día por delante. Contarla como fallada sería castigar
    a alguien por no haber corrido a las ocho de la mañana."""
    plan = plan_con(
        sesion(18, completada=True),
        sesion(19, completada=True),
        sesion(20),  # hoy, aún pendiente
    )

    assert resumir(plan, hoy=HOY).racha == 2


def test_la_sesion_de_hoy_ya_hecha_suma_a_la_racha() -> None:
    plan = plan_con(sesion(19, completada=True), sesion(20, completada=True))

    assert resumir(plan, hoy=HOY).racha == 2


def test_sin_sesiones_hechas_la_racha_es_cero() -> None:
    assert resumir(plan_con(sesion(19), sesion(20)), hoy=HOY).racha == 0


def test_las_sesiones_futuras_no_cuentan_para_la_racha() -> None:
    """Un plan recién generado tiene semanas por delante; ninguna es una racha."""
    plan = plan_con(sesion(21), sesion(22), sesion(23))

    assert resumir(plan, hoy=HOY).racha == 0


# --- la semana en curso --------------------------------------------------


def test_la_semana_va_de_lunes_a_domingo() -> None:
    resumen = resumir(plan_con(sesion(20)), hoy=HOY)

    assert [d.inicial for d in resumen.semana] == ["L", "M", "M", "J", "V", "S", "D"]
    assert resumen.semana[0].fecha == date(2026, 8, 17)
    assert resumen.semana[6].fecha == date(2026, 8, 23)


def test_cada_dia_de_la_semana_dice_en_que_estado_esta() -> None:
    plan = plan_con(
        sesion(17, completada=True),  # lunes, hecha
        sesion(18),  # martes, ya pasó sin reportar
        sesion(20),  # jueves = hoy
        sesion(22),  # sábado, por venir
    )

    estados = {d.fecha.day: d.estado for d in resumir(plan, hoy=HOY).semana}

    assert estados[17] == "hecha"
    assert estados[18] == "perdida"
    assert estados[19] == "descanso"  # no había nada programado
    assert estados[20] == "pendiente"  # hoy todavía cuenta
    assert estados[22] == "pendiente"


def test_un_dia_con_dos_sesiones_se_marca_hecho_si_alguna_lo_esta() -> None:
    plan = plan_con(sesion(17, completada=True), sesion(17, "calidad"))

    assert resumir(plan, hoy=HOY).semana[0].estado == "hecha"


# --- la próxima sesión ---------------------------------------------------


def test_la_proxima_es_la_primera_pendiente_desde_hoy() -> None:
    plan = plan_con(sesion(19), sesion(20, "largo", km=14.0), sesion(22))

    proxima = resumir(plan, hoy=HOY).proxima

    assert proxima is not None
    assert proxima.fecha == HOY
    assert proxima.tipo == "largo"
    assert proxima.km == 14.0
    assert proxima.cuando == "Hoy"


def test_la_proxima_saltea_lo_que_ya_se_reporto() -> None:
    plan = plan_con(sesion(20, completada=True), sesion(21))

    proxima = resumir(plan, hoy=HOY).proxima

    assert proxima is not None
    assert proxima.cuando == "Mañana"


def test_una_proxima_lejana_se_nombra_por_su_dia() -> None:
    plan = plan_con(sesion(23))  # domingo

    proxima = resumir(plan, hoy=HOY).proxima

    assert proxima is not None
    assert proxima.cuando == "Dom 23"


def test_con_el_plan_terminado_no_hay_proxima() -> None:
    plan = plan_con(sesion(17, completada=True))

    assert resumir(plan, hoy=HOY).proxima is None


# --- progreso de la semana ----------------------------------------------


def test_el_progreso_compara_kilometros_hechos_contra_planeados() -> None:
    plan = plan_con(
        sesion(17, km=6.0, completada=True),
        sesion(19, km=4.0, completada=True),
        sesion(22, km=10.0),
    )

    resumen = resumir(plan, hoy=HOY)

    assert resumen.km_hechos == 10.0
    assert resumen.km_planeados == 20.0
    assert resumen.porcentaje == 50


def test_una_semana_sin_nada_planeado_no_divide_por_cero() -> None:
    plan = plan_con(sesion(3, completada=True))  # otra semana

    resumen = resumir(plan, hoy=HOY)

    assert resumen.km_planeados == 0.0
    assert resumen.porcentaje == 0


@given(
    st.lists(
        st.tuples(
            st.integers(min_value=17, max_value=23),
            st.floats(min_value=1.0, max_value=45.0),
            st.booleans(),
        ),
        max_size=12,
    )
)
def test_el_porcentaje_siempre_cabe_en_la_barra(
    crudas: list[tuple[int, float, bool]],
) -> None:
    """Sea cual sea la semana, la barra se puede dibujar.

    Vale porque `km` es lo planeado y `completada` es el reporte: lo hecho es un
    subconjunto de lo planeado. Si algún día se guardaran los km REALES, esta
    propiedad se cae y avisa que la barra necesita tope.
    """
    plan = plan_con(*(sesion(dia, km=km, completada=hecha) for dia, km, hecha in crudas))

    resumen = resumir(plan, hoy=HOY)

    assert 0 <= resumen.porcentaje <= 100
    assert resumen.km_hechos <= resumen.km_planeados


# --- actividad reciente --------------------------------------------------


def test_la_actividad_lista_lo_hecho_de_lo_mas_nuevo_a_lo_mas_viejo() -> None:
    plan = plan_con(
        sesion(12, km=15.0, completada=True, sensacion="pesada"),
        sesion(19, km=6.0, completada=True, sensacion="facil"),
    )

    actividad = resumir(plan, hoy=HOY).actividad

    assert [h.fecha.day for h in actividad] == [19, 12]
    assert actividad[0].sensacion == "facil"


def test_la_actividad_nombra_las_fechas_como_las_diria_una_persona() -> None:
    plan = plan_con(
        sesion(20, completada=True),
        sesion(19, completada=True),
        sesion(17, completada=True),
        sesion(1, completada=True),
    )

    cuando = [h.cuando for h in resumir(plan, hoy=HOY).actividad]

    assert cuando == ["Hoy", "Ayer", "Hace 3 días", "1 ago"]


def test_la_actividad_no_crece_sin_limite() -> None:
    plan = plan_con(*(sesion(dia, completada=True) for dia in range(1, 21)))

    assert len(resumir(plan, hoy=HOY).actividad) == 4


def test_lo_que_no_se_ha_corrido_no_es_actividad() -> None:
    assert resumir(plan_con(sesion(19)), hoy=HOY).actividad == ()


# --- sin plan ------------------------------------------------------------


def test_sin_plan_el_tablero_existe_pero_esta_vacio() -> None:
    """La vista se dibuja igual el primer día, antes de que haya nada que contar."""
    resumen = resumir(None, hoy=HOY)

    assert resumen.racha == 0
    assert resumen.proxima is None
    assert resumen.actividad == ()
    assert resumen.porcentaje == 0
    assert len(resumen.semana) == 7
