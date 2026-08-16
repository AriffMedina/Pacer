"""Puerto del proveedor de lenguaje.

El dominio define la forma; la infraestructura la implementa. Cambiar de
proveedor no toca nada de lo que está detrás de esta frontera.
"""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class LlamadaHerramienta:
    id: str
    nombre: str
    entrada: dict[str, Any]


@dataclass(frozen=True)
class RespuestaLLM:
    texto: str
    llamadas: tuple[LlamadaHerramienta, ...]
    mensaje: dict[str, Any]
    """El mensaje tal cual lo devolvió el proveedor, para reenviarlo en el turno."""


class PuertoLLM(Protocol):
    def conversar(
        self,
        sistema: str,
        mensajes: list[dict[str, Any]],
        herramientas: dict[str, Any],
    ) -> RespuestaLLM: ...
