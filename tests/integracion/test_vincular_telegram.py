"""Canjear el código: el navegador y el chat pasan a ser la misma persona.

El fallo que esto arregla, medido en la base de producción antes de existir:
tres corredores, los tres solo de web, cero con las dos identidades. Quien
armaba su plan hablando por la web y luego le escribía al bot era, para el
bot, alguien que llegaba de cero.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from pacer.domain.servicios.vinculacion import DURACION, vence_en
from pacer.infrastructure.persistencia.repositorio_corredor import RepositorioCorredor

AHORA = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)
NAVEGADOR = "cookie-del-navegador"
OTRO = "cookie-de-otra-persona"
CHAT = 8_589_934_592  # por encima de int32, como los chat id reales
OTRO_CHAT = 8_589_934_593


async def _con_codigo(repo: RepositorioCorredor, clave: str, codigo: str) -> int:
    corredor = await repo.obtener_o_crear_por_sesion(clave)
    await repo.guardar_codigo_telegram(corredor.id, codigo, vence_en(AHORA))
    return corredor.id


# --- el canje ------------------------------------------------------------


async def test_el_codigo_une_el_chat_al_corredor_de_la_web(
    sesion_bd: AsyncSession,
) -> None:
    repo = RepositorioCorredor(sesion_bd)
    mio = await _con_codigo(repo, NAVEGADOR, "123456")

    canjeado = await repo.canjear_codigo_telegram("123456", CHAT, AHORA)

    assert canjeado is not None
    assert canjeado.id == mio
    assert (await repo.obtener_o_crear(CHAT)).id == mio


async def test_despues_de_vincular_la_web_sigue_siendo_el_mismo(
    sesion_bd: AsyncSession,
) -> None:
    """Vincular no puede costarte el plan que ya tenías en el navegador."""
    repo = RepositorioCorredor(sesion_bd)
    mio = await _con_codigo(repo, NAVEGADOR, "123456")

    await repo.canjear_codigo_telegram("123456", CHAT, AHORA)

    assert (await repo.obtener_o_crear_por_sesion(NAVEGADOR)).id == mio


async def test_el_codigo_solo_sirve_una_vez(sesion_bd: AsyncSession) -> None:
    """Si sobreviviera al canje, cualquiera que lo viera por encima del hombro
    entraría a la conversación de otro."""
    repo = RepositorioCorredor(sesion_bd)
    await _con_codigo(repo, NAVEGADOR, "123456")

    await repo.canjear_codigo_telegram("123456", CHAT, AHORA)

    assert await repo.canjear_codigo_telegram("123456", OTRO_CHAT, AHORA) is None


async def test_un_codigo_expirado_no_canjea(sesion_bd: AsyncSession) -> None:
    repo = RepositorioCorredor(sesion_bd)
    await _con_codigo(repo, NAVEGADOR, "123456")

    tarde = AHORA + DURACION + timedelta(seconds=1)
    assert await repo.canjear_codigo_telegram("123456", CHAT, tarde) is None


async def test_un_codigo_que_nadie_pidio_no_canjea(sesion_bd: AsyncSession) -> None:
    repo = RepositorioCorredor(sesion_bd)
    await repo.obtener_o_crear_por_sesion(NAVEGADOR)

    assert await repo.canjear_codigo_telegram("999999", CHAT, AHORA) is None


# --- casos que muerden ---------------------------------------------------


async def test_pedir_otro_codigo_invalida_el_anterior(
    sesion_bd: AsyncSession,
) -> None:
    """Dictas uno, te equivocas, pides otro. El primero tiene que morir ahí:
    dos códigos vivos son dos llaves de tu cuenta dando vueltas."""
    repo = RepositorioCorredor(sesion_bd)
    corredor_id = await _con_codigo(repo, NAVEGADOR, "111111")

    await repo.guardar_codigo_telegram(corredor_id, "222222", vence_en(AHORA))

    assert await repo.canjear_codigo_telegram("111111", CHAT, AHORA) is None
    assert (await repo.canjear_codigo_telegram("222222", CHAT, AHORA)) is not None


async def test_el_chat_se_muda_al_corredor_de_la_web(
    sesion_bd: AsyncSession,
) -> None:
    """El caso real: ya le habías escrito al bot antes de vincular, así que
    ese chat ya tenía SU corredor. `telegram_chat_id` es UNIQUE — sin soltarlo
    del anterior, el canje revienta contra el índice.
    """
    repo = RepositorioCorredor(sesion_bd)
    suelto = await repo.obtener_o_crear(CHAT)
    mio = await _con_codigo(repo, NAVEGADOR, "123456")
    assert suelto.id != mio

    canjeado = await repo.canjear_codigo_telegram("123456", CHAT, AHORA)

    assert canjeado is not None and canjeado.id == mio
    assert (await repo.obtener_o_crear(CHAT)).id == mio


async def test_el_codigo_de_uno_no_secuestra_al_otro(
    sesion_bd: AsyncSession,
) -> None:
    repo = RepositorioCorredor(sesion_bd)
    await _con_codigo(repo, NAVEGADOR, "111111")
    ajeno = await _con_codigo(repo, OTRO, "222222")

    canjeado = await repo.canjear_codigo_telegram("222222", CHAT, AHORA)

    assert canjeado is not None and canjeado.id == ajeno
