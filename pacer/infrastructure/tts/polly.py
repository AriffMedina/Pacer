"""Síntesis de voz con Amazon Polly.

En us-east-1 hay voces `generative` y `neural` para es-MX; en us-east-2 solo
`Mia` standard. Por eso el proyecto vive en us-east-1.

El texto pasa por `preparar_para_voz` antes de sintetizar: el modelo responde
en markdown y Polly lee los asteriscos literalmente.
"""

import re
from typing import Any

import boto3

LIMITE_CARACTERES = 2800  # Polly factura hasta 3000 por llamada.

_NEGRITA = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_CURSIVA = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", re.DOTALL)
_VINETA = re.compile(r"^\s*[-*•]\s+", re.MULTILINE)
_SALTOS = re.compile(r"\n+")
_ESPACIOS = re.compile(r"[ \t]+")


class AdaptadorPolly:
    def __init__(self, region: str, voz: str, motor: str) -> None:
        self._cliente = boto3.client("polly", region_name=region)
        self._voz = voz
        self._motor = motor

    def sintetizar(self, texto: str) -> bytes:
        respuesta: dict[str, Any] = self._cliente.synthesize_speech(
            Text=preparar_para_voz(texto),
            OutputFormat="mp3",
            VoiceId=self._voz,
            Engine=self._motor,
            LanguageCode="es-MX",
        )
        audio: bytes = respuesta["AudioStream"].read()
        return audio


def preparar_para_voz(texto: str) -> str:
    """Limpia markdown y estructura visual que no tienen sentido habladas."""
    limpio = _NEGRITA.sub(r"\1", texto)
    limpio = _CURSIVA.sub(r"\1", limpio)
    limpio = _VINETA.sub("", limpio)
    limpio = _SALTOS.sub(". ", limpio)
    limpio = _ESPACIOS.sub(" ", limpio).strip()

    if len(limpio) > LIMITE_CARACTERES:
        limpio = limpio[:LIMITE_CARACTERES].rsplit(" ", 1)[0]

    return limpio
