from datetime import date

from pacer.application.guardarrailes.reglas import (
    campos_faltantes,
    puede_generar_plan,
    puede_subir_intensidad,
)
from pacer.domain.entidades.perfil import Perfil

COMPLETO = Perfil(
    objetivo="21k",
    nivel="intermedio",
    dias_disponibles=4,
    km_semana=25,
    fecha_carrera=date(2026, 11, 1),
)


def test_un_perfil_completo_no_tiene_campos_faltantes() -> None:
    assert campos_faltantes(COMPLETO) == ()


def test_señala_exactamente_los_campos_que_faltan() -> None:
    perfil = Perfil(objetivo="21k", nivel="intermedio")

    faltantes = campos_faltantes(perfil)

    assert set(faltantes) == {"dias_disponibles", "km_semana", "fecha_carrera"}


def test_no_se_puede_generar_plan_sin_datos() -> None:
    assert not puede_generar_plan(Perfil(objetivo="21k"))


def test_se_puede_generar_plan_con_el_perfil_completo() -> None:
    assert puede_generar_plan(COMPLETO)


def test_el_dolor_bloquea_subir_intensidad() -> None:
    perfil = Perfil(
        objetivo="21k",
        nivel="intermedio",
        dias_disponibles=4,
        km_semana=25,
        fecha_carrera=date(2026, 11, 1),
        dolor_actual=True,
    )

    assert not puede_subir_intensidad(perfil)


def test_sin_dolor_se_puede_subir_intensidad() -> None:
    assert puede_subir_intensidad(COMPLETO)
