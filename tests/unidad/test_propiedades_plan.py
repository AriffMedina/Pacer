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
from pacer.domain.servicios.generador_plan import generar_plan

INICIO = date(2026, 8, 17)

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
        "dias": draw(st.sampled_from([3, 4])),
        "inicio": INICIO,
    }


@given(perfil=perfiles_validos())
def test_regla_del_diez_por_ciento_es_invariante(perfil: dict[str, object]) -> None:
    plan = generar_plan(**perfil)  # type: ignore[arg-type]

    # Se comparan semanas de carga entre sí: volver de una descarga a la línea
    # de tendencia es recuperación, no progresión, y no cuenta contra el techo.
    de_carga = [semana for semana in plan.semanas if not semana.es_descarga]

    for previa, actual in pairwise(de_carga):
        assert actual.km_total <= previa.km_total * 1.10 + 0.5


@given(perfil=perfiles_validos())
def test_ninguna_semana_supera_el_techo_de_volumen(perfil: dict[str, object]) -> None:
    plan = generar_plan(**perfil)  # type: ignore[arg-type]
    # Tolerancia de redondeo: el total semanal es la suma de kilómetros ya
    # redondeados por sesión, así que puede pasarse del techo por décimas.
    techo = PICO_MAX_KM[str(perfil["distancia"])] + 0.5

    for semana in plan.semanas:
        assert semana.km_total <= techo


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
