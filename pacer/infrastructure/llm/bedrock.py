"""Adaptador de Amazon Bedrock sobre la API `converse`.

Nota que vale para el ADR-003: los modelos de Amazon se invocan con su id
directo (`amazon.nova-lite-v1:0`), pero los de Anthropic en Bedrock exigen un
inference profile (`us.anthropic.claude-haiku-4-5-...`). No son intercambiables
por id, y esconder esa diferencia es exactamente el trabajo del puerto.
"""

from typing import Any

import boto3
from botocore.config import Config

from pacer.domain.puertos.llm import LlamadaHerramienta, RespuestaLLM

# Por encima de esto conviene reintentar en vez de seguir esperando.
TIEMPO_LIMITE_S = 12
from pacer.domain.puertos.observabilidad import (
    TIPO_GENERACION,
    PuertoObservabilidad,
    SinObservabilidad,
)


class AdaptadorBedrock:
    def __init__(
        self,
        model_id: str,
        region: str,
        observabilidad: PuertoObservabilidad | None = None,
    ) -> None:
        # Medido: las llamadas normales tardan 1–2 s, pero una de cada ocho se
        # atascó 42 s con el mismo prompt y el mismo contexto. Esperar no la
        # arregla; cortar y reintentar sí. El usuario tiene el teléfono en la
        # mano y 42 s es abandono garantizado.
        self._cliente = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(
                connect_timeout=5,
                read_timeout=TIEMPO_LIMITE_S,
                retries={"max_attempts": 3, "mode": "adaptive"},
            ),
        )
        self._model_id = model_id
        self._trazas = observabilidad or SinObservabilidad()

    def conversar(
        self,
        sistema: str,
        mensajes: list[dict[str, Any]],
        herramientas: dict[str, Any],
    ) -> RespuestaLLM:
        with self._trazas.observar(
            nombre="coach",
            tipo=TIPO_GENERACION,
            entrada={"sistema": sistema, "mensajes": mensajes},
            modelo=self._model_id,
            metadatos={"herramientas": [t["toolSpec"]["name"] for t in herramientas["tools"]]},
        ) as traza:
            respuesta = self._cliente.converse(
                modelId=self._model_id,
                system=[{"text": sistema}],
                messages=mensajes,
                toolConfig=herramientas,
                inferenceConfig={"temperature": 0},
            )
            interpretada = interpretar_respuesta(respuesta)

            traza.registrar_salida(
                {
                    "texto": interpretada.texto,
                    "herramientas_pedidas": [ll.nombre for ll in interpretada.llamadas],
                    "uso": respuesta.get("usage"),
                }
            )
            return interpretada


def interpretar_respuesta(respuesta: dict[str, Any]) -> RespuestaLLM:
    """Separa el texto de las llamadas a herramienta que pidió el modelo."""
    mensaje = respuesta["output"]["message"]
    bloques = mensaje.get("content", [])

    textos = [bloque["text"] for bloque in bloques if "text" in bloque]
    llamadas = tuple(
        LlamadaHerramienta(
            id=bloque["toolUse"]["toolUseId"],
            nombre=bloque["toolUse"]["name"],
            entrada=bloque["toolUse"].get("input", {}),
        )
        for bloque in bloques
        if "toolUse" in bloque
    )

    return RespuestaLLM(
        texto=" ".join(textos).strip(),
        llamadas=llamadas,
        mensaje=mensaje,
    )


def resultado_de_herramienta(
    llamada: LlamadaHerramienta, resultado: dict[str, Any]
) -> dict[str, Any]:
    """Arma el mensaje de vuelta que espera `converse` tras ejecutar una herramienta."""
    return {
        "role": "user",
        "content": [
            {
                "toolResult": {
                    "toolUseId": llamada.id,
                    "content": [{"json": resultado}],
                }
            }
        ],
    }
