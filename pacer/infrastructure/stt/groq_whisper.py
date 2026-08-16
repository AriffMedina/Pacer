"""Transcripción con Whisper en Groq.

Se eligió sobre Amazon Transcribe por latencia: Transcribe en modo batch es
job-based —subes a S3 y esperas— y eso no sirve para conversación. Cambiar de
proveedor es cambiar el adaptador, no el caso de uso.

Se pide `verbose_json` aunque hoy solo se use el texto: cuesta lo mismo y trae
duración y segmentos, que son la base de la señal de voz.

Sobre los reintentos: medido el 2026-08-16, Groq devuelve 401 "Invalid API Key"
de forma INTERMITENTE con una llave que /models acepta —dos fallos de seis
turnos reales desde el teléfono, con audios equivalentes a los que sí pasaron—.
Una llave inválida o una cuota agotada fallarían siempre. Es transitorio del
proveedor, así que se reintenta en vez de rendirse.
"""

from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from pacer.domain.puertos.voz import ErrorDeTranscripcion, Transcripcion

URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MODELO = "whisper-large-v3-turbo"
IDIOMA = "es"
TIEMPO_LIMITE_S = 30.0

INTENTOS = 3
# Esperas cortas a propósito: hay alguien con el teléfono en la mano esperando.
ESPERA_INICIAL_S = 0.4
ESPERA_MAXIMA_S = 1.5


def _es_recuperable(error: BaseException) -> bool:
    return isinstance(error, ErrorDeTranscripcion) and error.recuperable


class AdaptadorGroqWhisper:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        # Cliente persistente: sin esto cada turno abre una conexión TLS nueva
        # contra api.groq.com y paga el handshake completo.
        self._cliente = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=TIEMPO_LIMITE_S,
        )

    def cerrar(self) -> None:
        self._cliente.close()

    @retry(
        stop=stop_after_attempt(INTENTOS),
        wait=wait_exponential(multiplier=ESPERA_INICIAL_S, max=ESPERA_MAXIMA_S),
        retry=retry_if_exception(_es_recuperable),
        reraise=True,
    )
    def transcribir(self, audio: bytes, nombre_archivo: str) -> Transcripcion:
        try:
            respuesta = self._cliente.post(
                URL,
                files={"file": (nombre_archivo, audio)},
                data={
                    "model": MODELO,
                    "language": IDIOMA,
                    "response_format": "verbose_json",
                },
            )
        except httpx.RequestError as fallo:
            raise ErrorDeTranscripcion(
                f"no se pudo contactar a Groq: {fallo}", recuperable=True
            ) from fallo

        if respuesta.status_code != httpx.codes.OK:
            mensaje, recuperable = describir_fallo(
                respuesta.status_code, respuesta.text
            )
            raise ErrorDeTranscripcion(mensaje, recuperable=recuperable)

        return interpretar_transcripcion(respuesta.json())


def describir_fallo(codigo: int, cuerpo: str) -> tuple[str, bool]:
    """Traduce el error del proveedor y dice si vale la pena reintentar."""
    if codigo in (401, 403):
        mensaje = (
            "Groq rechazó la llave en el endpoint de audio. Se observó de forma"
            " intermitente con llaves válidas; si persiste tras los reintentos,"
            " revisa límites y facturación de audio en la consola."
        )
        return (mensaje, True)
    if codigo == 429:
        return ("Groq está limitando por cuota.", True)
    if codigo >= 500:
        return (f"Groq respondió {codigo}: servicio con problemas.", True)
    return (f"Groq respondió {codigo}: {cuerpo[:200]}", False)


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
