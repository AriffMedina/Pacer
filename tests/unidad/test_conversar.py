"""El bucle multi-turno se prueba con un LLM falso: sin red, determinista."""

from datetime import date
from typing import Any

from pacer.application.casos_uso.conversar import procesar_turno
from pacer.domain.entidades.perfil import Perfil
from pacer.domain.puertos.llm import LlamadaHerramienta, RespuestaLLM


class LLMFalso:
    """Devuelve respuestas preparadas, una por vuelta, y registra lo que recibió."""

    def __init__(self, *respuestas: RespuestaLLM) -> None:
        self._respuestas = list(respuestas)
        self.recibidos: list[list[dict[str, Any]]] = []

    def conversar(
        self,
        sistema: str,
        mensajes: list[dict[str, Any]],
        herramientas: dict[str, Any],
    ) -> RespuestaLLM:
        self.recibidos.append([dict(m) for m in mensajes])
        return self._respuestas.pop(0)


def solo_texto(texto: str) -> RespuestaLLM:
    return RespuestaLLM(texto=texto, llamadas=(), mensaje={"role": "assistant"})


def con_llamada(nombre: str, entrada: dict[str, Any]) -> RespuestaLLM:
    return RespuestaLLM(
        texto="",
        llamadas=(LlamadaHerramienta(id="tu_1", nombre=nombre, entrada=entrada),),
        mensaje={"role": "assistant"},
    )


def mensaje_usuario(texto: str) -> dict[str, Any]:
    return {"role": "user", "content": [{"text": texto}]}


def test_sin_herramientas_devuelve_el_texto_en_una_vuelta() -> None:
    llm = LLMFalso(solo_texto("¿Para qué carrera te preparas?"))

    resultado = procesar_turno(
        llm, "sistema", [mensaje_usuario("hola")], Perfil()
    )

    assert resultado.vueltas == 1
    assert "carrera" in resultado.texto


def test_ejecuta_la_herramienta_y_vuelve_a_preguntarle_al_modelo() -> None:
    llm = LLMFalso(
        con_llamada("actualizar_perfil", {"objetivo": "21k"}),
        solo_texto("Listo, lo anoté."),
    )

    resultado = procesar_turno(
        llm, "sistema", [mensaje_usuario("quiero un 21k")], Perfil()
    )

    assert resultado.vueltas == 2
    assert resultado.herramientas_usadas == ("actualizar_perfil",)
    assert "anoté" in resultado.texto


def test_la_actualizacion_de_perfil_se_aplica() -> None:
    llm = LLMFalso(
        con_llamada(
            "actualizar_perfil",
            {"objetivo": "21k", "km_semana": 25, "fecha_carrera": "2026-11-01"},
        ),
        solo_texto("Anotado."),
    )

    resultado = procesar_turno(llm, "sistema", [mensaje_usuario("...")], Perfil())

    assert resultado.perfil.objetivo == "21k"
    assert resultado.perfil.km_semana == 25
    assert resultado.perfil.fecha_carrera == date(2026, 11, 1)


def test_los_campos_no_mencionados_no_se_pisan() -> None:
    previo = Perfil(objetivo="21k", nivel="intermedio")
    llm = LLMFalso(
        con_llamada("actualizar_perfil", {"km_semana": 30}),
        solo_texto("ok"),
    )

    resultado = procesar_turno(llm, "sistema", [mensaje_usuario("...")], previo)

    assert resultado.perfil.nivel == "intermedio"
    assert resultado.perfil.km_semana == 30


def test_el_resultado_de_la_herramienta_se_le_devuelve_al_modelo() -> None:
    llm = LLMFalso(
        con_llamada("generar_plan", {}),
        solo_texto("Me falta la fecha."),
    )

    procesar_turno(llm, "sistema", [mensaje_usuario("hazme el plan")], Perfil())

    ultimos = llm.recibidos[-1]
    bloques = ultimos[-1]["content"]
    assert "toolResult" in bloques[0]
    assert bloques[0]["toolResult"]["content"][0]["json"]["error"] == "faltan_datos"


def test_el_bucle_no_gira_para_siempre() -> None:
    llm = LLMFalso(*[con_llamada("actualizar_perfil", {}) for _ in range(10)])

    resultado = procesar_turno(
        llm, "sistema", [mensaje_usuario("...")], Perfil(), max_vueltas=3
    )

    assert resultado.vueltas == 3
    assert resultado.corto_por_limite
