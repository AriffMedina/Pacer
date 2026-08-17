"""El sondeo de Telegram se puede apagar sin borrar el token.

Telegram entrega cada actualización a UN solo `getUpdates`. Dos procesos con
el mismo token se pelean los mensajes: pasó de verdad —el portátil y EC2
contestando el mismo mensaje con planes distintos, porque cada uno miraba su
propia base— y desde fuera se ve como un bot que responde dos veces.

Borrar el token del `.env` local también lo arregla, pero entonces hay que
acordarse de volver a ponerlo, y ese es justo el paso que se olvida.
"""

import os
from collections.abc import Iterator

import pytest

from pacer.infrastructure.configuracion import Configuracion


@pytest.fixture(autouse=True)
def entorno_limpio() -> Iterator[None]:
    previo = dict(os.environ)
    for llave in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_SONDEO"):
        os.environ.pop(llave, None)
    yield
    os.environ.clear()
    os.environ.update(previo)


def test_con_token_y_sin_decir_nada_el_bot_escucha() -> None:
    """El comportamiento de siempre no cambia: quien no sabe que esto existe
    no tiene que hacer nada."""
    assert Configuracion(telegram_bot_token="123:abc").telegram_disponible is True


def test_apagarlo_calla_el_sondeo_aunque_el_token_siga_puesto() -> None:
    assert (
        Configuracion(
            telegram_bot_token="123:abc", telegram_sondeo=False
        ).telegram_disponible
        is False
    )


def test_sin_token_da_igual_lo_que_diga_la_bandera() -> None:
    assert (
        Configuracion(telegram_bot_token="", telegram_sondeo=True).telegram_disponible
        is False
    )


def test_se_apaga_desde_el_entorno() -> None:
    """Es como se va a usar de verdad: una línea en el `.env` de la máquina de
    desarrollo, sin tocar el token ni el código."""
    os.environ["TELEGRAM_BOT_TOKEN"] = "123:abc"
    os.environ["TELEGRAM_SONDEO"] = "false"

    assert Configuracion().telegram_disponible is False
