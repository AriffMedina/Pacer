"""Adaptador de Telegram.

En desarrollo se sondea con `getUpdates`, que no necesita URL pública. En
producción el mismo adaptador se alimenta del webhook: cambia quién entrega el
mensaje, no cómo se procesa.

El canal externo no es "avisos": es el coach buscándote. Que la respuesta del
corredor entre por aquí es lo que cierra el cuarto paso del ciclo sin que tenga
que abrir la app.
"""

import logging
from typing import Any

import httpx

from pacer.domain.puertos.notificacion import MensajeEntrante

BASE = "https://api.telegram.org"
TIEMPO_LIMITE_S = 35.0
# Long polling: la petición se queda esperando en vez de martillar la API.
ESPERA_SONDEO_S = 25

registro = logging.getLogger("pacer")


class AdaptadorTelegram:
    def __init__(self, token: str) -> None:
        self._token = token
        self._cliente = httpx.Client(timeout=TIEMPO_LIMITE_S)

    def _url(self, metodo: str) -> str:
        return f"{BASE}/bot{self._token}/{metodo}"

    def enviar(self, chat_id: int, texto: str) -> None:
        try:
            self._cliente.post(
                self._url("sendMessage"), json={"chat_id": chat_id, "text": texto}
            )
        except httpx.RequestError as fallo:
            registro.warning("no se pudo enviar a Telegram: %s", fallo)

    def recibir(self, desde: int) -> list[MensajeEntrante]:
        """Sondea con long polling. `desde` es el primer update_id no procesado."""
        try:
            respuesta = self._cliente.get(
                self._url("getUpdates"),
                params={"offset": desde, "timeout": ESPERA_SONDEO_S},
            )
        except httpx.RequestError as fallo:
            registro.debug("sondeo de Telegram sin respuesta: %s", fallo)
            return []

        if respuesta.status_code != httpx.codes.OK:
            registro.warning("Telegram respondió %s", respuesta.status_code)
            return []

        return interpretar_actualizaciones(respuesta.json())

    def descargar_voz(self, voz_id: str) -> bytes:
        """Nota de voz: se resuelve la ruta y se baja el .oga."""
        ficha = self._cliente.get(self._url("getFile"), params={"file_id": voz_id})
        ficha.raise_for_status()
        ruta = ficha.json()["result"]["file_path"]

        archivo = self._cliente.get(f"{BASE}/file/bot{self._token}/{ruta}")
        archivo.raise_for_status()
        return archivo.content

    def cerrar(self) -> None:
        self._cliente.close()


def interpretar_actualizaciones(cuerpo: dict[str, Any]) -> list[MensajeEntrante]:
    """Normaliza la respuesta de `getUpdates`.

    Lo que no se sabe atender —stickers, cambios de permisos— se devuelve sin
    contenido en vez de descartarse: su `update_id` tiene que consumirse igual
    o el sondeo se queda atascado repitiéndolo para siempre.
    """
    mensajes = []

    for actualizacion in cuerpo.get("result", []):
        mensaje = actualizacion.get("message") or {}
        voz = mensaje.get("voice") or {}

        mensajes.append(
            MensajeEntrante(
                id_actualizacion=actualizacion.get("update_id", 0),
                chat_id=(mensaje.get("chat") or {}).get("id", 0),
                texto=mensaje.get("text"),
                voz_id=voz.get("file_id"),
            )
        )

    return mensajes
