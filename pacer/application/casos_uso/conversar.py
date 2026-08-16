"""Bucle de conversación con herramientas.

El modelo pide herramientas, el código las valida y ejecuta, y el resultado
vuelve al modelo para que redacte la respuesta hablada. El bucle tiene tope:
un modelo que insiste en llamar herramientas no puede colgar el turno.
"""

from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from pacer.application.herramientas.despachador import despachar
from pacer.application.herramientas.esquemas import catalogo_para_bedrock
from pacer.domain.entidades.perfil import Perfil
from pacer.domain.puertos.llm import LlamadaHerramienta, PuertoLLM

MAX_VUELTAS = 4

CAMPOS_DE_PERFIL = (
    "objetivo",
    "nivel",
    "dias_disponibles",
    "km_semana",
    "dolor_actual",
)


@dataclass(frozen=True)
class ResultadoTurno:
    texto: str
    perfil: Perfil
    mensajes: list[dict[str, Any]]
    vueltas: int
    herramientas_usadas: tuple[str, ...]
    corto_por_limite: bool = False


def procesar_turno(
    llm: PuertoLLM,
    sistema: str,
    mensajes: list[dict[str, Any]],
    perfil: Perfil,
    max_vueltas: int = MAX_VUELTAS,
) -> ResultadoTurno:
    """Corre el ciclo pedir-ejecutar-responder hasta que el modelo cierre el turno."""
    historial = list(mensajes)
    usadas: list[str] = []
    catalogo = catalogo_para_bedrock()

    for vuelta in range(1, max_vueltas + 1):
        respuesta = llm.conversar(sistema, historial, catalogo)

        if not respuesta.llamadas:
            return ResultadoTurno(
                texto=respuesta.texto,
                perfil=perfil,
                mensajes=historial,
                vueltas=vuelta,
                herramientas_usadas=tuple(usadas),
            )

        historial.append(respuesta.mensaje)
        resultados = []

        for llamada in respuesta.llamadas:
            usadas.append(llamada.nombre)
            resultado = despachar(llamada.nombre, llamada.entrada, perfil)
            if llamada.nombre == "actualizar_perfil" and "error" not in resultado:
                perfil = _aplicar_actualizacion(perfil, llamada.entrada)
            resultados.append((llamada, resultado))

        historial.append(_mensaje_de_resultados(resultados))

    return ResultadoTurno(
        texto="",
        perfil=perfil,
        mensajes=historial,
        vueltas=max_vueltas,
        herramientas_usadas=tuple(usadas),
        corto_por_limite=True,
    )


def _mensaje_de_resultados(
    resultados: list[tuple[LlamadaHerramienta, dict[str, Any]]],
) -> dict[str, Any]:
    """Bedrock espera TODOS los toolResult de la vuelta en un solo mensaje."""
    return {
        "role": "user",
        "content": [
            {
                "toolResult": {
                    "toolUseId": llamada.id,
                    "content": [{"json": resultado}],
                }
            }
            for llamada, resultado in resultados
        ],
    }


def _aplicar_actualizacion(perfil: Perfil, entrada: dict[str, Any]) -> Perfil:
    """Escribe solo los campos que el modelo mencionó; el resto no se toca."""
    cambios: dict[str, Any] = {
        campo: entrada[campo]
        for campo in CAMPOS_DE_PERFIL
        if entrada.get(campo) is not None
    }

    fecha = entrada.get("fecha_carrera")
    if fecha:
        try:
            cambios["fecha_carrera"] = date.fromisoformat(fecha)
        except ValueError:
            # Fecha ilegible: se ignora en vez de romper el turno. El coach la
            # volverá a pedir porque el guardarrail la sigue viendo faltante.
            pass

    return replace(perfil, **cambios)
