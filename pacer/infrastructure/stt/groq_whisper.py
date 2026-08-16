"""Transcripción con Whisper en Groq.

Se eligió sobre Amazon Transcribe por latencia: Transcribe en modo batch es
job-based —subes a S3 y esperas— y eso no sirve para conversación. Cambiar de
proveedor es cambiar el adaptador, no el caso de uso.

Se pide `verbose_json` aunque hoy solo se use el texto: cuesta lo mismo y trae
duración y segmentos, que son la base de la señal de voz.
"""

from typing import Any

import httpx

from pacer.domain.puertos.voz import ErrorDeTranscripcion, Transcripcion

URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MODELO = "whisper-large-v3-turbo"
IDIOMA = "es"
TIEMPO_LIMITE_S = 30.0


class AdaptadorGroqWhisper:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def transcribir(self, audio: bytes, nombre_archivo: str) -> Transcripcion:
        try:
            respuesta = httpx.post(
                URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                files={"file": (nombre_archivo, audio)},
                data={
                    "model": MODELO,
                    "language": IDIOMA,
                    "response_format": "verbose_json",
                },
                timeout=TIEMPO_LIMITE_S,
            )
        except httpx.RequestError as fallo:
            raise ErrorDeTranscripcion(
                f"no se pudo contactar a Groq: {fallo}", recuperable=True
            ) from fallo

        if respuesta.status_code != httpx.codes.OK:
            raise ErrorDeTranscripcion(
                describir_fallo(respuesta.status_code, respuesta.text),
                recuperable=respuesta.status_code >= 500,
            )

        return interpretar_transcripcion(respuesta.json())


def describir_fallo(codigo: int, cuerpo: str) -> str:
    """Traduce el error del proveedor a algo accionable.

    Groq devuelve 401 "Invalid API Key" en el endpoint de audio incluso con
    llaves que /models acepta, cuando la cuenta no tiene habilitado o agotó el
    acceso a audio. El mensaje literal manda a revisar la llave y hace perder
    el tiempo en el lugar equivocado.
    """
    if codigo in (401, 403):
        return (
            "Groq rechazó la llave en el endpoint de audio. Si la misma llave "
            "funciona en /models, revisa límites y facturación de audio en la "
            "consola de Groq, no la llave."
        )
    if codigo == 429:
        return "Groq está limitando por cuota. Espera o sube el plan."
    return f"Groq respondió {codigo}: {cuerpo[:200]}"


def interpretar_transcripcion(cuerpo: dict[str, Any]) -> Transcripcion:
    """Saca el texto y la señal de voz de la respuesta de Whisper."""
    texto = str(cuerpo.get("text", "")).strip()
    duracion = float(cuerpo.get("duration", 0) or 0)
    palabras = len(texto.split())

    return Transcripcion(
        texto=texto,
        duracion_s=duracion,
        palabras_por_s=palabras / duracion if duracion > 0 else 0.0,
    )
