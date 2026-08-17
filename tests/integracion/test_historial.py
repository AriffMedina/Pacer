"""El historial que se le manda al modelo tiene que ser válido SIEMPRE.

La API `converse` exige que la conversación empiece por el corredor y alterne.
Un turno que falló a medias —una nota de voz que no se transcribió, un error
antes de guardar la respuesta— deja la tabla sin alternar, y a partir de ahí
CADA turno siguiente revienta. Desde fuera eso se ve como "perdió el contexto".
"""

from sqlalchemy.ext.asyncio import AsyncSession

from pacer.infrastructure.persistencia.repositorio_corredor import RepositorioCorredor

CORREDOR = 1


async def crear(bd: AsyncSession) -> int:
    corredor = await RepositorioCorredor(bd).obtener_o_crear_por_sesion("sesion-de-prueba")
    return corredor.id


def roles(historial: list[dict]) -> list[str]:  # type: ignore[type-arg]
    return [m["role"] for m in historial]


async def test_devuelve_los_turnos_en_orden(sesion_bd: AsyncSession) -> None:
    repositorio = RepositorioCorredor(sesion_bd)
    corredor_id = await crear(sesion_bd)

    await repositorio.recordar(corredor_id, "user", "hola")
    await repositorio.recordar(corredor_id, "assistant", "qué tal")
    await repositorio.recordar(corredor_id, "user", "bien")

    historial = await repositorio.ultimos_turnos(corredor_id, 10)

    assert roles(historial) == ["user", "assistant", "user"]
    assert historial[0]["content"][0]["text"] == "hola"


async def test_nunca_empieza_por_el_coach(sesion_bd: AsyncSession) -> None:
    """Recortar la ventana puede dejar la primera línea en el coach."""
    repositorio = RepositorioCorredor(sesion_bd)
    corredor_id = await crear(sesion_bd)

    await repositorio.recordar(corredor_id, "user", "uno")
    await repositorio.recordar(corredor_id, "assistant", "dos")
    await repositorio.recordar(corredor_id, "user", "tres")
    await repositorio.recordar(corredor_id, "assistant", "cuatro")

    # Los dos últimos serían assistant, user... y al revés empieza por coach.
    historial = await repositorio.ultimos_turnos(corredor_id, 3)

    assert historial[0]["role"] == "user"


async def test_dos_mensajes_seguidos_del_mismo_lado_se_juntan(
    sesion_bd: AsyncSession,
) -> None:
    """Pasa cuando un turno se cae después de guardar lo que dijo el corredor.

    Juntarlos conserva lo dicho; descartarlos perdería contexto de verdad.
    """
    repositorio = RepositorioCorredor(sesion_bd)
    corredor_id = await crear(sesion_bd)

    await repositorio.recordar(corredor_id, "user", "el martes no puedo")
    await repositorio.recordar(corredor_id, "user", "¿lo paso al lunes?")
    await repositorio.recordar(corredor_id, "assistant", "va")

    historial = await repositorio.ultimos_turnos(corredor_id, 10)

    assert roles(historial) == ["user", "assistant"]
    assert "el martes no puedo" in historial[0]["content"][0]["text"]
    assert "¿lo paso al lunes?" in historial[0]["content"][0]["text"]


async def test_sin_conversacion_devuelve_vacio(sesion_bd: AsyncSession) -> None:
    assert await RepositorioCorredor(sesion_bd).ultimos_turnos(await crear(sesion_bd), 10) == []
