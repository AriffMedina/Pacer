"""Property-based tests del generador.

Los rangos de los perfiles salen de `paramethers.md` §2.1 y §2.3.
"""

from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from pacer.domain.servicios.generador_plan import generar_plan

SEMANAS = {"5k": (6, 12), "10k": (8, 14), "21k": (10, 18), "maraton": (12, 20)}
KM_ARRANQUE_MIN = {"5k": 12, "10k": 18, "21k": 25, "maraton": 32}
INICIO = date(2026, 8, 17)


@st.composite
def perfiles_validos(draw: st.DrawFn) -> dict[str, object]:
    distancia = draw(st.sampled_from(sorted(SEMANAS)))
    minimo, maximo = SEMANAS[distancia]
    km_min = KM_ARRANQUE_MIN[distancia]
    return {
        "distancia": distancia,
        "semanas": draw(st.integers(min_value=minimo, max_value=maximo)),
        "km_semana": draw(st.integers(min_value=km_min, max_value=km_min * 3)),
        "dias": draw(st.sampled_from([3, 4])),
        "inicio": INICIO,
    }


@given(perfil=perfiles_validos())
def test_regla_del_diez_por_ciento_es_invariante(perfil: dict[str, object]) -> None:
    plan = generar_plan(**perfil)  # type: ignore[arg-type]

    for previa, actual in zip(plan.semanas, plan.semanas[1:]):
        if not actual.es_descarga:
            assert actual.km_total <= previa.km_total * 1.10 + 0.5


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
