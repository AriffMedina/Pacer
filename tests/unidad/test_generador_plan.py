from datetime import date
from itertools import pairwise

from pacer.domain.reglas.duracion import PICO_MAX_KM
from pacer.domain.servicios.generador_plan import generar_plan

PERFIL = {
    "distancia": "21k",
    "nivel": "intermedio",
    "semanas": 12,
    "km_semana": 25,
    "dias": 4,
    "inicio": date(2026, 8, 17),
}


def plan_base():
    return generar_plan(**PERFIL)


def test_el_plan_tiene_las_semanas_pedidas() -> None:
    plan = plan_base()

    assert len(plan.semanas) == 12
    assert plan.version == 1


def test_el_tapering_va_al_final() -> None:
    plan = plan_base()
    ultimas = plan.semanas[-2:]

    for semana in ultimas:
        assert semana.km_total < plan.semanas[-3].km_total


def test_las_semanas_de_descarga_bajan_el_volumen() -> None:
    plan = plan_base()

    for previa, actual in zip(plan.semanas, plan.semanas[1:]):
        if actual.es_descarga:
            assert actual.km_total < previa.km_total


def test_ninguna_semana_normal_sube_mas_de_diez_por_ciento() -> None:
    plan = plan_base()

    de_carga = [semana for semana in plan.semanas if not semana.es_descarga]

    for previa, actual in pairwise(de_carga):
        assert actual.km_total <= previa.km_total * 1.10 + 0.5


def test_al_menos_78_por_ciento_de_los_km_son_faciles() -> None:
    plan = plan_base()

    for semana in plan.semanas:
        faciles = sum(s.km for s in semana.sesiones if s.tipo != "calidad")
        assert faciles / semana.km_total >= 0.78


def test_el_volumen_nunca_supera_el_techo_de_la_distancia() -> None:
    # Sin techo, este perfil llegaba a 91.4 km/semana contra un pico típico
    # recreativo documentado de 45-70 (§2.3).
    plan = generar_plan(
        distancia="maraton",
        nivel="principiante",
        semanas=20,
        km_semana=32,
        dias=4,
        inicio=date(2026, 8, 17),
    )

    for semana in plan.semanas:
        assert semana.km_total <= PICO_MAX_KM["maraton"]


def test_al_llegar_al_techo_la_carga_se_sostiene() -> None:
    plan = generar_plan(
        distancia="maraton",
        nivel="principiante",
        semanas=20,
        km_semana=32,
        dias=4,
        inicio=date(2026, 8, 17),
    )
    de_carga = [s for s in plan.semanas if not s.es_descarga]

    assert max(s.km_total for s in de_carga) >= PICO_MAX_KM["maraton"] * 0.95


def test_el_largo_es_siempre_la_sesion_mas_larga() -> None:
    plan = plan_base()

    for semana in plan.semanas:
        largo = next(s for s in semana.sesiones if s.tipo == "largo")
        for sesion in semana.sesiones:
            assert sesion.km <= largo.km, f"semana {semana.numero}"


def test_se_respetan_los_dias_disponibles() -> None:
    plan = plan_base()

    for semana in plan.semanas:
        assert len(semana.sesiones) == 4
