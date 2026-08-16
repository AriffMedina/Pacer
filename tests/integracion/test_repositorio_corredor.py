"""El corredor y su conversación, contra una base real.

`vision.md`: "Todo estado importante vive en tablas, no en la conversación."
El perfil son hechos —meta, nivel, fecha, dolor— y hasta ahora vivían en RAM.
"""

from datetime import date

from pacer.domain.entidades.perfil import Perfil
from pacer.infrastructure.persistencia.repositorio_corredor import RepositorioCorredor

CHAT = 55123

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
    """El multiusuario está en el modelo; lo que falta es autenticación."""
    ana = await corredores.obtener_o_crear(telegram_chat_id=1)
    beto = await corredores.obtener_o_crear(telegram_chat_id=2)

    await corredores.guardar_perfil(ana.id, PERFIL)

    assert ana.id != beto.id
    recuperado_beto = await corredores.por_id(beto.id)
    assert recuperado_beto is not None
    assert recuperado_beto.perfil.objetivo is None


async def test_el_piloto_es_siempre_el_mismo(
    corredores: RepositorioCorredor,
) -> None:
    """Web y Telegram atienden a la misma persona en el piloto."""
    primero = await corredores.obtener_o_crear_piloto()
    segundo = await corredores.obtener_o_crear_piloto()

    assert primero.id == segundo.id


async def test_telegram_se_ata_al_piloto_la_primera_vez(
    corredores: RepositorioCorredor,
) -> None:
    piloto = await corredores.obtener_o_crear_piloto()

    await corredores.vincular_telegram(piloto.id, CHAT)
    recuperado = await corredores.por_id(piloto.id)

    assert recuperado is not None
    assert recuperado.telegram_chat_id == CHAT


async def test_la_conversacion_sobrevive_al_reinicio(
    corredores: RepositorioCorredor,
) -> None:
    """El bonus del correo: memoria de conversaciones anteriores."""
    piloto = await corredores.obtener_o_crear_piloto()

    await corredores.recordar(piloto.id, "user", "quiero un medio maratón")
    await corredores.recordar(piloto.id, "assistant", "¿Cuándo es la carrera?")
    await corredores.recordar(piloto.id, "user", "el 1 de noviembre")

    turnos = await corredores.ultimos_turnos(piloto.id, cuantos=10)

    assert [t["role"] for t in turnos] == ["user", "assistant", "user"]
    assert turnos[0]["content"][0]["text"] == "quiero un medio maratón"


async def test_solo_se_cargan_los_ultimos_turnos(
    corredores: RepositorioCorredor,
) -> None:
    # El historial completo no cabe ni conviene: el estado lo dan las tablas.
    piloto = await corredores.obtener_o_crear_piloto()
    for i in range(10):
        await corredores.recordar(piloto.id, "user", f"mensaje {i}")

    turnos = await corredores.ultimos_turnos(piloto.id, cuantos=3)

    assert len(turnos) == 3
    assert turnos[-1]["content"][0]["text"] == "mensaje 9"


async def test_la_conversacion_de_otro_corredor_no_se_mezcla(
    corredores: RepositorioCorredor,
) -> None:
    ana = await corredores.obtener_o_crear(telegram_chat_id=1)
    beto = await corredores.obtener_o_crear(telegram_chat_id=2)

    await corredores.recordar(ana.id, "user", "lo de Ana")

    assert await corredores.ultimos_turnos(beto.id, cuantos=10) == []


async def test_el_corredor_nace_sin_credenciales(
    corredores: RepositorioCorredor,
) -> None:
    """`email` y `password_hash` existen desde hoy, vacíos.

    Así, agregar login más adelante no requiere migrar el esquema: solo
    llenarlos.
    """
    corredor = await corredores.obtener_o_crear(telegram_chat_id=CHAT)

    assert corredor.email is None
    assert corredor.password_hash is None
