"""Transcripción con Whisper en Groq.

Se eligió sobre Amazon Transcribe por latencia: Transcribe en modo batch es
job-based —subes a S3 y esperas— y eso no sirve para conversación. Cambiar de
proveedor es cambiar el adaptador, no el caso de uso.

Se pide `verbose_json` aunque hoy solo se use el texto: cuesta lo mismo y trae
duración y segmentos, que son la base de la señal de voz.
"""

from typing import Any

import httpx

from pacer.domain.puertos.voz import Transcripcion

URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MODELO = "whisper-large-v3-turbo"
IDIOMA = "es"
TIEMPO_LIMITE_S = 30.0


class AdaptadorGroqWhisper:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def transcribir(self, audio: bytes, nombre_archivo: str) -> Transcripcion:
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
        respuesta.raise_for_status()
        return interpretar_transcripcion(respuesta.json())


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
