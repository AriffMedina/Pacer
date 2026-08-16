"""Puerto del canal externo.

Telegram es el único canal del piloto, pero el caso de uso no lo sabe: recibe
mensajes con esta forma y responde por este puerto.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MensajeEntrante:
    """Lo que llega del canal, ya normalizado."""

    id_actualizacion: int
    chat_id: int
    texto: str | None = None
    voz_id: str | None = None

    @property
    def es_voz(self) -> bool:
        return self.voz_id is not None

    @property
    def tiene_contenido(self) -> bool:
        return bool(self.texto) or self.es_voz


class PuertoNotificacion(Protocol):
    def enviar(self, chat_id: int, texto: str) -> None: ...

    def recibir(self, desde: int) -> list[MensajeEntrante]: ...

    def descargar_voz(self, voz_id: str) -> bytes: ...
