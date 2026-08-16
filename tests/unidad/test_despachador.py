from datetime import date

from pacer.application.herramientas.despachador import despachar
from pacer.domain.entidades.perfil import Perfil

COMPLETO = Perfil(
    objetivo="21k",
    nivel="intermedio",
    dias_disponibles=4,
    km_semana=25,
    fecha_carrera=date(2026, 11, 1),
)


def test_generar_plan_sin_datos_devuelve_error_con_los_campos() -> None:
    resultado = despachar("generar_plan", {}, perfil=Perfil(objetivo="21k"))

    assert resultado["error"] == "faltan_datos"
    assert "fecha_carrera" in resultado["campos"]


def test_generar_plan_con_perfil_completo_no_devuelve_error() -> None:
    resultado = despachar("generar_plan", {}, perfil=COMPLETO)

    assert "error" not in resultado


def test_una_herramienta_desconocida_se_rechaza() -> None:
    resultado = despachar("borrar_todo", {}, perfil=COMPLETO)

    assert resultado["error"] == "herramienta_desconocida"


def test_con_dolor_no_se_ejecuta_una_subida_de_intensidad() -> None:
    perfil = Perfil(
        objetivo="21k",
        nivel="intermedio",
        dias_disponibles=4,
        km_semana=25,
        fecha_carrera=date(2026, 11, 1),
        dolor_actual=True,
    )

    resultado = despachar("subir_intensidad", {}, perfil=perfil)

    assert resultado["error"] == "bloqueado_por_dolor"


def test_actualizar_perfil_siempre_se_permite() -> None:
    resultado = despachar(
        "actualizar_perfil", {"km_semana": 30}, perfil=Perfil()
    )

    assert "error" not in resultado
