from datetime import date

from pacer.domain.servicios.generador_plan import generar_plan

PERFIL = {
    "distancia": "21k",
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

    for previa, actual in zip(plan.semanas, plan.semanas[1:]):
        if not actual.es_descarga:
            assert actual.km_total <= previa.km_total * 1.10 + 0.5


def test_al_menos_78_por_ciento_de_los_km_son_faciles() -> None:
    plan = plan_base()

    for semana in plan.semanas:
        faciles = sum(s.km for s in semana.sesiones if s.tipo != "calidad")
        assert faciles / semana.km_total >= 0.78


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
