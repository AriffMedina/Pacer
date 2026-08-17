"""Property-based tests del generador.

Los rangos NO se copian aquí: se derivan de las constantes de dominio, así el
espacio explorado no puede quedarse viejo cuando `paramethers.md` cambie. La
v1.0 de este archivo tenía los máximos desactualizados y probaba un espacio
equivocado sin avisar.
"""

from datetime import date
from itertools import pairwise

from hypothesis import given
from hypothesis import strategies as st

from pacer.domain.reglas.duracion import (
    KM_ARRANQUE_MIN,
    PICO_MAX_KM,
    SEMANAS,
    SEMANAS_MIN_POR_NIVEL,
)
from pacer.domain.reglas.largo import (
    LARGO_TOPE_KM,
    PROGRESION_SESION_MAX,
    SEMANAS_DE_VENTANA,
    tope_por_tiempo,
)
from pacer.domain.servicios.generador_plan import COMPOSICION, generar_plan

INICIO = date(2026, 8, 17)

# Tiene que superar el margen de recorte del generador (1%) MÁS el redondeo por
# sesión, o el test contradice a la implementación por centésimas. Sigue muy por
# debajo del 10% que se está probando, así que no tapa una violación real.
TOLERANCIA_REDONDEO = 1.02

# Todas las combinaciones que la compuerta dura admite. `maraton` + `nuevo`
# queda fuera por construcción: su mínimo es None, o sea rechazo incondicional.
COMBINACIONES = sorted(
    (distancia, nivel)
    for distancia, por_nivel in SEMANAS_MIN_POR_NIVEL.items()
    for nivel, minimo in por_nivel.items()
    if minimo is not None
)


@st.composite
def perfiles_validos(draw: st.DrawFn) -> dict[str, object]:
    distancia, nivel = draw(st.sampled_from(COMBINACIONES))
    minimo = SEMANAS_MIN_POR_NIVEL[distancia][nivel]
    assert minimo is not None
    km_min = KM_ARRANQUE_MIN[distancia]
    return {
        "distancia": distancia,
        "nivel": nivel,
        "semanas": draw(
            st.integers(min_value=minimo, max_value=SEMANAS[distancia]["max"])
        ),
        "km_semana": draw(st.integers(min_value=km_min, max_value=km_min * 3)),
        # Se deriva de la tabla del dominio: si mañana entra un reparto nuevo, las
        # propiedades lo cubren sin que nadie se acuerde de tocar esta lista.
        "dias": draw(st.sampled_from(sorted(COMPOSICION))),
        "inicio": INICIO,
    }


@given(perfil=perfiles_validos())
def test_regla_del_diez_por_ciento_es_invariante(perfil: dict[str, object]) -> None:
    plan = generar_plan(**perfil)  # type: ignore[arg-type]

    # Se comparan semanas de carga entre sí: volver de una descarga a la línea
    # de tendencia es recuperación, no progresión, y no cuenta contra el techo.
    # Solo pares CONSECUTIVOS de carga plena. Filtrar la lista antes de emparejar
    # compararía semanas separadas por varias de tendencia y exigiría 10% sobre
    # un tramo de tres semanas: el test fallaría por estar mal escrito, no por
    # una violación. Salir de una descarga o de un recorte es recuperación.
    def plena(semana: object) -> bool:
        return not semana.es_descarga and not semana.recortada  # type: ignore[attr-defined]

    for previa, actual in pairwise(plan.semanas):
        if plena(previa) and plena(actual):
            assert actual.km_total <= previa.km_total * 1.10 * TOLERANCIA_REDONDEO


@given(perfil=perfiles_validos())
def test_ninguna_semana_supera_el_techo_de_volumen(perfil: dict[str, object]) -> None:
    plan = generar_plan(**perfil)  # type: ignore[arg-type]
    # El techo es el pico de la distancia, salvo que el corredor ya entrene por
    # encima: en ese caso su propio volumen es el techo y no se le baja.
    # El +0.5 absorbe el redondeo por sesión.
    techo = (
        max(PICO_MAX_KM[str(perfil["distancia"])], float(perfil["km_semana"]))  # type: ignore[arg-type]
        + 0.5
    )

    for semana in plan.semanas:
        assert semana.km_total <= techo


@given(perfil=perfiles_validos())
def test_el_largo_no_crece_mas_de_10_sobre_el_maximo_de_4_semanas(
    perfil: dict[str, object],
) -> None:
    """La restricción con evidencia real: Nielsen 2025, grado B."""
    plan = generar_plan(**perfil)  # type: ignore[arg-type]
    largos = [s.largo.km for s in plan.semanas if s.largo]

    for indice, actual in enumerate(largos[1:], start=1):
        ventana = largos[max(0, indice - SEMANAS_DE_VENTANA) : indice]
        assert actual <= max(ventana) * PROGRESION_SESION_MAX + 0.5


@given(perfil=perfiles_validos())
def test_ningun_largo_supera_el_limite_de_tres_horas(
    perfil: dict[str, object],
) -> None:
    plan = generar_plan(**perfil)  # type: ignore[arg-type]

    for semana in plan.semanas:
        if semana.largo:
            assert semana.largo.km <= tope_por_tiempo() + 0.5


@given(perfil=perfiles_validos())
def test_ningun_largo_supera_el_tope_de_su_distancia(
    perfil: dict[str, object],
) -> None:
    plan = generar_plan(**perfil)  # type: ignore[arg-type]
    tope = LARGO_TOPE_KM[str(perfil["distancia"])]

    for semana in plan.semanas:
        if semana.largo:
            assert semana.largo.km <= tope + 0.5


@given(perfil=perfiles_validos())
def test_el_largo_pico_nunca_cae_en_el_tapering(perfil: dict[str, object]) -> None:
    """Llegar al pico durante el taper anula el propósito del taper."""
    plan = generar_plan(**perfil)  # type: ignore[arg-type]
    con_largo = [s for s in plan.semanas if s.largo]
    pico = max(con_largo, key=lambda s: s.largo.km if s.largo else 0.0)

    assert pico.bloque != "tapering"


@given(perfil=perfiles_validos())
def test_el_tapering_siempre_va_al_final(perfil: dict[str, object]) -> None:
    plan = generar_plan(**perfil)  # type: ignore[arg-type]

    assert plan.semanas[-1].km_total < max(s.km_total for s in plan.semanas)


@given(perfil=perfiles_validos())
def test_el_largo_nunca_deja_de_ser_el_mas_largo(perfil: dict[str, object]) -> None:
    plan = generar_plan(**perfil)  # type: ignore[arg-type]

    for semana in plan.semanas:
        largo = next(s for s in semana.sesiones if s.tipo == "largo")
        assert all(s.km <= largo.km for s in semana.sesiones)


@given(perfil=perfiles_validos())
def test_al_menos_78_por_ciento_de_km_son_faciles(perfil: dict[str, object]) -> None:
    plan = generar_plan(**perfil)  # type: ignore[arg-type]

    for semana in plan.semanas:
        faciles = sum(s.km for s in semana.sesiones if s.tipo != "calidad")
        assert faciles / semana.km_total >= 0.78


@given(perfil=perfiles_validos())
def test_el_plan_respeta_los_dias_disponibles(perfil: dict[str, object]) -> None:
    plan = generar_plan(**perfil)  # type: ignore[arg-type]

    for semana in plan.semanas:
        assert len(semana.sesiones) == perfil["dias"]
