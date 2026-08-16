"""Sondeo de Telegram para desarrollo.

`getUpdates` con long polling no necesita URL pública, así que el ciclo se
cierra desde la laptop sin túnel ni despliegue. En producción el webhook
entrega el mismo `MensajeEntrante` al mismo caso de uso: cambia quién trae el
mensaje, no qué se hace con él.
"""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from pacer.domain.puertos.notificacion import MensajeEntrante, PuertoNotificacion

registro = logging.getLogger("pacer")

ESPERA_TRAS_FALLO_S = 5.0

Atendedor = Callable[[MensajeEntrante], Coroutine[Any, Any, Any]]


async def sondear(canal: PuertoNotificacion, atender: Atendedor) -> None:
    """Ciclo infinito de sondeo. Se cancela al apagar la app."""
    siguiente = 0

    while True:
        try:
            mensajes = await asyncio.to_thread(canal.recibir, siguiente)

            for mensaje in mensajes:
                # El offset avanza SIEMPRE, incluso con mensajes que no se
                # atienden. Si no, un sticker deja el sondeo repitiéndolo eterno.
                siguiente = mensaje.id_actualizacion + 1
                try:
                    await atender(mensaje)
                except Exception as fallo:  # noqa: BLE001
                    registro.exception("mensaje de Telegram no atendido: %s", fallo)

        except asyncio.CancelledError:
            raise
        except Exception as fallo:  # noqa: BLE001 — el sondeo no se muere nunca
            registro.warning("sondeo de Telegram falló: %s", fallo)
            await asyncio.sleep(ESPERA_TRAS_FALLO_S)
