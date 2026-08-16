"""Puertos de voz: transcripción y síntesis.

Quién transcribe —Groq, Whisper local, Transcribe— y quién sintetiza —Polly u
otro— es decisión de infraestructura. El caso de uso solo conoce estas formas.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Transcripcion:
    texto: str
    duracion_s: float = 0.0
    palabras_por_s: float = 0.0
    """Señal de voz nivel 1: sirve para que el coach note cansancio. Nunca toca el plan."""


class ErrorDeTranscripcion(Exception):
    """El proveedor de transcripción no pudo atender el turno.

    Existe para que la interfaz no tenga que saber de httpx ni de códigos HTTP
    de un proveedor concreto, y para que un fallo del proveedor se vea como un
    mensaje y no como un stack trace en medio de una demo.
    """

    def __init__(self, motivo: str, recuperable: bool = False) -> None:
        super().__init__(motivo)
        self.motivo = motivo
        self.recuperable = recuperable


class PuertoSTT(Protocol):
    def transcribir(self, audio: bytes, nombre_archivo: str) -> Transcripcion: ...


class PuertoTTS(Protocol):
    def sintetizar(self, texto: str) -> bytes: ...
