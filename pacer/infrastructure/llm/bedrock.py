"""Adaptador de Amazon Bedrock sobre la API `converse`.

Nota que vale para el ADR-003: los modelos de Amazon se invocan con su id
directo (`amazon.nova-lite-v1:0`), pero los de Anthropic en Bedrock exigen un
inference profile (`us.anthropic.claude-haiku-4-5-...`). No son intercambiables
por id, y esconder esa diferencia es exactamente el trabajo del puerto.
"""

from typing import Any

import boto3

from pacer.domain.puertos.llm import LlamadaHerramienta, RespuestaLLM


class AdaptadorBedrock:
    def __init__(self, model_id: str, region: str) -> None:
        self._cliente = boto3.client("bedrock-runtime", region_name=region)
        self._model_id = model_id

    def conversar(
        self,
        sistema: str,
        mensajes: list[dict[str, Any]],
        herramientas: dict[str, Any],
    ) -> RespuestaLLM:
        respuesta = self._cliente.converse(
            modelId=self._model_id,
            system=[{"text": sistema}],
            messages=mensajes,
            toolConfig=herramientas,
            inferenceConfig={"temperature": 0},
        )
        return interpretar_respuesta(respuesta)


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
