"""Quién es quién.

Hasta ahora la web devolvía SIEMPRE el primer corredor de la tabla: compartir
el enlace era compartir la cuenta. Cada navegador es ahora su propio corredor, y
una cuenta opcional se queda con el que ya venías usando.
"""

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pacer.domain.entidades.corredor import Corredor
from pacer.infrastructure.persistencia.modelos import Base
from pacer.infrastructure.persistencia.repositorio_corredor import RepositorioCorredor
from pacer.infrastructure.seguridad import cifrar

CLAVE = "una-clave-de-navegador"
OTRA = "otro-navegador-distinto"


# --- sesión anónima ------------------------------------------------------


async def test_cada_navegador_es_un_corredor_distinto(sesion_bd: AsyncSession) -> None:
    """El fallo que esto arregla: mandar el enlace a alguien le daba TU plan."""
    repositorio = RepositorioCorredor(sesion_bd)

    uno = await repositorio.obtener_o_crear_por_sesion(CLAVE)
    otro = await repositorio.obtener_o_crear_por_sesion(OTRA)

    assert uno.id != otro.id


async def test_el_mismo_navegador_vuelve_a_lo_suyo(sesion_bd: AsyncSession) -> None:
    repositorio = RepositorioCorredor(sesion_bd)

    primero = await repositorio.obtener_o_crear_por_sesion(CLAVE)
    await repositorio.guardar_perfil(
        primero.id, primero.perfil.__class__(nombre="Ari", objetivo="10k")
    )
    devuelto = await repositorio.obtener_o_crear_por_sesion(CLAVE)

    assert devuelto.id == primero.id
    assert devuelto.perfil.nombre == "Ari"


# --- cuenta --------------------------------------------------------------


async def test_registrarse_adopta_el_corredor_que_ya_tenias(
    sesion_bd: AsyncSession,
) -> None:
    """Nadie pierde su plan por crear la cuenta: la cuenta se queda con él."""
    repositorio = RepositorioCorredor(sesion_bd)
    anonimo = await repositorio.obtener_o_crear_por_sesion(CLAVE)

    await repositorio.guardar_credenciales(
        anonimo.id, "ari@ejemplo.mx", cifrar("correr-es-vida")
    )
    con_cuenta = await repositorio.por_email("ari@ejemplo.mx")

    assert con_cuenta is not None
    assert con_cuenta.id == anonimo.id
    assert con_cuenta.email == "ari@ejemplo.mx"


async def test_el_correo_no_se_puede_repetir(sesion_bd: AsyncSession) -> None:
    repositorio = RepositorioCorredor(sesion_bd)
    uno = await repositorio.obtener_o_crear_por_sesion(CLAVE)
    otro = await repositorio.obtener_o_crear_por_sesion(OTRA)

    await repositorio.guardar_credenciales(uno.id, "ari@ejemplo.mx", cifrar("clave-larga"))
    ok = await repositorio.guardar_credenciales(
        otro.id, "ari@ejemplo.mx", cifrar("otra-clave-larga")
    )

    assert ok is False


async def test_entrar_mueve_el_navegador_a_la_cuenta(sesion_bd: AsyncSession) -> None:
    """Entras desde otro navegador y esa ventana pasa a ser tu cuenta."""
    repositorio = RepositorioCorredor(sesion_bd)
    mio = await repositorio.obtener_o_crear_por_sesion(CLAVE)
    await repositorio.guardar_credenciales(mio.id, "ari@ejemplo.mx", cifrar("clave-larga"))
    await repositorio.obtener_o_crear_por_sesion(OTRA)

    await repositorio.mudar_sesion(mio.id, OTRA)

    assert (await repositorio.obtener_o_crear_por_sesion(OTRA)).id == mio.id


async def test_al_mudar_la_sesion_nadie_queda_con_la_llave_repetida(
    sesion_bd: AsyncSession,
) -> None:
    """`clave_sesion` es UNIQUE: sin soltarla del anterior, el UPDATE revienta."""
    repositorio = RepositorioCorredor(sesion_bd)
    mio = await repositorio.obtener_o_crear_por_sesion(CLAVE)
    ajeno = await repositorio.obtener_o_crear_por_sesion(OTRA)

    await repositorio.mudar_sesion(mio.id, OTRA)

    devuelto = await repositorio.obtener_o_crear_por_sesion(OTRA)
    assert devuelto.id == mio.id
    assert devuelto.id != ajeno.id


async def test_un_correo_que_no_existe_no_devuelve_a_nadie(
    sesion_bd: AsyncSession,
) -> None:
    assert await RepositorioCorredor(sesion_bd).por_email("nadie@ejemplo.mx") is None


async def test_quien_pierde_la_carrera_encuentra_la_fila_de_la_otra(
    tmp_path: "Path",
) -> None:
    """Al abrir la app salen tres peticiones con la misma cookie a la vez.

    Cada una es una sesión distinta: todas miran, ninguna encuentra y todas
    insertan. Una gana y el resto choca contra el UNIQUE. Medido en vivo — la
    primera carga devolvía 500. Quien pierde vuelve a mirar y encuentra la fila
    que acaba de crear la otra, en vez de reventar.

    Hace falta una base en ARCHIVO: dos motores sobre SQLite en memoria no
    comparten datos y la carrera no se puede reproducir.
    """
    motor = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'carrera.db'}")
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(motor, expire_on_commit=False)

    async with fabrica() as primera, fabrica() as segunda:
        rezagada = RepositorioCorredor(primera)
        # La otra petición mira y no encuentra nada...
        assert await _mira(rezagada) is None
        # ...pero mientras tanto la rival crea la fila y hace commit.
        ganadora = await RepositorioCorredor(segunda).obtener_o_crear_por_sesion(CLAVE)
        # Y la rezagada intenta insertar la suya.
        alcanzada = await rezagada.obtener_o_crear_por_sesion(CLAVE)

    await motor.dispose()
    assert alcanzada.id == ganadora.id


async def _mira(repositorio: RepositorioCorredor) -> Corredor | None:
    return await repositorio.por_email("nadie@ejemplo.mx")
