"""Puerto de observabilidad.

Trazar no puede ser un requisito para funcionar: si no hay llaves, o Langfuse
está caído, el coach tiene que seguir contestando. Por eso el puerto tiene una
implementación nula que no hace nada y no falla nunca.
"""

from contextlib import AbstractContextManager, nullcontext
from typing import Any, Protocol

TIPO_GENERACION = "generation"
TIPO_HERRAMIENTA = "tool"
TIPO_SPAN = "span"


class Observacion(Protocol):
    def registrar_salida(self, salida: Any) -> None: ...


class PuertoObservabilidad(Protocol):
    def observar(
        self,
        nombre: str,
        tipo: str = TIPO_SPAN,
        entrada: Any = None,
        modelo: str | None = None,
        metadatos: dict[str, Any] | None = None,
    ) -> AbstractContextManager[Observacion]: ...

    def cerrar(self) -> None: ...


class ObservacionNula:
    def registrar_salida(self, salida: Any) -> None:
        return None


class SinObservabilidad:
    """Objeto nulo. Se usa cuando no hay llaves configuradas."""

    def observar(
        self,
        nombre: str,
        tipo: str = TIPO_SPAN,
        entrada: Any = None,
        modelo: str | None = None,
        metadatos: dict[str, Any] | None = None,
    ) -> AbstractContextManager[Observacion]:
        return nullcontext(ObservacionNula())

    def cerrar(self) -> None:
        return None
