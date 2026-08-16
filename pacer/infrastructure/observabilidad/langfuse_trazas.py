"""Adaptador de Langfuse.

Envuelve cada llamada al modelo y cada turno en una observación. Un fallo de
trazado NUNCA interrumpe el turno: se traga y se registra, porque perder una
traza es barato y perder la respuesta del coach no.
"""

import logging
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager, nullcontext
from typing import Any

from langfuse import Langfuse

from pacer.domain.puertos.observabilidad import (
    TIPO_SPAN,
    Observacion,
    ObservacionNula,
)

registro = logging.getLogger("pacer")


class ObservacionLangfuse:
    def __init__(self, span: Any) -> None:
        self._span = span

    def registrar_salida(self, salida: Any) -> None:
        try:
            self._span.update(output=salida)
        except Exception as fallo:  # noqa: BLE001 — trazar nunca rompe un turno
            registro.debug("no se pudo registrar la salida: %s", fallo)


class ObservabilidadLangfuse:
    def __init__(self, public_key: str, secret_key: str, base_url: str) -> None:
        self._cliente = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            base_url=base_url,
        )

    @contextmanager
    def _abrir(self, **kwargs: Any) -> Iterator[Observacion]:
        with self._cliente.start_as_current_observation(**kwargs) as span:
            yield ObservacionLangfuse(span)

    def observar(
        self,
        nombre: str,
        tipo: str = TIPO_SPAN,
        entrada: Any = None,
        modelo: str | None = None,
        metadatos: dict[str, Any] | None = None,
    ) -> AbstractContextManager[Observacion]:
        try:
            return self._abrir(
                name=nombre,
                as_type=tipo,
                input=entrada,
                model=modelo,
                metadata=metadatos,
            )
        except Exception as fallo:  # noqa: BLE001
            registro.warning("no se pudo abrir la traza %s: %s", nombre, fallo)
            return nullcontext(ObservacionNula())

    def cerrar(self) -> None:
        try:
            self._cliente.flush()
            self._cliente.shutdown()
        except Exception as fallo:  # noqa: BLE001
            registro.debug("no se pudo cerrar Langfuse: %s", fallo)
