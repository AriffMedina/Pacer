"""El corredor y su conversación, contra una base real.

`vision.md`: "Todo estado importante vive en tablas, no en la conversación."
El perfil son hechos —meta, nivel, fecha, dolor— y hasta ahora vivían en RAM.
"""

from datetime import date

from pacer.domain.entidades.perfil import Perfil
from pacer.infrastructure.persistencia.repositorio_corredor import RepositorioCorredor

# Un chat id real de Telegram tiene 10 digitos y NO cabe en un int32.
# Probar con numeros comodos ocultaba que la columna era INTEGER.
CHAT = 5457315468

PERFIL = Perfil(
    objetivo="21k",
    nivel="intermedio",
    dias_disponibles=4,
    km_semana=25,
    fecha_carrera=date(2026, 11, 1),
)


async def test_un_corredor_nuevo_se_crea_al_buscarlo(
    corredores: RepositorioCorredor,
) -> None:
    corredor = await corredores.obtener_o_crear(telegram_chat_id=CHAT)

    assert corredor.id > 0
    assert corredor.perfil == Perfil()


async def test_el_mismo_chat_devuelve_el_mismo_corredor(
    corredores: RepositorioCorredor,
) -> None:
    primero = await corredores.obtener_o_crear(telegram_chat_id=CHAT)
    segundo = await corredores.obtener_o_crear(telegram_chat_id=CHAT)

    assert primero.id == segundo.id


async def test_el_perfil_sobrevive_al_reinicio(
    corredores: RepositorioCorredor,
) -> None:
    corredor = await corredores.obtener_o_crear(telegram_chat_id=CHAT)

    await corredores.guardar_perfil(corredor.id, PERFIL)
    recuperado = await corredores.por_id(corredor.id)

    assert recuperado is not None
    assert recuperado.perfil.objetivo == "21k"
    assert recuperado.perfil.fecha_carrera == date(2026, 11, 1)
    assert recuperado.perfil.dias_disponibles == 4


async def test_guardar_el_perfil_no_duplica_corredores(
    corredores: RepositorioCorredor,
) -> None:
    corredor = await corredores.obtener_o_crear(telegram_chat_id=CHAT)

    await corredores.guardar_perfil(corredor.id, PERFIL)
    await corredores.guardar_perfil(corredor.id, PERFIL)

    assert (await corredores.obtener_o_crear(telegram_chat_id=CHAT)).id == corredor.id


async def test_dos_corredores_quedan_aislados(
    corredores: RepositorioCorredor,
) -> None:
    """Cada corredor con sus datos: es la garantía que sostiene todo lo demás."""
    ana = await corredores.obtener_o_crear(telegram_chat_id=7123456789)
    beto = await corredores.obtener_o_crear(telegram_chat_id=8987654321)

    await corredores.guardar_perfil(ana.id, PERFIL)

    assert ana.id != beto.id
    recuperado_beto = await corredores.por_id(beto.id)
    assert recuperado_beto is not None
    assert recuperado_beto.perfil.objetivo is None


async def test_el_mismo_navegador_devuelve_el_mismo_corredor(
    corredores: RepositorioCorredor,
) -> None:
    """La cookie es la identidad mientras no haya cuenta."""
    primero = await corredores.obtener_o_crear_por_sesion("sesion-de-prueba")
    segundo = await corredores.obtener_o_crear_por_sesion("sesion-de-prueba")

    assert primero.id == segundo.id


async def test_telegram_se_ata_al_corredor_la_primera_vez(
    corredores: RepositorioCorredor,
) -> None:
    corredor = await corredores.obtener_o_crear_por_sesion("sesion-de-prueba")

    await corredores.vincular_telegram(corredor.id, CHAT)
    recuperado = await corredores.por_id(corredor.id)

    assert recuperado is not None
    assert recuperado.telegram_chat_id == CHAT


async def test_la_conversacion_sobrevive_al_reinicio(
    corredores: RepositorioCorredor,
) -> None:
    """El bonus del correo: memoria de conversaciones anteriores."""
    corredor = await corredores.obtener_o_crear_por_sesion("sesion-de-prueba")

    await corredores.recordar(corredor.id, "user", "quiero un medio maratón")
    await corredores.recordar(corredor.id, "assistant", "¿Cuándo es la carrera?")
    await corredores.recordar(corredor.id, "user", "el 1 de noviembre")

    turnos = await corredores.ultimos_turnos(corredor.id, cuantos=10)

    assert [t["role"] for t in turnos] == ["user", "assistant", "user"]
    assert turnos[0]["content"][0]["text"] == "quiero un medio maratón"


async def test_solo_se_cargan_los_ultimos_turnos(
    corredores: RepositorioCorredor,
) -> None:
    # El historial completo no cabe ni conviene: el estado lo dan las tablas.
    corredor = await corredores.obtener_o_crear_por_sesion("sesion-de-prueba")
    for i in range(10):
        await corredores.recordar(corredor.id, "user", f"pregunta {i}")
        await corredores.recordar(corredor.id, "assistant", f"respuesta {i}")

    turnos = await corredores.ultimos_turnos(corredor.id, cuantos=4)

    assert len(turnos) == 4
    assert turnos[0]["role"] == "user"
    assert turnos[-1]["content"][0]["text"] == "respuesta 9"


async def test_la_conversacion_de_otro_corredor_no_se_mezcla(
    corredores: RepositorioCorredor,
) -> None:
    ana = await corredores.obtener_o_crear(telegram_chat_id=7123456789)
    beto = await corredores.obtener_o_crear(telegram_chat_id=8987654321)

    await corredores.recordar(ana.id, "user", "lo de Ana")

    assert await corredores.ultimos_turnos(beto.id, cuantos=10) == []


async def test_el_corredor_nace_sin_credenciales(
    corredores: RepositorioCorredor,
) -> None:
    """Se corre sin cuenta. Las credenciales se llenan solo si te registras."""
    corredor = await corredores.obtener_o_crear(telegram_chat_id=CHAT)

    assert corredor.email is None
    assert corredor.password_hash is None
