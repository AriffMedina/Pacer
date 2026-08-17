"""Recordatorios contra una base real. La idempotencia se prueba, no se asume."""

from datetime import UTC, datetime

from pacer.domain.entidades.recordatorio import Recordatorio
from pacer.infrastructure.persistencia.repositorio_corredor import RepositorioCorredor
from pacer.infrastructure.persistencia.repositorio_recordatorio import (
    RepositorioRecordatorio,
)

AYER = datetime(2026, 8, 20, 19, tzinfo=UTC)
HOY = datetime(2026, 8, 21, 12, tzinfo=UTC)
MANANA = datetime(2026, 8, 22, 19, tzinfo=UTC)


def uno(corredor_id: int, clave: str, cuando: datetime) -> Recordatorio:
    return Recordatorio(
        corredor_id=corredor_id,
        texto="¿Cómo te fue?",
        programado_para=cuando,
        clave=clave,
    )


async def test_se_guarda_y_aparece_como_vencido(
    corredores: RepositorioCorredor, recordatorios: RepositorioRecordatorio
) -> None:
    corredor = await corredores.obtener_o_crear_por_sesion("sesion-de-prueba")

    nuevos = await recordatorios.materializar([uno(corredor.id, "a", AYER)])
    vencidos = await recordatorios.vencidos(HOY)

    assert nuevos == 1
    assert len(vencidos) == 1
    assert vencidos[0].texto == "¿Cómo te fue?"


async def test_materializar_dos_veces_no_duplica(
    corredores: RepositorioCorredor, recordatorios: RepositorioRecordatorio
) -> None:
    """El materializador corre cada noche; no puede llenar el chat de repetidos."""
    corredor = await corredores.obtener_o_crear_por_sesion("sesion-de-prueba")
    mismo = [uno(corredor.id, "a", AYER)]

    primera = await recordatorios.materializar(mismo)
    segunda = await recordatorios.materializar(mismo)

    assert primera == 1
    assert segunda == 0
    assert len(await recordatorios.vencidos(HOY)) == 1


async def test_lo_que_todavia_no_toca_no_esta_vencido(
    corredores: RepositorioCorredor, recordatorios: RepositorioRecordatorio
) -> None:
    corredor = await corredores.obtener_o_crear_por_sesion("sesion-de-prueba")

    await recordatorios.materializar([uno(corredor.id, "a", MANANA)])

    assert await recordatorios.vencidos(HOY) == []


async def test_confirmar_lo_saca_de_los_vencidos(
    corredores: RepositorioCorredor, recordatorios: RepositorioRecordatorio
) -> None:
    corredor = await corredores.obtener_o_crear_por_sesion("sesion-de-prueba")
    await recordatorios.materializar([uno(corredor.id, "a", AYER)])
    pendiente = (await recordatorios.vencidos(HOY))[0]

    confirmado = await recordatorios.confirmar(pendiente.id, "msg_123")

    assert confirmado
    assert await recordatorios.vencidos(HOY) == []


async def test_confirmar_dos_veces_no_reenvia(
    corredores: RepositorioCorredor, recordatorios: RepositorioRecordatorio
) -> None:
    """Un reintento de n8n devuelve False; nunca duplica la entrega."""
    corredor = await corredores.obtener_o_crear_por_sesion("sesion-de-prueba")
    await recordatorios.materializar([uno(corredor.id, "a", AYER)])
    pendiente = (await recordatorios.vencidos(HOY))[0]

    primera = await recordatorios.confirmar(pendiente.id)
    segunda = await recordatorios.confirmar(pendiente.id)

    assert primera
    assert not segunda


async def test_confirmar_algo_inexistente_no_revienta(
    recordatorios: RepositorioRecordatorio,
) -> None:
    assert not await recordatorios.confirmar(9999)


async def test_el_vencido_viaja_con_el_chat_al_que_va(
    corredores: RepositorioCorredor, recordatorios: RepositorioRecordatorio
) -> None:
    """A quién entregar lo decide el backend, no un campo fijo en n8n."""
    corredor = await corredores.obtener_o_crear_por_sesion("sesion-de-prueba")
    await corredores.vincular_telegram(corredor.id, 987654)
    await recordatorios.materializar([uno(corredor.id, "a", AYER)])

    con_destino = await recordatorios.vencidos_con_destino(HOY)

    assert len(con_destino) == 1
    _, chat_id = con_destino[0]
    assert chat_id == 987654


async def test_sin_canal_vinculado_no_sale_a_entregarse(
    corredores: RepositorioCorredor, recordatorios: RepositorioRecordatorio
) -> None:
    """Un recordatorio sin destino solo haría fallar la entrega."""
    corredor = await corredores.obtener_o_crear_por_sesion("sesion-de-prueba")
    await recordatorios.materializar([uno(corredor.id, "a", AYER)])

    assert await recordatorios.vencidos_con_destino(HOY) == []
    # Sigue existiendo: cuando vincule Telegram, se entrega.
    assert len(await recordatorios.vencidos(HOY)) == 1


async def test_cada_corredor_recibe_en_su_propio_chat(
    corredores: RepositorioCorredor, recordatorios: RepositorioRecordatorio
) -> None:
    ana = await corredores.obtener_o_crear(telegram_chat_id=111)
    beto = await corredores.obtener_o_crear(telegram_chat_id=222)
    await recordatorios.materializar(
        [uno(ana.id, "ana", AYER), uno(beto.id, "beto", AYER)]
    )

    destinos = {
        r.clave: chat for r, chat in await recordatorios.vencidos_con_destino(HOY)
    }

    assert destinos == {"ana": 111, "beto": 222}


async def test_los_vencidos_salen_del_mas_viejo_al_mas_nuevo(
    corredores: RepositorioCorredor, recordatorios: RepositorioRecordatorio
) -> None:
    corredor = await corredores.obtener_o_crear_por_sesion("sesion-de-prueba")
    anteayer = datetime(2026, 8, 19, 19, tzinfo=UTC)

    await recordatorios.materializar(
        [uno(corredor.id, "nuevo", AYER), uno(corredor.id, "viejo", anteayer)]
    )
    vencidos = await recordatorios.vencidos(HOY)

    assert [r.clave for r in vencidos] == ["viejo", "nuevo"]
