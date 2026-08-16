from datetime import date

import pytest

from pacer.application.casos_uso.crear_plan import crear_plan
from pacer.domain.entidades.perfil import Perfil
from pacer.domain.reglas.duracion import PlanImposible

HOY = date(2026, 8, 16)

COMPLETO = Perfil(
    objetivo="21k",
    nivel="intermedio",
    dias_disponibles=4,
    km_semana=25,
    fecha_carrera=date(2026, 11, 1),  # 11 semanas
)


def test_crea_un_plan_con_las_semanas_que_quedan() -> None:
    plan = crear_plan(COMPLETO, hoy=HOY)

    assert plan.version == 1
    assert len(plan.semanas) == 11


def test_el_plan_arranca_en_el_volumen_actual_del_corredor() -> None:
    plan = crear_plan(COMPLETO, hoy=HOY)

    assert plan.semanas[0].km_total == pytest.approx(25.0, abs=0.5)


def test_un_perfil_incompleto_no_llega_al_generador() -> None:
    with pytest.raises(ValueError):
        crear_plan(Perfil(objetivo="21k"), hoy=HOY)


def test_sin_semanas_suficientes_se_rechaza_con_alternativas() -> None:
    apurado = Perfil(
        objetivo="maraton",
        nivel="principiante",
        dias_disponibles=4,
        km_semana=32,
        fecha_carrera=date(2026, 10, 1),  # ~6 semanas, exige 20
    )

    with pytest.raises(PlanImposible) as error:
        crear_plan(apurado, hoy=HOY)

    assert error.value.minimo == 20


def test_maraton_para_nuevo_se_rechaza_aunque_sobre_tiempo() -> None:
    novato = Perfil(
        objetivo="maraton",
        nivel="nuevo",
        dias_disponibles=4,
        km_semana=32,
        fecha_carrera=date(2027, 8, 1),
    )

    with pytest.raises(PlanImposible):
        crear_plan(novato, hoy=HOY)
